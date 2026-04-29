from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.observability import (
    BackupDrillCreateRequest,
    BackupDrillDTO,
    ErrorSummaryResponse,
    HealthPanelResponse,
    RuntimeMetricsResponse,
    SlowLinkDiagnosticsResponse,
)
from app.services.observability_service import (
    ObservabilityPermissionError,
    create_backup_drill,
    get_backup_drill,
    get_error_summary,
    get_health_panel,
    get_runtime_metrics,
    get_slow_link_diagnostics,
    list_backup_drills,
)

router = APIRouter(prefix="/knowledge-bases/{kb_id}", tags=["observability"])


def _raise_observability_error(exc: Exception) -> None:
    """将观测服务层权限异常映射为 HTTP 响应。"""
    if isinstance(exc, ObservabilityPermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    raise exc


@router.get("/observability/metrics", response_model=RuntimeMetricsResponse)
def read_runtime_metrics(
    kb_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> RuntimeMetricsResponse:
    """查询 QARun、IngestJob 和 Provider Trace 的关键运行指标。"""
    try:
        response = get_runtime_metrics(session, current_user, kb_id)
    except Exception as exc:
        _raise_observability_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/observability/slow-links", response_model=SlowLinkDiagnosticsResponse)
def read_slow_links(
    kb_id: UUID,
    threshold_ms: Annotated[int, Query(alias="thresholdMs", ge=1)] = 1500,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> SlowLinkDiagnosticsResponse:
    """查询慢链路诊断，定位检索、rerank、生成、权限裁剪或文档处理阶段。"""
    response = get_slow_link_diagnostics(session, current_user, kb_id, threshold_ms)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/observability/error-summary", response_model=ErrorSummaryResponse)
def read_error_summary(
    kb_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ErrorSummaryResponse:
    """查询 QARun、Provider Trace、IngestJob 和副本同步错误摘要。"""
    response = get_error_summary(session, current_user, kb_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/observability/health-panel", response_model=HealthPanelResponse)
def read_health_panel(
    kb_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> HealthPanelResponse:
    """返回组合健康面板，供运维或知识库负责人快速排障。"""
    response = get_health_panel(session, current_user, kb_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/backup-drills", response_model=list[BackupDrillDTO])
def read_backup_drills(
    kb_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[BackupDrillDTO]:
    """列出备份恢复演练记录。"""
    response = list_backup_drills(session, current_user, kb_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.post("/backup-drills", response_model=BackupDrillDTO, status_code=status.HTTP_201_CREATED)
def create_backup_drill_endpoint(
    kb_id: UUID,
    request: BackupDrillCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> BackupDrillDTO:
    """回填一次备份恢复演练结果。"""
    try:
        response = create_backup_drill(session, current_user, kb_id, request)
    except Exception as exc:
        _raise_observability_error(exc)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/backup-drills/{drill_id}", response_model=BackupDrillDTO)
def read_backup_drill(
    kb_id: UUID,
    drill_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> BackupDrillDTO:
    """读取单次备份恢复演练详情。"""
    response = get_backup_drill(session, current_user, kb_id, drill_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup drill not found.")
    return response
