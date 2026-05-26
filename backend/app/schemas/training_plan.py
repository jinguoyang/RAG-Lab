"""学习计划 schemas。"""
from typing import Any
from pydantic import BaseModel, Field


class TrainingPlanDraftRequest(BaseModel):
    """生成学习计划草稿请求。"""
    appId: str = Field(min_length=1, max_length=36)
    jobTitle: str = Field(min_length=1, max_length=256)
    jobDescription: str = ""


class TrainingPlanReviewRequest(BaseModel):
    """审核学习计划请求。"""
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""


class TrainingPlanDTO(BaseModel):
    """学习计划 DTO。"""
    planId: str
    appId: str
    jobTitle: str
    jobDescription: str | None = None
    status: str
    abilityGroups: list[Any] = Field(default_factory=list)
    documents: list[Any] = Field(default_factory=list)
    evidenceChunkIds: list[str] = Field(default_factory=list)
    recommendReason: str | None = None
    readingOrder: list[Any] = Field(default_factory=list)
    version: int = 1
    createdAt: str
    updatedAt: str
