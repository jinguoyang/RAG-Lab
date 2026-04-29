from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from sqlalchemy import RowMapping, and_, exists, or_, select
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse, UserDTO
from app.schemas.permission import (
    EffectivePermissionSimulationRequest,
    EffectivePermissionSimulationResponse,
    PermissionSourceDTO,
    PermissionSummaryDTO,
)
from app.tables import (
    kb_member_bindings,
    knowledge_bases,
    role_permission_bindings,
    user_groups,
    user_group_members,
    users,
)


@dataclass(frozen=True)
class PermissionEvaluation:
    """权限解析结果，供 API 鉴权、权限摘要和检索过滤共用。"""

    permissions: set[str]
    denied_permissions: set[str]
    kb_roles: set[str]
    group_ids: set[UUID]
    subject_keys: set[str]
    inherited_from_platform_role: bool


@dataclass(frozen=True)
class ChunkAccessFilterContext:
    """检索前访问过滤摘要，Provider 用它构造召回前过滤条件。"""

    permission_code: str
    allow_subject_keys: list[str]
    deny_subject_keys: list[str]
    security_level: str
    document_status: str
    version_status: str
    chunk_status: str
    filter_hash: str
    allowed: bool

    def to_trace_summary(self) -> dict:
        """返回可写入 Trace 的脱敏过滤摘要，不包含未授权正文。"""
        return {
            "permissionCode": self.permission_code,
            "allowSubjectKeys": self.allow_subject_keys,
            "denySubjectKeys": self.deny_subject_keys,
            "securityLevel": self.security_level,
            "documentStatus": self.document_status,
            "versionStatus": self.version_status,
            "chunkStatus": self.chunk_status,
            "filterHash": self.filter_hash,
            "allowed": self.allowed,
        }


def _user_id(current_user: CurrentUserResponse) -> UUID:
    """将当前用户 DTO 中的字符串 ID 转换为 UUID。"""
    return UUID(current_user.user.userId)


def _active_group_ids(session: Session, user_id: UUID) -> set[UUID]:
    """读取当前用户所在的有效用户组，用于用户组授权和 ACL 命中。"""
    rows = session.execute(
        select(user_group_members.c.group_id).where(
            user_group_members.c.user_id == user_id,
            user_group_members.c.status == "active",
        )
    )
    return {row[0] for row in rows}


def _active_kb_roles(session: Session, kb_id: UUID, user_id: UUID, group_ids: set[UUID]) -> set[str]:
    """合并用户直接绑定和用户组绑定得到知识库角色集合。"""
    subject_conditions = [
        and_(
            kb_member_bindings.c.subject_type == "user",
            kb_member_bindings.c.subject_id == user_id,
        )
    ]
    if group_ids:
        subject_conditions.append(
            and_(
                kb_member_bindings.c.subject_type == "group",
                kb_member_bindings.c.subject_id.in_(group_ids),
            )
        )

    rows = session.execute(
        select(kb_member_bindings.c.kb_role).where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.status == "active",
            or_(*subject_conditions),
        )
    )
    return {row[0] for row in rows}


def _role_permissions(session: Session, role_scope: str, role_codes: set[str]) -> tuple[set[str], set[str]]:
    """按角色解析 allow / deny 权限集合，调用方负责执行 deny 优先。"""
    if not role_codes:
        return set(), set()

    rows = session.execute(
        select(role_permission_bindings.c.permission_code, role_permission_bindings.c.effect).where(
            role_permission_bindings.c.role_scope == role_scope,
            role_permission_bindings.c.role_code.in_(role_codes),
            role_permission_bindings.c.status == "active",
        )
    )
    allowed: set[str] = set()
    denied: set[str] = set()
    for permission_code, effect in rows:
        if effect == "deny":
            denied.add(permission_code)
        else:
            allowed.add(permission_code)
    return allowed, denied


def evaluate_kb_permissions(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> PermissionEvaluation:
    """解析当前用户在知识库内的有效权限，统一执行 deny 优先规则。"""
    user_id = _user_id(current_user)
    group_ids = _active_group_ids(session, user_id)
    kb_roles = _active_kb_roles(session, kb_id, user_id, group_ids)

    platform_allowed, platform_denied = _role_permissions(
        session,
        "platform",
        {current_user.user.platformRole},
    )
    kb_allowed, kb_denied = _role_permissions(session, "kb", kb_roles)
    denied = platform_denied | kb_denied
    allowed = (platform_allowed | kb_allowed) - denied

    subject_keys = {f"user:{user_id}", f"platform_role:{current_user.user.platformRole}"}
    subject_keys.update(f"group:{group_id}" for group_id in group_ids)
    subject_keys.update(f"kb_role:{role}" for role in kb_roles)

    return PermissionEvaluation(
        permissions=allowed,
        denied_permissions=denied,
        kb_roles=kb_roles,
        group_ids=group_ids,
        subject_keys=subject_keys,
        inherited_from_platform_role=bool(platform_allowed - platform_denied),
    )


def has_kb_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    permission_code: str,
) -> bool:
    """判断当前用户是否具备知识库权限码，供业务服务做最终后端授权。"""
    return permission_code in evaluate_kb_permissions(session, current_user, kb_id).permissions


