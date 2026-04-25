from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PipelineValidationIssueDTO(BaseModel):
    """Pipeline 校验问题，供前端按字段和错误码展示反馈。"""

    code: str
    message: str
    field: str | None = None


class PipelineValidateRequest(BaseModel):
    """Pipeline 校验请求，基线版本仅用于后续差异提示。"""

    pipelineDefinition: dict[str, Any]
    baseRevisionId: str | None = None


class PipelineValidationResultDTO(BaseModel):
    """Pipeline 校验结果；保存接口会复用 normalizedPipelineDefinition。"""

    valid: bool
    errors: list[PipelineValidationIssueDTO]
    warnings: list[PipelineValidationIssueDTO]
    normalizedPipelineDefinition: dict[str, Any]


class ConfigRevisionCreateRequest(BaseModel):
    """保存配置版本请求；保存不等于激活。"""

    pipelineDefinition: dict[str, Any]
    sourceTemplateId: UUID | None = None
    remark: str | None = Field(default=None, max_length=500)


class ConfigRevisionActivateRequest(BaseModel):
    """激活配置版本请求，confirmImpact 必须为 true。"""

    confirmImpact: bool
    reason: str | None = Field(default=None, max_length=500)


class ConfigTemplateDTO(BaseModel):
    """配置模板摘要。"""

    templateId: str
    name: str
    description: str | None
    pipelineDefinition: dict[str, Any]
    defaultParams: dict[str, Any]
    status: str
    createdAt: str
    updatedAt: str


class ConfigRevisionDTO(BaseModel):
    """配置版本 DTO，接口层保持 camelCase 字段。"""

    configRevisionId: str
    kbId: str
    revisionNo: int
    sourceTemplateId: str | None
    status: str
    pipelineDefinition: dict[str, Any]
    validationSnapshot: dict[str, Any]
    remark: str | None
    activatedAt: str | None
    createdAt: str
    updatedAt: str


class ConfigRevisionCreateResponse(BaseModel):
    """保存 Revision 的最小响应。"""

    configRevisionId: str
    revisionNo: int
    status: str
    validationSnapshot: dict[str, Any]


class ConfigRevisionActivationResponse(BaseModel):
    """激活 Revision 后返回新旧 active 指针。"""

    activeConfigRevisionId: str
    previousActiveConfigRevisionId: str | None
    activatedAt: str
    auditLogId: str | None = None
