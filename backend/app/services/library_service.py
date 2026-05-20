"""文档库服务：文档上传、列表、详情和文本提取作业管理。"""

from dataclasses import dataclass
from typing import Literal
from hashlib import sha256
from pathlib import PurePath
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.library import (
    LibraryDocumentDTO,
    LibraryDocumentDetailDTO,
    LibraryDocumentUploadResponse,
    LibraryDocumentVersionDTO,
    LibraryFullTextResponse,
    LibraryParseJobDTO,
    LibraryParsedChunkDTO,
    LibraryParsedChunksResponse,
    LibraryStoredFileDTO,
    LibraryTextPreviewResponse,
    LibraryVersionActivateResponse,
    LibraryVersionUploadResponse,
)
from app.tables import (
    document_kb_bindings,
    document_libraries,
    document_versions,
    documents,
    knowledge_bases,
    library_parse_jobs,
    stored_files,
    users,
)
from app.services.object_storage import ObjectStorageProvider, get_object_storage_provider


class LibraryPermissionError(Exception):
    """当前用户无权访问该文档库资源。"""


class LibraryDocumentNotFoundError(Exception):
    """文档不存在或不属于当前用户。"""


class LibraryVersionNotFoundError(Exception):
    """版本不存在或不属于当前文档。"""


class LibraryVersionInUseError(Exception):
    """版本正在被知识库绑定引用，无法删除。"""

    def __init__(self, kb_names: list[str]) -> None:
        self.kb_names = kb_names
        super().__init__(f"Version is in use by KBs: {', '.join(kb_names)}")


