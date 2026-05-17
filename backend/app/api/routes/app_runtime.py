from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.schemas.app_runtime import AppRuntimeChatRequest, AppRuntimeChatResponse, AppRuntimeFeedbackRequest, AppRuntimeFeedbackResponse
from app.services.app_runtime_service import (
    AppRuntimeAuthError,
    AppRuntimeConflictError,
    AppRuntimeNotFoundError,
    AppRuntimeQuotaExceededError,
    chat_with_app_runtime,
    iter_chat_sse_events,
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
    if isinstance(exc, AppRuntimeQuotaExceededError):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="RAG_APP_QUOTA_EXCEEDED") from exc
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
