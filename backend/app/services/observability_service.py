from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, inspect, select
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.observability import (
    BackupDrillCreateRequest,
    BackupDrillDTO,
    CompensationStatusDTO,
    ErrorSummaryItemDTO,
    ErrorSummaryResponse,
    HealthPanelResponse,
    ProviderCallMetricDTO,
    RuntimeMetricBucketDTO,
    RuntimeMetricsResponse,
    SlowLinkDTO,
    SlowLinkDiagnosticsResponse,
)
from app.services.audit_service import write_audit_log
from app.services.permission_service import has_kb_permission
from app.tables import audit_logs, ingest_jobs, index_sync_jobs, knowledge_bases, qa_run_trace_steps, qa_runs

PROVIDER_STEP_KEYS = {
    "queryRewrite",
    "embedding",
    "denseRetrieval",
    "sparseRetrieval",
    "graphRetrieval",
    "rerank",
    "generation",
}
DEFAULT_SLOW_LINK_THRESHOLD_MS = 1500


class ObservabilityPermissionError(Exception):
    """当前用户缺少知识库观测或演练记录权限。"""


def _now() -> datetime:
    """统一生成带时区时间，保证接口响应可比对。"""
    return datetime.now(UTC)


def _table_exists(session: Session, table_name: str) -> bool:
    """兼容未完整迁移的本地库，可选观测维度缺表时降级为空数据。"""
    return inspect(session.get_bind()).has_table(table_name)


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库；不可见资源不暴露存在性。"""
    row = session.execute(
        select(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id, knowledge_bases.c.deleted_at.is_(None))
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    if not has_kb_permission(session, current_user, kb_id, "kb.view"):
        return None
    return row


def _require_observability_permission(session: Session, current_user: CurrentUserResponse, kb_id: UUID) -> None:
    """观测接口以 kb.view 为读取边界，避免无权限用户侧向探测资源存在。"""
    if not has_kb_permission(session, current_user, kb_id, "kb.view"):
        raise ObservabilityPermissionError


def _status_counts(rows: list[RowMapping]) -> dict[str, int]:
    """统计状态分布，空数据返回空字典而不是 None。"""
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["status"])
        counts[status] = counts.get(status, 0) + 1
    return counts


def _p95(values: list[int]) -> int | None:
    """计算轻量 p95，数据量很小时取排序后的近似值即可满足本地验收。"""
    if not values:
        return None
    sorted_values = sorted(values)
    index = min(len(sorted_values) - 1, int(len(sorted_values) * 0.95))
    return sorted_values[index]


def _avg(values: list[int]) -> int | None:
    """计算整数平均耗时。"""
    return int(sum(values) / len(values)) if values else None


def _duration_ms(row: RowMapping) -> int | None:
    """从 started_at/finished_at 计算作业耗时，缺失时返回 None。"""
    started_at = row.get("started_at")
    finished_at = row.get("finished_at")
    if started_at is None or finished_at is None:
        return None
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _metric_latency(row: RowMapping) -> int | None:
    """从 JSON metrics 中读取 latencyMs，兼容历史空指标。"""
    metrics = row.get("metrics") or {}
    if not isinstance(metrics, dict):
        return None
    value = metrics.get("latencyMs")
    return int(value) if isinstance(value, (int, float)) else None


def _runtime_bucket(name: str, rows: list[RowMapping], latencies: list[int]) -> RuntimeMetricBucketDTO:
    """构造 QARun 或 IngestJob 指标桶。"""
    return RuntimeMetricBucketDTO(
        name=name,
        total=len(rows),
        statusCounts=_status_counts(rows),
        avgLatencyMs=_avg(latencies),
        p95LatencyMs=_p95(latencies),
        errorCount=sum(1 for row in rows if row["status"] in {"failed", "partial", "cancelled"}),
    )


def get_runtime_metrics(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RuntimeMetricsResponse | None:
    """聚合 QARun、IngestJob 与 Provider Trace 指标，供 B-073 查询。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _require_observability_permission(session, current_user, kb_id)

    qa_rows = list(
        session.execute(
            select(
                qa_runs.c.run_id,
                qa_runs.c.status,
                qa_runs.c.metrics,
                qa_runs.c.started_at,
                qa_runs.c.finished_at,
                qa_runs.c.created_at,
            )
            .where(qa_runs.c.kb_id == kb_id)
            .order_by(qa_runs.c.created_at.desc())
        )
        .mappings()
    )
    ingest_rows = list(
        session.execute(
            select(
                ingest_jobs.c.job_id,
                ingest_jobs.c.job_type,
                ingest_jobs.c.status,
                ingest_jobs.c.stage,
                ingest_jobs.c.error_code,
                ingest_jobs.c.error_message,
                ingest_jobs.c.result_summary,
                ingest_jobs.c.started_at,
                ingest_jobs.c.finished_at,
                ingest_jobs.c.created_at,
            )
            .where(ingest_jobs.c.kb_id == kb_id)
            .order_by(ingest_jobs.c.created_at.desc())
        )
        .mappings()
    )
    trace_rows = list(
        session.execute(
            select(qa_run_trace_steps)
            .select_from(qa_run_trace_steps.join(qa_runs, qa_run_trace_steps.c.run_id == qa_runs.c.run_id))
            .where(qa_runs.c.kb_id == kb_id, qa_run_trace_steps.c.step_key.in_(PROVIDER_STEP_KEYS))
            .order_by(qa_run_trace_steps.c.created_at.desc())
        ).mappings()
    )

    qa_latencies = [value for row in qa_rows if (value := _metric_latency(row)) is not None]
    ingest_latencies = [value for row in ingest_rows if (value := _duration_ms(row)) is not None]
    provider_rows_by_step: dict[str, list[RowMapping]] = defaultdict(list)
    provider_latencies_by_step: dict[str, list[int]] = defaultdict(list)
    for row in trace_rows:
        step_key = row["step_key"]
        provider_rows_by_step[step_key].append(row)
        metrics = row["metrics"] or {}
        latency = metrics.get("latencyMs") if isinstance(metrics, dict) else None
        if isinstance(latency, (int, float)):
            provider_latencies_by_step[step_key].append(int(latency))

    provider_calls = [
        ProviderCallMetricDTO(
            stepKey=step_key,
            total=len(rows),
            statusCounts=_status_counts(rows),
            avgLatencyMs=_avg(provider_latencies_by_step[step_key]),
            errorCount=sum(1 for row in rows if row["status"] in {"failed", "partial"}),
        )
        for step_key, rows in sorted(provider_rows_by_step.items())
    ]

    return RuntimeMetricsResponse(
        kbId=str(kb_id),
        generatedAt=_now().isoformat(),
        qaRun=_runtime_bucket("qa_runs", qa_rows, qa_latencies),
        ingestJob=_runtime_bucket("ingest_jobs", ingest_rows, ingest_latencies),
        providerCalls=provider_calls,
    )


