"""培训题目生成端点。"""
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/training/questions", tags=["training"])


class QuestionDraftRequest(BaseModel):
    planId: str
    appId: str
    jobTitle: str = ""
    abilityGroups: list[str] = Field(default_factory=list)
    count: int = 4


class QuestionOptionDTO(BaseModel):
    label: str
    text: str


class QuestionDraftDTO(BaseModel):
    questionType: str
    category: str
    content: str
    options: list[QuestionOptionDTO] = Field(default_factory=list)
    correctAnswer: str | None = None
    explanation: str | None = None
    rubric: dict | None = None
    evidenceChunkIds: list[str] = Field(default_factory=list)


@router.post("/drafts", response_model=list[QuestionDraftDTO], status_code=status.HTTP_201_CREATED)
async def create_question_drafts(request: QuestionDraftRequest):
    """生成题目草稿（stub：返回固定模板，后续替换为 RAG+LLM）。"""
    # TODO: 添加 API Key 认证（参考 app_runtime.py 的 _extract_bearer_token）
    templates = [
        {
            "questionType": "single_choice",
            "category": "practice",
            "content": f"关于「{request.jobTitle}」，以下哪项是正确的？",
            "options": [
                {"label": "A", "text": "选项 A"},
                {"label": "B", "text": "选项 B"},
                {"label": "C", "text": "选项 C"},
                {"label": "D", "text": "选项 D"},
            ],
            "correctAnswer": "A",
            "explanation": "待 LLM 生成",
            "evidenceChunkIds": [],
        }
    ]
    return templates[: request.count]
