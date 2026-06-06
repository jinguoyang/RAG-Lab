"""课后测验路由。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.training_post_quiz import (
    PostQuizDTO,
    PostQuizStartRequest,
    PostQuizSubmissionDTO,
    PostQuizSubmitRequest,
)
from app.services.training_post_quiz_service import (
    TrainingPostQuizConflictError,
    TrainingPostQuizNotFoundError,
    create_post_quiz,
    submit_post_quiz,
)

router = APIRouter(prefix="/training/post-quizzes", tags=["training-post-quizzes"])


def _raise_error(exc: Exception) -> None:
    if isinstance(exc, TrainingPostQuizNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, TrainingPostQuizConflictError):
        raise HTTPException(status_code=409, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=PostQuizDTO, status_code=status.HTTP_201_CREATED)
def create_post_quiz_endpoint(request: PostQuizStartRequest, session: Session = Depends(get_db)):
    try:
        return create_post_quiz(session, request)
    except Exception as exc:
        _raise_error(exc)
        raise


@router.post("/{quiz_id}/submissions", response_model=PostQuizSubmissionDTO)
def submit_post_quiz_endpoint(quiz_id: str, request: PostQuizSubmitRequest, session: Session = Depends(get_db)):
    try:
        return submit_post_quiz(session, quiz_id, request)
    except Exception as exc:
        _raise_error(exc)
        raise
