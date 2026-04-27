from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import RowMapping, and_, exists, or_, select
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.permission import PermissionSummaryDTO
from app.tables import (
    kb_member_bindings,
    knowledge_bases,
    role_permission_bindings,
    user_group_members,
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
