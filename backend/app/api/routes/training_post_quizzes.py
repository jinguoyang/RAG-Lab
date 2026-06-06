"""员工培训课后测验端点。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.app_runtime import _extract_bearer_token, _raise_runtime_error
from app.core.database import get_db_session
from app.schemas.training_post_quiz import (
    PostQuizDTO,
    PostQuizStartRequest,
    PostQuizSubmissionDTO,
    PostQuizSubmitRequest,
    SubjectiveGradingDTO,
    SubjectiveGradingRequest,
)
from app.services.training_agent_service import TrainingAgentConflictError, TrainingAgentNotFoundError, resolve_training_context
from app.services.training_grading_service import grade_subjective_answer_payload
from app.services.training_post_quiz_service import start_post_quiz, submit_post_quiz

router = APIRouter(prefix="/training/post-quizzes", tags=["training"])


@router.post("/subjective-grading", response_model=SubjectiveGradingDTO)
def grade_subjective_answer_for_external_question(
    request: SubjectiveGradingRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> SubjectiveGradingDTO:
    """按 ex-app 传入的题目内容进行主观题评分。"""
    credential = _extract_bearer_token(authorization)
    context = resolve_training_context(session, credential)
    result = grade_subjective_answer_payload(
        session,
        str(context.app_row["app_id"]),
        request.content,
        request.answer,
        request.rubric,
        request.evidenceChunkIds,
    )
    score = round(result.score / 20, 2)
    return SubjectiveGradingDTO(
        score=score,
        passed=score > 4,
        reason=result.reason,
        matchedCriteria=result.matchedCriteria,
        needsManualReview=result.needsManualReview,
    )


@router.post("", response_model=PostQuizDTO, status_code=status.HTTP_201_CREATED)
def create_training_post_quiz(
    request: PostQuizStartRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> PostQuizDTO:
    """文档学习完成后创建课后测验。"""
    credential = _extract_bearer_token(authorization)
    try:
        return start_post_quiz(session, credential, request)
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        _raise_runtime_error(exc)
        raise


@router.post("/{quiz_id}/submissions", response_model=PostQuizSubmissionDTO)
def submit_training_post_quiz(
    quiz_id: str,
    request: PostQuizSubmitRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> PostQuizSubmissionDTO:
    """提交课后测验答案。"""
    credential = _extract_bearer_token(authorization)
    try:
        return submit_post_quiz(session, credential, quiz_id, request)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        _raise_runtime_error(exc)
        raise
