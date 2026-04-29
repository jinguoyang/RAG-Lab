from hashlib import sha256
from pathlib import PurePath
import re
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import RowMapping, delete, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse
from app.schemas.document import (
    ChunkDTO,
    BulkDocumentGovernanceResponse,
    DocumentDetailDTO,
    ChunkGovernanceResponse,
    DocumentDTO,
    DocumentVersionActivateResponse,
    DocumentQualityIssueDTO,
    DocumentQualitySummaryDTO,
    DocumentUploadResponse,
    DocumentVersionDTO,
    IndexSyncJobDTO,
    IngestJobDTO,
    StoredFileDTO,
)
from app.schemas.common import PageResponse
from app.tables import (
    audit_logs,
    chunk_access_filters,
    chunks,
    document_versions,
    documents,
    graph_chunk_refs,
    graph_snapshots,
    index_sync_jobs,
    index_sync_records,
    ingest_jobs,
    knowledge_bases,
    stored_files,
)
from app.services.object_storage import ObjectStorageProvider, get_object_storage_provider
from app.services.knowledge_base_service import KnowledgeBaseDisabledError
from app.services.permission_service import build_chunk_access_filter_context, has_kb_permission
from app.services.graph_service import mark_graph_snapshots_stale


class DocumentPermissionError(Exception):
    """当前用户缺少文档生命周期操作权限。"""


