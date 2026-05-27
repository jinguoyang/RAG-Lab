"""学习计划生成端点。"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/training/plans", tags=["training"])


class PlanDraftRequest(BaseModel):
    appId: str
    jobTitle: str
    jobDescription: str = ""


class AbilityGroupDTO(BaseModel):
    name: str
    description: str


class DocumentDTO(BaseModel):
    documentId: str
    title: str
    relevance: float = 0.0


class PlanDraftDTO(BaseModel):
    abilityGroups: list[AbilityGroupDTO] = Field(default_factory=list)
    documents: list[DocumentDTO] = Field(default_factory=list)
    evidenceChunkIds: list[str] = Field(default_factory=list)
    recommendReason: str = ""
    readingOrder: list[str] = Field(default_factory=list)


@router.post("/drafts", response_model=PlanDraftDTO, status_code=status.HTTP_201_CREATED)
async def create_plan_draft(request: PlanDraftRequest):
    """生成学习计划草稿（stub：返回固定模板，后续替换为 RAG+LLM）。"""
    # TODO: 添加 API Key 认证（参考 app_runtime.py 的 _extract_bearer_token）
    return PlanDraftDTO(
        abilityGroups=[
            {"name": "基础能力", "description": f"{request.jobTitle}岗位基础知识"},
            {"name": "专业技能", "description": f"{request.jobTitle}核心专业技能"},
        ],
        documents=[
            {"documentId": "doc-001", "title": f"{request.jobTitle}入门指南", "relevance": 0.95},
            {"documentId": "doc-002", "title": f"{request.jobTitle}最佳实践", "relevance": 0.88},
        ],
        evidenceChunkIds=["chunk-001", "chunk-002", "chunk-003"],
        recommendReason=f"基于{request.jobTitle}岗位描述，推荐以上文档作为核心学习材料。",
        readingOrder=["doc-001", "doc-002"],
    )
