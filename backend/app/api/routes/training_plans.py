"""员工培训学习计划平台侧端点。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.app_runtime import _extract_bearer_token, _raise_runtime_error
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.training_plan import PlanDraftDTO, PlanDraftRequest
from app.services.training_agent_service import TrainingAgentConflictError, TrainingAgentNotFoundError
from app.services.training_plan_service import create_plan_draft, publish_plan, reject_plan

router = APIRouter(prefix="/training/plans", tags=["training"])


def _require_training_admin(current_user: CurrentUserResponse) -> None:
    """校验培训管理操作权限，当前仅平台管理员可审核培训内容。"""
    if current_user.user.platformRole != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED")


@router.post("/drafts", response_model=PlanDraftDTO, status_code=status.HTTP_201_CREATED)
def create_training_plan_draft(
    request: PlanDraftRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> PlanDraftDTO:
    """基于员工培训 Agent 和知识库证据生成学习计划草稿。"""
    credential = _extract_bearer_token(authorization)
    try:
        return create_plan_draft(session, credential, request)
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        _raise_runtime_error(exc)
        raise


@router.post("/{plan_id}/publish", response_model=PlanDraftDTO)
def publish_training_plan(
    plan_id: str,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    session: Session = Depends(get_db_session),
) -> PlanDraftDTO:
    """管理员发布学习计划。"""
    _require_training_admin(current_user)
    try:
        return publish_plan(session, plan_id, current_user.user.userId)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{plan_id}/reject", response_model=PlanDraftDTO)
def reject_training_plan(
    plan_id: str,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    session: Session = Depends(get_db_session),
) -> PlanDraftDTO:
    """管理员拒绝学习计划。"""
    _require_training_admin(current_user)
    try:
        return reject_plan(session, plan_id, current_user.user.userId)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
