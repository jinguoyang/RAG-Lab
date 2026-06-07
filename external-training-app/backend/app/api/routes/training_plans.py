"""学习计划路由。"""
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.training_plan import (
    TrainingPlanDraftRequest,
    TrainingPlanReviewRequest,
    TrainingPlanDTO,
    TrainingDocumentDTO,
    TrainingPlanSaveRequest,
    TrainingPlanUpdateRequest,
)
from app.services.training_plan_service import (
    TrainingPlanNotFoundError,
    TrainingPlanConflictError,
    create_plan_draft,
    list_training_documents,
    list_plans,
    review_plan,
    get_plan,
    save_plan,
    update_plan,
    delete_plan,
    generate_questions_for_plan,
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
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return create_plan_draft(session, user_id, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.get("", response_model=list[TrainingPlanDTO])
def read_plans(
    appId: str | None = None,
    session: Session = Depends(get_db),
):
    return list_plans(session, appId)


@router.get("/documents", response_model=list[TrainingDocumentDTO])
def read_training_documents(
    query: str = "",
    category: str | None = None,
    difficulty: str | None = None,
):
    try:
        return list_training_documents(query=query, category=category, difficulty=difficulty)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.get("/{plan_id}", response_model=TrainingPlanDTO)
def read_plan(plan_id: str, session: Session = Depends(get_db)):
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
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return review_plan(session, user_id, plan_id, request.decision, request.notes)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.post("/{plan_id}/save")
def save_plan_endpoint(
    plan_id: str,
    request: TrainingPlanSaveRequest,
    background_tasks: BackgroundTasks,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        result = save_plan(session, user_id, plan_id, request)
        background_tasks.add_task(generate_questions_for_plan, plan_id)
        return {**result, "message": "计划已保存，题目正在后台生成"}
    except Exception as exc:
        _raise_error(exc)
        raise


@router.patch("/{plan_id}")
def update_plan_endpoint(
    plan_id: str,
    request: TrainingPlanUpdateRequest,
    background_tasks: BackgroundTasks,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        result = update_plan(session, user_id, plan_id, request)
        if request.documents is not None:
            background_tasks.add_task(generate_questions_for_plan, plan_id)
        return result
    except Exception as exc:
        _raise_error(exc)
        raise


@router.delete("/{plan_id}")
def delete_plan_endpoint(
    plan_id: str,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return delete_plan(session, user_id, plan_id)
    except Exception as exc:
        _raise_error(exc)
        raise
