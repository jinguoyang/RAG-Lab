"""课堂 API 路由。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.schemas.training_classroom import (
    ClassroomEventResponse,
    ClassroomEventSubmitRequest,
    ClassroomSessionCreateRequest,
    ClassroomSessionDetailResponse,
    ClassroomSessionResponse,
)
from app.services.training_classroom_service import (
    ClassroomEventError,
    ClassroomSessionConflictError,
    ClassroomSessionNotFoundError,
    ClassroomTransitionError,
    create_classroom_session,
    get_classroom_session,
    submit_classroom_event,
)

router = APIRouter(prefix="/training/classroom", tags=["training-classroom"])


def _extract_user_id(authorization: str | None) -> str:
    """从 dev header 或 bearer token 提取用户标识。"""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return "dev-user"


def _raise_classroom_error(exc: Exception) -> None:
    """将服务层异常映射为 HTTP 状态码。"""
    if isinstance(exc, ClassroomSessionNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ClassroomSessionConflictError, ClassroomTransitionError)):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ClassroomEventError):
        raise HTTPException(status_code=422, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sessions", response_model=ClassroomSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    request: ClassroomSessionCreateRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> ClassroomSessionResponse:
    """创建课堂会话。"""
    try:
        user_id = _extract_user_id(authorization)
        from types import SimpleNamespace
        current_user = SimpleNamespace(user_id=user_id)
        return create_classroom_session(session, current_user, request)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise  # unreachable


@router.get("/sessions/{session_id}", response_model=ClassroomSessionDetailResponse)
def read_session(
    session_id: str,
    session: Session = Depends(get_db_session),
) -> ClassroomSessionDetailResponse:
    """获取课堂会话详情。"""
    try:
        return get_classroom_session(session, session_id)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise  # unreachable


@router.post("/sessions/{session_id}/events", response_model=ClassroomEventResponse, status_code=status.HTTP_201_CREATED)
def submit_event(
    session_id: str,
    request: ClassroomEventSubmitRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> ClassroomEventResponse:
    """提交课堂事件。"""
    try:
        user_id = _extract_user_id(authorization)
        from types import SimpleNamespace
        current_user = SimpleNamespace(user_id=user_id)
        return submit_classroom_event(session, current_user, session_id, request)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise  # unreachable
