from pydantic import BaseModel, EmailStr


class UserDTO(BaseModel):
    """当前接口层使用的用户摘要，字段保持 camelCase。"""

    userId: str
    username: str
    displayName: str
    email: EmailStr | None = None
    platformRole: str
    securityLevel: str
    status: str


class CurrentUserResponse(BaseModel):
    """当前用户响应，供前端初始化登录态和能力摘要。"""

    user: UserDTO
    platformPermissions: list[str]
    visibleKbCount: int
