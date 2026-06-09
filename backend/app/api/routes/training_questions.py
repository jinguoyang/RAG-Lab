"""员工培训题库平台侧端点。"""
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
from app.schemas.training_question import (
    QuestionAppealDTO,
    QuestionAppealRequest,
    QuestionAppealResolveRequest,
    QuestionDraftDTO,
    QuestionDraftRequest,
    QuestionReviewRequest,
    QuestionUpdateRequest,
)
from app.services.task_manager import TaskType, task_manager
from app.services.training_agent_service import TrainingAgentConflictError, TrainingAgentNotFoundError
from app.services.training_question_service import (
    create_question_appeal,
    create_question_drafts,
    publish_question,
    reject_question,
    resolve_question_appeal,
    review_question_with_credential,
    update_question,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training/questions", tags=["training"])


def _require_training_admin(current_user: CurrentUserResponse) -> None:
    """校验培训管理操作权限，当前仅平台管理员可审核培训题目。"""
    if current_user.user.platformRole != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED")


def _run_question_draft_task(task_id: str, credential: str, request: QuestionDraftRequest) -> None:
    """后台执行题目草稿生成任务。"""
    session: Session | None = None
    task_manager.start_task(task_id)
    try:
        from app.core.database import get_session_factory

        session = get_session_factory()()
        task_manager.append_log(task_id, "info", "开始生成题目草稿...")
        result = create_question_drafts(session, credential, request, task_id=task_id)
        task_manager.append_log(task_id, "info", "题目草稿生成完成")
        task_manager.complete_task(task_id, result=[item.model_dump() for item in result])
    except Exception as exc:
        logger.exception("题目草稿生成失败: %s", exc)
        task_manager.append_log(task_id, "error", f"生成失败: {exc}")
        task_manager.fail_task(task_id, str(exc))
    finally:
        if session is not None:
            session.close()


@router.post("/drafts", response_model=TaskSummaryDTO, status_code=status.HTTP_202_ACCEPTED)
def create_training_question_drafts(
    request: QuestionDraftRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> TaskSummaryDTO:
    """基于员工培训 Agent 和知识库证据生成题目草稿（异步后台执行）。"""
    credential = _extract_bearer_token(authorization)
    task = task_manager.create_task(
        task_type=TaskType.QUESTION_GENERATION,
        title=f"生成题目草稿: {request.jobTitle or request.planId}",
    )
    thread = threading.Thread(target=_run_question_draft_task, args=(task.id, credential, request), daemon=True)
    thread.start()
    return TaskSummaryDTO(**task.to_summary())


@router.post("/{question_id}/publish", response_model=QuestionDraftDTO)
def publish_training_question(
    question_id: str,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    session: Session = Depends(get_db_session),
) -> QuestionDraftDTO:
    """管理员发布题目。"""
    _require_training_admin(current_user)
    try:
        return publish_question(session, question_id, current_user.user.userId)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/{question_id}", response_model=QuestionDraftDTO)
def update_training_question(
    question_id: str,
    request: QuestionUpdateRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    session: Session = Depends(get_db_session),
) -> QuestionDraftDTO:
    """管理员修改题目草稿或已发布题目。"""
    _require_training_admin(current_user)
    try:
        return update_question(session, question_id, request, current_user.user.userId)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{question_id}/appeals", response_model=QuestionAppealDTO, status_code=status.HTTP_201_CREATED)
def create_training_question_appeal(
    question_id: str,
    request: QuestionAppealRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> QuestionAppealDTO:
    """学员上报题目异议。"""
    credential = _extract_bearer_token(authorization)
    try:
        return create_question_appeal(session, credential, question_id, request)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        _raise_runtime_error(exc)
        raise


@router.post("/{question_id}/review", response_model=QuestionDraftDTO)
def review_training_question_by_app_key(
    question_id: str,
    request: QuestionReviewRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> QuestionDraftDTO:
    """ex-app 管理员通过 App API Key 审核题目。"""
    credential = _extract_bearer_token(authorization)
    try:
        return review_question_with_credential(session, credential, question_id, request)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        _raise_runtime_error(exc)
        raise


@router.post("/appeals/{appeal_id}/resolve", response_model=QuestionAppealDTO)
def resolve_training_question_appeal(
    appeal_id: str,
    request: QuestionAppealResolveRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    session: Session = Depends(get_db_session),
) -> QuestionAppealDTO:
    """管理员处理题目异议。"""
    _require_training_admin(current_user)
    try:
        return resolve_question_appeal(session, appeal_id, request, current_user.user.userId)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{question_id}/reject", response_model=QuestionDraftDTO)
def reject_training_question(
    question_id: str,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    session: Session = Depends(get_db_session),
) -> QuestionDraftDTO:
    """管理员拒绝题目。"""
    _require_training_admin(current_user)
    try:
        return reject_question(session, question_id, current_user.user.userId)
    except TrainingAgentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrainingAgentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
