from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RagAppDTO(BaseModel):
    """RAG App 管理端摘要，接口层统一使用 camelCase 字段。"""

    appId: str
    kbId: str
    defaultConfigRevisionId: str | None = None
    name: str
    description: str | None = None
    status: str
    outputPolicy: dict[str, Any]
    metadata: dict[str, Any]
    createdAt: str
    updatedAt: str


class RagAppCreateRequest(BaseModel):
    """创建 RAG App 请求；应用只保存 KB 和配置绑定，不复制 Pipeline。"""

    name: str = Field(min_length=1, max_length=128)
    kbId: UUID
    defaultConfigRevisionId: UUID | None = None
    outputPolicy: dict[str, Any] | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """写入前裁剪名称，避免空白应用名进入管理列表。"""
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("RAG app name is required.")
        return stripped_value


class RagAppUpdateRequest(BaseModel):
    """更新 RAG App 基础信息；未传字段保持原值不变。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    defaultConfigRevisionId: UUID | None = None
    outputPolicy: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    status: str | None = Field(default=None, pattern="^(active|disabled|archived)$")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """更新名称时同样裁剪空白。"""
        if value is None:
            return value
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("RAG app name is required.")
        return stripped_value


class RagAppApiKeyDTO(BaseModel):
    """App API Key 摘要；列表和详情永远不返回明文。"""

    apiKeyId: str
    appId: str
    keyPrefix: str
    status: str
    expiresAt: str | None = None
    lastUsedAt: str | None = None
    createdAt: str
    revokedAt: str | None = None


class RagAppApiKeyCreateRequest(BaseModel):
    """生成 App API Key 请求，明文只在创建响应中返回一次。"""

    expiresAt: datetime | None = None


class RagAppApiKeyCreateResponse(BaseModel):
    """生成 App API Key 响应，包含一次性明文。"""

    apiKey: str
    item: RagAppApiKeyDTO


class RagAppApiKeyRevokeResponse(BaseModel):
    """禁用 App API Key 响应。"""

    apiKeyId: str
    status: str
    revokedAt: str


class AppInvocationDTO(BaseModel):
    """App Runtime 调用审计摘要，供管理端列表展示。"""

    invocationId: str
    appId: str
    apiKeyId: str | None = None
    conversationId: str | None = None
    messageId: str | None = None
    qaRunId: str | None = None
    status: str
    errorCode: str | None = None
    latencyMs: int | None = None
    requestSummary: dict[str, Any]
    responseSummary: dict[str, Any]
    createdAt: str


class AppInvocationStatsDTO(BaseModel):
    """应用维度调用统计摘要，用于 P13 或观测模块展示。"""

    appId: str
    totalInvocations: int
    successInvocations: int
    failedInvocations: int
    quotaExceededInvocations: int
    noEvidenceInvocations: int
    averageLatencyMs: int | None
    failureRate: float
    noEvidenceRate: float


class AppMessageDTO(BaseModel):
    """App Conversation 下的单条消息，只读用于管理端追溯。"""

    messageId: str
    conversationId: str
    role: str
    content: str
    qaRunId: str | None = None
    status: str
    metadata: dict[str, Any]
    createdAt: str


class AppConversationDetailDTO(BaseModel):
    """App Conversation 详情，包含按时间排序的消息列表。"""

    conversationId: str
    appId: str
    endUserId: str | None = None
    status: str
    metadata: dict[str, Any]
    createdAt: str
    updatedAt: str
    messages: list[AppMessageDTO]