def can_view_kb(session: Session, current_user: CurrentUserResponse, kb_id: UUID) -> bool:
    """判断当前用户是否能看到知识库，避免列表和详情只认 owner。"""
    return has_kb_permission(session, current_user, kb_id, "kb.view")


def kb_visibility_condition(current_user: CurrentUserResponse):
    """构造知识库列表可见性条件，平台管理员或有效成员均可见。"""
    user_id = _user_id(current_user)
    active_group_ids = (
        select(user_group_members.c.group_id)
        .where(
            user_group_members.c.user_id == user_id,
            user_group_members.c.status == "active",
        )
        .scalar_subquery()
    )
    member_exists = exists(
        select(kb_member_bindings.c.binding_id).where(
            kb_member_bindings.c.kb_id == knowledge_bases.c.kb_id,
            kb_member_bindings.c.status == "active",
            or_(
                and_(
                    kb_member_bindings.c.subject_type == "user",
                    kb_member_bindings.c.subject_id == user_id,
                ),
                and_(
                    kb_member_bindings.c.subject_type == "group",
                    kb_member_bindings.c.subject_id.in_(active_group_ids),
                ),
            ),
        )
    )
    return (knowledge_bases.c.deleted_at.is_(None)) & (
        (knowledge_bases.c.owner_id == user_id)
        | member_exists
        | (current_user.user.platformRole == "platform_admin")
    )


def get_kb_permission_summary(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> PermissionSummaryDTO | None:
    """返回当前用户在知识库下的权限摘要；无 `kb.view` 时不暴露资源细节。"""
    kb_row: RowMapping | None = session.execute(
        select(knowledge_bases.c.kb_id).where(
            knowledge_bases.c.kb_id == kb_id,
            knowledge_bases.c.deleted_at.is_(None),
        )
    ).mappings().first()
    if kb_row is None:
        return None

    evaluation = evaluate_kb_permissions(session, current_user, kb_id)
    if "kb.view" not in evaluation.permissions:
        return None

    denied_reasons = [
        f"权限 {permission_code} 被显式拒绝，deny 优先。"
        for permission_code in sorted(evaluation.denied_permissions)
    ]
    if not evaluation.kb_roles and not evaluation.inherited_from_platform_role:
        denied_reasons.append("当前用户没有有效知识库角色。")

    return PermissionSummaryDTO(
        resourceType="knowledge_base",
        resourceId=str(kb_id),
        permissions=sorted(evaluation.permissions),
        deniedReasons=denied_reasons,
        roles=sorted(evaluation.kb_roles),
        subjectKeys=sorted(evaluation.subject_keys),
        inheritedFromPlatformRole=evaluation.inherited_from_platform_role,
    )


def _current_user_from_user_row(row: RowMapping) -> CurrentUserResponse:
    """把用户行转换为权限解析所需的 CurrentUserResponse。"""
    return CurrentUserResponse(
        user=UserDTO(
            userId=str(row["user_id"]),
            username=row["username"],
            displayName=row["display_name"],
            email=row["email"],
            platformRole=row["platform_role"],
            securityLevel=row["security_level"],
            status=row["status"],
        ),
        platformPermissions=[],
        visibleKbCount=0,
    )


def _permission_sources_for_role(
    session: Session,
    role_scope: str,
    role_code: str,
    source_type: str,
    source_id: str,
    source_name: str | None,
) -> list[PermissionSourceDTO]:
    """展开单个角色的权限绑定，供权限模拟解释来源。"""
    rows = session.execute(
        select(role_permission_bindings).where(
            role_permission_bindings.c.role_scope == role_scope,
            role_permission_bindings.c.role_code == role_code,
            role_permission_bindings.c.status == "active",
        )
    ).mappings()
    return [
        PermissionSourceDTO(
            sourceType=source_type,
            sourceId=source_id,
            sourceName=source_name,
            roleCode=role_code,
            permissionCode=row["permission_code"],
            effect=row["effect"],
        )
        for row in rows
    ]


def _simulation_sources(session: Session, kb_id: UUID, target_user: CurrentUserResponse) -> list[PermissionSourceDTO]:
    """收集平台角色、直接知识库角色和用户组继承角色的权限来源。"""
    user_id = UUID(target_user.user.userId)
    sources = _permission_sources_for_role(
        session,
        "platform",
        target_user.user.platformRole,
        "platformRole",
        target_user.user.platformRole,
        "平台角色",
    )

    direct_bindings = session.execute(
        select(kb_member_bindings)
        .where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.subject_type == "user",
            kb_member_bindings.c.subject_id == user_id,
            kb_member_bindings.c.status == "active",
        )
    ).mappings()
    for binding in direct_bindings:
        sources.extend(
            _permission_sources_for_role(
                session,
                "kb",
                binding["kb_role"],
                "directKbRole",
                str(binding["binding_id"]),
                "用户直接绑定",
            )
        )

    group_rows = session.execute(
        select(user_group_members.c.group_id, user_groups.c.name)
        .select_from(user_group_members.join(user_groups, user_group_members.c.group_id == user_groups.c.group_id))
        .where(
            user_group_members.c.user_id == user_id,
            user_group_members.c.status == "active",
            user_groups.c.status == "active",
            user_groups.c.deleted_at.is_(None),
        )
    )
    group_names = {group_id: name for group_id, name in group_rows}
    if group_names:
        group_bindings = session.execute(
            select(kb_member_bindings)
            .where(
                kb_member_bindings.c.kb_id == kb_id,
                kb_member_bindings.c.subject_type == "group",
                kb_member_bindings.c.subject_id.in_(set(group_names.keys())),
                kb_member_bindings.c.status == "active",
            )
        ).mappings()
        for binding in group_bindings:
            sources.extend(
                _permission_sources_for_role(
                    session,
                    "kb",
                    binding["kb_role"],
                    "groupKbRole",
                    str(binding["subject_id"]),
                    group_names.get(binding["subject_id"]),
                )
            )
    return sources


