from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, or_, select
from sqlalchemy.orm import Session

from app.schemas.audit import AuditLogDTO
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
