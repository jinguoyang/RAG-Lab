from hashlib import sha256
from pathlib import PurePath
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import RowMapping, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse
from app.schemas.document import (
    DocumentDetailDTO,
    DocumentDTO,
    DocumentUploadResponse,
    DocumentVersionDTO,
    IngestJobDTO,
    StoredFileDTO,
)
from app.schemas.common import PageResponse
from app.tables import (
    document_versions,
    documents,
    ingest_jobs,
    knowledge_bases,
    stored_files,
)
from app.services.object_storage import ObjectStorageProvider, get_object_storage_provider
from app.services.knowledge_base_service import KnowledgeBaseDisabledError


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用 E1 最小权限：平台管理员可访问全部知识库。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库，上传链路需要默认密级和索引能力。"""
    condition = (knowledge_bases.c.deleted_at.is_(None)) & (knowledge_bases.c.kb_id == kb_id)
    if not _is_platform_admin(current_user):
        condition = condition & (knowledge_bases.c.owner_id == UUID(current_user.user.userId))

    return session.execute(select(knowledge_bases).where(condition).limit(1)).mappings().first()


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
