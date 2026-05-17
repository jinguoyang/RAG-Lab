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


class AppRuntimeFeedbackRequest(BaseModel):
    """外部回答质量反馈；只允许回流到当前 App 的助手消息。"""

    feedbackStatus: str = Field(pattern="^(correct|partiallyCorrect|partially_correct|wrong|citationError|citation_error|noEvidence|no_evidence)$")
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
