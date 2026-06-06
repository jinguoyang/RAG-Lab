"""课后测验 schemas。"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PostQuizStartRequest(BaseModel):
    """课后测验开始请求。"""

    model_config = ConfigDict(extra="forbid")

    sessionId: str
    endUserId: str
    documentId: str
    planId: str | None = None
    count: int | None = Field(default=None, ge=1, le=50)


class PostQuizSubmitRequest(BaseModel):
    """课后测验提交请求。"""

    model_config = ConfigDict(extra="forbid")

    endUserId: str
    answers: list[dict[str, str]]


class PostQuizDTO(BaseModel):
    """平台课后测验响应。"""

    quizId: str
    sessionId: str
    appId: str
    endUserId: str
    documentId: str
    questions: list[dict[str, Any]]
    status: str
    createdAt: str


class PostQuizSubmissionDTO(BaseModel):
    """课后测验提交结果。"""

    quizId: str
    score: float
    passed: bool
    results: list[dict[str, Any]]
    submittedAt: str