def get_slow_link_diagnostics(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    threshold_ms: int = DEFAULT_SLOW_LINK_THRESHOLD_MS,
) -> SlowLinkDiagnosticsResponse | None:
    """返回慢链路诊断，覆盖检索、rerank、generation、permissionFilter 和文档处理阶段。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    threshold_ms = max(1, threshold_ms)
    items: list[SlowLinkDTO] = []

    trace_rows = session.execute(
        select(qa_run_trace_steps)
        .select_from(qa_run_trace_steps.join(qa_runs, qa_run_trace_steps.c.run_id == qa_runs.c.run_id))
        .where(qa_runs.c.kb_id == kb_id)
    ).mappings()
    for row in trace_rows:
        metrics = row["metrics"] or {}
        latency = metrics.get("latencyMs") if isinstance(metrics, dict) else None
        if not isinstance(latency, (int, float)) or latency < threshold_ms:
            continue
        items.append(
            SlowLinkDTO(
                sourceType="qa_trace",
                resourceId=str(row["run_id"]),
                stage=row["step_key"],
                status=row["status"],
                latencyMs=int(latency),
                reason=f"{row['step_key']} 超过阈值 {threshold_ms}ms",
                createdAt=row["created_at"].isoformat(),
            )
        )

    for row in session.execute(select(ingest_jobs).where(ingest_jobs.c.kb_id == kb_id)).mappings():
        latency = _duration_ms(row)
        if latency is None or latency < threshold_ms:
            continue
        items.append(
            SlowLinkDTO(
                sourceType="ingest_job",
                resourceId=str(row["job_id"]),
                stage=row["stage"] or row["job_type"],
                status=row["status"],
                latencyMs=latency,
                reason=f"文档处理阶段超过阈值 {threshold_ms}ms",
                createdAt=row["created_at"].isoformat(),
            )
        )

    items.sort(key=lambda item: item.latencyMs, reverse=True)
    return SlowLinkDiagnosticsResponse(kbId=str(kb_id), thresholdMs=threshold_ms, items=items[:50])


def get_error_summary(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> ErrorSummaryResponse | None:
    """按错误码聚合 QARun Trace、IngestJob 和副本同步失败。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_error(source_type: str, code: str, message: str, resource_id: UUID, created_at: datetime) -> None:
        key = (source_type, code or "UNKNOWN", message or "")
        item = grouped.setdefault(
            key,
            {"count": 0, "latestAt": None, "resourceIds": []},
        )
        item["count"] += 1
        item["resourceIds"].append(str(resource_id))
        latest_at = item["latestAt"]
        if latest_at is None or created_at > latest_at:
            item["latestAt"] = created_at

    trace_rows = session.execute(
        select(qa_run_trace_steps)
        .select_from(qa_run_trace_steps.join(qa_runs, qa_run_trace_steps.c.run_id == qa_runs.c.run_id))
        .where(qa_runs.c.kb_id == kb_id, qa_run_trace_steps.c.status.in_(["failed", "partial"]))
    ).mappings()
    for row in trace_rows:
        add_error("provider_trace", row["error_code"] or row["step_key"], row["error_message"] or row["status"], row["run_id"], row["created_at"])

    for row in session.execute(select(ingest_jobs).where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.status == "failed")).mappings():
        add_error("ingest_job", row["error_code"] or "INGEST_FAILED", row["error_message"] or "Ingest job failed", row["job_id"], row["created_at"])

    if _table_exists(session, "index_sync_jobs"):
        for row in session.execute(select(index_sync_jobs).where(index_sync_jobs.c.kb_id == kb_id, index_sync_jobs.c.status == "failed")).mappings():
            add_error("index_sync_job", "INDEX_SYNC_FAILED", row["error_message"] or "Index sync failed", row["sync_job_id"], row["created_at"])

    items = [
        ErrorSummaryItemDTO(
            sourceType=source_type,
            errorCode=code,
            message=message,
            count=payload["count"],
            latestAt=payload["latestAt"].isoformat() if payload["latestAt"] else None,
            resourceIds=payload["resourceIds"][:20],
        )
        for (source_type, code, message), payload in grouped.items()
    ]
    items.sort(key=lambda item: (item.latestAt or "", item.count), reverse=True)
    return ErrorSummaryResponse(kbId=str(kb_id), items=items)


