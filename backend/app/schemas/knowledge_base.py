from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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
    ownerId: UUID | None = None
    defaultSecurityLevel: str = Field(default="public", min_length=1, max_length=32)
    sparseIndexEnabled: bool = False
    graphIndexEnabled: bool = False
    requiredForActivation: RequiredForActivationDTO | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """创建前裁剪名称，避免空白字符串绕过最小长度校验。"""
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Knowledge base name is required.")
        return stripped_value


class KnowledgeBaseUpdateRequest(BaseModel):
    """更新知识库基础信息请求；未传字段保持原值不变。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    ownerId: UUID | None = None
    defaultSecurityLevel: str | None = Field(default=None, min_length=1, max_length=32)
    sparseIndexEnabled: bool | None = None
    graphIndexEnabled: bool | None = None
    requiredForActivation: RequiredForActivationDTO | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        """更新名称时同样裁剪空白，避免写入不可读名称。"""
        if value is None:
            return value
        stripped_value = value.strip()
        if not stripped_value:
            raise ValueError("Knowledge base name is required.")
        return stripped_value


SubjectType = Literal["user", "group"]
KbRole = Literal["kb_owner", "kb_editor", "kb_operator", "kb_viewer"]


class KbMemberBindingDTO(BaseModel):
    """知识库成员绑定摘要，供 P12 成员与权限页展示。"""

    bindingId: str
    kbId: str
    subjectType: SubjectType
    subjectId: str
    subjectName: str
    subjectStatus: str
    kbRole: KbRole
    status: str
    createdAt: str
    updatedAt: str


class KbMemberSubjectOptionDTO(BaseModel):
    """P12 添加成员下拉选项，避免前端直接输入不可读的 UUID。"""

    subjectType: SubjectType
    subjectId: str
    label: str
    secondaryText: str | None = None
    status: str
    isAlreadyBound: bool = False


class KbMemberCreateRequest(BaseModel):
    """添加知识库成员绑定请求，一个主体在同一知识库内只保留一个有效角色。"""

    subjectType: SubjectType
    subjectId: UUID
    kbRole: KbRole


class KbMemberUpdateRequest(BaseModel):
    """修改知识库成员角色请求；不允许通过更新接口更换绑定主体。"""

    kbRole: KbRole
