"""学习计划路由。"""
from typing import Annotated
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.schemas.training_plan import (
    TrainingPlanDraftRequest,
    TrainingPlanReviewRequest,
    TrainingPlanDTO,
)
from app.services.training_plan_service import (
    TrainingPlanNotFoundError,
    TrainingPlanConflictError,
    create_plan_draft,
    list_plans,
    review_plan,
    get_plan,
)

router = APIRouter(prefix="/training/plans", tags=["training-plans"])


def _extract_user_id(authorization: str | None) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return "dev-user"


def _raise_error(exc: Exception) -> None:
    if isinstance(exc, TrainingPlanNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, TrainingPlanConflictError):
        raise HTTPException(status_code=409, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


@router.post("/drafts", response_model=TrainingPlanDTO, status_code=status.HTTP_201_CREATED)
def create_draft(
    request: TrainingPlanDraftRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
):
    try:
        user = SimpleNamespace(user_id=_extract_user_id(authorization))
        return create_plan_draft(session, user, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.get("", response_model=list[TrainingPlanDTO])
def read_plans(
    appId: str | None = None,
    session: Session = Depends(get_db_session),
):
    return list_plans(session, appId)


@router.get("/{plan_id}", response_model=TrainingPlanDTO)
def read_plan(plan_id: str, session: Session = Depends(get_db_session)):
    try:
        return get_plan(session, plan_id)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.post("/{plan_id}/review")
def review_plan_endpoint(
    plan_id: str,
    request: TrainingPlanReviewRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
):
    try:
        user = SimpleNamespace(user_id=_extract_user_id(authorization))
        return review_plan(session, user, plan_id, request.decision, request.notes)
    except Exception as exc:
        _raise_error(exc)
        raise
