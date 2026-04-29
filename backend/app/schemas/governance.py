from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConfigReleaseRecordCreateRequest(BaseModel):
    """配置发布记录创建请求，用于复核变更说明和关联评估结果。"""

    changeSummary: str = Field(min_length=1, max_length=1000)
    linkedEvaluationRunId: UUID | None = None
    rollbackPlan: str | None = Field(default=None, max_length=1000)


class ConfigRollbackConfirmRequest(BaseModel):
    """配置回滚确认请求；只记录确认事实，不绕过正式激活流程。"""

    confirmImpact: bool
    targetRevisionId: UUID | None = None
    reason: str = Field(min_length=1, max_length=1000)


class ConfigReleaseRecordDTO(BaseModel):
    """配置发布与回滚记录 DTO。"""

    releaseRecordId: str
    configRevisionId: str
    action: str
    changeSummary: str
    linkedEvaluationRunId: str | None = None
    rollbackPlan: str | None = None
    rollbackConfirmed: bool
    rollbackTargetRevisionId: str | None = None
    actorId: str | None
    createdAt: str
    detail: dict[str, Any] = Field(default_factory=dict)