def _compensation_status(session: Session, kb_id: UUID) -> list[CompensationStatusDTO]:
    """读取失败作业与补偿作业关系，标记是否已存在重试或仍需处理。"""
    items: list[CompensationStatusDTO] = []
    failed_jobs = list(
        session.execute(
            select(ingest_jobs).where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.status.in_(["failed", "cancelled"]))
        ).mappings()
    )
    for job in failed_jobs:
        existing_retry = session.execute(
            select(ingest_jobs)
            .where(
                ingest_jobs.c.kb_id == kb_id,
                ingest_jobs.c.retry_of_job_id == job["job_id"],
                ingest_jobs.c.status.in_(["queued", "running", "success"]),
            )
            .limit(1)
        ).mappings().first()
        status_value = "compensated" if existing_retry else "pending"
        items.append(
            CompensationStatusDTO(
                sourceType="ingest_job",
                resourceId=str(job["job_id"]),
                status=job["status"],
                compensationStatus=status_value,
                detail={
                    "retryJobId": str(existing_retry["job_id"]) if existing_retry else None,
                    "errorMessage": job["error_message"],
                },
            )
        )

    if _table_exists(session, "index_sync_jobs"):
        for job in session.execute(select(index_sync_jobs).where(index_sync_jobs.c.kb_id == kb_id, index_sync_jobs.c.status == "failed")).mappings():
            items.append(
                CompensationStatusDTO(
                    sourceType="index_sync_job",
                    resourceId=str(job["sync_job_id"]),
                    status=job["status"],
                    compensationStatus="rebuild_required",
                    detail={"targetStore": job["target_store"], "errorMessage": job["error_message"]},
                )
            )
    return items[:50]


