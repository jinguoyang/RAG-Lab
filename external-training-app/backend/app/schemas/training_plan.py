"""学习计划 schemas。"""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class TrainingPlanDraftRequest(BaseModel):
    """生成学习计划草稿请求。"""
    model_config = ConfigDict(extra="forbid")

    jobTitle: str = Field(min_length=1, max_length=256)
    jobDescription: str = ""
    planName: str | None = Field(default=None, max_length=256)


class TrainingPlanReviewRequest(BaseModel):
    """审核学习计划请求。"""
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""


class TrainingPlanDTO(BaseModel):
    """学习计划 DTO。"""
    planId: str
    appId: str
    planName: str | None = None
    jobTitle: str
    jobDescription: str | None = None
    status: str
    abilityGroups: list[Any] = Field(default_factory=list)
    documents: list[Any] = Field(default_factory=list)
    evidenceChunkIds: list[str] = Field(default_factory=list)
    recommendReason: str | None = None
    readingOrder: list[Any] = Field(default_factory=list)
    employeeIds: list[str] = Field(default_factory=list)
    completedDocuments: list[str] = Field(default_factory=list)
    passedDocuments: list[str] = Field(default_factory=list)
    version: int = 1
    createdAt: str
    updatedAt: str


class TrainingDocumentDTO(BaseModel):
    """平台知识库文档候选。"""

    documentId: str
    title: str
    category: str | None = None
    difficulty: str | None = None
    summary: str | None = None


class TrainingPlanSaveRequest(BaseModel):
    """保存最终学习计划请求。"""

    planName: str = Field(min_length=1, max_length=256)
    appId: str = Field(min_length=1, max_length=36)
    jobTitle: str = Field(min_length=1, max_length=256)
    jobDescription: str | None = None
    abilityGroups: list[Any] = Field(default_factory=list)
    documents: list[Any] = Field(default_factory=list)
    evidenceChunkIds: list[str] = Field(default_factory=list)
    recommendReason: str | None = None
    readingOrder: list[str] = Field(default_factory=list)
    employeeIds: list[str] = Field(default_factory=list)
    version: int = 1


class TrainingPlanUpdateRequest(BaseModel):
    """更新学习计划请求。文档元数据（难易程度、能力分类）修改仅保存在本地。"""

    planName: str | None = Field(default=None, max_length=256)
    documents: list[Any] | None = None
    readingOrder: list[str] | None = None
    employeeIds: list[str] | None = None
