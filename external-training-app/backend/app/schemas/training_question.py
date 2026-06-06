"""题库 schemas。"""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TrainingQuestionDraftRequest(BaseModel):
    """生成题库草稿请求。"""
    model_config = ConfigDict(extra="forbid")

    planId: str = Field(min_length=1, max_length=36)
    jobTitle: str = ""
    abilityGroups: list[str] = Field(default_factory=list)
    count: int | None = Field(default=None, ge=1, le=50)
    documentIds: list[str] = Field(default_factory=list)


class TrainingQuestionReviewRequest(BaseModel):
    """审核题目请求。"""
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""


class TrainingQuestionDTO(BaseModel):
    """题目 DTO。"""
    questionId: str
    planId: str
    appId: str
    documentId: str | None = None
    questionType: str
    category: str
    content: str
    options: list[Any] | None = None
    correctAnswer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None
    evidenceChunkIds: list[str] = Field(default_factory=list)
    status: str
    createdAt: str
    updatedAt: str | None = None


class TrainingQuestionUpdateRequest(BaseModel):
    """题目修改请求。"""

    content: str | None = Field(default=None, min_length=1)
    options: list[Any] | None = None
    correctAnswer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None
    evidenceChunkIds: list[str] | None = None


class TrainingQuestionCreateRequest(BaseModel):
    """管理员手动录入题目请求。"""
    model_config = ConfigDict(extra="forbid")

    planId: str = Field(min_length=1, max_length=36)
    documentId: str | None = None
    questionType: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1)
    options: list[Any] | None = None
    correctAnswer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None


class TrainingQuestionAppealRequest(BaseModel):
    """题目异议上报请求。"""

    endUserId: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)
    answerRecordId: str | None = None


class TrainingQuestionAppealDTO(BaseModel):
    """题目异议 DTO。"""

    appealId: str
    questionId: str
    endUserId: str
    reason: str
    answerRecordId: str | None = None
    status: str
    resolution: str | None = None
    createdAt: str
    resolvedAt: str | None = None


class TrainingQuestionAppealResolveRequest(BaseModel):
    """题目异议处理请求。"""

    status: str = Field(pattern="^(resolved|rejected)$")
    resolution: str = Field(min_length=1, max_length=2000)
