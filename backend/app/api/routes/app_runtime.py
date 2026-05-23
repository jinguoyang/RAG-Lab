from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.schemas.app_runtime import (
    AppRuntimeChatRequest,
    AppRuntimeChatResponse,
    AppRuntimeEmbedTokenRequest,
    AppRuntimeEmbedTokenResponse,
    AppRuntimeFeedbackRequest,
    AppRuntimeFeedbackResponse,
    AppRuntimeRetrieveRequest,
    AppRuntimeRetrieveResponse,
)
from app.services.app_runtime_service import (
    AppRuntimeAuthError,
    AppRuntimeConcurrencyExceededError,
    AppRuntimeConflictError,
    AppRuntimeNotFoundError,
    AppRuntimeQuotaExceededError,
    chat_with_app_runtime,
    create_app_runtime_embed_token,
    iter_chat_sse_events,
    retrieve_app_runtime_evidence,
    submit_app_runtime_feedback,
)
from app.services.qa_run_service import QARunCreateConflict

router = APIRouter(prefix="/app-runtime", tags=["app-runtime"])


def _extract_bearer_token(authorization: str | None) -> str:
    """解析 Bearer Token，避免把格式错误的 Authorization 传入服务层。"""
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="APP_API_KEY_INVALID")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="APP_API_KEY_INVALID")
    return token.strip()


def _raise_runtime_error(exc: Exception) -> None:
    """统一映射 Runtime 服务层错误，保持错误码稳定。"""
    if isinstance(exc, AppRuntimeAuthError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="APP_API_KEY_INVALID") from exc
    if isinstance(exc, AppRuntimeNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RESOURCE_NOT_FOUND") from exc
    if isinstance(exc, (AppRuntimeQuotaExceededError, AppRuntimeConcurrencyExceededError)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    if isinstance(exc, AppRuntimeConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, QARunCreateConflict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise exc


@router.post("/chat-messages", response_model=AppRuntimeChatResponse)
def create_app_runtime_chat_message(
    request: AppRuntimeChatRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> AppRuntimeChatResponse | StreamingResponse:
    """通过 App API Key 执行对话；streaming 以 SSE 兼容输出。"""
    api_key = _extract_bearer_token(authorization)
    try:
        response = chat_with_app_runtime(session, api_key, request)
    except Exception as exc:
        _raise_runtime_error(exc)
    if request.responseMode == "streaming":
        return StreamingResponse(iter_chat_sse_events(response), media_type="text/event-stream")
    return response


@router.post("/embed-tokens", response_model=AppRuntimeEmbedTokenResponse, status_code=status.HTTP_201_CREATED)
def create_embed_token(
    request: AppRuntimeEmbedTokenRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> AppRuntimeEmbedTokenResponse:
    """通过 App API Key 生成短期 Embed Token，嵌入页不接触长期 Key。"""
    api_key = _extract_bearer_token(authorization)
    try:
        return create_app_runtime_embed_token(session, api_key, request)
    except Exception as exc:
        _raise_runtime_error(exc)


@router.post("/retrieve", response_model=AppRuntimeRetrieveResponse)
def retrieve_evidence(
    request: AppRuntimeRetrieveRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> AppRuntimeRetrieveResponse:
    """只返回当前 App 所属知识库的授权证据摘要，不暴露内部 Trace。"""
    credential = _extract_bearer_token(authorization)
    try:
        return retrieve_app_runtime_evidence(session, credential, request)
    except Exception as exc:
        _raise_runtime_error(exc)


@router.post("/messages/{message_id}/feedback", response_model=AppRuntimeFeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_app_runtime_feedback(
    message_id: UUID,
    request: AppRuntimeFeedbackRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> AppRuntimeFeedbackResponse:
    """接收外部回答质量反馈，回流到 QARun 和可选 EvaluationSample。"""
    api_key = _extract_bearer_token(authorization)
    try:
        return submit_app_runtime_feedback(session, api_key, message_id, request)
    except Exception as exc:
        _raise_runtime_error(exc)
