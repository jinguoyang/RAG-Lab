from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.document import (
    ChunkDTO,
    DocumentDTO,
    DocumentDetailDTO,
    DocumentReparseRequest,
    DocumentUploadResponse,
    DocumentVersionActivateRequest,
    DocumentVersionActivateResponse,
    DocumentVersionDTO,
    IndexSyncJobDTO,
    IngestJobDTO,
)
from app.services.document_service import (
    DocumentConflictError,
    DocumentPermissionError,
    activate_document_version,
    cancel_ingest_job,
    create_document_upload,
    get_chunk,
    get_document_detail,
    get_ingest_job,
    list_chunks,
    list_document_versions,
    list_documents,
    list_ingest_jobs,
    list_index_sync_jobs,
    rebuild_index_sync,
    reparse_document,
    retry_ingest_job,
)
from app.services.knowledge_base_service import KnowledgeBaseDisabledError
from app.services.object_storage import ObjectStorageError

router = APIRouter(prefix="/knowledge-bases/{kb_id}/documents", tags=["documents"])
ingest_job_router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/ingest-jobs",
    tags=["ingest-jobs"],
)
chunk_router = APIRouter(prefix="/knowledge-bases/{kb_id}/chunks", tags=["chunks"])
index_sync_router = APIRouter(prefix="/knowledge-bases/{kb_id}/index-sync-jobs", tags=["index-sync-jobs"])


def _raise_document_error(exc: Exception) -> None:
    """将文档服务层业务异常映射为稳定 HTTP 状态。"""
    if isinstance(exc, DocumentPermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if isinstance(exc, KnowledgeBaseDisabledError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="KB_DISABLED: knowledge base is disabled.") from exc
    if isinstance(exc, DocumentConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.get("", response_model=PageResponse[DocumentDTO])
def read_documents(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[DocumentDTO]:
    """分页返回当前知识库文档列表。"""
    response = list_documents(session, current_user, kb_id, page_no, page_size, keyword)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: UUID,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    security_level: Annotated[str | None, Form(alias="securityLevel")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    """上传文档元数据，并创建首个版本和 queued 入库作业。"""
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        response = create_document_upload(
            session=session,
            current_user=current_user,
            kb_id=kb_id,
            file_name=file.filename or "uploaded-document",
            mime_type=file.content_type,
            file_bytes=file_bytes,
            name=name,
            security_level=security_level,
        )
    except (KnowledgeBaseDisabledError, DocumentPermissionError, DocumentConflictError) as exc:
        _raise_document_error(exc)
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STORAGE_WRITE_FAILED: object storage write failed.",
        ) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.post("/{document_id}/reparse", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def reparse_document_endpoint(
    kb_id: UUID,
    document_id: UUID,
    request: DocumentReparseRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    """创建重解析版本和作业，并执行本地解析 Worker。"""
    try:
        response = reparse_document(session, current_user, kb_id, document_id, request.reason)
    except (KnowledgeBaseDisabledError, DocumentPermissionError, DocumentConflictError) as exc:
        _raise_document_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return response


@router.get("/{document_id}", response_model=DocumentDetailDTO)
def read_document_detail(
    kb_id: UUID,
    document_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DocumentDetailDTO:
    """返回文档详情和 active version 摘要。"""
    response = get_document_detail(session, current_user, kb_id, document_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return response


@router.get("/{document_id}/versions", response_model=list[DocumentVersionDTO])
def read_document_versions(
    kb_id: UUID,
    document_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[DocumentVersionDTO]:
    """返回文档版本列表。"""
    response = list_document_versions(session, current_user, kb_id, document_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return response


@router.post("/{document_id}/versions/{version_id}/activate", response_model=DocumentVersionActivateResponse)
def activate_version_endpoint(
    kb_id: UUID,
    document_id: UUID,
    version_id: UUID,
    request: DocumentVersionActivateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DocumentVersionActivateResponse:
    """切换文档 active version，要求前端传入二次确认标记。"""
    try:
        response = activate_document_version(
            session,
            current_user,
            kb_id,
            document_id,
            version_id,
            request.confirmImpact,
            request.reason,
        )
    except (KnowledgeBaseDisabledError, DocumentPermissionError, DocumentConflictError) as exc:
        _raise_document_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found.")
    return response


@router.get("/{document_id}/versions/{version_id}/chunks", response_model=PageResponse[ChunkDTO])
def read_chunks(
    kb_id: UUID,
    document_id: UUID,
    version_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[ChunkDTO]:
    """分页返回版本 Chunk 正文。"""
    try:
        response = list_chunks(session, current_user, kb_id, document_id, version_id, page_no, page_size)
    except DocumentPermissionError as exc:
        _raise_document_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found.")
    return response


@ingest_job_router.get("", response_model=PageResponse[IngestJobDTO])
def read_ingest_jobs(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    document_id: Annotated[UUID | None, Query(alias="documentId")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[IngestJobDTO]:
    """分页返回知识库入库作业列表。"""
    response = list_ingest_jobs(session, current_user, kb_id, page_no, page_size, document_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@ingest_job_router.get("/{job_id}", response_model=IngestJobDTO)
def read_ingest_job(
    kb_id: UUID,
    job_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> IngestJobDTO:
    """返回单个入库作业详情。"""
    response = get_ingest_job(session, current_user, kb_id, job_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingest job not found.")
    return response


@chunk_router.get("/{chunk_id}", response_model=ChunkDTO)
def read_chunk(
    kb_id: UUID,
    chunk_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ChunkDTO:
    """返回单个 Chunk 正文和元数据。"""
    try:
        response = get_chunk(session, current_user, kb_id, chunk_id)
    except DocumentPermissionError as exc:
        _raise_document_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk not found.")
    return response


@ingest_job_router.post("/{job_id}/retry", response_model=IngestJobDTO, status_code=status.HTTP_201_CREATED)
def retry_ingest_job_endpoint(
    kb_id: UUID,
    job_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> IngestJobDTO:
    """重试失败或取消的 IngestJob。"""
    try:
        response = retry_ingest_job(session, current_user, kb_id, job_id)
    except (KnowledgeBaseDisabledError, DocumentPermissionError, DocumentConflictError) as exc:
        _raise_document_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingest job not found.")
    return response


@ingest_job_router.post("/{job_id}/cancel", response_model=IngestJobDTO)
def cancel_ingest_job_endpoint(
    kb_id: UUID,
    job_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> IngestJobDTO:
    """取消 queued/running IngestJob。"""
    try:
        response = cancel_ingest_job(session, current_user, kb_id, job_id)
    except (KnowledgeBaseDisabledError, DocumentPermissionError, DocumentConflictError) as exc:
        _raise_document_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingest job not found.")
    return response


@index_sync_router.get("", response_model=PageResponse[IndexSyncJobDTO])
def read_index_sync_jobs(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[IndexSyncJobDTO]:
    """分页返回副本同步作业。"""
    response = list_index_sync_jobs(session, current_user, kb_id, page_no, page_size)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@index_sync_router.post("/rebuild", response_model=IndexSyncJobDTO, status_code=status.HTTP_201_CREATED)
def rebuild_index_sync_endpoint(
    kb_id: UUID,
    target_store: Annotated[str, Query(alias="targetStore")],
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> IndexSyncJobDTO:
    """基于 PostgreSQL Chunk 真值创建本地副本重建作业。"""
    try:
        response = rebuild_index_sync(session, current_user, kb_id, target_store)
    except (DocumentPermissionError, DocumentConflictError) as exc:
        _raise_document_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response
