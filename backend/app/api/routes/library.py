"""文档库 API 路由。"""

import json
import logging
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse

logger = logging.getLogger(__name__)

# 文件上传大小限制：100MB
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024
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
    LibraryUploadParseOptions,
    LibraryParseJobDTO,
    LibraryParseRevisionCreateResponse,
    LibraryParseRevisionDTO,
    LibraryParseRevisionActivateRequest,
    LibraryParseRevisionActivateResponse,
    LibraryParsedChunksResponse,
    LibraryReparseRequest,
    LibraryStatsResponse,
    LibraryTextPreviewResponse,
    LibraryVersionActivateRequest,
    LibraryVersionActivateResponse,
    LibraryVersionUploadResponse,
)
from app.schemas.document import DeletionImpactAnalysis
from app.services.document_service import analyze_document_version_deletion_impact
from app.services.library_service import (
    LibraryDocumentDeleteBlockedError,
    LibraryDocumentDeleteRequiresConfirmationError,
    LibraryDocumentNotFoundError,
    LibraryPermissionError,
    LibraryVersionInUseError,
    LibraryVersionNotFoundError,
    activate_library_version,
    activate_library_parse_revision,
    analyze_document_deletion_impact,
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
    create_library_parse_revision_job,
    list_library_parse_revisions,
    list_library_documents,
    list_library_versions,
    retry_library_parse,
    update_library_document,
    upload_library_version,
)
from app.services.object_storage import ObjectStorageError
from app.tables import document_versions, documents

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
    if isinstance(exc, LibraryDocumentDeleteBlockedError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DOCUMENT_DELETE_BLOCKED", "blockingReasons": exc.blocking_reasons},
        ) from exc
    if isinstance(exc, LibraryDocumentDeleteRequiresConfirmationError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DOCUMENT_DELETE_REQUIRES_CONFIRMATION", "impactAnalysis": exc.impact_analysis},
        ) from exc
    if isinstance(exc, ObjectStorageError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STORAGE_ERROR: object storage operation failed.",
        ) from exc
    raise exc


