from typing import Any

from pydantic import BaseModel, Field


class RuntimeMetricBucketDTO(BaseModel):
    """单类运行对象的指标汇总，用于健康面板和发布排障。"""

    name: str
    total: int
    statusCounts: dict[str, int]
    avgLatencyMs: int | None = None
    p95LatencyMs: int | None = None
    errorCount: int


class ProviderCallMetricDTO(BaseModel):
    """Provider 调用阶段指标，来自 QARun Trace。"""

    stepKey: str
    total: int
    statusCounts: dict[str, int]
    avgLatencyMs: int | None = None
    errorCount: int


class RuntimeMetricsResponse(BaseModel):
    """QARun、IngestJob 和 Provider 调用的核心运行指标。"""

    kbId: str
    generatedAt: str
    qaRun: RuntimeMetricBucketDTO
    ingestJob: RuntimeMetricBucketDTO
    providerCalls: list[ProviderCallMetricDTO]


class SlowLinkDTO(BaseModel):
    """慢链路诊断项，定位慢在检索、rerank、生成或文档处理阶段。"""

    sourceType: str
    resourceId: str
    stage: str
    status: str
    latencyMs: int
    reason: str
    createdAt: str


class SlowLinkDiagnosticsResponse(BaseModel):
    """慢链路诊断响应。"""

    kbId: str
    thresholdMs: int
    items: list[SlowLinkDTO]


class ErrorSummaryItemDTO(BaseModel):
    """错误摘要项，按来源、错误码和阶段聚合。"""

    sourceType: str
    errorCode: str
    message: str
    count: int
    latestAt: str | None
    resourceIds: list[str]


class ErrorSummaryResponse(BaseModel):
    """QARun、IngestJob 和 Provider Trace 的错误摘要。"""

    kbId: str
    items: list[ErrorSummaryItemDTO]


class CompensationStatusDTO(BaseModel):
    """补偿任务状态摘要，帮助识别重复执行和遗留失败。"""

    sourceType: str
    resourceId: str
    status: str
    compensationStatus: str
    detail: dict[str, Any] = Field(default_factory=dict)


class HealthPanelResponse(BaseModel):
    """健康面板接口，组合指标、错误、慢链路和补偿状态。"""

    kbId: str
    status: str
    generatedAt: str
    metrics: RuntimeMetricsResponse
    slowLinks: list[SlowLinkDTO]
    errorSummary: list[ErrorSummaryItemDTO]
    compensationStatus: list[CompensationStatusDTO]


class BackupDrillCreateRequest(BaseModel):
    """备份恢复演练结果回填请求。"""

    result: str = Field(pattern="^(success|partial|failed)$")
    restoredObjects: list[str] = Field(default_factory=list)
    residualRisks: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = Field(default=None, max_length=1000)


class BackupDrillDTO(BaseModel):
    """备份恢复演练记录。"""

    drillId: str
    kbId: str
    result: str
    restoredObjects: list[str]
    residualRisks: list[str]
    evidence: dict[str, Any]
    remark: str | None
    actorId: str | None
    auditLogId: str
    createdAt: str
