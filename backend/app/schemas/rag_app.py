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
    # Sprint 42: KB status fields
    knowledgeBaseName: str | None = None
    knowledgeBaseStatus: str | None = None  # "active" | "disabled" | "deleted"
    scenarioType: str
    scenarioTemplateId: str
    scenarioConfig: dict[str, Any]
    publishChannels: dict[str, bool]
    embedSettings: dict[str, Any]


class RagAppCreateRequest(BaseModel):
    """创建 RAG App 请求；应用只保存 KB 和配置绑定，不复制 Pipeline。"""

    name: str = Field(min_length=1, max_length=128)
    kbId: UUID
    defaultConfigRevisionId: UUID | None = None
    outputPolicy: dict[str, Any] | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
    scenarioType: str | None = None
    scenarioTemplateId: str | None = None
    scenarioConfig: dict[str, Any] | None = None
    publishChannels: dict[str, bool] | None = None
    embedSettings: dict[str, Any] | None = None
    createRecommendedConfigRevision: bool = False

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
    scenarioType: str | None = None
    scenarioTemplateId: str | None = None
    scenarioConfig: dict[str, Any] | None = None
    publishChannels: dict[str, bool] | None = None
    embedSettings: dict[str, Any] | None = None

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
    keyType: str = "normal"
    managedBy: str = "user"
    displayName: str | None = None
    deletable: bool = True
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


class EmbeddedAppDeploymentDTO(BaseModel):
    """内置嵌入子程序部署状态，供后续运维监控页展示。"""

    deploymentId: str
    appId: str
    appType: str
    apiKeyId: str
    databaseName: str
    backendPort: int
    frontendPort: int
    backendPid: int | None = None
    frontendPid: int | None = None
    serviceName: str | None = None
    status: str
    healthStatus: str
    publicUrl: str | None = None
    lastStartAt: str | None = None
    lastStopAt: str | None = None
    lastHealthCheckAt: str | None = None
    errorMessage: str | None = None
    metadata: dict[str, Any]
    createdAt: str
    updatedAt: str


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
    runningInvocations: int
    successInvocations: int
    failedInvocations: int
    quotaExceededInvocations: int
    concurrencyExceededInvocations: int
    noEvidenceInvocations: int
    averageLatencyMs: int | None
    failureRate: float
    noEvidenceRate: float


class AppTrainingResultDTO(BaseModel):
    """单次培训答题结果摘要，来自 AppMessage metadata.trainingResult。"""

    messageId: str
    conversationId: str
    qaRunId: str | None = None
    score: float
    passed: bool
    passingScore: float | None = None
    createdAt: str


class AppTrainingReportDTO(BaseModel):
    """应用级培训结果聚合摘要，供 P13 展示和后续验收追溯。"""

    appId: str
    totalSubmissions: int
    passedSubmissions: int
    failedSubmissions: int
    averageScore: float | None = None
    passRate: float
    latestSubmittedAt: str | None = None
    recentResults: list[AppTrainingResultDTO]


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


class BatchDeleteRagAppsRequest(BaseModel):
    """批量删除 RAG App 请求；接受应用 ID 列表。"""

    app_ids: list[UUID] = Field(min_length=1, max_length=100)


class BatchDeleteRagAppsResponse(BaseModel):
    """批量删除 RAG App 响应；返回成功删除的数量。"""

    deleted_count: int
