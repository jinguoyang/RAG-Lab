from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.document import (
    DocumentDTO,
    DocumentDetailDTO,
    DocumentUploadResponse,
    DocumentVersionDTO,
    IngestJobDTO,
)
from app.services.document_service import (
    create_document_upload,
    get_document_detail,
    get_ingest_job,
    list_document_versions,
    list_documents,
    list_ingest_jobs,
)

router = APIRouter(prefix="/knowledge-bases/{kb_id}/documents", tags=["documents"])
ingest_job_router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/ingest-jobs",
    tags=["ingest-jobs"],
)


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
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
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
