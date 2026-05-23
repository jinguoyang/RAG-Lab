from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AppRuntimeChatRequest(BaseModel):
    """外部 Web 应用对话请求，支持 blocking 和兼容式 SSE streaming。"""

    query: str = Field(min_length=1, max_length=4000)
    conversationId: UUID | None = None
    endUserId: str | None = Field(default=None, max_length=128)
    inputs: dict[str, Any] | None = None
    responseMode: str = Field(default="blocking", pattern="^(blocking|streaming)$")

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """裁剪空白问题，避免空请求进入 QARun。"""
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Query is required.")
        return stripped_value


class AppRuntimeCitationDTO(BaseModel):
    """外部响应中的安全 Citation 摘要。"""

    citationId: str
    evidenceId: str
    label: str | None = None
    locationSnapshot: dict[str, Any]


class AppRuntimeChatResponse(BaseModel):
    """App Runtime blocking 对话响应，只暴露安全摘要。"""

    answer: str
    conversationId: str
    messageId: str
    runId: str
    citations: list[AppRuntimeCitationDTO]
    usage: dict[str, Any]
    metadata: dict[str, Any]


class AppRuntimeEmbedTokenRequest(BaseModel):
    """通过 App API Key 生成短期嵌入 Token。"""

    ttlSeconds: int = Field(default=900, ge=60, le=3600)
    allowedOrigin: str | None = Field(default=None, max_length=256)
    endUserId: str | None = Field(default=None, max_length=128)


class AppRuntimeEmbedTokenResponse(BaseModel):
    """短期嵌入 Token 响应，不包含 App API Key。"""

    embedToken: str
    appId: str
    expiresAt: str


class AppRuntimeRetrieveRequest(BaseModel):
    """只返回授权证据摘要的 Runtime 检索请求。"""

    query: str = Field(min_length=1, max_length=4000)
    topK: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """裁剪空白问题，避免空检索进入服务层。"""
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Query is required.")
        return stripped_value


class AppRuntimeRetrievedEvidenceDTO(BaseModel):
    """Runtime retrieve 返回的安全证据摘要。"""

    evidenceId: str
    chunkId: str
    label: str | None = None
    summary: str
    locationSnapshot: dict[str, Any]


class AppRuntimeRetrieveResponse(BaseModel):
    """Runtime retrieve 响应，不暴露内部 Trace 或完整 Chunk 正文。"""

    appId: str
    kbId: str
    evidences: list[AppRuntimeRetrievedEvidenceDTO]
    metadata: dict[str, Any]


class AppRuntimeStructuredRunRequest(BaseModel):
    """员工培训助手结构化运行请求，用于讲解和测验生成。"""

    action: str = Field(pattern="^(training_explain|training_quiz_generate)$")
    topic: str = Field(min_length=1, max_length=400)
    conversationId: UUID | None = None
    endUserId: str | None = Field(default=None, max_length=128)
    difficulty: str | None = Field(default=None, max_length=32)
    questionCount: int | None = Field(default=None, ge=1, le=10)
    inputs: dict[str, Any] | None = None

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        """裁剪培训主题，避免空主题进入 QARun。"""
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Topic is required.")
        return stripped_value


class AppRuntimeStructuredRunResponse(BaseModel):
    """员工培训助手结构化运行响应，始终保留 QARun 回溯信息。"""

    appId: str
    conversationId: str
    messageId: str
    runId: str
    action: str
    output: dict[str, Any]
    metadata: dict[str, Any]


class AppRuntimeTrainingAnswerDTO(BaseModel):
    """培训测验答题项。"""

    questionId: str
    answer: str


class AppRuntimeTrainingQuizSubmissionRequest(BaseModel):
    """培训测验提交请求。"""

    conversationId: UUID
    quizMessageId: UUID
    answers: list[AppRuntimeTrainingAnswerDTO] = Field(min_length=1)


class AppRuntimeTrainingQuestionResultDTO(BaseModel):
    """单题评分结果。"""

    questionId: str
    answer: str
    correctAnswer: str
    isCorrect: bool
    explanation: str


class AppRuntimeTrainingQuizSubmissionResponse(BaseModel):
    """培训测验评分结果，并返回记录训练结果的 AppMessage。"""

    conversationId: str
    messageId: str
    quizMessageId: str
    runId: str
    score: int
    passed: bool
    passingScore: int
    results: list[AppRuntimeTrainingQuestionResultDTO]
    metadata: dict[str, Any]


class AppRuntimeFeedbackRequest(BaseModel):
    """外部回答质量反馈；只允许回流到当前 App 的助手消息。"""

    feedbackStatus: str = Field(min_length=1, max_length=64)
    failureType: str | None = Field(default=None, max_length=64)
    feedbackNote: str | None = Field(default=None, max_length=1000)
    createEvaluationSample: bool = False
    expectedAnswer: str | None = None
    expectedEvidence: dict[str, Any] | None = None


class AppRuntimeFeedbackResponse(BaseModel):
    """外部反馈回流结果，不返回 Trace 或 Evidence 正文。"""

    messageId: str
    runId: str
    feedbackStatus: str
    failureType: str | None
    feedbackNote: str | None
    evaluationSampleId: str | None = None
    createdAt: str
