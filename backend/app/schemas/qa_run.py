from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QARunCreateRequest(BaseModel):
    """创建单次 QA 调试请求，临时覆盖只作用于本次运行。"""

    query: str = Field(min_length=1, max_length=4000)
    configRevisionId: UUID | None = None
    overrideParams: dict[str, Any] | None = None
    sourceRunId: UUID | None = None
    remark: str | None = Field(default=None, max_length=500)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """提交前裁剪空白，避免空问题进入运行记录。"""
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Query is required.")
        return stripped_value


class QARunCreateResponse(BaseModel):
    """创建 QARun 后返回轮询入口，保持异步接口契约。"""

    runId: str
    status: str
    kbId: str
    configRevisionId: str
    query: str
    createdAt: str
    statusUrl: str
    detailUrl: str


class QARunStatusDTO(BaseModel):
    """QARun 状态轮询响应，供前端控制加载和详情读取时机。"""

    runId: str
    status: str
    currentStage: str
    progress: int
    stageMessage: str
    startedAt: str | None
    finishedAt: str | None
    detailReady: bool


class QARunTraceStepDTO(BaseModel):
    """Executed Pipeline Trace 步骤摘要。"""

    stepKey: str
    status: str
    inputSummary: dict[str, Any]
    outputSummary: dict[str, Any]
    metrics: dict[str, Any]
    errorCode: str | None = None
    errorMessage: str | None = None


class QARunCandidateDTO(BaseModel):
    """检索候选摘要，正文不会在候选中直接暴露。"""

    candidateId: str
    chunkId: str | None
    sourceType: str
    rawScore: float | None
    rerankScore: float | None
    rankNo: int | None
    isAuthorized: bool
    dropReason: str | None
    metadata: dict[str, Any]


class QARunEvidenceDTO(BaseModel):
    """授权 Evidence 摘要，后续会与真实 Chunk 权限二次校验衔接。"""

    evidenceId: str
    chunkId: str
    candidateId: str | None
    contentSnapshot: str | None
    sourceSnapshot: dict[str, Any]
    redactionStatus: str


class QARunCitationDTO(BaseModel):
    """Citation 引用摘要，只能指向已授权 Evidence。"""

    citationId: str
    evidenceId: str
    label: str | None
    locationSnapshot: dict[str, Any]


class QARunDetailDTO(BaseModel):
    """QARun 详情响应，覆盖 P09 结果区和 P10 历史详情的最小字段。"""

    runId: str
    status: str
    kbId: str
    configRevisionId: str
    query: str
    rewrittenQuery: str | None
    answer: str | None
    retrievalDiagnostics: dict[str, Any]
    overrideSnapshot: dict[str, Any]
    feedbackStatus: str
    feedbackNote: str | None
    failureType: str | None
    candidates: list[QARunCandidateDTO]
    evidence: list[QARunEvidenceDTO]
    citations: list[QARunCitationDTO]
    trace: list[QARunTraceStepDTO]
    metrics: dict[str, Any]
    createdAt: str


class QARunListItemDTO(BaseModel):
    """QA 历史列表项，避免 P10 为列表读取完整 Trace 和 Evidence。"""

    runId: str
    kbId: str
    configRevisionId: str
    query: str
    status: str
    answer: str | None
    hasOverride: bool
    feedbackStatus: str
    feedbackNote: str | None = None
    failureType: str | None = None
    createdBy: str | None
    createdAt: str
    latencyMs: int | None = None


class QARunFeedbackUpdateRequest(BaseModel):
    """人工反馈更新请求，失败归因随 metrics 持久化。"""

    feedbackStatus: str
    failureType: str | None = Field(default=None, max_length=64)
    feedbackNote: str | None = Field(default=None, max_length=1000)


class QARunFeedbackResponse(BaseModel):
    """人工反馈更新结果。"""

    runId: str
    feedbackStatus: str
    failureType: str | None
    feedbackNote: str | None
    updatedAt: str


