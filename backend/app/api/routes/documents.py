from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.document import DocumentUploadResponse
from app.services.document_service import create_document_upload

router = APIRouter(prefix="/knowledge-bases/{kb_id}/documents", tags=["documents"])


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
