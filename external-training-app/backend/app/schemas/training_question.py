"""题库 schemas。"""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TrainingQuestionDraftRequest(BaseModel):
    """生成题库草稿请求。"""
    model_config = ConfigDict(extra="forbid")

    planId: str = Field(min_length=1, max_length=36)
    jobTitle: str = ""
    abilityGroups: list[str] = Field(default_factory=list)
    count: int = Field(ge=1, le=50, default=5)


class TrainingQuestionReviewRequest(BaseModel):
    """审核题目请求。"""
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""


class TrainingQuestionDTO(BaseModel):
    """题目 DTO。"""
    questionId: str
    planId: str
    appId: str
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
