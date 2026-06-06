"""员工培训课后测验 DTO。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.training_question import QuestionOptionDTO


class PostQuizStartRequest(BaseModel):
    """课后测验开始请求。"""

    model_config = ConfigDict(extra="forbid")

    sessionId: str = Field(min_length=1, max_length=36)
    endUserId: str = Field(min_length=1, max_length=128)
    documentId: str = Field(min_length=1, max_length=36)
    planId: str | None = Field(default=None, max_length=128)
    count: int | None = Field(default=None, ge=1, le=50)


class PostQuizQuestionDTO(BaseModel):
    """课后测验题目；不暴露标准答案。"""

    questionId: str
    questionType: str
    content: str
    options: list[QuestionOptionDTO] = Field(default_factory=list)
    rubric: dict[str, Any] | None = None


class PostQuizDTO(BaseModel):
    """课后测验快照。"""

    quizId: str
    sessionId: str
    appId: str
    endUserId: str
    documentId: str
    questions: list[PostQuizQuestionDTO]
    status: str
    createdAt: str


class PostQuizAnswerDTO(BaseModel):
    """单题提交答案。"""

    questionId: str
    answer: str


class PostQuizSubmitRequest(BaseModel):
    """课后测验提交请求。"""

    model_config = ConfigDict(extra="forbid")

    endUserId: str = Field(min_length=1, max_length=128)
    answers: list[PostQuizAnswerDTO] = Field(min_length=1)


class PostQuizResultItemDTO(BaseModel):
    """课后测验单题结果。"""

    questionId: str
    questionType: str
    score: float
    passed: bool
    isCorrect: bool | None = None
    explanation: str | None = None


class PostQuizSubmissionDTO(BaseModel):
    """课后测验提交结果。"""

    quizId: str
    score: float
    passed: bool
    results: list[PostQuizResultItemDTO]
    submittedAt: str


class SubjectiveGradingRequest(BaseModel):
    """主观题评分请求；题库真值由 ex-app 保存，平台只接收评分所需内容。"""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    rubric: dict[str, Any] | None = None
    evidenceChunkIds: list[str] = Field(default_factory=list)


class SubjectiveGradingDTO(BaseModel):
    """主观题评分响应，满分 5 分。"""

    score: float
    passed: bool
    reason: str
    matchedCriteria: list[str] = Field(default_factory=list)
    needsManualReview: bool = False
