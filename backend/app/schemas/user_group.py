from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

PlatformRole = Literal["platform_admin", "platform_user"]
UserStatus = Literal["active", "disabled"]
GroupStatus = Literal["active", "disabled"]


class UserSummaryDTO(BaseModel):
    """平台用户摘要，供 P03 用户管理列表和详情复用。"""

    userId: str
    username: str
    displayName: str
    email: EmailStr | None = None
    platformRole: PlatformRole
    securityLevel: str
    status: UserStatus
    createdAt: str
    updatedAt: str


class UserCreateRequest(BaseModel):
    """创建平台用户请求；开发期不处理密码和生产认证资料。"""

    username: str = Field(min_length=1, max_length=64)
    displayName: str = Field(min_length=1, max_length=128)
    email: EmailStr | None = None
    platformRole: PlatformRole = "platform_user"
    securityLevel: str = Field(default="public", min_length=1, max_length=32)

    @field_validator("username", "displayName", "securityLevel")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """裁剪必填文本，避免空白字符串写入主体表。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Required text cannot be blank.")
        return stripped


class UserUpdateRequest(BaseModel):
    """更新平台用户基础资料；用户名作为登录标识不在此接口修改。"""

    displayName: str | None = Field(default=None, min_length=1, max_length=128)
    email: EmailStr | None = None
    platformRole: PlatformRole | None = None
    securityLevel: str | None = Field(default=None, min_length=1, max_length=32)
    status: UserStatus | None = None


class UserGroupSummaryDTO(BaseModel):
    """用户组摘要，包含 active 成员数便于 P04 列表展示。"""

    groupId: str
    name: str
    description: str | None = None
    memberCount: int
    status: GroupStatus
    createdAt: str
    updatedAt: str


class UserGroupCreateRequest(BaseModel):
    """创建用户组请求。"""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """用户组名称需要可读且不可为空白。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Group name cannot be blank.")
        return stripped


class UserGroupUpdateRequest(BaseModel):
    """更新用户组基础资料。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    status: GroupStatus | None = None


class GroupMemberDTO(BaseModel):
    """用户组成员摘要。"""

    groupMemberId: str
    userId: str
    username: str
    displayName: str
    email: EmailStr | None = None
    status: UserStatus
    joinedAt: str


class UserGroupDetailDTO(UserGroupSummaryDTO):
    """用户组详情，附带当前 active 成员列表。"""

    members: list[GroupMemberDTO]


class GroupMemberAddRequest(BaseModel):
    """批量添加用户组成员。"""

    userIds: list[UUID] = Field(min_length=1, max_length=100)
