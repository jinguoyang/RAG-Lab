"""员工培训学习计划平台侧 DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PlanDraftRequest(BaseModel):
    """学习计划草稿生成请求。"""

    appId: str = Field(min_length=1, max_length=36)
    jobTitle: str = Field(min_length=1, max_length=256)
    jobDescription: str = Field(default="", max_length=4000)

    @field_validator("jobTitle")
    @classmethod
    def validate_job_title(cls, value: str) -> str:
        """裁剪岗位名称，避免空白岗位进入计划生成。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("jobTitle is required.")
        return stripped


class AbilityGroupDTO(BaseModel):
    """学习计划中的能力分组。"""

    name: str
    description: str


class DocumentDTO(BaseModel):
    """学习计划推荐文档。"""

    documentId: str
    title: str
    relevance: float = 0.0
    abilityGroup: str | None = None
    difficulty: str | None = None


class PlanDraftDTO(BaseModel):
    """学习计划草稿响应。"""

    planId: str
    appId: str
    jobTitle: str
    jobDescription: str = ""
    status: str = "draft"
    abilityGroups: list[AbilityGroupDTO] = Field(default_factory=list)
    documents: list[DocumentDTO] = Field(default_factory=list)
    evidenceChunkIds: list[str] = Field(default_factory=list)
    recommendReason: str = ""
    readingOrder: list[str] = Field(default_factory=list)
    version: int = 1
    createdAt: str
    updatedAt: str
