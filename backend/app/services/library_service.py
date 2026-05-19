"""文档库服务：文档上传、列表、详情和文本提取作业管理。"""

from dataclasses import dataclass
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
)
from app.tables import (
    document_versions,
    documents,
    library_parse_jobs,
    stored_files,
    users,
)
from app.services.object_storage import ObjectStorageProvider, get_object_storage_provider


class LibraryPermissionError(Exception):
    """当前用户无权访问该文档库资源。"""


class LibraryDocumentNotFoundError(Exception):
    """文档不存在或不属于当前用户。"""


def _safe_file_name(file_name: str) -> str:
    """提取并清理文件名，避免路径遍历。"""
    return PurePath(file_name).name or "uploaded-document"


def _to_document_dto(row: RowMapping) -> LibraryDocumentDTO:
    return LibraryDocumentDTO(
        documentId=str(row["document_id"]),
        ownerId=str(row["owner_id"]),
        name=row["name"],
        sourceType=row["source_type"],
        securityLevel=row["security_level"],
        status=row["status"],
        activeVersionId=str(row["active_version_id"]) if row["active_version_id"] else None,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_version_dto(row: RowMapping) -> LibraryDocumentVersionDTO:
    return LibraryDocumentVersionDTO(
        versionId=str(row["version_id"]),
        documentId=str(row["document_id"]),
        versionNo=row["version_no"],
        sourceFileId=str(row["source_file_id"]),
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
) -> RowMapping:
    """校验文档属于当前用户，否则抛出异常。"""
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
    if str(row["owner_id"]) != current_user.user.userId:
        raise LibraryPermissionError
    return row


def create_library_upload(
    session: Session,
    current_user: CurrentUserResponse,
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    name: str | None,
    security_level: str | None,
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
    resolved_security_level = security_level or "internal"

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
            name=document_name,
            source_type="upload",
            security_level=resolved_security_level,
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
) -> PageResponse[LibraryDocumentDTO]:
    """分页列出当前用户的文档库文档。"""
    owner_id = UUID(current_user.user.userId)
    where_clauses = [
        documents.c.owner_id == owner_id,
        documents.c.deleted_at.is_(None),
    ]
    if keyword:
        where_clauses.append(documents.c.name.ilike(f"%{keyword}%"))
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
    _ensure_owner(session, current_user, document_id)
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

        try:
            parsed = parse_document(
                file_name=file_row["file_name"],
                mime_type=file_row["mime_type"],
                file_bytes=file_bytes,
            )
        except DocumentParseError as exc:
            _mark_job_failed(session, job_id, exc.error_code, str(exc))
            return {"error": exc.error_code}

        # 生成纯文本预览
        full_text = "\n\n".join(chunk.content for chunk in parsed.chunks)
        preview_text = full_text[:2000] if len(full_text) > 2000 else full_text
        token_count = sum(chunk.token_count for chunk in parsed.chunks)

        # 更新 version 的 metadata，保存解析结果
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == version_id)
            .values(
                parse_status="success",
                chunk_count=len(parsed.chunks),
                token_count=token_count,
                status="active",
                metadata={
                    "parser_name": parsed.parser_name,
                    "parser_version": parsed.parser_version,
                    "preview_text": preview_text,
                    "full_text_length": len(full_text),
                },
                updated_by=None,
            )
        )

        # 更新 document 的 active_version_id
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


def get_document_text(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    mode: str = "preview",
) -> LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse:
    """获取文档的文本内容，支持 preview/full/chunks 三种模式。"""
    _ensure_owner(session, current_user, document_id)

    ver_row = session.execute(
        select(document_versions)
        .where(document_versions.c.document_id == document_id)
        .order_by(document_versions.c.version_no.desc())
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


def _mark_job_failed(session: Session, job_id: UUID, error_code: str, error_message: str) -> None:
    session.execute(
        update(library_parse_jobs)
        .where(library_parse_jobs.c.job_id == job_id)
        .values(
            status="failed",
            error_code=error_code,
            error_message=error_message,
            finished_at=sa.func.now(),
        )
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
