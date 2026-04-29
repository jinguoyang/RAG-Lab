from uuid import UUID

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


class EffectivePermissionSimulationRequest(BaseModel):
    """有效权限模拟请求，用于解释某用户对某权限的来源。"""

    userId: UUID
    permissionCode: str | None = None
    resourceType: str = "knowledge_base"
    resourceId: UUID | None = None


class PermissionSourceDTO(BaseModel):
    """单条权限来源解释。"""

    sourceType: str
    sourceId: str
    sourceName: str | None = None
    roleCode: str | None = None
    permissionCode: str
    effect: str


class EffectivePermissionSimulationResponse(BaseModel):
    """有效权限模拟结果，说明允许/拒绝及其来源。"""

    userId: str
    kbId: str
    requestedPermissionCode: str | None
    allowed: bool
    permissions: list[str]
    deniedPermissions: list[str]
    roles: list[str]
    subjectKeys: list[str]
    sources: list[PermissionSourceDTO]
    deniedReasons: list[str]
