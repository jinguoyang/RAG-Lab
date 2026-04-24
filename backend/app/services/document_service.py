from hashlib import sha256
from pathlib import PurePath
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.document import (
    DocumentDTO,
    DocumentUploadResponse,
    DocumentVersionDTO,
    IngestJobDTO,
    StoredFileDTO,
)
from app.tables import (
    document_versions,
    documents,
    ingest_jobs,
    knowledge_bases,
    stored_files,
)

DEV_SOURCE_BUCKET = "dev-local"


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
) -> DocumentUploadResponse | None:
    """事务内创建文件、文档、首版本和 queued IngestJob，失败时整体回滚。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None

    actor_id = UUID(current_user.user.userId)
    document_id = uuid4()
    version_id = uuid4()
    file_id = uuid4()
    job_id = uuid4()
    normalized_file_name = _safe_file_name(file_name)
    document_name = (name or normalized_file_name).strip() or normalized_file_name
    checksum = sha256(file_bytes).hexdigest()
    object_key = f"dev/kb/{kb_id}/documents/{document_id}/versions/{version_id}/{normalized_file_name}"
    sparse_status = "pending" if kb_row["sparse_index_enabled"] else "not_required"
    graph_status = "pending" if kb_row["graph_index_enabled"] else "not_required"

    try:
        stored_file_row = session.execute(
            insert(stored_files)
            .values(
                file_id=file_id,
                bucket=DEV_SOURCE_BUCKET,
                object_key=object_key,
                file_name=normalized_file_name,
                mime_type=mime_type,
                file_size=len(file_bytes),
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
        raise

    return DocumentUploadResponse(
        document=_to_document_dto(document_row),
        version=_to_version_dto(version_row),
        ingestJob=_to_ingest_job_dto(job_row),
        storedFile=_to_stored_file_dto(stored_file_row),
    )
