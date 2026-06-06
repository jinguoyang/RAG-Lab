"""员工培训知识库文档查询端点。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.routes.app_runtime import _extract_bearer_token, _raise_runtime_error
from app.core.database import get_db_session
from app.schemas.training_document import TrainingDocumentDTO
from app.services.training_agent_service import TrainingAgentConflictError
from app.services.training_document_service import list_training_documents

router = APIRouter(prefix="/training/documents", tags=["training"])


@router.get("", response_model=list[TrainingDocumentDTO])
def list_training_kb_documents(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    query: str = Query(default="", max_length=256),
    category: str | None = Query(default=None, max_length=64),
    difficulty: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> list[TrainingDocumentDTO]:
    """查询当前员工培训 App 知识库中可加入学习计划的文档。"""
    credential = _extract_bearer_token(authorization)
    try:
        return list_training_documents(
            session,
            credential,
            query=query,
            category=category,
            difficulty=difficulty,
            limit=limit,
        )
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        _raise_runtime_error(exc)
        raise
