from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, or_, select
from sqlalchemy.orm import Session

from app.schemas.audit import AuditExportResponse, AuditLogDTO, AuditReportBucketDTO, AuditReportResponse
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.services.permission_service import has_kb_permission
from app.tables import audit_logs


def write_audit_log(
    session: Session,
    current_user: CurrentUserResponse,
    action: str,
    resource_type: str,
    resource_id: UUID,
    kb_id: UUID | None = None,
    document_id: UUID | None = None,
    detail: dict | None = None,
) -> UUID:
    """写入高风险操作审计日志，调用方负责在同一业务事务内提交。"""
    audit_log_id = uuid4()
    session.execute(
        insert(audit_logs).values(
            audit_log_id=audit_log_id,
            actor_id=UUID(current_user.user.userId),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            kb_id=kb_id,
            document_id=document_id,
            detail=detail or {},
        )
    )
    return audit_log_id


def _to_dto(row: RowMapping) -> AuditLogDTO:
    """将数据库审计行转换为接口层 camelCase DTO。"""
    return AuditLogDTO(
        auditLogId=str(row["audit_log_id"]),
        actorId=str(row["actor_id"]) if row["actor_id"] else None,
        action=row["action"],
        resourceType=row["resource_type"],
        resourceId=str(row["resource_id"]),
        kbId=str(row["kb_id"]) if row["kb_id"] else None,
        documentId=str(row["document_id"]) if row["document_id"] else None,
        detail=row["detail"] or {},
        createdAt=row["created_at"].isoformat(),
    )