def _ensure_library_access(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    permission_code: str,
) -> RowMapping:
    """校验当前用户对指定文档库具备目标权限。"""
    from app.services.permission_service import has_library_access

    lib_row = session.execute(
        select(document_libraries)
        .where(
            document_libraries.c.library_id == library_id,
            document_libraries.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if lib_row is None:
        raise LibraryPermissionError

    if not has_library_access(
        session,
        current_user,
        permission_code=permission_code,
        library_id=library_id,
        library_owner_id=UUID(str(lib_row["owner_id"])),
        library_visibility=lib_row["visibility"],
    ):
        raise LibraryPermissionError
    return lib_row


def _safe_file_name(file_name: str) -> str:
    """提取并清理文件名，避免路径遍历。"""
    return PurePath(file_name).name or "uploaded-document"


def _to_document_dto(row: RowMapping) -> LibraryDocumentDTO:
    return LibraryDocumentDTO(
        documentId=str(row["document_id"]),
        ownerId=str(row["owner_id"]),
        libraryId=str(row["library_id"]) if row.get("library_id") else None,
        name=row["name"],
        sourceType=row["source_type"],
        status=row["status"],
        activeVersionId=str(row["active_version_id"]) if row["active_version_id"] else None,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_version_dto(row: RowMapping, file_name: str | None = None, file_size: int | None = None) -> LibraryDocumentVersionDTO:
    return LibraryDocumentVersionDTO(
        versionId=str(row["version_id"]),
        documentId=str(row["document_id"]),
        versionNo=row["version_no"],
        sourceFileId=str(row["source_file_id"]),
        fileName=file_name,
        fileSize=file_size,
        status=row["status"],
        parseStatus=row["parse_status"],
        chunkCount=row["chunk_count"],
        tokenCount=row["token_count"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_stored_file_dto(row: RowMapping) -> LibraryStoredFileDTO:
    return LibraryStoredFileDTO(
        fileId=str(row["file_id"]),
        fileName=row["file_name"],
        mimeType=row["mime_type"],
        fileSize=row["file_size"],
        checksum=row["checksum"],
        objectKey=row["object_key"],
    )


def _to_parse_job_dto(row: RowMapping) -> LibraryParseJobDTO:
    return LibraryParseJobDTO(
        jobId=str(row["job_id"]),
        documentId=str(row["document_id"]),
        versionId=str(row["version_id"]),
        jobType=row["job_type"],
        status=row["status"],
        progress=row["progress"],
        errorCode=row["error_code"],
        errorMessage=row["error_message"],
        createdAt=row["created_at"].isoformat(),
    )


def _ensure_owner(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    permission_code: str = "library.document.read",
) -> RowMapping:
    """校验文档存在且当前用户有权限访问，否则抛出异常。"""
    from app.services.permission_service import has_library_access

    row = session.execute(
        select(documents)
        .where(
            documents.c.document_id == document_id,
            documents.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if row is None:
        raise LibraryDocumentNotFoundError

    # 获取文档库信息以进行可见性判断
    library_owner_id = None
    library_visibility = None
    library_id = row.get("library_id")
    if library_id:
        lib_row = session.execute(
            select(document_libraries.c.owner_id, document_libraries.c.visibility).where(
                document_libraries.c.library_id == library_id,
                document_libraries.c.deleted_at.is_(None),
            )
        ).mappings().first()
        if lib_row:
            library_owner_id = UUID(str(lib_row["owner_id"]))
            library_visibility = lib_row["visibility"]

    # 回退：如果没有 library_id，使用 owner_id
    if library_owner_id is None:
        owner_id = row.get("owner_id")
        if owner_id:
            library_owner_id = UUID(str(owner_id))
            library_visibility = "personal"

    if not has_library_access(
        session, current_user, permission_code,
        library_id=UUID(str(library_id)) if library_id else None,
        library_owner_id=library_owner_id,
        library_visibility=library_visibility,
    ):
        raise LibraryPermissionError
    return row


def create_library_upload(
    session: Session,
    current_user: CurrentUserResponse,
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    name: str | None,
    library_id: UUID | None = None,
    storage_provider: ObjectStorageProvider | None = None,
) -> LibraryDocumentUploadResponse:
    """上传文档到个人文档库，创建文件、文档、版本和解析作业。"""
    settings = get_settings()
    actor_id = UUID(current_user.user.userId)
    document_id = uuid4()
    version_id = uuid4()
    file_id = uuid4()
    job_id = uuid4()
    normalized_file_name = _safe_file_name(file_name)
    document_name = (name or normalized_file_name).strip() or normalized_file_name
    checksum = sha256(file_bytes).hexdigest()

    # 如果未指定 library_id，使用用户的默认文档库
    if library_id is None:
        default_lib = session.execute(
            select(document_libraries.c.library_id).where(
                document_libraries.c.owner_id == actor_id,
                document_libraries.c.name == "默认文档库",
                document_libraries.c.deleted_at.is_(None),
            ).limit(1)
        ).scalar()
        if default_lib:
            library_id = default_lib
        else:
            # 自动创建默认文档库
            library_id = uuid4()
            now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            session.execute(
                document_libraries.insert().values(
                    library_id=library_id,
                    owner_id=actor_id,
                    name="默认文档库",
                    visibility="personal",
                    status="active",
                    created_at=now,
                    created_by=actor_id,
                    updated_at=now,
                    updated_by=actor_id,
                )
            )
    else:
        _ensure_library_access(
            session,
            current_user,
            library_id,
            permission_code="library.document.create",
        )

    object_prefix = settings.storage_object_prefix.strip("/")
    object_path = f"users/{actor_id}/library/{document_id}/{normalized_file_name}"
    object_key = f"{object_prefix}/{object_path}" if object_prefix else object_path

    storage = storage_provider or get_object_storage_provider()
    stored_object = storage.put_object(object_key=object_key, data=file_bytes, content_type=mime_type)

    stored_file_row = session.execute(
        insert(stored_files)
        .values(
            file_id=file_id,
            bucket=stored_object.bucket,
            object_key=stored_object.object_key,
            file_name=normalized_file_name,
            mime_type=mime_type,
            file_size=stored_object.size,
            checksum=checksum,
            file_role="source",
            status="active",
            created_by=actor_id,
        )
        .returning(stored_files)
    ).mappings().one()

    document_row = session.execute(
        insert(documents)
        .values(
            document_id=document_id,
            kb_id=None,
            owner_id=actor_id,
            library_id=library_id,
            name=document_name,
            source_type="upload",
            security_level="internal",
            status="active",
            metadata={},
            created_by=actor_id,
            updated_by=actor_id,
        )
        .returning(documents)
    ).mappings().one()

    version_row = session.execute(
        insert(document_versions)
        .values(
            version_id=version_id,
            document_id=document_id,
            version_no=1,
            source_file_id=file_id,
            status="processing",
            parse_status="pending",
            dense_index_status="not_required",
            sparse_index_status="not_required",
            graph_index_status="not_required",
            retrieval_ready=False,
            chunk_count=0,
            metadata={},
            created_by=actor_id,
            updated_by=actor_id,
        )
        .returning(document_versions)
    ).mappings().one()

    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(active_version_id=version_id)
    )

    job_row = session.execute(
        insert(library_parse_jobs)
        .values(
            job_id=job_id,
            document_id=document_id,
            version_id=version_id,
            job_type="extract_text",
            status="queued",
            progress=0,
            created_by=actor_id,
        )
        .returning(library_parse_jobs)
    ).mappings().one()

    session.commit()

    # 尝试投递 Celery 文本提取任务，失败不影响上传响应
    try:
        from app.worker import run_library_parse_task

        run_library_parse_task.delay(str(job_id))
    except Exception:
        pass

    return LibraryDocumentUploadResponse(
        document=_to_document_dto(document_row),
        version=_to_version_dto(version_row),
        parseJob=_to_parse_job_dto(job_row),
        storedFile=_to_stored_file_dto(stored_file_row),
    )


def list_library_documents(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    status_filter: str | None = None,
    library_id: UUID | None = None,
) -> PageResponse[LibraryDocumentDTO]:
    """分页列出当前用户的文档库文档。"""
    from app.services.permission_service import library_visibility_condition

    # 使用可见性条件替代简单的 owner_id 过滤
    owner_id = UUID(current_user.user.userId)
    where_clauses = [
        documents.c.deleted_at.is_(None),
    ]

    if library_id:
        _ensure_library_access(
            session,
            current_user,
            library_id,
            permission_code="library.document.read",
        )
        where_clauses.append(documents.c.library_id == library_id)
    else:
        # 未指定库时，使用可见性条件
        vis_cond = library_visibility_condition(current_user)
        visible_library_ids = select(document_libraries.c.library_id).where(vis_cond)
        where_clauses.append(documents.c.library_id.in_(visible_library_ids))
    if keyword:
        safe = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where_clauses.append(documents.c.name.ilike(f"%{safe}%", escape="\\"))
    if status_filter:
        where_clauses.append(documents.c.status == status_filter)

    total = session.execute(
        select(func.count()).select_from(documents).where(*where_clauses)
    ).scalar_one()

    rows = session.execute(
        select(documents)
        .where(*where_clauses)
        .order_by(documents.c.updated_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings().all()

    return PageResponse(
        items=[_to_document_dto(r) for r in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_library_document_detail(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> LibraryDocumentDetailDTO:
    """获取文档库文档详情，含 active version 信息。"""
    doc_row = _ensure_owner(session, current_user, document_id)
    active_version = None
    if doc_row["active_version_id"]:
        ver_row = session.execute(
            select(document_versions)
            .where(document_versions.c.version_id == doc_row["active_version_id"])
            .limit(1)
        ).mappings().first()
        if ver_row:
            active_version = _to_version_dto(ver_row)

    return LibraryDocumentDetailDTO(
        document=_to_document_dto(doc_row),
        activeVersion=active_version,
    )


def get_library_document_source_download(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> tuple[str, str | None, bytes]:
    """下载文档库文档原始文件，返回 (file_name, mime_type, content)。"""
    _ensure_owner(session, current_user, document_id)

    doc_row = session.execute(
        select(documents).where(documents.c.document_id == document_id)
    ).mappings().one()

    if not doc_row["active_version_id"]:
        raise LibraryDocumentNotFoundError

    ver_row = session.execute(
        select(document_versions).where(document_versions.c.version_id == doc_row["active_version_id"])
    ).mappings().first()
    if not ver_row:
        raise LibraryDocumentNotFoundError

    file_row = session.execute(
        select(stored_files).where(stored_files.c.file_id == ver_row["source_file_id"])
    ).mappings().first()
    if not file_row:
        raise LibraryDocumentNotFoundError

    storage = get_object_storage_provider()
    content = storage.get_object(file_row["object_key"])
    if content is None:
        raise LibraryDocumentNotFoundError

    return file_row["file_name"], file_row["mime_type"], content


def update_library_document(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    name: str | None = None,
    doc_status: str | None = None,
) -> LibraryDocumentDTO:
    """更新文档库文档的基本字段。"""
    _ensure_owner(session, current_user, document_id, "library.document.update")
    actor_id = UUID(current_user.user.userId)

    values: dict = {"updated_by": actor_id}
    if name is not None:
        values["name"] = name.strip()
    if doc_status is not None:
        values["status"] = doc_status

    row = session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(**values)
        .returning(documents)
    ).mappings().one()

    session.commit()
    return _to_document_dto(row)


def delete_library_document(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> dict:
    """软删除文档并级联清理所有绑定。"""
    _ensure_owner(session, current_user, document_id, "library.document.delete")
    user_id = UUID(current_user.user.userId)

    # 1. Soft delete the document
    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(
            status="archived",
            deleted_at=func.now(),
            deleted_by=user_id,
            updated_at=func.now(),
            updated_by=user_id,
        )
    )

    # 2. Find all active bindings
    active_bindings = list(
        session.execute(
            select(document_kb_bindings)
            .where(
                document_kb_bindings.c.document_id == document_id,
                document_kb_bindings.c.status.in_(["active", "processing", "pending"]),
            )
        ).mappings()
    )

    # 3. Unbind each one
    unbound_count = 0
    for binding in active_bindings:
        # Get KB-side document_id from the binding's version_id
        kb_doc_id = session.execute(
            select(document_versions.c.document_id)
            .where(document_versions.c.version_id == binding["version_id"])
            .limit(1)
        ).scalar()

        # Mark binding as disabled
        session.execute(
            update(document_kb_bindings)
            .where(document_kb_bindings.c.binding_id == binding["binding_id"])
            .values(status="disabled", updated_by=user_id, updated_at=func.now())
        )

        # Clean up KB-side document using existing delete_document
        if kb_doc_id:
            from app.services.document_service import delete_document as _delete_kb_doc

            try:
                _delete_kb_doc(
                    session, current_user, binding["kb_id"], kb_doc_id,
                    confirm_impact=True, reason="library_cascade_delete",
                )
            except Exception:
                pass  # Best-effort cleanup

        unbound_count += 1

    session.commit()

    return {
        "documentId": str(document_id),
        "unboundCount": unbound_count,
    }


def get_library_parse_jobs(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> list[LibraryParseJobDTO]:
    """获取文档的解析作业列表。"""
    _ensure_owner(session, current_user, document_id)

    rows = session.execute(
        select(library_parse_jobs)
        .where(library_parse_jobs.c.document_id == document_id)
        .order_by(library_parse_jobs.c.created_at.desc())
    ).mappings().all()

    return [_to_parse_job_dto(r) for r in rows]


def run_library_parse_job_by_id(job_id: UUID) -> dict:
    """Celery 任务入口：按 job_id 执行文档库文本提取。"""
    from app.core.database import get_session_factory
    from app.services.document_parsing import parse_document, DocumentParseError

    factory = get_session_factory()
    session = factory()
    try:
        job_row = session.execute(
            select(library_parse_jobs)
            .where(library_parse_jobs.c.job_id == job_id)
            .limit(1)
        ).mappings().first()
        if job_row is None:
            return {"error": "JOB_NOT_FOUND"}

        session.execute(
            update(library_parse_jobs)
            .where(library_parse_jobs.c.job_id == job_id)
            .values(status="running", started_at=sa.func.now())
        )
        session.commit()

        document_id = job_row["document_id"]
        version_id = job_row["version_id"]

        ver_row = session.execute(
            select(document_versions).where(document_versions.c.version_id == version_id)
        ).mappings().first()
        if ver_row is None:
            _mark_job_failed(session, job_id, "VERSION_NOT_FOUND", "Document version not found.")
            return {"error": "VERSION_NOT_FOUND"}

        file_row = session.execute(
            select(stored_files).where(stored_files.c.file_id == ver_row["source_file_id"])
        ).mappings().first()
        if file_row is None:
            _mark_job_failed(session, job_id, "FILE_NOT_FOUND", "Stored file not found.")
            return {"error": "FILE_NOT_FOUND"}

        storage = get_object_storage_provider()
        file_bytes = storage.get_object(file_row["object_key"])
        if file_bytes is None:
            _mark_job_failed(session, job_id, "FILE_READ_FAILED", "Cannot read file from storage.")
            return {"error": "FILE_READ_FAILED"}

        # 带重试的解析逻辑
        import time

        max_retries = 3
        retry_delays = [5, 15, 45]  # 指数退避
        parsed = None
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                parsed = parse_document(
                    file_name=file_row["file_name"],
                    mime_type=file_row["mime_type"],
                    file_bytes=file_bytes,
                )
                break  # 成功，退出重试循环
            except DocumentParseError as exc:
                last_error = exc
                if attempt < max_retries:
                    # 更新 job 进度，记录重试信息
                    session.execute(
                        update(library_parse_jobs)
                        .where(library_parse_jobs.c.job_id == job_id)
                        .values(
                            progress=int((attempt + 1) / (max_retries + 1) * 50),
                            error_message=f"重试 {attempt + 1}/{max_retries}: {exc}",
                        )
                    )
                    session.commit()
                    time.sleep(retry_delays[attempt])
                else:
                    # 最终失败
                    error_detail = {
                        "type": "parse_error",
                        "file": file_row["file_name"],
                        "fileSize": file_row["file_size"],
                        "retryCount": max_retries,
                        "errorCode": exc.error_code,
                        "suggestion": _get_error_suggestion(exc.error_code),
                    }
                    _mark_job_failed(session, job_id, exc.error_code, str(exc), error_detail)
                    return {"error": exc.error_code}

        if parsed is None:
            _mark_job_failed(session, job_id, "UNKNOWN", "解析失败", {
                "type": "unknown",
                "file": file_row["file_name"],
                "retryCount": max_retries,
                "suggestion": "请联系管理员",
            })
            return {"error": "UNKNOWN"}

        # 生成纯文本预览
        full_text = "\n\n".join(chunk.content for chunk in parsed.chunks)
        preview_text = full_text[:2000] if len(full_text) > 2000 else full_text
        token_count = sum(chunk.token_count for chunk in parsed.chunks)

        # Store structured chunk results for KB ingest reuse
        structured_chunks = []
        for chunk in parsed.chunks:
            structured_chunks.append({
                "content": chunk.content,
                "token_count": chunk.token_count,
                "section": getattr(chunk, "section", None),
                "page_no": getattr(chunk, "page_no", None),
                "start_offset": getattr(chunk, "start_offset", None),
                "end_offset": getattr(chunk, "end_offset", None),
            })

        doc_active_version_id = session.execute(
            select(documents.c.active_version_id).where(documents.c.document_id == document_id)
        ).scalar()
        should_activate = (
            job_row["job_type"] != "upload_version"
            or doc_active_version_id is None
            or doc_active_version_id == version_id
        )

        # 更新 version 的 metadata，保存解析结果
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == version_id)
            .values(
                parse_status="success",
                chunk_count=len(parsed.chunks),
                token_count=token_count,
                status="active" if should_activate else "inactive",
                metadata={
                    "parser_name": parsed.parser_name,
                    "parser_version": parsed.parser_version,
                    "preview_text": preview_text,
                    "full_text_length": len(full_text),
                    "parsed_chunks": structured_chunks,
                },
                updated_by=None,
            )
        )

        if should_activate:
            session.execute(
                update(documents)
                .where(documents.c.document_id == document_id)
                .values(active_version_id=version_id)
            )

        _mark_job_success(session, job_id)
        session.commit()

        return {
            "job_id": str(job_id),
            "status": "success",
            "chunk_count": len(parsed.chunks),
            "token_count": token_count,
        }

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def retry_library_parse(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> dict:
    """重新触发文档解析。"""
    _ensure_owner(session, current_user, document_id)
    user_id = UUID(current_user.user.userId)

    # 使用活跃版本而非最新版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    if not doc_row or not doc_row["active_version_id"]:
        raise LibraryDocumentNotFoundError

    version_row = session.execute(
        select(document_versions)
        .where(
            document_versions.c.version_id == doc_row["active_version_id"],
            document_versions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if version_row is None:
        raise LibraryDocumentNotFoundError

    # Create new parse job
    job_id = uuid4()
    session.execute(
        insert(library_parse_jobs).values(
            job_id=job_id,
            document_id=document_id,
            version_id=version_row["version_id"],
            job_type="reparse_library",
            status="queued",
            progress=0,
            created_by=user_id,
        )
    )

    # Reset version parse status
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_row["version_id"])
        .values(parse_status="pending", updated_by=user_id, updated_at=func.now())
    )

    session.commit()

    # Trigger Celery
    from app.worker import run_library_parse_task
    run_library_parse_task.delay(str(job_id))

    return {"jobId": str(job_id), "status": "queued"}


def batch_action(
    session: Session,
    current_user: CurrentUserResponse,
    document_ids: list[str],
    action: str,
) -> dict:
    """批量操作文档：delete / reparse / disable。逐个检查权限，部分执行。"""
    succeeded: list[str] = []
    failed: list[dict] = []

    for doc_id_str in document_ids:
        try:
            doc_id = UUID(doc_id_str)
        except ValueError:
            failed.append({"documentId": doc_id_str, "error": "INVALID_ID", "message": "无效的文档 ID"})
            continue

        try:
            if action == "delete":
                delete_library_document(session, current_user, doc_id)
            elif action == "reparse":
                retry_library_parse(session, current_user, doc_id)
            elif action == "disable":
                _ensure_owner(session, current_user, doc_id, "library.document.update")
                row = session.execute(
                    select(documents).where(documents.c.document_id == doc_id)
                ).mappings().first()
                if row and row["status"] != "active":
                    raise LibraryPermissionError
                session.execute(
                    update(documents)
                    .where(documents.c.document_id == doc_id)
                    .values(
                        status="disabled",
                        updated_by=UUID(current_user.user.userId),
                        updated_at=func.now(),
                    )
                )
                session.commit()
            succeeded.append(doc_id_str)
        except LibraryPermissionError:
            failed.append({"documentId": doc_id_str, "error": "PERMISSION_DENIED", "message": "无权限操作该文档"})
        except LibraryDocumentNotFoundError:
            failed.append({"documentId": doc_id_str, "error": "NOT_FOUND", "message": "文档不存在"})
        except Exception:
            failed.append({"documentId": doc_id_str, "error": "UNKNOWN", "message": "操作失败，请稍后重试"})

    return {
        "succeeded": succeeded,
        "failed": failed,
        "summary": {
            "total": len(document_ids),
            "succeeded": len(succeeded),
            "failed": len(failed),
        },
    }


def get_library_stats(
    session: Session,
    current_user: CurrentUserResponse,
) -> dict:
    """获取当前用户的文档库统计数据。"""
    owner_id = UUID(current_user.user.userId)
    today_start = sa.text("date_trunc('day', now())")
    library_source_types = ["upload", "library"]

    total_documents = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.owner_id == owner_id,
            documents.c.source_type.in_(library_source_types),
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    today_uploads = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.owner_id == owner_id,
            documents.c.source_type.in_(library_source_types),
            documents.c.deleted_at.is_(None),
            documents.c.created_at >= today_start,
        )
    ).scalar_one()

    pending_parse = session.execute(
        select(func.count())
        .select_from(library_parse_jobs)
        .join(documents, library_parse_jobs.c.document_id == documents.c.document_id)
        .where(
            library_parse_jobs.c.status.in_(["pending", "running", "queued"]),
            documents.c.owner_id == owner_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    return {
        "totalDocuments": total_documents,
        "todayUploads": today_uploads,
        "pendingParse": pending_parse,
    }


def get_document_text(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    mode: Literal["preview", "full", "chunks"] = "preview",
) -> LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse:
    """获取文档的文本内容，支持 preview/full/chunks 三种模式。"""
    _ensure_owner(session, current_user, document_id)

    # 使用活跃版本而非最新版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    if not doc_row or not doc_row["active_version_id"]:
        raise LibraryDocumentNotFoundError

    ver_row = session.execute(
        select(document_versions)
        .where(
            document_versions.c.version_id == doc_row["active_version_id"],
            document_versions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()

    if ver_row is None:
        raise LibraryDocumentNotFoundError

    metadata = ver_row["metadata"] or {}
    preview_text = metadata.get("preview_text", "")
    full_text_length = metadata.get("full_text_length", len(preview_text))
    parsed_chunks_raw = metadata.get("parsed_chunks", [])

    if mode == "chunks":
        chunks = [
            LibraryParsedChunkDTO(
                content=chunk.get("content", ""),
                tokenCount=chunk.get("token_count", 0),
                section=chunk.get("section"),
                pageNo=chunk.get("page_no"),
                startOffset=chunk.get("start_offset"),
                endOffset=chunk.get("end_offset"),
            )
            for chunk in parsed_chunks_raw
        ]
        return LibraryParsedChunksResponse(chunks=chunks)

    if mode == "full":
        if parsed_chunks_raw:
            text = "\n\n".join(chunk.get("content", "") for chunk in parsed_chunks_raw)
        else:
            text = preview_text
        return LibraryFullTextResponse(text=text)

    # mode == "preview" (default)
    truncated = len(preview_text) < full_text_length
    return LibraryTextPreviewResponse(
        text=preview_text,
        truncated=truncated,
        fullLength=full_text_length,
    )


def get_document_usage(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> dict:
    """查询文档绑定的所有知识库。"""
    _ensure_owner(session, current_user, document_id)

    rows = session.execute(
        select(
            document_kb_bindings.c.binding_id,
            document_kb_bindings.c.kb_id,
            document_kb_bindings.c.status,
            document_kb_bindings.c.chunk_count,
            document_kb_bindings.c.created_at,
            knowledge_bases.c.name.label("kb_name"),
        )
        .join(knowledge_bases, knowledge_bases.c.kb_id == document_kb_bindings.c.kb_id)
        .where(document_kb_bindings.c.document_id == document_id)
        .order_by(document_kb_bindings.c.created_at.desc())
    ).mappings().all()

    return {
        "documentId": str(document_id),
        "usages": [
            {
                "bindingId": str(row["binding_id"]),
                "kbId": str(row["kb_id"]),
                "kbName": row["kb_name"],
                "status": row["status"],
                "chunkCount": row["chunk_count"],
                "createdAt": row["created_at"].isoformat(),
            }
            for row in rows
        ],
    }


def list_library_versions(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> list[LibraryDocumentVersionDTO]:
    """列出文档的所有版本（不含已删除）。"""
    _ensure_owner(session, current_user, document_id)

    rows = session.execute(
        select(
            document_versions,
            stored_files.c.file_name,
            stored_files.c.file_size,
        )
        .join(stored_files, stored_files.c.file_id == document_versions.c.source_file_id)
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
        .order_by(document_versions.c.version_no.desc())
    ).mappings().all()

    return [_to_version_dto(row, file_name=row["file_name"], file_size=row["file_size"]) for row in rows]


def upload_library_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    storage_provider: ObjectStorageProvider | None = None,
) -> LibraryVersionUploadResponse:
    """上传新版本文件到已有文档。"""
    doc_row = _ensure_owner(session, current_user, document_id, "library.document.update")
    actor_id = UUID(current_user.user.userId)
    normalized_file_name = _safe_file_name(file_name)
    checksum = sha256(file_bytes).hexdigest()

    # 查询当前最大 version_no
    max_version_no = session.execute(
        select(func.max(document_versions.c.version_no))
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
    ).scalar() or 0

    next_version_no = max_version_no + 1
    version_id = uuid4()
    file_id = uuid4()
    job_id = uuid4()

    # 存储文件
    settings = get_settings()
    storage = storage_provider or get_object_storage_provider()
    owner_id = str(doc_row["owner_id"]) if doc_row.get("owner_id") else str(actor_id)
    object_prefix = settings.storage_object_prefix.strip("/")
    object_path = f"users/{owner_id}/library/{document_id}/{normalized_file_name}"
    object_key = f"{object_prefix}/{object_path}" if object_prefix else object_path
    stored_object = storage.put_object(object_key, file_bytes, mime_type or "application/octet-stream")

    # 创建 stored_files 行
    session.execute(
        insert(stored_files).values(
            file_id=file_id,
            bucket=stored_object.bucket,
            object_key=stored_object.object_key,
            file_name=normalized_file_name,
            mime_type=mime_type,
            file_size=stored_object.size,
            checksum=checksum,
            file_role="source",
            status="active",
            created_by=actor_id,
            updated_by=actor_id,
        )
    )

    # 创建 document_versions 行（不自动激活）
    session.execute(
        insert(document_versions).values(
            version_id=version_id,
            document_id=document_id,
            version_no=next_version_no,
            source_file_id=file_id,
            status="processing",
            parse_status="pending",
            dense_index_status="not_required",
            sparse_index_status="not_required",
            graph_index_status="not_required",
            retrieval_ready=False,
            chunk_count=0,
            metadata={},
            created_by=actor_id,
            updated_by=actor_id,
        )
    )

    # 创建解析任务
    session.execute(
        insert(library_parse_jobs).values(
            job_id=job_id,
            document_id=document_id,
            version_id=version_id,
            job_type="upload_version",
            status="queued",
            progress=0,
            created_by=actor_id,
        )
    )

    session.commit()

    # 触发 Celery
    from app.worker import run_library_parse_task
    run_library_parse_task.delay(str(job_id))

    # 构造响应
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    ver_dto = LibraryDocumentVersionDTO(
        versionId=str(version_id),
        documentId=str(document_id),
        versionNo=next_version_no,
        sourceFileId=str(file_id),
        fileName=normalized_file_name,
        fileSize=len(file_bytes),
        status="processing",
        parseStatus="pending",
        chunkCount=0,
        tokenCount=None,
        createdAt=now_iso,
        updatedAt=now_iso,
    )
    parse_job_dto = LibraryParseJobDTO(
        jobId=str(job_id),
        documentId=str(document_id),
        versionId=str(version_id),
        jobType="upload_version",
        status="queued",
        progress=0,
        errorCode=None,
        errorMessage=None,
        createdAt=now_iso,
    )
    stored_file_dto = LibraryStoredFileDTO(
        fileId=str(file_id),
        fileName=normalized_file_name,
        mimeType=mime_type,
        fileSize=stored_object.size,
        checksum=checksum,
        objectKey=stored_object.object_key,
    )

    return LibraryVersionUploadResponse(
        version=ver_dto,
        parseJob=parse_job_dto,
        storedFile=stored_file_dto,
    )


def activate_library_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    version_id: UUID,
    confirm_impact: bool = False,
) -> LibraryVersionActivateResponse:
    """切换文档的活跃版本。"""
    _ensure_owner(session, current_user, document_id, "library.document.update")

    if not confirm_impact:
        raise LibraryPermissionError("CONFIRM_REQUIRED: Set confirmImpact=true to proceed.")

    # 校验目标版本
    ver_row = session.execute(
        select(document_versions).where(
            document_versions.c.version_id == version_id,
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    if ver_row is None:
        raise LibraryVersionNotFoundError
    if ver_row["parse_status"] != "success":
        raise LibraryPermissionError("VERSION_NOT_READY: Version must be successfully parsed before activation.")

    # 获取当前活跃版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    previous_active_id = str(doc_row["active_version_id"]) if doc_row and doc_row["active_version_id"] else None

    # 将所有版本设为 inactive
    session.execute(
        update(document_versions)
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
        .values(status="inactive", updated_at=func.now())
    )

    # 目标版本设为 active
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_id)
        .values(status="active", updated_at=func.now())
    )

    # 更新 documents.active_version_id
    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(active_version_id=version_id, updated_at=func.now())
    )

    session.commit()

    return LibraryVersionActivateResponse(
        documentId=str(document_id),
        activeVersionId=str(version_id),
        previousActiveVersionId=previous_active_id,
    )


def delete_library_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    version_id: UUID,
) -> dict:
    """删除指定版本（软删除）。不能删除活跃版本或被 KB 绑定引用的版本。"""
    _ensure_owner(session, current_user, document_id, "library.document.update")
    actor_id = UUID(current_user.user.userId)

    # 校验版本存在
    ver_row = session.execute(
        select(document_versions).where(
            document_versions.c.version_id == version_id,
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    if ver_row is None:
        raise LibraryVersionNotFoundError

    # 不能删除活跃版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    if doc_row and str(doc_row["active_version_id"]) == str(version_id):
        raise LibraryPermissionError("VERSION_IS_ACTIVE: Cannot delete the active version. Switch to another version first.")

    # 检查是否有 KB 绑定引用此版本
    kb_versions = document_versions.alias("kb_versions")
    binding_rows = session.execute(
        select(
            document_kb_bindings.c.binding_id,
            knowledge_bases.c.name.label("kb_name"),
        )
        .select_from(
            document_kb_bindings
            .join(knowledge_bases, knowledge_bases.c.kb_id == document_kb_bindings.c.kb_id)
            .join(kb_versions, kb_versions.c.version_id == document_kb_bindings.c.version_id)
        )
        .where(
            document_kb_bindings.c.document_id == document_id,
            document_kb_bindings.c.status.in_(["active", "processing", "pending"]),
            sa.or_(
                kb_versions.c.metadata["library_version_id"].astext == str(version_id),
                sa.and_(
                    kb_versions.c.metadata["library_version_id"].astext.is_(None),
                    kb_versions.c.source_file_id == ver_row["source_file_id"],
                ),
            ),
        )
    ).mappings().all()

    if binding_rows:
        kb_names = [row["kb_name"] for row in binding_rows]
        raise LibraryVersionInUseError(kb_names)

    # 软删除版本
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_id)
        .values(
            status="archived",
            deleted_at=func.now(),
            deleted_by=actor_id,
            updated_at=func.now(),
            updated_by=actor_id,
        )
    )

    # 软删除关联的 stored_files
    session.execute(
        update(stored_files)
        .where(stored_files.c.file_id == ver_row["source_file_id"])
        .values(
            status="deleted",
            updated_at=func.now(),
            updated_by=actor_id,
        )
    )

    session.commit()

    return {"versionId": str(version_id), "status": "deleted"}


def _get_error_suggestion(error_code: str) -> str:
    """根据错误码返回用户友好的建议。"""
    suggestions = {
        "PARSE_TIMEOUT": "请尝试拆分文件或联系管理员",
        "UNSUPPORTED_FORMAT": "请检查文件格式是否受支持",
        "FILE_CORRUPTED": "请重新上传文件",
        "STORAGE_ERROR": "存储服务异常，请稍后重试",
    }
    return suggestions.get(error_code, "请联系管理员")


def _mark_job_failed(
    session: Session,
    job_id: UUID,
    error_code: str,
    error_message: str,
    error_detail: dict | None = None,
) -> None:
    values = {
        "status": "failed",
        "error_code": error_code,
        "error_message": error_message,
        "finished_at": sa.func.now(),
    }
    if error_detail is not None:
        values["error_detail"] = error_detail

    session.execute(
        update(library_parse_jobs)
        .where(library_parse_jobs.c.job_id == job_id)
        .values(**values)
    )
    # 同步更新 version 状态
    job = session.execute(
        select(library_parse_jobs).where(library_parse_jobs.c.job_id == job_id)
    ).mappings().first()
    if job:
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == job["version_id"])
            .values(
                parse_status="failed",
                error_code=error_code,
                error_message=error_message,
            )
        )
    session.commit()


def _mark_job_success(session: Session, job_id: UUID) -> None:
    session.execute(
        update(library_parse_jobs)
        .where(library_parse_jobs.c.job_id == job_id)
        .values(status="success", progress=100, finished_at=sa.func.now())
    )