def get_health_panel(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> HealthPanelResponse | None:
    """组合健康面板数据，避免前端为 P05/P运维面板拼接多个诊断语义。"""
    metrics = get_runtime_metrics(session, current_user, kb_id)
    if metrics is None:
        return None
    slow_links = get_slow_link_diagnostics(session, current_user, kb_id).items
    error_summary = get_error_summary(session, current_user, kb_id).items
    compensation_status = _compensation_status(session, kb_id)
    status_value = "degraded" if error_summary or compensation_status else "ok"
    return HealthPanelResponse(
        kbId=str(kb_id),
        status=status_value,
        generatedAt=_now().isoformat(),
        metrics=metrics,
        slowLinks=slow_links,
        errorSummary=error_summary,
        compensationStatus=compensation_status,
    )


def _to_backup_drill_dto(row: RowMapping) -> BackupDrillDTO:
    """将 backup_restore.drill 审计日志转换为备份演练 DTO。"""
    detail = row["detail"] or {}
    return BackupDrillDTO(
        drillId=str(row["resource_id"]),
        kbId=str(row["kb_id"]),
        result=detail.get("result", "unknown"),
        restoredObjects=list(detail.get("restoredObjects") or []),
        residualRisks=list(detail.get("residualRisks") or []),
        evidence=detail.get("evidence") if isinstance(detail.get("evidence"), dict) else {},
        remark=detail.get("remark"),
        actorId=str(row["actor_id"]) if row["actor_id"] else None,
        auditLogId=str(row["audit_log_id"]),
        createdAt=row["created_at"].isoformat(),
    )


def create_backup_drill(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: BackupDrillCreateRequest,
) -> BackupDrillDTO | None:
    """记录备份恢复演练结果；真实备份动作由运维流程执行，本接口负责回填证据。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    if not has_kb_permission(session, current_user, kb_id, "kb.manage"):
        raise ObservabilityPermissionError

    drill_id = uuid4()
    detail = {
        "result": request.result,
        "restoredObjects": request.restoredObjects,
        "residualRisks": request.residualRisks,
        "evidence": request.evidence,
        "remark": request.remark,
    }
    try:
        audit_log_id = write_audit_log(
            session,
            current_user,
            "backup_restore.drill",
            "backup_drill",
            drill_id,
            kb_id=kb_id,
            detail=detail,
        )
        row = session.execute(select(audit_logs).where(audit_logs.c.audit_log_id == audit_log_id)).mappings().one()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _to_backup_drill_dto(row)


def list_backup_drills(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> list[BackupDrillDTO] | None:
    """列出某知识库的备份恢复演练记录。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    rows = session.execute(
        select(audit_logs)
        .where(
            audit_logs.c.kb_id == kb_id,
            audit_logs.c.action == "backup_restore.drill",
            audit_logs.c.resource_type == "backup_drill",
        )
        .order_by(audit_logs.c.created_at.desc())
    ).mappings()
    return [_to_backup_drill_dto(row) for row in rows]


def get_backup_drill(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    drill_id: UUID,
) -> BackupDrillDTO | None:
    """读取单条备份恢复演练记录。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    row = session.execute(
        select(audit_logs)
        .where(
            audit_logs.c.kb_id == kb_id,
            audit_logs.c.action == "backup_restore.drill",
            audit_logs.c.resource_type == "backup_drill",
            audit_logs.c.resource_id == drill_id,
        )
        .limit(1)
    ).mappings().first()
    return _to_backup_drill_dto(row) if row else None
