"""题库路由。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.training_question import (
    TrainingQuestionDraftRequest,
    TrainingQuestionReviewRequest,
    TrainingQuestionDTO,
    TrainingQuestionAppealRequest,
    TrainingQuestionAppealResolveRequest,
    TrainingQuestionUpdateRequest,
    TrainingQuestionCreateRequest,
)
from app.services.training_question_service import (
    TrainingQuestionNotFoundError,
    TrainingQuestionConflictError,
    create_question_drafts,
    create_question_appeal,
    list_questions,
    review_question,
    resolve_question_appeal,
    update_question,
    create_question,
    delete_question,
    count_questions_by_document,
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
    status: str | None = None,
    session: Session = Depends(get_db),
):
    return list_questions(session, planId, status)


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


@router.patch("/{question_id}")
def update_question_endpoint(
    question_id: str,
    request: TrainingQuestionUpdateRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return update_question(session, user_id, question_id, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.post("/{question_id}/appeals")
def create_question_appeal_endpoint(
    question_id: str,
    request: TrainingQuestionAppealRequest,
    session: Session = Depends(get_db),
):
    try:
        return create_question_appeal(session, question_id, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.post("/appeals/{appeal_id}/resolve")
def resolve_question_appeal_endpoint(
    appeal_id: str,
    request: TrainingQuestionAppealResolveRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return resolve_question_appeal(session, user_id, appeal_id, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.post("", response_model=TrainingQuestionDTO, status_code=status.HTTP_201_CREATED)
def create_question_endpoint(
    request: TrainingQuestionCreateRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db),
):
    try:
        user_id = _extract_user_id(authorization)
        return create_question(session, user_id, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.delete("/{question_id}")
def delete_question_endpoint(
    question_id: str,
    session: Session = Depends(get_db),
):
    try:
        return delete_question(session, question_id)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.get("/count-by-document")
def count_by_document_endpoint(
    planId: str = "",
    session: Session = Depends(get_db),
):
    if not planId:
        raise HTTPException(status_code=400, detail="planId 参数必填")
    return count_questions_by_document(session, planId)
