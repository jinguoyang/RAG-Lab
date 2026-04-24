from pydantic import BaseModel, Field


class RequiredForActivationDTO(BaseModel):
    """文档版本激活门槛摘要，当前 E1 只落 Sparse 与 Graph 开关。"""

    dense: bool = True
    sparse: bool
    graph: bool


class KnowledgeBaseDTO(BaseModel):
    """知识库 API 摘要，保持接口层 camelCase 字段。"""

    kbId: str
    name: str
    description: str | None = None
    ownerId: str
    defaultSecurityLevel: str
    sparseIndexEnabled: bool
    graphIndexEnabled: bool
    requiredForActivation: RequiredForActivationDTO
    status: str
    activeConfigRevisionId: str | None = None
    createdAt: str
    updatedAt: str


class KnowledgeBaseCreateRequest(BaseModel):
    """创建知识库请求；未传可选开关时采用 E1 默认值。"""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    ownerId: str | None = None
    defaultSecurityLevel: str = Field(default="public", min_length=1, max_length=32)
    sparseIndexEnabled: bool = False
    graphIndexEnabled: bool = False
    requiredForActivation: RequiredForActivationDTO | None = None
