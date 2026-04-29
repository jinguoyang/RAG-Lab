from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.config import ConfigRevisionDTO
from app.schemas.qa_run import (
    EvaluationOptimizationDraftResponse,
    EvaluationRunCancelResponse,
    EvaluationRunConfigDiffDTO,
    EvaluationRunCreateRequest,
    EvaluationRunDTO,
    EvaluationRunDetailDTO,
    EvaluationRunExportResponse,
    EvaluationSampleCreateRequest,
    EvaluationSampleDTO,
    QARunCreateRequest,
    QARunCreateResponse,
    QARunDetailDTO,
    QARunFeedbackResponse,
    QARunFeedbackUpdateRequest,
    QARunListItemDTO,
    QARunReplayContextDTO,
    QARunStatusDTO,
)
from app.services.qa_run_service import (
    QARunCreateConflict,
    QARunPermissionError,
    cancel_evaluation_run,
    create_evaluation_run,
    create_optimization_draft_from_evaluation_run,
    create_qa_run,
    create_config_revision_draft_from_qa_run,
    create_evaluation_sample_from_run,
    export_evaluation_run,
    get_evaluation_run_config_diff,
    get_evaluation_run_detail,
    get_qa_run_detail,
    get_qa_run_replay_context,
    get_qa_run_status,
    list_evaluation_runs,
    list_evaluation_samples,
    list_qa_runs,
    retry_evaluation_run,
    update_qa_run_feedback,
)
from app.services.knowledge_base_service import KnowledgeBaseDisabledError

router = APIRouter(prefix="/knowledge-bases/{kb_id}/qa-runs", tags=["qa-runs"])


