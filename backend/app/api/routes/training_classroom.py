"""员工培训课堂 Agent 平台侧端点。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.app_runtime import _extract_bearer_token, _raise_runtime_error
from app.core.database import get_db_session
from app.schemas.training_classroom import (
    ClassroomEventResponse,
    ClassroomEventSubmitRequest,
    ClassroomSessionCreateRequest,
    ClassroomSessionDetailResponse,
    ClassroomSessionResponse,
)
from app.services.training_agent_service import TrainingAgentConflictError, TrainingAgentNotFoundError
from app.services.training_classroom_service import (
    ClassroomEventError,
    ClassroomTransitionError,
    create_classroom_session,
    get_classroom_session,
    submit_classroom_event,
)
from app.services.agent_runtime.runtime_facade import (
    RuntimeVersion,
    resolve_runtime_version,
    submit_training_classroom_runtime_event,
)

router = APIRouter(prefix="/training/classroom", tags=["training"])


def _raise_training_classroom_error(exc: Exception) -> None:
    """统一映射课堂 Agent 服务错误。"""
    if isinstance(exc, TrainingAgentNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, (TrainingAgentConflictError, ClassroomTransitionError)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, ClassroomEventError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    _raise_runtime_error(exc)


@router.post("/sessions", response_model=ClassroomSessionResponse, status_code=status.HTTP_201_CREATED)
def create_training_classroom_session(
    request: ClassroomSessionCreateRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> ClassroomSessionResponse:
    """创建员工培训课堂会话。"""
    credential = _extract_bearer_token(authorization)
    try:
        return create_classroom_session(session, credential, request)
    except Exception as exc:
        _raise_training_classroom_error(exc)
        raise


@router.get("/sessions/{session_id}", response_model=ClassroomSessionDetailResponse)
def read_training_classroom_session(
    session_id: str,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> ClassroomSessionDetailResponse:
    """读取员工培训课堂会话。"""
    credential = _extract_bearer_token(authorization)
    try:
        return get_classroom_session(session, session_id, credential)
    except Exception as exc:
        _raise_training_classroom_error(exc)
        raise


@router.post("/sessions/{session_id}/events", response_model=ClassroomEventResponse, status_code=status.HTTP_201_CREATED)
def submit_training_classroom_event(
    session_id: str,
    request: ClassroomEventSubmitRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> ClassroomEventResponse:
    """提交课堂事件，并返回结构化 Agent 输出。"""
    credential = _extract_bearer_token(authorization)
    try:
        # 读取会话的 runtime_version，委托给 facade 分流
        from app.tables import training_classroom_sessions
        from sqlalchemy import select

        row = session.execute(
            select(training_classroom_sessions.c.runtime_version)
            .where(training_classroom_sessions.c.session_id == session_id)
            .limit(1)
        ).scalar()
        rt_version = resolve_runtime_version(row)
        return submit_training_classroom_runtime_event(session, credential, session_id, request, rt_version)
    except Exception as exc:
        _raise_training_classroom_error(exc)
        raise
