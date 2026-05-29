"""员工培训题库平台侧 DTO。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QuestionDraftRequest(BaseModel):
    """题库草稿生成请求。"""

    planId: str = Field(min_length=1, max_length=36)
    appId: str = Field(min_length=1, max_length=36)
    jobTitle: str = Field(default="", max_length=256)
    abilityGroups: list[str] = Field(default_factory=list)
    count: int = Field(default=3, ge=1, le=10)
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
