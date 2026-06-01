from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.rag_app import (
    AppConversationDetailDTO,
    AppInvocationDTO,
    AppInvocationStatsDTO,
    AppTrainingReportDTO,
    BatchDeleteRagAppsRequest,
    BatchDeleteRagAppsResponse,
    RagAppApiKeyCreateRequest,
    RagAppApiKeyCreateResponse,
    RagAppApiKeyDTO,
    RagAppCreateRequest,
    RagAppDTO,
    RagAppUpdateRequest,
)
from app.services.rag_app_service import (
    RagAppApiKeyNotFoundError,
    RagAppConflictError,
    RagAppNotFoundError,
    RagAppPermissionError,
    batch_delete_rag_apps,
    create_rag_app,
    create_rag_app_api_key,
    delete_rag_app,
    delete_rag_app_api_key,
    get_rag_app,
    get_rag_app_conversation_detail,
    get_rag_app_invocation_stats,
    get_rag_app_training_report,
    list_rag_app_api_keys,
    list_rag_app_invocations,
    list_rag_apps,
    update_rag_app,
)

router = APIRouter(prefix="/rag-apps", tags=["rag-apps"])


def _raise_rag_app_error(exc: Exception) -> None:
    """将 RAG App 服务层异常映射为现有 HTTPException 风格。"""
    if isinstance(exc, RagAppNotFoundError | RagAppApiKeyNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG app not found.") from exc
    if isinstance(exc, RagAppPermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if isinstance(exc, RagAppConflictError):
        detail = str(exc) or "RAG_APP_CONFLICT"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
    raise exc


@router.get("", response_model=PageResponse[RagAppDTO])
def read_rag_apps(
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    kb_id: Annotated[UUID | None, Query(alias="kbId")] = None,
    status_filter: Annotated[Literal["active", "disabled", "archived"] | None, Query(alias="status")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[RagAppDTO]:
    """分页返回当前用户可见的 RAG App。"""
    return list_rag_apps(session, current_user, page_no, page_size, keyword, kb_id, status_filter)


@router.post("", response_model=RagAppDTO, status_code=status.HTTP_201_CREATED)
def create_rag_app_endpoint(
    request: RagAppCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RagAppDTO:
    """创建 RAG App，绑定知识库和可选默认配置版本。"""
    try:
        return create_rag_app(session, current_user, request)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RAG app conflicts with existing data.") from exc
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.get("/{app_id}", response_model=RagAppDTO)
def read_rag_app(
    app_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RagAppDTO:
    """读取单个 RAG App 详情。"""
    try:
        return get_rag_app(session, current_user, app_id)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rag_app_endpoint(
    app_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    """逻辑删除 RAG App；历史调用和 QARun 保持只读可追溯。"""
    try:
        delete_rag_app(session, current_user, app_id)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.post("/batch-delete", response_model=BatchDeleteRagAppsResponse)
def batch_delete_rag_apps_endpoint(
    request: BatchDeleteRagAppsRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> BatchDeleteRagAppsResponse:
    """批量逻辑删除 RAG App；逐个校验权限并归档。"""
    try:
        return batch_delete_rag_apps(session, current_user, request.app_ids)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.get("/{app_id}/stats", response_model=AppInvocationStatsDTO)
def read_rag_app_stats(
    app_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AppInvocationStatsDTO:
    """读取应用级调用统计摘要。"""
    try:
        return get_rag_app_invocation_stats(session, current_user, app_id)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.get("/{app_id}/training-report", response_model=AppTrainingReportDTO)
def read_rag_app_training_report(
    app_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AppTrainingReportDTO:
    """读取员工培训助手的答题结果聚合摘要。"""
    try:
        return get_rag_app_training_report(session, current_user, app_id)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.patch("/{app_id}", response_model=RagAppDTO)
def update_rag_app_endpoint(
    app_id: UUID,
    request: RagAppUpdateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RagAppDTO:
    """更新 RAG App 基础信息、状态和默认配置绑定。"""
    try:
        return update_rag_app(session, current_user, app_id, request)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RAG app conflicts with existing data.") from exc
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.get("/{app_id}/api-keys", response_model=list[RagAppApiKeyDTO])
def read_rag_app_api_keys(
    app_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[RagAppApiKeyDTO]:
    """列出应用 API Key 摘要，永不返回明文。"""
    try:
        return list_rag_app_api_keys(session, current_user, app_id)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.post(
    "/{app_id}/api-keys",
    response_model=RagAppApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rag_app_api_key_endpoint(
    app_id: UUID,
    request: RagAppApiKeyCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RagAppApiKeyCreateResponse:
    """生成 App API Key；明文只在本响应返回一次。"""
    try:
        return create_rag_app_api_key(session, current_user, app_id, request)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RAG app API key conflicts with existing data.") from exc
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.delete("/{app_id}/api-keys/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rag_app_api_key_endpoint(
    app_id: UUID,
    api_key_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    """物理删除 App API Key；调用审计保留但解除 Key 关联。"""
    try:
        delete_rag_app_api_key(session, current_user, app_id, api_key_id)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.get("/{app_id}/invocations", response_model=PageResponse[AppInvocationDTO])
def read_rag_app_invocations(
    app_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    status_filter: Annotated[Literal["running", "success", "failed"] | None, Query(alias="status")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[AppInvocationDTO]:
    """分页查看应用调用审计摘要。"""
    try:
        return list_rag_app_invocations(session, current_user, app_id, page_no, page_size, status_filter)
    except Exception as exc:
        _raise_rag_app_error(exc)


@router.get("/{app_id}/conversations/{conversation_id}", response_model=AppConversationDetailDTO)
def read_rag_app_conversation(
    app_id: UUID,
    conversation_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AppConversationDetailDTO:
    """读取应用会话详情和消息时间线。"""
    try:
        return get_rag_app_conversation_detail(session, current_user, app_id, conversation_id)
    except Exception as exc:
        _raise_rag_app_error(exc)
