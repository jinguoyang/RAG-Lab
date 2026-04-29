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


class AuditReportBucketDTO(BaseModel):
    """审计报表聚合桶。"""

    key: str
    count: int


class AuditReportResponse(BaseModel):
    """审计报表响应，支持按操作、资源和操作者聚合。"""

    total: int
    groupByAction: list[AuditReportBucketDTO]
    groupByResourceType: list[AuditReportBucketDTO]
    groupByActor: list[AuditReportBucketDTO]
    retentionPolicy: dict = Field(default_factory=dict)


class AuditExportResponse(BaseModel):
    """审计导出响应，当前返回可复制内容，不直接写文件。"""

    format: str
    fileName: str
    content: str
    total: int
