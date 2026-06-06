"""员工培训题库平台侧 DTO。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QuestionDraftRequest(BaseModel):
    """题库草稿生成请求。"""

    model_config = ConfigDict(extra="forbid")

    planId: str = Field(min_length=1, max_length=36)
    jobTitle: str = Field(default="", max_length=256)
    abilityGroups: list[str] = Field(default_factory=list)
    count: int | None = Field(default=None, ge=1, le=50)
    documentIds: list[str] = Field(default_factory=list)


class QuestionOptionDTO(BaseModel):
    """选择题选项。"""

    label: str
    text: str


class QuestionDraftDTO(BaseModel):
    """题库草稿响应。"""

    questionId: str
    planId: str
    appId: str
    documentId: str | None = None
    questionType: str
    category: str = "practice"
    content: str
    options: list[QuestionOptionDTO] = Field(default_factory=list)
    correctAnswer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None
    evidenceChunkIds: list[str] = Field(default_factory=list)
    status: str = "draft"
    createdAt: str
    updatedAt: str | None = None


class QuestionUpdateRequest(BaseModel):
    """管理员修改题目请求。"""

    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(default=None, min_length=1)
    options: list[QuestionOptionDTO] | None = None
    correctAnswer: str | None = None
    explanation: str | None = None
    rubric: dict[str, Any] | None = None
    evidenceChunkIds: list[str] | None = None
    category: str | None = Field(default=None, max_length=16)


class QuestionAppealRequest(BaseModel):
    """学员题目异议上报请求。"""

    model_config = ConfigDict(extra="forbid")

    endUserId: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=2000)
    answerRecordId: str | None = Field(default=None, max_length=36)


class QuestionAppealDTO(BaseModel):
    """题目异议记录。"""

    appealId: str
    questionId: str
    appId: str
    endUserId: str
    reason: str
    status: str
    createdAt: str


class QuestionAppealResolveRequest(BaseModel):
    """管理员处理题目异议请求。"""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(resolved|rejected)$")
    notes: str = Field(default="", max_length=2000)


class QuestionReviewRequest(BaseModel):
    """ex-app 管理员审核平台题目请求。"""

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = Field(default="", max_length=2000)