class DocumentConflictError(Exception):
    """文档生命周期状态冲突，例如作业不可重试或版本不可激活。"""


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用 E1 最小权限：平台管理员可访问全部知识库。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库，文档模块以后端权限摘要为最终判断。"""
    row = session.execute(
        select(knowledge_bases)
        .where(knowledge_bases.c.deleted_at.is_(None), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    if not has_kb_permission(session, current_user, kb_id, "kb.view"):
        return None
    return row


def _ensure_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    permission_code: str,
) -> None:
    """写操作和正文读取必须显式校验权限，避免只依赖资源可见性。"""
    if not has_kb_permission(session, current_user, kb_id, permission_code):
        raise DocumentPermissionError


def _to_document_dto(row: RowMapping) -> DocumentDTO:
    """将 documents 行转换为文档 DTO。"""
    return DocumentDTO(
        documentId=str(row["document_id"]),
        kbId=str(row["kb_id"]),
        name=row["name"],
        sourceType=row["source_type"],
        securityLevel=row["security_level"],
        status=row["status"],
        activeVersionId=str(row["active_version_id"]) if row["active_version_id"] else None,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_version_dto(row: RowMapping) -> DocumentVersionDTO:
    """将 document_versions 行转换为版本 DTO。"""
    return DocumentVersionDTO(
        versionId=str(row["version_id"]),
        documentId=str(row["document_id"]),
        versionNo=row["version_no"],
        sourceFileId=str(row["source_file_id"]),
        status=row["status"],
        parseStatus=row["parse_status"],
        denseIndexStatus=row["dense_index_status"],
        sparseIndexStatus=row["sparse_index_status"],
        graphIndexStatus=row["graph_index_status"],
        retrievalReady=row["retrieval_ready"],
        chunkCount=row["chunk_count"],
        tokenCount=row["token_count"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_ingest_job_dto(row: RowMapping) -> IngestJobDTO:
    """将 ingest_jobs 行转换为作业 DTO。"""
    return IngestJobDTO(
        jobId=str(row["job_id"]),
        kbId=str(row["kb_id"]),
        documentId=str(row["document_id"]) if row["document_id"] else None,
        versionId=str(row["version_id"]) if row["version_id"] else None,
        jobType=row["job_type"],
        status=row["status"],
        stage=row["stage"],
        progress=row["progress"],
        errorCode=row["error_code"],
        errorMessage=row["error_message"],
        createdAt=row["created_at"].isoformat(),
    )


def _to_chunk_dto(row: RowMapping) -> ChunkDTO:
    """将 Chunk 真值行转换为 API DTO。"""
    return ChunkDTO(
        chunkId=str(row["chunk_id"]),
        versionId=str(row["version_id"]),
        documentId=str(row["document_id"]),
        kbId=str(row["kb_id"]),
        chunkIndex=row["chunk_index"],
        pageNo=row["page_no"],
        section=row["section"],
        content=row["content"],
        contentHash=row["content_hash"],
        tokenCount=row["token_count"],
        securityLevel=row["security_level"],
        status=row["status"],
        metadata=row["metadata"],
        createdAt=row["created_at"].isoformat(),
    )


def _to_index_sync_job_dto(row: RowMapping) -> IndexSyncJobDTO:
    """将索引同步作业行转换为 API DTO。"""
    return IndexSyncJobDTO(
        syncJobId=str(row["sync_job_id"]),
        kbId=str(row["kb_id"]),
        targetStore=row["target_store"],
        syncType=row["sync_type"],
        scope=row["scope"],
        requiredForActivation=row["required_for_activation"],
        status=row["status"],
        errorMessage=row["error_message"],
        createdAt=row["created_at"].isoformat(),
        startedAt=row["started_at"].isoformat() if row["started_at"] else None,
        finishedAt=row["finished_at"].isoformat() if row["finished_at"] else None,
    )


def _to_stored_file_dto(row: RowMapping) -> StoredFileDTO:
    """将 stored_files 行转换为文件元数据 DTO。"""
    return StoredFileDTO(
        fileId=str(row["file_id"]),
        fileName=row["file_name"],
        mimeType=row["mime_type"],
        fileSize=row["file_size"],
        checksum=row["checksum"],
        objectKey=row["object_key"],
    )


def _safe_file_name(file_name: str) -> str:
    """提取上传文件名，避免客户端路径片段进入对象引用。"""
    name = PurePath(file_name).name.strip()
    return name or "uploaded-document"


def _decode_source_text(file_bytes: bytes, fallback_name: str) -> str:
    """从上传文件中提取可切块文本；不支持的二进制文件保留可追踪占位摘要。"""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = file_bytes.decode(encoding)
            if text.strip():
                return text
        except UnicodeDecodeError:
            continue
    return f"{fallback_name}\n\n当前文件无法按文本解析，已生成占位 Chunk 以保留入库链路。"


def _split_text_to_chunks(text: str, max_chars: int = 900) -> list[dict]:
    """按段落和长度生成稳定 Chunk，返回 Worker 可直接写库的结构。"""
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if not paragraphs and normalized:
        paragraphs = [normalized]
    if not paragraphs:
        paragraphs = ["空文档占位 Chunk。"]

    result: list[dict] = []
    for paragraph in paragraphs:
        cursor = 0
        while cursor < len(paragraph):
            content = paragraph[cursor : cursor + max_chars].strip()
            cursor += max_chars
            if content:
                result.append(
                    {
                        "content": content,
                        "token_count": max(1, len(content) // 4),
                        "section": f"Section {len(result) + 1}",
                        "page_no": None,
                    }
                )
    return result


def _insert_audit_log(
    session: Session,
    current_user: CurrentUserResponse,
    action: str,
    resource_type: str,
    resource_id: UUID,
    kb_id: UUID,
    document_id: UUID | None,
    detail: dict,
) -> UUID:
    """写入文档生命周期审计日志，支撑高风险操作可追溯。"""
    audit_log_id = uuid4()
    session.execute(
        insert(audit_logs).values(
            audit_log_id=audit_log_id,
            actor_id=UUID(current_user.user.userId),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            kb_id=kb_id,
            document_id=document_id,
            detail=detail,
        )
    )
    return audit_log_id


def _read_source_bytes(
    session: Session,
    version_row: RowMapping,
    storage_provider: ObjectStorageProvider,
) -> tuple[bytes | None, RowMapping | None]:
    """按版本读取原始文件内容；开发期元数据存储可能只能返回 None。"""
    file_row = session.execute(
        select(stored_files)
        .where(stored_files.c.file_id == version_row["source_file_id"])
        .limit(1)
    ).mappings().first()
    if file_row is None:
        return None, None
    return storage_provider.get_object(file_row["object_key"]), file_row


def _create_index_sync_job(
    session: Session,
    kb_row: RowMapping,
    current_user: CurrentUserResponse,
    target_store: str,
    version_id: UUID | None,
    chunk_ids: list[UUID],
    required_for_activation: bool,
    sync_type: str = "upsert",
    status: str = "success",
    error_message: str | None = None,
) -> UUID:
    """记录本地副本同步结果；外部 Provider 可由后续 Worker 替换同一表契约。"""
    sync_job_id = uuid4()
    scope = {"chunkIds": [str(chunk_id) for chunk_id in chunk_ids]}
    if version_id:
        scope["versionIds"] = [str(version_id)]
    session.execute(
        insert(index_sync_jobs).values(
            sync_job_id=sync_job_id,
            kb_id=kb_row["kb_id"],
            target_store=target_store,
            sync_type=sync_type,
            scope=scope,
            required_for_activation=required_for_activation,
            status=status,
            error_message=error_message,
            created_by=UUID(current_user.user.userId),
            started_at=func.now(),
            finished_at=func.now(),
        )
    )
    for chunk_id in chunk_ids:
        session.execute(
            insert(index_sync_records).values(
                sync_record_id=uuid4(),
                sync_job_id=sync_job_id,
                target_store=target_store,
                resource_type="chunk",
                resource_id=chunk_id,
                operation="upsert" if sync_type != "delete" else "delete",
                status="success",
                provider_payload={"provider": "local", "versionId": str(version_id)},
            )
        )
    return sync_job_id


def _write_chunk_access_filters(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    chunk_rows: list[RowMapping],
    version_status: str,
) -> None:
    """为新 Chunk 写入访问过滤摘要，供检索副本同步和 QA 前置过滤复用。"""
    access_filter = build_chunk_access_filter_context(session, current_user, kb_id)
    for row in chunk_rows:
        session.execute(
            insert(chunk_access_filters).values(
                access_filter_id=uuid4(),
                chunk_id=row["chunk_id"],
                kb_id=kb_id,
                permission_code=access_filter.permission_code,
                allow_subject_keys=access_filter.allow_subject_keys,
                deny_subject_keys=access_filter.deny_subject_keys,
                security_level=row["security_level"],
                document_status="active",
                version_status=version_status,
                chunk_status=row["status"],
                filter_hash=access_filter.filter_hash,
            )
        )


def run_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_row: RowMapping,
    job_id: UUID,
    source_bytes: bytes | None = None,
    storage_provider: ObjectStorageProvider | None = None,
) -> RowMapping:
    """执行本地解析切块 Worker，并同步更新版本、作业和副本状态。"""
    job_row = session.execute(
        select(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id, ingest_jobs.c.kb_id == kb_row["kb_id"])
        .limit(1)
    ).mappings().first()
    if job_row is None:
        raise DocumentConflictError("Ingest job not found.")
    if job_row["status"] == "cancelled":
        return job_row
    if job_row["version_id"] is None or job_row["document_id"] is None:
        raise DocumentConflictError("Ingest job has no document version.")

    version_row = session.execute(
        select(document_versions)
        .where(document_versions.c.version_id == job_row["version_id"])
        .limit(1)
    ).mappings().first()
    document_row = session.execute(
        select(documents)
        .where(documents.c.document_id == job_row["document_id"], documents.c.kb_id == kb_row["kb_id"])
        .limit(1)
    ).mappings().first()
    if version_row is None or document_row is None:
        raise DocumentConflictError("Document version not found.")

    storage = storage_provider or get_object_storage_provider()
    file_row = None
    if source_bytes is None:
        source_bytes, file_row = _read_source_bytes(session, version_row, storage)
    else:
        file_row = session.execute(
            select(stored_files).where(stored_files.c.file_id == version_row["source_file_id"]).limit(1)
        ).mappings().first()

    file_name = file_row["file_name"] if file_row else document_row["name"]
    if source_bytes is None:
        raise DocumentConflictError("Source file content is unavailable.")
    session.execute(
        update(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id)
        .values(status="running", stage="parse", progress=20, started_at=func.now())
    )
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_row["version_id"])
        .values(status="processing", parse_status="running", updated_by=UUID(current_user.user.userId), updated_at=func.now())
    )

    try:
        text = _decode_source_text(source_bytes or b"", file_name)
        parsed_chunks = _split_text_to_chunks(text)
        session.execute(delete(chunk_access_filters).where(chunk_access_filters.c.chunk_id.in_(select(chunks.c.chunk_id).where(chunks.c.version_id == version_row["version_id"]))))
        session.execute(delete(graph_chunk_refs).where(graph_chunk_refs.c.chunk_id.in_(select(chunks.c.chunk_id).where(chunks.c.version_id == version_row["version_id"]))))
        session.execute(delete(chunks).where(chunks.c.version_id == version_row["version_id"]))

        chunk_rows: list[RowMapping] = []
        for index, parsed in enumerate(parsed_chunks, start=1):
            content = parsed["content"]
            row = session.execute(
                insert(chunks)
                .values(
                    chunk_id=uuid4(),
                    version_id=version_row["version_id"],
                    document_id=document_row["document_id"],
                    kb_id=kb_row["kb_id"],
                    chunk_index=index,
                    page_no=parsed["page_no"],
                    section=parsed["section"],
                    content=content,
                    content_hash=sha256(content.encode("utf-8")).hexdigest(),
                    token_count=parsed["token_count"],
                    security_level=document_row["security_level"],
                    status="active",
                    metadata={"parser": "local_text", "sourceFileName": file_name},
                )
                .returning(chunks)
            ).mappings().one()
            chunk_rows.append(row)

        chunk_ids = [row["chunk_id"] for row in chunk_rows]
        new_version_status = "active" if document_row["active_version_id"] == version_row["version_id"] else "inactive"
        _write_chunk_access_filters(session, current_user, kb_row["kb_id"], chunk_rows, new_version_status)
        _create_index_sync_job(session, kb_row, current_user, "milvus", version_row["version_id"], chunk_ids, True)
        sparse_status = "not_required"
        graph_status = "not_required"
        if kb_row["sparse_index_enabled"]:
            _create_index_sync_job(
                session,
                kb_row,
                current_user,
                "opensearch",
                version_row["version_id"],
                chunk_ids,
                kb_row["sparse_required_for_activation"],
            )
            sparse_status = "success"
        if kb_row["graph_index_enabled"]:
            if new_version_status == "active":
                mark_graph_snapshots_stale(session, kb_row["kb_id"], "chunk_changed", current_user)
            graph_snapshot_id = uuid4()
            session.execute(
                insert(graph_snapshots).values(
                    graph_snapshot_id=graph_snapshot_id,
                    kb_id=kb_row["kb_id"],
                    source_scope={"versionIds": [str(version_row["version_id"])]},
                    status="success",
                    neo4j_graph_key=f"local:{graph_snapshot_id}",
                    entity_count=0,
                    relation_count=0,
                    community_count=0,
                    job_id=job_id,
                    created_by=UUID(current_user.user.userId),
                    updated_by=UUID(current_user.user.userId),
                )
            )
            _create_index_sync_job(
                session,
                kb_row,
                current_user,
                "neo4j",
                version_row["version_id"],
                chunk_ids,
                kb_row["graph_required_for_activation"],
            )
            graph_status = "success"

        retrieval_ready = True
        if kb_row["sparse_required_for_activation"] and sparse_status != "success":
            retrieval_ready = False
        if kb_row["graph_required_for_activation"] and graph_status != "success":
            retrieval_ready = False

        total_tokens = sum(row["token_count"] or 0 for row in chunk_rows)
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == version_row["version_id"])
            .values(
                status=new_version_status,
                parse_status="success",
                dense_index_status="success",
                sparse_index_status=sparse_status,
                graph_index_status=graph_status,
                retrieval_ready=retrieval_ready,
                chunk_count=len(chunk_rows),
                token_count=total_tokens,
                error_code=None,
                error_message=None,
                metadata={"parser": "local_text", "sourceFileName": file_name},
                updated_by=UUID(current_user.user.userId),
                updated_at=func.now(),
            )
        )
        job_row = session.execute(
            update(ingest_jobs)
            .where(ingest_jobs.c.job_id == job_id)
            .values(
                status="success",
                stage="completed",
                progress=100,
                error_code=None,
                error_message=None,
                result_summary={"chunkCount": len(chunk_rows), "tokenCount": total_tokens},
                finished_at=func.now(),
            )
            .returning(ingest_jobs)
        ).mappings().one()
    except Exception as exc:
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == version_row["version_id"])
            .values(
                status="failed",
                parse_status="failed",
                dense_index_status="failed",
                sparse_index_status="failed" if kb_row["sparse_index_enabled"] else "not_required",
                graph_index_status="failed" if kb_row["graph_index_enabled"] else "not_required",
                retrieval_ready=False,
                error_code="INGEST_PARSE_FAILED",
                error_message=str(exc),
                updated_by=UUID(current_user.user.userId),
                updated_at=func.now(),
            )
        )
        job_row = session.execute(
            update(ingest_jobs)
            .where(ingest_jobs.c.job_id == job_id)
            .values(
                status="failed",
                stage="failed",
                progress=100,
                error_code="INGEST_PARSE_FAILED",
                error_message=str(exc),
                finished_at=func.now(),
            )
            .returning(ingest_jobs)
        ).mappings().one()
    return job_row


def create_document_upload(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    name: str | None,
    security_level: str | None,
    storage_provider: ObjectStorageProvider | None = None,
) -> DocumentUploadResponse | None:
    """写入原始文件对象，并事务内创建文件、文档、首版本和 queued IngestJob。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    settings = get_settings()
    actor_id = UUID(current_user.user.userId)
    document_id = uuid4()
    version_id = uuid4()
    file_id = uuid4()
    job_id = uuid4()
    normalized_file_name = _safe_file_name(file_name)
    document_name = (name or normalized_file_name).strip() or normalized_file_name
    checksum = sha256(file_bytes).hexdigest()
    object_prefix = settings.storage_object_prefix.strip("/")
    object_path = f"kb/{kb_id}/documents/{document_id}/versions/{version_id}/{normalized_file_name}"
    object_key = f"{object_prefix}/{object_path}" if object_prefix else object_path
    sparse_status = "pending" if kb_row["sparse_index_enabled"] else "not_required"
    graph_status = "pending" if kb_row["graph_index_enabled"] else "not_required"
    storage = storage_provider or get_object_storage_provider()
    stored_object = storage.put_object(object_key=object_key, data=file_bytes, content_type=mime_type)

    try:
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
                kb_id=kb_id,
                name=document_name,
                source_type="upload",
                security_level=security_level or kb_row["default_security_level"],
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
                dense_index_status="pending",
                sparse_index_status=sparse_status,
                graph_index_status=graph_status,
                retrieval_ready=False,
                chunk_count=0,
                metadata={},
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(document_versions)
        ).mappings().one()
        document_row = session.execute(
            update(documents)
            .where(documents.c.document_id == document_id)
            .values(active_version_id=version_id)
            .returning(documents)
        ).mappings().one()
        job_row = session.execute(
            insert(ingest_jobs)
            .values(
                job_id=job_id,
                kb_id=kb_id,
                document_id=document_id,
                version_id=version_id,
                job_type="upload_parse",
                status="queued",
                stage="queued",
                progress=0,
                result_summary={},
                created_by=actor_id,
            )
            .returning(ingest_jobs)
        ).mappings().one()
        _insert_audit_log(
            session,
            current_user,
            "document.upload",
            "document",
            document_id,
            kb_id,
            document_id,
            {"versionId": str(version_id), "jobId": str(job_id), "fileName": normalized_file_name},
        )
        job_row = run_ingest_job(
            session=session,
            current_user=current_user,
            kb_row=kb_row,
            job_id=job_id,
            source_bytes=file_bytes,
            storage_provider=storage,
        )
        document_row = session.execute(select(documents).where(documents.c.document_id == document_id)).mappings().one()
        version_row = session.execute(select(document_versions).where(document_versions.c.version_id == version_id)).mappings().one()
        session.commit()
    except Exception:
        session.rollback()
        try:
            storage.delete_object(stored_object.object_key)
        except Exception:
            # 保留原始数据库异常，补偿删除失败交给后续运维巡检处理。
            pass
        raise

    return DocumentUploadResponse(
        document=_to_document_dto(document_row),
        version=_to_version_dto(version_row),
        ingestJob=_to_ingest_job_dto(job_row),
        storedFile=_to_stored_file_dto(stored_file_row),
    )