def _parse_upload_options(raw: str | None) -> LibraryUploadParseOptions | None:
    """解析前端传来的 JSON 字符串 parseOptions。"""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return LibraryUploadParseOptions(**data)
    except Exception:
        logger.warning("Failed to parse parseOptions: %s", raw, exc_info=True)
        return None


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
    parseOptions: str | None = Form(default=None),
) -> LibraryDocumentUploadResponse:
    """上传文档到个人文档库。"""
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="EMPTY_FILE")
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB）",
        )
    parsed_options = _parse_upload_options(parseOptions)
    try:
        return create_library_upload(
            session=db,
            current_user=current_user,
            file_name=file.filename or "uploaded-document",
            mime_type=file.content_type,
            file_bytes=file_bytes,
            name=name,
            library_id=libraryId,
            parse_options=parsed_options,
        )
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("/batch-actions", response_model=BatchActionResponse)
def batch_actions(
    body: BatchActionRequest,
    strong_confirmation: bool = Query(default=False, alias="strongConfirmation"),
    current_user: CurrentUserResponse = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> BatchActionResponse:
    """批量操作文档：删除、重新解析、停用。"""
    try:
        result = batch_action(db, current_user, body.documentIds, body.action, strong_confirmation)
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


@router.get("/{document_id}/deletion-impact", response_model=DeletionImpactAnalysis)
def get_document_deletion_impact(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> DeletionImpactAnalysis:
    """分析删除文档的影响。"""
    try:
        result = analyze_document_deletion_impact(db, document_id)
        return DeletionImpactAnalysis(
            canDelete=result["can_delete"],
            blockingReasons=result["blocking_reasons"],
            isActiveVersion=False,  # 文档级别不适用
            activeBindingCount=result["active_binding_count"],
            pendingJobsCount=result["pending_jobs_count"],
            qaEvidenceCount=result["qa_evidence_count"],
            qaCitationCount=0,
            requiresStrongConfirmation=result["requires_strong_confirmation"],
        )
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.delete("/{document_id}")
def delete_document(
    document_id: UUID,
    strong_confirmation: bool = Query(default=False, alias="strongConfirmation"),
    current_user: CurrentUserResponse = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> dict:
    """删除文档库文档（软删除），级联清理所有知识库绑定。"""
    try:
        return delete_library_document(db, current_user, document_id, strong_confirmation)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get("/{document_id}/download")
def download_document(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    version_id: UUID | None = Query(default=None, alias="versionId"),
) -> Response:
    """下载文档库文档原始文件。"""
    try:
        file_name, mime_type, content = get_library_document_source_download(db, current_user, document_id, version_id)
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


@router.get("/{document_id}/preview")
def preview_document(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    version_id: UUID | None = Query(default=None, alias="versionId"),
) -> Response:
    """将 docx 文档转换为 PDF 返回，用于高保真预览。"""
    import os
    import tempfile

    from docx2pdf import convert as docx2pdf_convert

    from app.services import pdf_preview_cache

    try:
        # 1. 先做权限检查 + 下载源文件（内部会校验权限）
        file_name, _mime_type, content = get_library_document_source_download(
            db, current_user, document_id, version_id,
        )
        if not file_name.lower().endswith(".docx"):
            raise ValueError("仅支持 docx 文件预览")

        # 2. 解析版本 id，用于缓存键
        doc_row = db.execute(
            select(documents).where(documents.c.document_id == document_id)
        ).mappings().first()
        resolved_version_id = version_id or (doc_row["active_version_id"] if doc_row else None)
        if not resolved_version_id:
            raise LibraryDocumentNotFoundError

        # 3. 查缓存
        cached = pdf_preview_cache.get(document_id, resolved_version_id)
        if cached is not None:
            encoded_name = quote(file_name.rsplit(".", 1)[0] + ".pdf")
            return Response(
                content=cached,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
                    "Content-Length": str(len(cached)),
                    "X-Cache": "HIT",
                },
            )

        # 4. 缓存未命中，转换（COM 对象需在当前线程初始化）
        import pythoncom

        pythoncom.CoInitialize()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                docx_path = os.path.join(tmp_dir, file_name)
                pdf_path = os.path.join(tmp_dir, file_name.rsplit(".", 1)[0] + ".pdf")
                with open(docx_path, "wb") as f:
                    f.write(content)
                docx2pdf_convert(docx_path, pdf_path)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
        finally:
            pythoncom.CoUninitialize()

        # 5. 写入缓存
        pdf_preview_cache.put(document_id, resolved_version_id, pdf_bytes)

        encoded_name = quote(file_name.rsplit(".", 1)[0] + ".pdf")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename*=UTF-8''{encoded_name}",
                "Content-Length": str(len(pdf_bytes)),
                "X-Cache": "MISS",
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
    parse_revision_id: UUID | None = Query(default=None, alias="parseRevisionId"),
) -> LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse:
    """获取文档文本内容，支持 preview/full/chunks 三种模式。"""
    try:
        return get_document_text(db, current_user, document_id, mode, parse_revision_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.get(
    "/{document_id}/versions/{version_id}/parse-revisions",
    response_model=list[LibraryParseRevisionDTO],
)
def list_parse_revisions(
    document_id: UUID,
    version_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[LibraryParseRevisionDTO]:
    """列出源文件版本下的解析版本。"""
    try:
        return list_library_parse_revisions(db, current_user, document_id, version_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post(
    "/{document_id}/versions/{version_id}/parse-revisions",
    response_model=LibraryParseRevisionCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_parse_revision(
    document_id: UUID,
    version_id: UUID,
    body: LibraryReparseRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryParseRevisionCreateResponse:
    """基于指定源文件版本创建新的解析版本。"""
    try:
        result = create_library_parse_revision_job(
            db,
            current_user,
            document_id,
            version_id,
            parser_name=body.parserName,
            parser_version=body.parserVersion,
            content_format=body.contentFormat,
            parse_options=body.parseOptions,
            reason=body.reason,
        )
        return LibraryParseRevisionCreateResponse(**result)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.put(
    "/{document_id}/versions/{version_id}/active-parse-revision",
    response_model=LibraryParseRevisionActivateResponse,
)
def activate_parse_revision(
    document_id: UUID,
    version_id: UUID,
    body: LibraryParseRevisionActivateRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryParseRevisionActivateResponse:
    """切换文档版本的活动解析修订。"""
    try:
        return activate_library_parse_revision(
            db,
            current_user,
            document_id,
            version_id,
            UUID(body.parseRevisionId),
        )
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
    parseOptions: str | None = Form(default=None),
) -> LibraryVersionUploadResponse:
    """上传新版本文件。"""
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="EMPTY_FILE")
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB）",
        )
    parsed_options = _parse_upload_options(parseOptions)
    try:
        return upload_library_version(
            session=db,
            current_user=current_user,
            document_id=document_id,
            file_name=file.filename or "uploaded-document",
            mime_type=file.content_type,
            file_bytes=file_bytes,
            parse_options=parsed_options,
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


@router.get("/{document_id}/versions/{version_id}/deletion-impact", response_model=DeletionImpactAnalysis)
def get_deletion_impact(
    document_id: UUID,
    version_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> DeletionImpactAnalysis:
    """分析删除指定版本的影响。"""
    try:
        version = db.execute(
            select(document_versions.c.document_id).where(
                document_versions.c.version_id == version_id,
                document_versions.c.document_id == document_id,
            )
        ).scalar()
        if version is None:
            raise LibraryVersionNotFoundError()
        result = analyze_document_version_deletion_impact(db, version_id)
        return DeletionImpactAnalysis(
            canDelete=result["can_delete"],
            blockingReasons=result["blocking_reasons"],
            isActiveVersion=result["is_active_version"],
            activeBindingCount=result["active_binding_count"],
            pendingJobsCount=result["pending_jobs_count"],
            qaEvidenceCount=result["qa_evidence_count"],
            qaCitationCount=result["qa_citation_count"],
            requiresStrongConfirmation=result["requires_strong_confirmation"],
        )
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