@router.get("", response_model=PageResponse[QARunListItemDTO])
def read_qa_runs(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    feedback_status: Annotated[str | None, Query(alias="feedbackStatus")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[QARunListItemDTO]:
    """分页返回 QA 历史列表，供 P10 最小接入。"""
    try:
        response = list_qa_runs(
            session,
            current_user,
            kb_id,
            page_no,
            page_size,
            keyword,
            status_filter,
            feedback_status,
        )
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.post("", response_model=QARunCreateResponse, status_code=status.HTTP_201_CREATED)
def create_qa_run_endpoint(
    kb_id: UUID,
    request: QARunCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> QARunCreateResponse:
    """创建单次 QA Run；执行器在后续 backlog 接入。"""
    try:
        response = create_qa_run(session, current_user, kb_id, request)
    except KnowledgeBaseDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="KB_DISABLED: knowledge base is disabled.",
        ) from exc
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/evaluation-samples", response_model=PageResponse[EvaluationSampleDTO])
def read_evaluation_samples(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[EvaluationSampleDTO]:
    """分页返回评估样本列表。"""
    try:
        response = list_evaluation_samples(session, current_user, kb_id, page_no, page_size)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/{run_id}/status", response_model=QARunStatusDTO)
def read_qa_run_status(
    kb_id: UUID,
    run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> QARunStatusDTO:
    """返回 QARun 轮询状态；不可见资源按不存在处理。"""
    response = get_qa_run_status(session, current_user, kb_id, run_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA run not found.")
    return response


@router.get("/{run_id}", response_model=QARunDetailDTO)
def read_qa_run_detail(
    kb_id: UUID,
    run_id: UUID,
    include_trace: bool = Query(default=True, alias="includeTrace"),
    include_candidates: bool = Query(default=True, alias="includeCandidates"),
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> QARunDetailDTO:
    """返回 QARun 详情，Trace 与 Candidate 支持按需关闭。"""
    response = get_qa_run_detail(
        session=session,
        current_user=current_user,
        kb_id=kb_id,
        run_id=run_id,
        include_trace=include_trace,
        include_candidates=include_candidates,
    )
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA run not found.")
    return response


@router.patch("/{run_id}/feedback", response_model=QARunFeedbackResponse)
def update_feedback(
    kb_id: UUID,
    run_id: UUID,
    request: QARunFeedbackUpdateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> QARunFeedbackResponse:
    """更新 QARun 人工反馈和失败归因。"""
    try:
        response = update_qa_run_feedback(session, current_user, kb_id, run_id, request)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA run not found.")
    return response


@router.get("/{run_id}/replay-context", response_model=QARunReplayContextDTO)
def read_replay_context(
    kb_id: UUID,
    run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> QARunReplayContextDTO:
    """返回带上下文的回放参数，供 P09 创建新实验。"""
    try:
        response = get_qa_run_replay_context(session, current_user, kb_id, run_id)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA run not found.")
    return response


@router.post("/{run_id}/config-revision-draft", response_model=ConfigRevisionDTO, status_code=status.HTTP_201_CREATED)
def create_revision_draft_from_run(
    kb_id: UUID,
    run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConfigRevisionDTO:
    """从 QARun 使用的配置版本生成 Revision 草稿。"""
    try:
        response = create_config_revision_draft_from_qa_run(session, current_user, kb_id, run_id)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA run or config revision not found.")
    return response


@router.post("/{run_id}/evaluation-samples", response_model=EvaluationSampleDTO, status_code=status.HTTP_201_CREATED)
def create_evaluation_sample(
    kb_id: UUID,
    run_id: UUID,
    request: EvaluationSampleCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationSampleDTO:
    """从历史 QARun 生成评估样本。"""
    try:
        response = create_evaluation_sample_from_run(session, current_user, kb_id, run_id, request)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QA run not found.")
    return response


@router.get("/evaluation/runs", response_model=PageResponse[EvaluationRunDTO])
def read_evaluation_runs(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[EvaluationRunDTO]:
    """分页返回评估运行列表。"""
    try:
        response = list_evaluation_runs(session, current_user, kb_id, page_no, page_size)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.post("/evaluation/runs", response_model=EvaluationRunDTO, status_code=status.HTTP_201_CREATED)
def create_evaluation_run_endpoint(
    kb_id: UUID,
    request: EvaluationRunCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationRunDTO:
    """创建并执行评估运行。"""
    try:
        response = create_evaluation_run(session, current_user, kb_id, request)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/evaluation/runs/{evaluation_run_id}", response_model=EvaluationRunDetailDTO)
def read_evaluation_run_detail(
    kb_id: UUID,
    evaluation_run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationRunDetailDTO:
    """读取评估运行详情和样本结果。"""
    try:
        response = get_evaluation_run_detail(session, current_user, kb_id, evaluation_run_id)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found.")
    return response


@router.post("/evaluation/runs/{evaluation_run_id}/cancel", response_model=EvaluationRunCancelResponse)
def cancel_evaluation_run_endpoint(
    kb_id: UUID,
    evaluation_run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationRunCancelResponse:
    """取消评估运行。"""
    try:
        response = cancel_evaluation_run(session, current_user, kb_id, evaluation_run_id)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found.")
    return response


@router.post("/evaluation/runs/{evaluation_run_id}/retry", response_model=EvaluationRunDTO)
def retry_evaluation_run_endpoint(
    kb_id: UUID,
    evaluation_run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationRunDTO:
    """重试失败或取消的评估运行。"""
    try:
        response = retry_evaluation_run(session, current_user, kb_id, evaluation_run_id)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found.")
    return response


@router.get("/evaluation/runs/{evaluation_run_id}/export", response_model=EvaluationRunExportResponse)
def export_evaluation_run_endpoint(
    kb_id: UUID,
    evaluation_run_id: UUID,
    export_format: Annotated[str, Query(alias="format")] = "markdown",
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationRunExportResponse:
    """导出评估运行结果。"""
    try:
        response = export_evaluation_run(session, current_user, kb_id, evaluation_run_id, export_format)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found.")
    return response


@router.get("/evaluation/runs/{evaluation_run_id}/config-diff", response_model=EvaluationRunConfigDiffDTO)
def read_evaluation_run_config_diff(
    kb_id: UUID,
    evaluation_run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationRunConfigDiffDTO:
    """读取评估运行关联的配置差异。"""
    try:
        response = get_evaluation_run_config_diff(session, current_user, kb_id, evaluation_run_id)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found.")
    return response


@router.post(
    "/evaluation/runs/{evaluation_run_id}/optimization-draft",
    response_model=EvaluationOptimizationDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_optimization_draft(
    kb_id: UUID,
    evaluation_run_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> EvaluationOptimizationDraftResponse:
    """从评估运行失败样本生成可复核配置优化草稿。"""
    try:
        response = create_optimization_draft_from_evaluation_run(session, current_user, kb_id, evaluation_run_id)
    except QARunPermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation run not found.")
    return response