def simulate_effective_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: EffectivePermissionSimulationRequest,
) -> EffectivePermissionSimulationResponse | None:
    """模拟指定用户在知识库下的有效权限，并解释权限来源。"""
    kb_row: RowMapping | None = session.execute(
        select(knowledge_bases.c.kb_id).where(
            knowledge_bases.c.kb_id == kb_id,
            knowledge_bases.c.deleted_at.is_(None),
        )
    ).mappings().first()
    if kb_row is None:
        return None
    if request.resourceId is not None and request.resourceId != kb_id:
        raise ValueError("resourceId must match kbId.")
    if current_user.user.platformRole != "platform_admin" and not has_kb_permission(
        session,
        current_user,
        kb_id,
        "kb.member.manage",
    ):
        raise PermissionError("Current user cannot simulate effective permissions.")

    target_row = session.execute(
        select(users)
        .where(
            users.c.user_id == request.userId,
            users.c.status == "active",
            users.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if target_row is None:
        return None

    target_user = _current_user_from_user_row(target_row)
    evaluation = evaluate_kb_permissions(session, target_user, kb_id)
    allowed = (
        request.permissionCode in evaluation.permissions
        if request.permissionCode
        else bool(evaluation.permissions)
    )
    sources = _simulation_sources(session, kb_id, target_user)
    if request.permissionCode:
        sources = [source for source in sources if source.permissionCode == request.permissionCode]

    denied_reasons = [
        f"权限 {permission_code} 被显式拒绝，deny 优先。"
        for permission_code in sorted(evaluation.denied_permissions)
    ]
    if request.permissionCode and not allowed:
        denied_reasons.append(f"没有有效 allow 来源授予 {request.permissionCode}。")
    if not evaluation.kb_roles and not evaluation.inherited_from_platform_role:
        denied_reasons.append("目标用户没有有效知识库角色。")

    return EffectivePermissionSimulationResponse(
        userId=target_user.user.userId,
        kbId=str(kb_id),
        requestedPermissionCode=request.permissionCode,
        allowed=allowed,
        permissions=sorted(evaluation.permissions),
        deniedPermissions=sorted(evaluation.denied_permissions),
        roles=sorted(evaluation.kb_roles),
        subjectKeys=sorted(evaluation.subject_keys),
        sources=sources,
        deniedReasons=denied_reasons,
    )


def build_chunk_access_filter_context(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> ChunkAccessFilterContext:
    """生成 QA 检索前可传给 Provider 的 Chunk 访问过滤摘要。"""
    evaluation = evaluate_kb_permissions(session, current_user, kb_id)
    allowed = "kb.chunk.read" in evaluation.permissions
    allow_subject_keys = sorted(evaluation.subject_keys) if allowed else []
    deny_subject_keys = sorted(f"permission:{code}" for code in evaluation.denied_permissions)
    payload = {
        "permissionCode": "kb.chunk.read",
        "allowSubjectKeys": allow_subject_keys,
        "denySubjectKeys": deny_subject_keys,
        "securityLevel": current_user.user.securityLevel,
        "documentStatus": "active",
        "versionStatus": "active",
        "chunkStatus": "active",
        "allowed": allowed,
    }
    filter_hash = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return ChunkAccessFilterContext(
        permission_code="kb.chunk.read",
        allow_subject_keys=allow_subject_keys,
        deny_subject_keys=deny_subject_keys,
        security_level=current_user.user.securityLevel,
        document_status="active",
        version_status="active",
        chunk_status="active",
        filter_hash=filter_hash,
        allowed=allowed,
    )
