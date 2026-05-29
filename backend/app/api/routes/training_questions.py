"""员工培训题库平台侧端点。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.app_runtime import _extract_bearer_token, _raise_runtime_error
from app.core.database import get_db_session
from app.schemas.training_question import QuestionDraftDTO, QuestionDraftRequest
from app.services.training_agent_service import TrainingAgentConflictError
from app.services.training_question_service import create_question_drafts

router = APIRouter(prefix="/training/questions", tags=["training"])


@router.post("/drafts", response_model=list[QuestionDraftDTO], status_code=status.HTTP_201_CREATED)
def create_training_question_drafts(
    request: QuestionDraftRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> list[QuestionDraftDTO]:
    """基于员工培训 Agent 和知识库证据生成题目草稿。"""
    credential = _extract_bearer_token(authorization)
    try:
        return create_question_drafts(session, credential, request)
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        _raise_runtime_error(exc)
        raise