class QARunReplayContextDTO(BaseModel):
    """回放到 QA 调试页所需上下文。"""

    sourceRunId: str
    query: str
    configRevisionId: str
    overrideParams: dict[str, Any]
    suggestedMode: str
    warnings: list[str] = Field(default_factory=list)


class QARunCommentDTO(BaseModel):
    """QA Run 协作评论。"""

    commentId: str
    authorId: str
    content: str
    createdAt: str


class QARunCollaborationDTO(BaseModel):
    """QA Run 协作状态，覆盖分享、责任人、处理状态和评论。"""

    runId: str
    sharedWithSubjectKeys: list[str]
    ownerId: str | None
    handlingStatus: str
    comments: list[QARunCommentDTO]
    updatedAt: str | None = None


class QARunCollaborationUpdateRequest(BaseModel):
    """更新 QA Run 协作信息请求。"""

    sharedWithSubjectKeys: list[str] | None = None
    ownerId: UUID | None = None
    handlingStatus: str | None = Field(default=None, max_length=32)


class QARunCommentCreateRequest(BaseModel):
    """新增 QA Run 评论请求。"""

    content: str = Field(min_length=1, max_length=1000)


class EvaluationSampleCreateRequest(BaseModel):
    """从 QARun 生成评估样本的可选补充信息。"""

    expectedAnswer: str | None = None
    expectedEvidence: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class EvaluationSampleDTO(BaseModel):
    """评估样本 DTO，用于回归样本最小管理。"""

    sampleId: str
    kbId: str
    sourceRunId: str | None
    query: str
    expectedAnswer: str | None
    expectedEvidence: dict[str, Any]
    status: str
    metadata: dict[str, Any]
    createdAt: str
    updatedAt: str


class EvaluationRunCreateRequest(BaseModel):
    """创建评估运行请求，复用现有评估样本集进行批量回归。"""

    sampleIds: list[UUID] | None = None
    configRevisionId: UUID | None = None
    remark: str | None = Field(default=None, max_length=500)


class EvaluationRunDTO(BaseModel):
    """评估运行摘要。"""

    evaluationRunId: str
    kbId: str
    configRevisionId: str
    status: str
    totalSamples: int
    passedSamples: int
    failedSamples: int
    cancelledSamples: int
    passRate: float
    errorSummary: dict[str, int]
    remark: str | None
    createdBy: str | None
    createdAt: str
    startedAt: str | None
    finishedAt: str | None


class EvaluationResultDTO(BaseModel):
    """单条评估结果。"""

    evaluationResultId: str
    evaluationRunId: str
    sampleId: str
    sourceRunId: str | None
    status: str
    query: str
    expectedAnswer: str | None
    actualAnswer: str | None
    failureReason: str | None
    actualRunId: str | None
    metrics: dict[str, Any]
    createdAt: str
    updatedAt: str


class EvaluationRunDetailDTO(BaseModel):
    """评估运行详情。"""

    run: EvaluationRunDTO
    results: list[EvaluationResultDTO]


class EvaluationRunCancelResponse(BaseModel):
    """取消评估运行结果。"""

    evaluationRunId: str
    status: str
    cancelledAt: str


class EvaluationRunExportResponse(BaseModel):
    """评估运行导出响应。"""

    evaluationRunId: str
    format: str
    fileName: str
    content: str


class ConfigRevisionDiffItemDTO(BaseModel):
    """配置差异项摘要。"""

    path: str
    before: Any
    after: Any


class EvaluationRunConfigDiffDTO(BaseModel):
    """评估运行关联配置差异。"""

    evaluationRunId: str
    fromConfigRevisionId: str
    toConfigRevisionId: str
    diffItems: list[ConfigRevisionDiffItemDTO]


class EvaluationOptimizationDraftResponse(BaseModel):
    """失败样本生成配置优化草稿的结果。"""

    evaluationRunId: str
    configRevisionId: str
    remark: str
