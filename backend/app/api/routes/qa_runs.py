from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.qa_run import QARunCreateRequest, QARunCreateResponse, QARunDetailDTO, QARunStatusDTO
from app.schemas.qa_run import QARunListItemDTO
from app.services.qa_run_service import (
    QARunCreateConflict,
    create_qa_run,
    get_qa_run_detail,
    get_qa_run_status,
    list_qa_runs,
)

router = APIRouter(prefix="/knowledge-bases/{kb_id}/qa-runs", tags=["qa-runs"])


@router.get("", response_model=PageResponse[QARunListItemDTO])
def read_qa_runs(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[QARunListItemDTO]:
    """分页返回 QA 历史列表，供 P10 最小接入。"""
    response = list_qa_runs(session, current_user, kb_id, page_no, page_size, keyword)
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
    except QARunCreateConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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
