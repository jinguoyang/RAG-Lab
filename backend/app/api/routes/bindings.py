"""知识库文档库绑定 API 路由。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.binding import (
    LibraryBindRequest,
    LibraryBindResponse,
    LibraryBindingDTO,
    LibraryUnbindResponse,
    SwitchBindingVersionRequest,
)
from app.services.binding_service import (
    BindingAlreadyExistsError,
    BindingDispatchError,
    BindingDocumentNotFoundError,
    BindingKBNotFoundError,
    BindingNotFoundError,
    BindingPermissionError,
    BindingVersionNotReadyError,
    bind_documents_to_kb,
    list_kb_bindings,
    retry_binding,
    switch_binding_version,
    unbind_document_from_kb,
)

router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/library-bindings",
    tags=["library-bindings"],
)


def _raise_binding_error(exc: Exception) -> None:
    """将绑定服务层业务异常映射为稳定 HTTP 状态。"""
    if isinstance(exc, BindingPermissionError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PERMISSION_DENIED",
        ) from exc
    if isinstance(exc, BindingDocumentNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="DOCUMENT_NOT_FOUND",
        ) from exc
    if isinstance(exc, BindingKBNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KB_NOT_FOUND",
        ) from exc
    if isinstance(exc, BindingAlreadyExistsError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="BINDING_ALREADY_EXISTS",
        ) from exc
    if isinstance(exc, BindingNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BINDING_NOT_FOUND",
        ) from exc
    if isinstance(exc, BindingVersionNotReadyError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VERSION_NOT_READY",
        ) from exc
    if isinstance(exc, BindingDispatchError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "INGEST_ENQUEUE_FAILED", "jobIds": exc.job_ids},
        ) from exc
    raise exc


@router.post("", response_model=LibraryBindResponse)
def bind_documents(
    kb_id: UUID,
    body: LibraryBindRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryBindResponse:
    """将文档库文档绑定到知识库。"""
    try:
        doc_ids = [UUID(d) for d in body.documentIds]
        return bind_documents_to_kb(db, current_user, kb_id, doc_ids)
    except Exception as exc:
        _raise_binding_error(exc)
        raise  # unreachable


@router.get("", response_model=list[LibraryBindingDTO])
def list_bindings(
    kb_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[LibraryBindingDTO]:
    """列出知识库的所有文档库绑定。"""
    try:
        return list_kb_bindings(db, current_user, kb_id)
    except Exception as exc:
        _raise_binding_error(exc)
        raise  # unreachable


@router.post("/{binding_id}/retry")
def retry_binding_route(
    kb_id: UUID,
    binding_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """重试失败的绑定。"""
    try:
        return retry_binding(db, current_user, kb_id, binding_id)
    except Exception as exc:
        _raise_binding_error(exc)
        raise  # unreachable


@router.delete("/{binding_id}", response_model=LibraryUnbindResponse)
def unbind_document(
    kb_id: UUID,
    binding_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryUnbindResponse:
    """解绑文档库文档与知识库的绑定关系。"""
    try:
        return unbind_document_from_kb(db, current_user, kb_id, binding_id)
    except Exception as exc:
        _raise_binding_error(exc)
        raise  # unreachable


@router.post("/{binding_id}/switch-version", response_model=LibraryBindingDTO)
def switch_version(
    kb_id: UUID,
    binding_id: UUID,
    body: SwitchBindingVersionRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryBindingDTO:
    """切换绑定到不同的库文档版本。"""
    try:
        return switch_binding_version(db, current_user, kb_id, binding_id, UUID(body.libraryVersionId))
    except Exception as exc:
        _raise_binding_error(exc)
        raise  # unreachable