def list_documents(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    keyword: str | None,
) -> PageResponse[DocumentDTO] | None:
    """分页查询文档中心列表，按更新时间倒序返回当前知识库文档。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = (documents.c.kb_id == kb_id) & (documents.c.deleted_at.is_(None))
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            documents.c.name.ilike(keyword_pattern),
            documents.c.document_id.cast(sa.String).ilike(keyword_pattern),
        )

    total = session.execute(select(func.count()).select_from(documents).where(condition)).scalar_one()
    rows = session.execute(
        select(documents)
        .where(condition)
        .order_by(documents.c.updated_at.desc(), documents.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_document_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_document_detail(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
) -> DocumentDetailDTO | None:
    """读取文档详情，并附带 active version 摘要用于 P07 顶部信息区。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    document_row = session.execute(
        select(documents)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.document_id == document_id,
            documents.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if document_row is None:
        return None

    active_version = None
    if document_row["active_version_id"]:
        active_version = session.execute(
            select(document_versions)
            .where(document_versions.c.version_id == document_row["active_version_id"])
            .limit(1)
        ).mappings().first()

    return DocumentDetailDTO(
        document=_to_document_dto(document_row),
        activeVersion=_to_version_dto(active_version) if active_version else None,
    )


def get_document_quality_summary(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> DocumentQualitySummaryDTO | None:
    """汇总文档解析、Chunk 和权限过滤摘要质量问题，作为治理入口数据源。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    document_count = session.execute(
        select(func.count()).select_from(documents).where(documents.c.kb_id == kb_id, documents.c.deleted_at.is_(None))
    ).scalar_one()
    active_chunk_count = session.execute(
        select(func.count()).select_from(chunks).where(chunks.c.kb_id == kb_id, chunks.c.status == "active")
    ).scalar_one()
    failed_versions = session.execute(
        select(document_versions.c.document_id, document_versions.c.version_id, document_versions.c.error_message)
        .select_from(document_versions.join(documents, document_versions.c.document_id == documents.c.document_id))
        .where(documents.c.kb_id == kb_id, document_versions.c.parse_status == "failed")
    ).mappings().all()
    empty_chunks = session.execute(
        select(chunks.c.document_id, chunks.c.version_id, chunks.c.chunk_id)
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active", func.length(func.trim(chunks.c.content)) == 0)
    ).mappings().all()
    duplicate_groups = session.execute(
        select(chunks.c.content_hash, func.count().label("chunk_count"))
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active", chunks.c.content_hash.is_not(None))
        .group_by(chunks.c.content_hash)
        .having(func.count() > 1)
    ).mappings().all()
    permission_anomalies = session.execute(
        select(chunks.c.document_id, chunks.c.version_id, chunks.c.chunk_id)
        .select_from(chunks.outerjoin(chunk_access_filters, chunks.c.chunk_id == chunk_access_filters.c.chunk_id))
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active", chunk_access_filters.c.chunk_id.is_(None))
    ).mappings().all()

    issues: list[DocumentQualityIssueDTO] = []
    for row in failed_versions[:20]:
        issues.append(
            DocumentQualityIssueDTO(
                issueType="parse_failed",
                severity="high",
                documentId=str(row["document_id"]),
                versionId=str(row["version_id"]),
                count=1,
                message=row["error_message"] or "文档版本解析失败。",
            )
        )
    for row in empty_chunks[:20]:
        issues.append(
            DocumentQualityIssueDTO(
                issueType="empty_chunk",
                severity="medium",
                documentId=str(row["document_id"]),
                versionId=str(row["version_id"]),
                chunkId=str(row["chunk_id"]),
                count=1,
                message="Chunk 正文为空，建议重解析或排除。",
            )
        )
    for row in duplicate_groups[:20]:
        issues.append(
            DocumentQualityIssueDTO(
                issueType="duplicate_chunk",
                severity="low",
                count=row["chunk_count"],
                message=f"存在 {row['chunk_count']} 个重复正文 Chunk，contentHash={row['content_hash']}。",
            )
        )
    for row in permission_anomalies[:20]:
        issues.append(
            DocumentQualityIssueDTO(
                issueType="permission_filter_missing",
                severity="high",
                documentId=str(row["document_id"]),
                versionId=str(row["version_id"]),
                chunkId=str(row["chunk_id"]),
                count=1,
                message="Chunk 缺少访问过滤摘要，检索副本同步前应重建。",
            )
        )

    return DocumentQualitySummaryDTO(
        kbId=str(kb_id),
        documentCount=document_count,
        activeChunkCount=active_chunk_count,
        failedVersionCount=len(failed_versions),
        emptyChunkCount=len(empty_chunks),
        duplicateChunkGroupCount=len(duplicate_groups),
        permissionAnomalyCount=len(permission_anomalies),
        issues=issues,
    )


def run_bulk_document_governance(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    operation: str,
    document_ids: list[UUID],
    confirm_impact: bool,
    reason: str | None,
    target_store: str | None,
) -> BulkDocumentGovernanceResponse | None:
    """执行批量文档治理动作；所有高影响动作必须带二次确认。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")
    if not confirm_impact:
        raise DocumentConflictError("confirmImpact must be true.")

    if operation == "reparse":
        affected: list[str] = []
        errors: list[str] = []
        for document_id in document_ids:
            try:
                response = reparse_document(session, current_user, kb_id, document_id, reason)
                if response is None:
                    errors.append(f"{document_id}: document not found")
                else:
                    affected.append(str(document_id))
            except Exception as exc:
                errors.append(f"{document_id}: {exc}")
        return BulkDocumentGovernanceResponse(
            operation=operation,
            requestedCount=len(document_ids),
            successCount=len(affected),
            failedCount=len(errors),
            affectedIds=affected,
            errors=errors,
        )

    if operation == "disable":
        result = session.execute(
            update(documents)
            .where(documents.c.kb_id == kb_id, documents.c.document_id.in_(document_ids), documents.c.deleted_at.is_(None))
            .values(status="disabled", updated_by=UUID(current_user.user.userId), updated_at=func.now())
            .returning(documents.c.document_id)
        )
        affected_ids = [str(row[0]) for row in result]
        for document_id in affected_ids:
            _insert_audit_log(
                session,
                current_user,
                "document.batch_disable",
                "document",
                UUID(document_id),
                kb_id,
                UUID(document_id),
                {"reason": reason},
            )
        session.commit()
        return BulkDocumentGovernanceResponse(
            operation=operation,
            requestedCount=len(document_ids),
            successCount=len(affected_ids),
            failedCount=len(document_ids) - len(affected_ids),
            affectedIds=affected_ids,
            errors=[],
        )

    if operation == "rebuild_index":
        if not target_store:
            raise DocumentConflictError("targetStore is required for rebuild_index.")
        if target_store not in {"milvus", "opensearch", "neo4j"}:
            raise DocumentConflictError("Unsupported target store.")
        condition = (
            (chunks.c.kb_id == kb_id)
            & (chunks.c.status == "active")
            & (document_versions.c.status == "active")
        )
        if document_ids:
            condition = condition & chunks.c.document_id.in_(document_ids)
        chunk_ids = [
            row[0]
            for row in session.execute(
                select(chunks.c.chunk_id)
                .select_from(chunks.join(document_versions, chunks.c.version_id == document_versions.c.version_id))
                .where(condition)
            )
        ]
        status = "success" if chunk_ids else "failed"
        error_message = None if chunk_ids else "No active chunks found for rebuild scope."
        sync_job_id = _create_index_sync_job(
            session,
            kb_row,
            current_user,
            target_store,
            None,
            chunk_ids,
            target_store == "milvus",
            sync_type="rebuild",
            status=status,
            error_message=error_message,
        )
        _insert_audit_log(
            session,
            current_user,
            "document.batch_rebuild_index",
            "index_sync_job",
            sync_job_id,
            kb_id,
            None,
            {"targetStore": target_store, "documentIds": [str(item) for item in document_ids], "status": status},
        )
        session.commit()
        return BulkDocumentGovernanceResponse(
            operation=operation,
            requestedCount=len(document_ids),
            successCount=1 if status == "success" else 0,
            failedCount=0 if status == "success" else 1,
            affectedIds=[str(sync_job_id)],
            errors=[] if error_message is None else [error_message],
        )

    raise DocumentConflictError("Unsupported batch governance operation.")


def list_document_versions(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
) -> list[DocumentVersionDTO] | None:
    """返回指定文档的版本列表，默认按版本号倒序。"""
    if get_document_detail(session, current_user, kb_id, document_id) is None:
        return None

    rows = session.execute(
        select(document_versions)
        .where(document_versions.c.document_id == document_id)
        .order_by(document_versions.c.version_no.desc(), document_versions.c.created_at.desc())
    ).mappings()
    return [_to_version_dto(row) for row in rows]


def list_ingest_jobs(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    document_id: UUID | None = None,
) -> PageResponse[IngestJobDTO] | None:
    """分页查询知识库入库作业，可按文档 ID 收窄范围。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = ingest_jobs.c.kb_id == kb_id
    if document_id is not None:
        condition = condition & (ingest_jobs.c.document_id == document_id)

    total = session.execute(select(func.count()).select_from(ingest_jobs).where(condition)).scalar_one()
    rows = session.execute(
        select(ingest_jobs)
        .where(condition)
        .order_by(ingest_jobs.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_ingest_job_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    job_id: UUID,
) -> IngestJobDTO | None:
    """读取单个入库作业；不可见知识库和不存在作业统一返回 None。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    row = session.execute(
        select(ingest_jobs)
        .where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.job_id == job_id)
        .limit(1)
    ).mappings().first()
    return _to_ingest_job_dto(row) if row else None


def list_chunks(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    version_id: UUID,
    page_no: int,
    page_size: int,
) -> PageResponse[ChunkDTO] | None:
    """分页读取指定版本 Chunk；无正文读取权时不返回资源细节。"""
    if get_document_detail(session, current_user, kb_id, document_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.chunk.read")

    condition = (
        (chunks.c.kb_id == kb_id)
        & (chunks.c.document_id == document_id)
        & (chunks.c.version_id == version_id)
        & (chunks.c.status == "active")
    )
    total = session.execute(select(func.count()).select_from(chunks).where(condition)).scalar_one()
    rows = session.execute(
        select(chunks)
        .where(condition)
        .order_by(chunks.c.chunk_index.asc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_chunk_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_chunk(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    chunk_id: UUID,
) -> ChunkDTO | None:
    """读取单个 Chunk 正文，按 `kb.chunk.read` 做最终后端鉴权。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.chunk.read")

    row = session.execute(
        select(chunks)
        .where(chunks.c.kb_id == kb_id, chunks.c.chunk_id == chunk_id, chunks.c.status == "active")
        .limit(1)
    ).mappings().first()
    return _to_chunk_dto(row) if row else None


def update_chunk_governance(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    chunk_id: UUID,
    excluded: bool,
    note: str | None,
) -> ChunkGovernanceResponse | None:
    """更新 Chunk 治理标记；排除只影响检索上下文，不删除 PostgreSQL 正文。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    row = session.execute(
        select(chunks).where(chunks.c.kb_id == kb_id, chunks.c.chunk_id == chunk_id, chunks.c.status == "active").limit(1)
    ).mappings().first()
    if row is None:
        return None

    metadata = dict(row["metadata"] or {})
    governance = dict(metadata.get("governance") or {})
    governance["excluded"] = excluded
    governance["note"] = note
    governance["updatedBy"] = current_user.user.userId
    metadata["governance"] = governance
    updated_row = session.execute(
        update(chunks)
        .where(chunks.c.chunk_id == chunk_id)
        .values(metadata=metadata)
        .returning(chunks)
    ).mappings().one()
    _insert_audit_log(
        session,
        current_user,
        "chunk.governance_update",
        "chunk",
        chunk_id,
        kb_id,
        row["document_id"],
        {"excluded": excluded, "note": note},
    )
    session.commit()
    return ChunkGovernanceResponse(
        chunk=_to_chunk_dto(updated_row),
        excluded=excluded,
        governanceNote=note,
        permissionInheritance="Chunk 继承文档密级、文档状态和知识库成员权限；治理排除只影响后续检索上下文。",
    )


def reparse_document(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    reason: str | None,
) -> DocumentUploadResponse | None:
    """基于当前 active version 的源文件创建新版本，并立即执行本地解析 Worker。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    document_row = session.execute(
        select(documents)
        .where(documents.c.kb_id == kb_id, documents.c.document_id == document_id, documents.c.deleted_at.is_(None))
        .limit(1)
    ).mappings().first()
    if document_row is None:
        return None

    source_version = session.execute(
        select(document_versions)
        .where(document_versions.c.version_id == document_row["active_version_id"])
        .limit(1)
    ).mappings().first()
    if source_version is None:
        raise DocumentConflictError("Active version is required before reparse.")

    next_version_no = session.execute(
        select(func.coalesce(func.max(document_versions.c.version_no), 0) + 1).where(
            document_versions.c.document_id == document_id
        )
    ).scalar_one()
    version_id = uuid4()
    job_id = uuid4()
    actor_id = UUID(current_user.user.userId)
    sparse_status = "pending" if kb_row["sparse_index_enabled"] else "not_required"
    graph_status = "pending" if kb_row["graph_index_enabled"] else "not_required"

    try:
        version_row = session.execute(
            insert(document_versions)
            .values(
                version_id=version_id,
                document_id=document_id,
                version_no=next_version_no,
                source_file_id=source_version["source_file_id"],
                status="processing",
                parse_status="pending",
                dense_index_status="pending",
                sparse_index_status=sparse_status,
                graph_index_status=graph_status,
                retrieval_ready=False,
                chunk_count=0,
                metadata={"reparseReason": reason},
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(document_versions)
        ).mappings().one()
        job_row = session.execute(
            insert(ingest_jobs)
            .values(
                job_id=job_id,
                kb_id=kb_id,
                document_id=document_id,
                version_id=version_id,
                job_type="reparse",
                status="queued",
                stage="queued",
                progress=0,
                result_summary={"reason": reason},
                created_by=actor_id,
            )
            .returning(ingest_jobs)
        ).mappings().one()
        _insert_audit_log(
            session,
            current_user,
            "document.reparse",
            "document",
            document_id,
            kb_id,
            document_id,
            {"versionId": str(version_id), "jobId": str(job_id), "reason": reason},
        )
        job_row = run_ingest_job(session, current_user, kb_row, job_id)
        version_row = session.execute(select(document_versions).where(document_versions.c.version_id == version_id)).mappings().one()
        stored_file_row = session.execute(
            select(stored_files).where(stored_files.c.file_id == version_row["source_file_id"]).limit(1)
        ).mappings().one()
        session.commit()
    except Exception:
        session.rollback()
        raise

    return DocumentUploadResponse(
        document=_to_document_dto(document_row),
        version=_to_version_dto(version_row),
        ingestJob=_to_ingest_job_dto(job_row),
        storedFile=_to_stored_file_dto(stored_file_row),
    )


def activate_document_version(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    version_id: UUID,
    confirm_impact: bool,
    reason: str | None,
) -> DocumentVersionActivateResponse | None:
    """切换文档 active version，并将旧图快照标记 stale。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")
    if not confirm_impact:
        raise DocumentConflictError("confirmImpact must be true.")

    document_row = session.execute(
        select(documents)
        .where(documents.c.kb_id == kb_id, documents.c.document_id == document_id, documents.c.deleted_at.is_(None))
        .limit(1)
    ).mappings().first()
    version_row = session.execute(
        select(document_versions)
        .where(document_versions.c.document_id == document_id, document_versions.c.version_id == version_id)
        .limit(1)
    ).mappings().first()
    if document_row is None or version_row is None:
        return None
    if version_row["status"] == "failed" or version_row["parse_status"] != "success":
        raise DocumentConflictError("Version is not parse-ready.")
    if not version_row["retrieval_ready"]:
        raise DocumentConflictError("Version is not retrieval-ready.")

    previous_active_version_id = document_row["active_version_id"]
    audit_log_id = _insert_audit_log(
        session,
        current_user,
        "document.version.activate",
        "document_version",
        version_id,
        kb_id,
        document_id,
        {
            "previousActiveVersionId": str(previous_active_version_id) if previous_active_version_id else None,
            "activeVersionId": str(version_id),
            "reason": reason,
        },
    )
    session.execute(
        update(document_versions)
        .where(document_versions.c.document_id == document_id, document_versions.c.status == "active")
        .values(status="inactive", updated_by=UUID(current_user.user.userId), updated_at=func.now())
    )
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_id)
        .values(status="active", updated_by=UUID(current_user.user.userId), updated_at=func.now())
    )
    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(active_version_id=version_id, updated_by=UUID(current_user.user.userId), updated_at=func.now())
    )
    mark_graph_snapshots_stale(session, kb_id, "active_version_changed", current_user)
    session.commit()
    return DocumentVersionActivateResponse(
        documentId=str(document_id),
        activeVersionId=str(version_id),
        previousActiveVersionId=str(previous_active_version_id) if previous_active_version_id else None,
        auditLogId=str(audit_log_id),
    )


def retry_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    job_id: UUID,
) -> IngestJobDTO | None:
    """重试失败或取消的 IngestJob；重试必须创建新作业记录。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    old_job = session.execute(
        select(ingest_jobs).where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.job_id == job_id).limit(1)
    ).mappings().first()
    if old_job is None:
        return None
    if old_job["status"] not in {"failed", "cancelled"}:
        raise DocumentConflictError("Ingest job is not retryable.")

    new_job_id = uuid4()
    job_row = session.execute(
        insert(ingest_jobs)
        .values(
            job_id=new_job_id,
            kb_id=kb_id,
            document_id=old_job["document_id"],
            version_id=old_job["version_id"],
            job_type=old_job["job_type"],
            status="queued",
            stage="queued",
            progress=0,
            retry_of_job_id=old_job["job_id"],
            result_summary={"retryOfJobId": str(old_job["job_id"])},
            created_by=UUID(current_user.user.userId),
        )
        .returning(ingest_jobs)
    ).mappings().one()
    _insert_audit_log(
        session,
        current_user,
        "ingest_job.retry",
        "ingest_job",
        new_job_id,
        kb_id,
        old_job["document_id"],
        {"retryOfJobId": str(old_job["job_id"])},
    )
    job_row = run_ingest_job(session, current_user, kb_row, new_job_id)
    session.commit()
    return _to_ingest_job_dto(job_row)


def cancel_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    job_id: UUID,
) -> IngestJobDTO | None:
    """取消 queued/running 作业；已完成作业不允许回退状态。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    old_job = session.execute(
        select(ingest_jobs).where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.job_id == job_id).limit(1)
    ).mappings().first()
    if old_job is None:
        return None
    if old_job["status"] not in {"queued", "running"}:
        raise DocumentConflictError("Only queued or running ingest jobs can be cancelled.")

    job_row = session.execute(
        update(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id)
        .values(status="cancelled", stage="cancelled", progress=100, finished_at=func.now())
        .returning(ingest_jobs)
    ).mappings().one()
    _insert_audit_log(
        session,
        current_user,
        "ingest_job.cancel",
        "ingest_job",
        job_id,
        kb_id,
        old_job["document_id"],
        {},
    )
    session.commit()
    return _to_ingest_job_dto(job_row)


