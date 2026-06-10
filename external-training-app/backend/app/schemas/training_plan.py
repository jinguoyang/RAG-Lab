"""学习计划 schemas。"""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrainingPlanDraftRequest(BaseModel):
    """生成学习计划草稿请求。"""
    model_config = ConfigDict(extra="forbid")

    jobTitle: str = Field(min_length=1, max_length=256)
    jobDescription: str = ""
    planName: str = Field(min_length=1, max_length=256)


class TrainingPlanReviewRequest(BaseModel):
    """审核学习计划请求。"""
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""


class TeachingScriptDTO(BaseModel):
    """章节级课堂讲稿。"""

    opening: str
    explanation: str
    scenario: str
    interactionQuestions: list[str] = Field(default_factory=list)
    summary: str


class TrainingSectionDTO(BaseModel):
    """单份文档内按学习目标组织的课程小节。"""

    sectionId: str
    title: str
    learningObjective: str
    evidenceChunkIds: list[str] = Field(default_factory=list)
    keyPoints: list[str] = Field(default_factory=list)
    checkpointCriteria: list[str] = Field(default_factory=list)
    teachingScript: TeachingScriptDTO | None = None
    teachingQualityScore: float = Field(default=0.0, ge=0.0, le=1.0)
    estimatedMinutes: int = Field(default=8, ge=1, le=120)
    required: bool = True


class TrainingPlanDocumentDTO(BaseModel):
    """学习计划文档及其附属小节。"""

    documentId: str
    title: str
    relevance: float | None = None
    abilityGroup: str | None = None
    category: str | None = None
    difficulty: str | None = None
    summary: str | None = None
    sections: list[TrainingSectionDTO] = Field(default_factory=list)


class TrainingPlanDTO(BaseModel):
    """学习计划 DTO。"""
    planId: str
    appId: str
    planName: str | None = None
    jobTitle: str
    jobDescription: str | None = None
    status: str
    abilityGroups: list[Any] = Field(default_factory=list)
    documents: list[TrainingPlanDocumentDTO] = Field(default_factory=list)
    evidenceChunkIds: list[str] = Field(default_factory=list)
    recommendReason: str | None = None
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
    documents: list[TrainingPlanDocumentDTO] = Field(default_factory=list)
    evidenceChunkIds: list[str] = Field(default_factory=list)
    recommendReason: str | None = None
    employeeIds: list[str] = Field(default_factory=list)
    version: int = 1

    @model_validator(mode="after")
    def validate_document_sections(self):
        """最终计划中的每份文档都必须包含至少一个学习小节。"""
        if any(not document.sections for document in self.documents):
            raise ValueError("每份学习文档必须包含至少一个学习小节")
        return self


class TrainingPlanUpdateRequest(BaseModel):
    """更新学习计划请求。文档元数据（难易程度、能力分类）修改仅保存在本地。"""

    planName: str | None = Field(default=None, max_length=256)
    documents: list[TrainingPlanDocumentDTO] | None = None
    employeeIds: list[str] | None = None

    @model_validator(mode="after")
    def validate_document_sections(self):
        """更新文档时不允许产生没有学习小节的文档。"""
        if self.documents is not None and any(not document.sections for document in self.documents):
            raise ValueError("每份学习文档必须包含至少一个学习小节")
        return self
