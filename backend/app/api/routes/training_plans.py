"""员工培训学习计划平台侧端点。"""
from __future__ import annotations

import logging
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.app_runtime import _extract_bearer_token, _raise_runtime_error
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.task import TaskSummaryDTO
from app.schemas.training_plan import PlanDraftDTO, PlanDraftRequest
from app.services.task_manager import TaskType, task_manager
from app.services.training_agent_service import TrainingAgentConflictError, TrainingAgentNotFoundError
from app.services.training_plan_service import create_plan_draft, publish_plan, reject_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training/plans", tags=["training"])


def _require_training_admin(current_user: CurrentUserResponse) -> None:
    """校验培训管理操作权限，当前仅平台管理员可审核培训内容。"""
    if current_user.user.platformRole != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED")


def _run_plan_draft_task(task_id: str, credential: str, request: PlanDraftRequest) -> None:
    """后台执行学习计划生成任务。"""
    session: Session | None = None
    task_manager.start_task(task_id)
    try:
        from app.core.database import get_session_factory

        session = get_session_factory()()
        task_manager.append_log(task_id, "info", "开始生成学习计划...")
        result = create_plan_draft(session, credential, request, task_id=task_id)
        task_manager.append_log(task_id, "info", "学习计划生成完成")
        task_manager.complete_task(task_id, result=result.model_dump())
    except Exception as exc:
        logger.exception("学习计划生成失败: %s", exc)
        task_manager.append_log(task_id, "error", f"生成失败: {exc}")
        task_manager.fail_task(task_id, str(exc))
    finally:
        if session is not None:
            session.close()


@router.post("/drafts", response_model=TaskSummaryDTO, status_code=status.HTTP_202_ACCEPTED)
def create_training_plan_draft(
    request: PlanDraftRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TaskSummaryDTO:
    """基于员工培训 Agent 和知识库证据生成学习计划草稿（异步后台执行）。"""
    credential = _extract_bearer_token(authorization)
    task = task_manager.create_task(
        task_type=TaskType.PLAN_GENERATION,
        title=f"生成学习计划: {request.jobTitle}",
    )
    thread = threading.Thread(target=_run_plan_draft_task, args=(task.id, credential, request), daemon=True)
    thread.start()
    return TaskSummaryDTO(**task.to_summary())


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