def list_index_sync_jobs(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
) -> PageResponse[IndexSyncJobDTO] | None:
    """分页查询知识库副本同步作业状态。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    condition = index_sync_jobs.c.kb_id == kb_id
    total = session.execute(select(func.count()).select_from(index_sync_jobs).where(condition)).scalar_one()
    rows = session.execute(
        select(index_sync_jobs)
        .where(condition)
        .order_by(index_sync_jobs.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_index_sync_job_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def rebuild_index_sync(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    target_store: str,
    document_id: UUID | None = None,
    version_id: UUID | None = None,
) -> IndexSyncJobDTO | None:
    """基于 PostgreSQL Chunk 真值创建副本重建作业，并记录空范围失败原因。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if target_store not in {"milvus", "opensearch", "neo4j"}:
        raise DocumentConflictError("Unsupported target store.")
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    condition = (
        (chunks.c.kb_id == kb_id)
        & (chunks.c.status == "active")
        & (document_versions.c.status == "active")
    )
    if document_id is not None:
        condition = condition & (chunks.c.document_id == document_id)
    if version_id is not None:
        condition = condition & (chunks.c.version_id == version_id)

    chunk_ids = [
        row[0]
        for row in session.execute(
            select(chunks.c.chunk_id)
            .select_from(chunks.join(document_versions, chunks.c.version_id == document_versions.c.version_id))
            .where(condition)
        )
    ]
    status = "success" if chunk_ids else "failed"
    error_message = None if chunk_ids else "No active chunks found for rebuild scope."
    sync_job_id = _create_index_sync_job(
        session,
        kb_row,
        current_user,
        target_store,
        version_id,
        chunk_ids,
        target_store == "milvus",
        sync_type="rebuild",
        status=status,
        error_message=error_message,
    )
    _insert_audit_log(
        session,
        current_user,
        "index_sync.rebuild",
        "index_sync_job",
        sync_job_id,
        kb_id,
        document_id,
        {
            "targetStore": target_store,
            "documentId": str(document_id) if document_id else None,
            "versionId": str(version_id) if version_id else None,
            "chunkCount": len(chunk_ids),
            "status": status,
            "errorMessage": error_message,
        },
    )
    row = session.execute(select(index_sync_jobs).where(index_sync_jobs.c.sync_job_id == sync_job_id)).mappings().one()
    session.commit()
    return _to_index_sync_job_dto(row)
