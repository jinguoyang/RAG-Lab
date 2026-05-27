"""题库路由。"""
from typing import Annotated
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.training_question import (
    TrainingQuestionDraftRequest,
    TrainingQuestionReviewRequest,
    TrainingQuestionDTO,
)
from app.services.training_question_service import (
    TrainingQuestionNotFoundError,
    TrainingQuestionConflictError,
    create_question_drafts,
    list_questions,
    review_question,
)

router = APIRouter(prefix="/training/questions", tags=["training-questions"])


def _extract_user_id(authorization: str | None) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return "dev-user"


def _raise_error(exc: Exception) -> None:
    if isinstance(exc, TrainingQuestionNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, TrainingQuestionConflictError):
        raise HTTPException(status_code=409, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


@router.post("/drafts", response_model=list[TrainingQuestionDTO], status_code=status.HTTP_201_CREATED)
def create_drafts(
    request: TrainingQuestionDraftRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return create_question_drafts(session, user_id, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.get("", response_model=list[TrainingQuestionDTO])
def read_questions(
    planId: str | None = None,
    session: Session = Depends(get_db),
):
    return list_questions(session, planId)


@router.post("/{question_id}/review")
def review_question_endpoint(
    question_id: str,
    request: TrainingQuestionReviewRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return review_question(session, user_id, question_id, request.decision)
    except Exception as exc:
        _raise_error(exc)
        raise