def list_audit_logs(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int,
    page_size: int,
    kb_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    actor_id: UUID | None = None,
    keyword: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> PageResponse[AuditLogDTO]:
    """分页查询审计日志；非平台管理员仅能查询自己可见知识库范围内日志。"""
    is_platform_admin = current_user.user.platformRole == "platform_admin"
    if kb_id is None and not is_platform_admin:
        raise PermissionError("kbId is required for non platform admin audit queries.")
    if kb_id is not None and not is_platform_admin and not has_kb_permission(session, current_user, kb_id, "kb.view"):
        raise PermissionError("Current user cannot view audit logs for this knowledge base.")

    condition = audit_logs.c.audit_log_id.is_not(None)
    if kb_id is not None:
        condition = condition & (audit_logs.c.kb_id == kb_id)
    if action:
        condition = condition & (audit_logs.c.action == action)
    if resource_type:
        condition = condition & (audit_logs.c.resource_type == resource_type)
    if resource_id is not None:
        condition = condition & (audit_logs.c.resource_id == resource_id)
    if actor_id is not None:
        condition = condition & (audit_logs.c.actor_id == actor_id)
    if created_from is not None:
        condition = condition & (audit_logs.c.created_at >= created_from)
    if created_to is not None:
        condition = condition & (audit_logs.c.created_at <= created_to)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            audit_logs.c.action.ilike(keyword_pattern),
            audit_logs.c.resource_type.ilike(keyword_pattern),
        )

    total = session.execute(select(func.count()).select_from(audit_logs).where(condition)).scalar_one()
    rows = session.execute(
        select(audit_logs)
        .where(condition)
        .order_by(audit_logs.c.created_at.desc(), audit_logs.c.audit_log_id.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def _audit_condition(
    kb_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    actor_id: UUID | None = None,
    keyword: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
):
    """构造审计查询条件；报表、列表和导出共用同一套过滤语义。"""
    condition = audit_logs.c.audit_log_id.is_not(None)
    if kb_id is not None:
        condition = condition & (audit_logs.c.kb_id == kb_id)
    if action:
        condition = condition & (audit_logs.c.action == action)
    if resource_type:
        condition = condition & (audit_logs.c.resource_type == resource_type)
    if resource_id is not None:
        condition = condition & (audit_logs.c.resource_id == resource_id)
    if actor_id is not None:
        condition = condition & (audit_logs.c.actor_id == actor_id)
    if created_from is not None:
        condition = condition & (audit_logs.c.created_at >= created_from)
    if created_to is not None:
        condition = condition & (audit_logs.c.created_at <= created_to)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            audit_logs.c.action.ilike(keyword_pattern),
            audit_logs.c.resource_type.ilike(keyword_pattern),
        )
    return condition


def _assert_audit_visible(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID | None,
) -> None:
    """复用列表接口可见性规则，避免报表和导出绕过权限。"""
    is_platform_admin = current_user.user.platformRole == "platform_admin"
    if kb_id is None and not is_platform_admin:
        raise PermissionError("kbId is required for non platform admin audit queries.")
    if kb_id is not None and not is_platform_admin and not has_kb_permission(session, current_user, kb_id, "kb.view"):
        raise PermissionError("Current user cannot view audit logs for this knowledge base.")


def _count_buckets(session: Session, condition, column) -> list[AuditReportBucketDTO]:
    """按指定列统计审计桶，空值统一显示为 unknown。"""
    rows = session.execute(
        select(column.label("key"), func.count().label("count"))
        .select_from(audit_logs)
        .where(condition)
        .group_by(column)
        .order_by(func.count().desc())
        .limit(20)
    )
    return [AuditReportBucketDTO(key=str(key or "unknown"), count=count) for key, count in rows]


def build_audit_report(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    actor_id: UUID | None = None,
    keyword: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> AuditReportResponse:
    """生成审计报表摘要，覆盖操作、资源类型和操作者维度。"""
    _assert_audit_visible(session, current_user, kb_id)
    condition = _audit_condition(kb_id, action, resource_type, resource_id, actor_id, keyword, created_from, created_to)
    total = session.execute(select(func.count()).select_from(audit_logs).where(condition)).scalar_one()
    groupByAction = _count_buckets(session, condition, audit_logs.c.action)
    groupByResourceType = _count_buckets(session, condition, audit_logs.c.resource_type)
    groupByActor = _count_buckets(session, condition, audit_logs.c.actor_id)
    retentionPolicy = {
        "policy": "online_query",
        "defaultDays": 180,
        "archiveRecommendation": "按知识库和 createdAt 分区归档。",
    }
    return AuditReportResponse(
        total=total,
        groupByAction=groupByAction,
        groupByResourceType=groupByResourceType,
        groupByActor=groupByActor,
        retentionPolicy=retentionPolicy,
    )


def _csv_cell(value: object) -> str:
    """输出 CSV 单元格，保证逗号和引号不会破坏列结构。"""
    text = "" if value is None else str(value)
    return f'"{text.replace(chr(34), chr(34) + chr(34))}"'


def export_audit_logs(
    session: Session,
    current_user: CurrentUserResponse,
    export_format: str = "csv",
    kb_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    actor_id: UUID | None = None,
    keyword: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> AuditExportResponse:
    """导出审计日志，当前支持 csv 和 markdown 两种文本格式。"""
    _assert_audit_visible(session, current_user, kb_id)
    if export_format not in {"csv", "markdown"}:
        raise ValueError("Unsupported export format.")

    condition = _audit_condition(kb_id, action, resource_type, resource_id, actor_id, keyword, created_from, created_to)
    rows = list(
        session.execute(
            select(audit_logs)
            .where(condition)
            .order_by(audit_logs.c.created_at.desc(), audit_logs.c.audit_log_id.desc())
            .limit(1000)
        ).mappings()
    )
    dtos = [_to_dto(row) for row in rows]
    if export_format == "csv":
        header = "auditLogId,createdAt,actorId,action,resourceType,resourceId,kbId\n"
        content = header + "\n".join(
            ",".join(
                [
                    _csv_cell(item.auditLogId),
                    _csv_cell(item.createdAt),
                    _csv_cell(item.actorId),
                    _csv_cell(item.action),
                    _csv_cell(item.resourceType),
                    _csv_cell(item.resourceId),
                    _csv_cell(item.kbId),
                ]
            )
            for item in dtos
        )
        file_name = "audit-logs.csv"
    else:
        lines = ["# Audit Logs", ""]
        for item in dtos:
            lines.append(f"- `{item.createdAt}` {item.action} `{item.resourceType}:{item.resourceId}` actor={item.actorId}")
        content = "\n".join(lines)
        file_name = "audit-logs.md"

    return AuditExportResponse(format=export_format, fileName=file_name, content=content, total=len(dtos))
