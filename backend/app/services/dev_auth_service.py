from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.auth import CurrentUserResponse, UserDTO


@dataclass(frozen=True)
class DevUser:
    """开发期内置用户，只用于本地联调占位。"""

    user_id: str
    username: str
    display_name: str
    email: str
    platform_role: str
    permissions: tuple[str, ...]


DEV_USERS: dict[str, DevUser] = {
    "admin": DevUser(
        user_id="00000000-0000-0000-0000-000000000001",
        username="admin",
        display_name="开发管理员",
        email="admin@example.com",
        platform_role="platform_admin",
        permissions=(
            "platform.user.manage",
            "kb.view",
            "kb.manage",
            "kb.member.manage",
            "kb.document.upload",
            "kb.document.read",
            "kb.document.download",
            "kb.chunk.read",
            "kb.config.manage",
            "kb.qa.run",
            "kb.qa.history.read",
            "kb.evaluation.manage",
        ),
    ),
    "user": DevUser(
        user_id="00000000-0000-0000-0000-000000000002",
        username="user",
        display_name="开发用户",
        email="user@example.com",
        platform_role="platform_user",
        permissions=("kb.view", "kb.document.read", "kb.qa.run"),
    ),
}


def get_dev_user(username: str, settings: Settings) -> CurrentUserResponse | None:
    """按用户名返回开发期用户摘要；不存在时返回 None。"""
    dev_user = DEV_USERS.get(username)
    if dev_user is None:
        return None

    return CurrentUserResponse(
        user=UserDTO(
            userId=dev_user.user_id,
            username=dev_user.username,
            displayName=dev_user.display_name,
            email=dev_user.email,
            platformRole=dev_user.platform_role,
            securityLevel=settings.dev_default_security_level,
            status="active",
        ),
        platformPermissions=list(dev_user.permissions),
        visibleKbCount=0,
    )
