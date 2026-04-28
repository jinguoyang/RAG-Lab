from pydantic import BaseModel, Field


class AuditLogDTO(BaseModel):
    """审计日志 DTO，提供排障所需的操作者、资源和上下文字段。"""

    auditLogId: str
    actorId: str | None
    action: str
    resourceType: str
    resourceId: str
    kbId: str | None
    documentId: str | None
    detail: dict = Field(default_factory=dict)
    createdAt: str
