from pydantic import BaseModel


class PermissionSummaryDTO(BaseModel):
    """当前用户在指定资源上的权限摘要，仅供前端展示和交互置灰。"""

    resourceType: str
    resourceId: str
    permissions: list[str]
    deniedReasons: list[str]
    roles: list[str]
    subjectKeys: list[str]
    inheritedFromPlatformRole: bool
