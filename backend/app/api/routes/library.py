"""文档库 API 路由。"""

from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.library import (
    BatchActionRequest,
    BatchActionResponse,
    LibraryDocumentDTO,
    LibraryDocumentDetailDTO,
    LibraryDocumentUpdateRequest,
    LibraryDocumentUploadResponse,
    LibraryDocumentVersionDTO,
    LibraryFullTextResponse,
    LibraryParseJobDTO,
    LibraryParsedChunksResponse,
    LibraryStatsResponse,
    LibraryTextPreviewResponse,
    LibraryVersionActivateRequest,
    LibraryVersionActivateResponse,
    LibraryVersionUploadResponse,
)
from app.services.library_service import (
    LibraryDocumentNotFoundError,
    LibraryPermissionError,
    LibraryVersionInUseError,
    LibraryVersionNotFoundError,
    activate_library_version,
    batch_action,
    create_library_upload,
    delete_library_document,
    delete_library_version,
    get_document_text,
    get_document_usage,
    get_library_document_detail,
    get_library_document_source_download,
    get_library_parse_jobs,
    get_library_stats,
    list_library_documents,
    list_library_versions,
    retry_library_parse,
    update_library_document,
    upload_library_version,
)
from app.services.object_storage import ObjectStorageError

router = APIRouter(prefix="/library/documents", tags=["library"])


def _raise_library_error(exc: Exception) -> None:
    if isinstance(exc, LibraryPermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc) or "PERMISSION_DENIED") from exc
    if isinstance(exc, LibraryDocumentNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DOCUMENT_NOT_FOUND") from exc
    if isinstance(exc, LibraryVersionNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VERSION_NOT_FOUND") from exc
    if isinstance(exc, LibraryVersionInUseError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_IN_USE", "kbNames": exc.kb_names},
        ) from exc
    if isinstance(exc, ObjectStorageError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STORAGE_ERROR: object storage operation failed.",
        ) from exc
    raise exc


@router.get("", response_model=PageResponse[LibraryDocumentDTO])
def list_documents(
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
    doc_status: str | None = Query(default=None, alias="status"),
    library_id: UUID | None = Query(default=None),
) -> PageResponse[LibraryDocumentDTO]:
    """列出当前用户的文档库文档。"""
    try:
        return list_library_documents(db, current_user, page_no, page_size, keyword, doc_status, library_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("", response_model=LibraryDocumentUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    libraryId: UUID | None = Form(default=None),
) -> LibraryDocumentUploadResponse:
    """上传文档到个人文档库。"""
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="EMPTY_FILE")
    try:
        return create_library_upload(
            session=db,
            current_user=current_user,
            file_name=file.filename or "uploaded-document",
            mime_type=file.content_type,
            file_bytes=file_bytes,
            name=name,
            library_id=libraryId,
        )
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("/batch-actions", response_model=BatchActionResponse)
def batch_actions(
    body: BatchActionRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> BatchActionResponse:
    """批量操作文档：删除、重新解析、停用。"""
    try:
        result = batch_action(db, current_user, body.documentIds, body.action)
        return BatchActionResponse(**result)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get("/stats", response_model=LibraryStatsResponse)
def get_stats(
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryStatsResponse:
    """获取当前用户的文档库统计。"""
    try:
        return LibraryStatsResponse(**get_library_stats(db, current_user))
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get("/{document_id}", response_model=LibraryDocumentDetailDTO)
def get_document_detail(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryDocumentDetailDTO:
    """获取文档库文档详情。"""
    try:
        return get_library_document_detail(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.patch("/{document_id}", response_model=LibraryDocumentDTO)
def update_document(
    document_id: UUID,
    body: LibraryDocumentUpdateRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryDocumentDTO:
    """更新文档库文档的基本字段。"""
    try:
        return update_library_document(db, current_user, document_id, body.name, body.status)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.delete("/{document_id}")
def delete_document(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """删除文档库文档（软删除），级联清理所有知识库绑定。"""
    try:
        return delete_library_document(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get("/{document_id}/download")
def download_document(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> Response:
    """下载文档库文档原始文件。"""
    try:
        file_name, mime_type, content = get_library_document_source_download(db, current_user, document_id)
        encoded_name = quote(file_name)
        return Response(
            content=content,
            media_type=mime_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
                "Content-Length": str(len(content)),
            },
        )
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get("/{document_id}/parse-jobs", response_model=list[LibraryParseJobDTO])
def list_parse_jobs(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[LibraryParseJobDTO]:
    """获取文档的解析作业列表。"""
    try:
        return get_library_parse_jobs(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("/{document_id}/parse-retry")
def retry_parse(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """重新触发文档解析。"""
    try:
        return retry_library_parse(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get("/{document_id}/usage")
def get_document_usage_route(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """查询文档绑定的所有知识库。"""
    try:
        return get_document_usage(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get(
    "/{document_id}/text",
    response_model=LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse,
)
def get_document_text_route(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    mode: Literal["preview", "full", "chunks"] = Query(default="preview"),
) -> LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse:
    """获取文档文本内容，支持 preview/full/chunks 三种模式。"""
    try:
        return get_document_text(db, current_user, document_id, mode)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get("/{document_id}/versions", response_model=list[LibraryDocumentVersionDTO])
def list_versions(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[LibraryDocumentVersionDTO]:
    """列出文档的所有版本。"""
    try:
        return list_library_versions(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("/{document_id}/versions", response_model=LibraryVersionUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_version(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    file: UploadFile = File(...),
) -> LibraryVersionUploadResponse:
    """上传新版本文件。"""
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="EMPTY_FILE")
    try:
        return upload_library_version(
            session=db,
            current_user=current_user,
            document_id=document_id,
            file_name=file.filename or "uploaded-document",
            mime_type=file.content_type,
            file_bytes=file_bytes,
        )
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("/{document_id}/versions/{version_id}/activate", response_model=LibraryVersionActivateResponse)
def activate_version(
    document_id: UUID,
    version_id: UUID,
    body: LibraryVersionActivateRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryVersionActivateResponse:
    """切换文档的活跃版本。"""
    try:
        return activate_library_version(db, current_user, document_id, version_id, body.confirmImpact)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.delete("/{document_id}/versions/{version_id}")
def delete_version(
    document_id: UUID,
    version_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """删除指定版本。"""
    try:
        return delete_library_version(db, current_user, document_id, version_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable
