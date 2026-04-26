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
    createdBy: str | None
    createdAt: str
    latencyMs: int | None = None
