"""课堂路由。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
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

router = APIRouter(prefix="/classroom", tags=["classroom"])


def _extract_user_id(authorization: str | None) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return "dev-user"


def _raise_classroom_error(exc: Exception) -> None:
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
    session: Session = Depends(get_db),
) -> ClassroomSessionResponse:
    try:
        user_id = _extract_user_id(authorization)
        return create_classroom_session(session, user_id, request)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise


@router.get("/sessions/{session_id}", response_model=ClassroomSessionDetailResponse)
def read_session(
    session_id: str,
    session: Session = Depends(get_db),
) -> ClassroomSessionDetailResponse:
    try:
        return get_classroom_session(session, session_id)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise


@router.post("/sessions/{session_id}/events", response_model=ClassroomEventResponse, status_code=status.HTTP_201_CREATED)
def submit_event(
    session_id: str,
    request: ClassroomEventSubmitRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
) -> ClassroomEventResponse:
    try:
        user_id = _extract_user_id(authorization)
        return submit_classroom_event(session, user_id, session_id, request)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise
