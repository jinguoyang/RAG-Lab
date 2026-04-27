from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, and_, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.user_group import (
    GroupMemberAddRequest,
    GroupMemberDTO,
    UserCreateRequest,
    UserGroupCreateRequest,
    UserGroupDetailDTO,
    UserGroupSummaryDTO,
    UserGroupUpdateRequest,
    UserSummaryDTO,
    UserUpdateRequest,
)
from app.tables import user_group_members, user_groups, users


class PlatformUserPermissionError(Exception):
    """当前用户缺少平台用户与用户组管理权限。"""


class UserNotFoundError(Exception):
    """用户不存在、已删除或不可管理。"""


class UserGroupNotFoundError(Exception):
    """用户组不存在、已删除或不可管理。"""


class UserGroupConflictError(Exception):
    """用户、用户组或组成员关系与现有 active 数据冲突。"""


def _now() -> datetime:
    """统一生成数据库更新时间。"""
    return datetime.now(UTC)


def _actor_id(current_user: CurrentUserResponse) -> UUID:
    """读取当前开发用户 ID，用于审计字段。"""
    return UUID(current_user.user.userId)


def _ensure_platform_user_manage(current_user: CurrentUserResponse) -> None:
    """平台用户管理是全局权限，所有 Users/Groups 写操作都必须先校验。"""
    if (
        current_user.user.platformRole != "platform_admin"
        and "platform.user.manage" not in current_user.platformPermissions
    ):
        raise PlatformUserPermissionError


def _user_to_dto(row: RowMapping) -> UserSummaryDTO:
    """将 users 表行转换为前端 camelCase DTO。"""
    return UserSummaryDTO(
        userId=str(row["user_id"]),
        username=row["username"],
        displayName=row["display_name"],
        email=row["email"],
        platformRole=row["platform_role"],
        securityLevel=row["security_level"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _group_to_dto(row: RowMapping) -> UserGroupSummaryDTO:
    """将用户组聚合查询行转换为列表 DTO。"""
    return UserGroupSummaryDTO(
        groupId=str(row["group_id"]),
        name=row["name"],
        description=row["description"],
        memberCount=row["member_count"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _member_to_dto(row: RowMapping) -> GroupMemberDTO:
    """将用户组成员查询行转换为详情 DTO。"""
    return GroupMemberDTO(
        groupMemberId=str(row["group_member_id"]),
        userId=str(row["user_id"]),
        username=row["username"],
        displayName=row["display_name"],
        email=row["email"],
        status=row["user_status"],
        joinedAt=row["joined_at"].isoformat(),
    )


def _active_group_member_counts():
    """构造 active 成员数子查询，避免列表逐组查询。"""
    return (
        select(
            user_group_members.c.group_id,
            func.count().label("member_count"),
        )
        .where(user_group_members.c.status == "active")
        .group_by(user_group_members.c.group_id)
        .subquery()
    )


def list_users(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int,
    page_size: int,
    keyword: str | None,
) -> PageResponse[UserSummaryDTO]:
    """分页查询平台用户，支撑 P03 用户管理页。"""
    _ensure_platform_user_manage(current_user)

    condition = users.c.deleted_at.is_(None)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            users.c.username.ilike(keyword_pattern),
            users.c.display_name.ilike(keyword_pattern),
            users.c.email.ilike(keyword_pattern),
        )

    total = session.execute(select(func.count()).select_from(users).where(condition)).scalar_one()
    rows = session.execute(
        select(users)
        .where(condition)
        .order_by(users.c.created_at.desc(), users.c.username.asc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return PageResponse(
        items=[_user_to_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def create_user(
    session: Session,
    current_user: CurrentUserResponse,
    request: UserCreateRequest,
) -> UserSummaryDTO:
    """创建平台用户；认证凭据仍由开发期占位登录或后续认证模块负责。"""
    _ensure_platform_user_manage(current_user)
    actor_id = _actor_id(current_user)
    try:
        row = session.execute(
            insert(users)
            .values(
                user_id=uuid4(),
                username=request.username,
                display_name=request.displayName,
                email=str(request.email) if request.email else None,
                platform_role=request.platformRole,
                security_level=request.securityLevel,
                status="active",
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(users)
        ).mappings().one()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise UserGroupConflictError from exc
    return _user_to_dto(row)


def get_user(
    session: Session,
    current_user: CurrentUserResponse,
    user_id: UUID,
) -> UserSummaryDTO:
    """读取单个用户详情。"""
    _ensure_platform_user_manage(current_user)
    row = session.execute(
        select(users)
        .where(users.c.user_id == user_id, users.c.deleted_at.is_(None))
        .limit(1)
    ).mappings().first()
    if row is None:
        raise UserNotFoundError
    return _user_to_dto(row)


def update_user(
    session: Session,
    current_user: CurrentUserResponse,
    user_id: UUID,
    request: UserUpdateRequest,
) -> UserSummaryDTO:
    """更新用户基础资料，保持 user_id 与 username 稳定。"""
    _ensure_platform_user_manage(current_user)
    values = request.model_dump(exclude_unset=True)
    column_values: dict[str, object] = {}
    field_map = {
        "displayName": "display_name",
        "platformRole": "platform_role",
        "securityLevel": "security_level",
    }
    for key, value in values.items():
        column_values[field_map.get(key, key)] = str(value) if key == "email" and value else value

    if not column_values:
        return get_user(session, current_user, user_id)

    column_values["updated_at"] = _now()
    column_values["updated_by"] = _actor_id(current_user)
    result = session.execute(
        update(users)
        .where(users.c.user_id == user_id, users.c.deleted_at.is_(None))
        .values(**column_values)
    )
    if result.rowcount == 0:
        session.rollback()
        raise UserNotFoundError
    session.commit()
    return get_user(session, current_user, user_id)


def disable_user(
    session: Session,
    current_user: CurrentUserResponse,
    user_id: UUID,
) -> UserSummaryDTO:
    """禁用用户；保留用户主体，后续权限计算会按 disabled 状态过滤。"""
    return update_user(
        session,
        current_user,
        user_id,
        UserUpdateRequest(status="disabled"),
    )


def _group_base_select():
    """构造用户组列表查询，附带 active 成员数。"""
    counts = _active_group_member_counts()
    return (
        select(
            user_groups,
            func.coalesce(counts.c.member_count, 0).label("member_count"),
        )
        .select_from(user_groups.outerjoin(counts, user_groups.c.group_id == counts.c.group_id))
        .where(user_groups.c.deleted_at.is_(None))
    )


def list_user_groups(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int,
    page_size: int,
    keyword: str | None,
) -> PageResponse[UserGroupSummaryDTO]:
    """分页查询用户组，支撑 P04 用户组管理页。"""
    _ensure_platform_user_manage(current_user)

    condition = user_groups.c.deleted_at.is_(None)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            user_groups.c.name.ilike(keyword_pattern),
            user_groups.c.description.ilike(keyword_pattern),
        )

    base_select = _group_base_select().where(condition)
    total = session.execute(select(func.count()).select_from(base_select.subquery())).scalar_one()
    rows = session.execute(
        base_select.order_by(user_groups.c.created_at.desc(), user_groups.c.name.asc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return PageResponse(
        items=[_group_to_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def create_user_group(
    session: Session,
    current_user: CurrentUserResponse,
    request: UserGroupCreateRequest,
) -> UserGroupSummaryDTO:
    """创建用户组；组成员通过独立接口维护。"""
    _ensure_platform_user_manage(current_user)
    actor_id = _actor_id(current_user)
    try:
        row = session.execute(
            insert(user_groups)
            .values(
                group_id=uuid4(),
                name=request.name,
                description=request.description,
                status="active",
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(user_groups)
        ).mappings().one()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise UserGroupConflictError from exc

    group_row = dict(row)
    group_row["member_count"] = 0
    return _group_to_dto(group_row)


def _list_group_members(session: Session, group_id: UUID) -> list[GroupMemberDTO]:
    """查询用户组 active 成员列表。"""
    rows = session.execute(
        select(
            user_group_members.c.group_member_id,
            user_group_members.c.user_id,
            user_group_members.c.joined_at,
            users.c.username,
            users.c.display_name,
            users.c.email,
            users.c.status.label("user_status"),
        )
        .select_from(
            user_group_members.join(
                users,
                user_group_members.c.user_id == users.c.user_id,
            )
        )
        .where(
            user_group_members.c.group_id == group_id,
            user_group_members.c.status == "active",
            users.c.deleted_at.is_(None),
        )
        .order_by(user_group_members.c.joined_at.desc())
    ).mappings()
    return [_member_to_dto(row) for row in rows]


def get_user_group(
    session: Session,
    current_user: CurrentUserResponse,
    group_id: UUID,
) -> UserGroupDetailDTO:
    """读取用户组详情和当前成员。"""
    _ensure_platform_user_manage(current_user)
    row = session.execute(
        _group_base_select().where(user_groups.c.group_id == group_id).limit(1)
    ).mappings().first()
    if row is None:
        raise UserGroupNotFoundError

    summary = _group_to_dto(row)
    return UserGroupDetailDTO(
        **summary.model_dump(),
        members=_list_group_members(session, group_id),
    )


def update_user_group(
    session: Session,
    current_user: CurrentUserResponse,
    group_id: UUID,
    request: UserGroupUpdateRequest,
) -> UserGroupSummaryDTO:
    """更新用户组基础资料。"""
    _ensure_platform_user_manage(current_user)
    values = request.model_dump(exclude_unset=True)
    if not values:
        return get_user_group(session, current_user, group_id)

    values["updated_at"] = _now()
    values["updated_by"] = _actor_id(current_user)
    try:
        result = session.execute(
            update(user_groups)
            .where(user_groups.c.group_id == group_id, user_groups.c.deleted_at.is_(None))
            .values(**values)
        )
    except IntegrityError as exc:
        session.rollback()
        raise UserGroupConflictError from exc

    if result.rowcount == 0:
        session.rollback()
        raise UserGroupNotFoundError
    session.commit()
    return get_user_group(session, current_user, group_id)


def add_group_members(
    session: Session,
    current_user: CurrentUserResponse,
    group_id: UUID,
    request: GroupMemberAddRequest,
) -> UserGroupDetailDTO:
    """批量添加用户组成员，已存在的 active 关系会被跳过。"""
    _ensure_platform_user_manage(current_user)
    if session.execute(
        select(user_groups.c.group_id)
        .where(user_groups.c.group_id == group_id, user_groups.c.deleted_at.is_(None))
        .limit(1)
    ).scalar_one_or_none() is None:
        raise UserGroupNotFoundError

    active_user_ids = set(
        session.execute(
            select(users.c.user_id).where(
                users.c.user_id.in_(request.userIds),
                users.c.status == "active",
                users.c.deleted_at.is_(None),
            )
        ).scalars()
    )
    if len(active_user_ids) != len(set(request.userIds)):
        raise UserNotFoundError

    existing_user_ids = set(
        session.execute(
            select(user_group_members.c.user_id).where(
                user_group_members.c.group_id == group_id,
                user_group_members.c.user_id.in_(request.userIds),
                user_group_members.c.status == "active",
            )
        ).scalars()
    )
    new_user_ids = [user_id for user_id in request.userIds if user_id not in existing_user_ids]
    if new_user_ids:
        actor_id = _actor_id(current_user)
        session.execute(
            insert(user_group_members),
            [
                {
                    "group_member_id": uuid4(),
                    "group_id": group_id,
                    "user_id": user_id,
                    "status": "active",
                    "created_by": actor_id,
                }
                for user_id in new_user_ids
            ],
        )
        session.commit()

    return get_user_group(session, current_user, group_id)


def remove_group_member(
    session: Session,
    current_user: CurrentUserResponse,
    group_id: UUID,
    user_id: UUID,
) -> None:
    """移除用户组成员时采用 inactive 失效，保留历史关系线索。"""
    _ensure_platform_user_manage(current_user)
    left_at = _now()
    result = session.execute(
        update(user_group_members)
        .where(
            user_group_members.c.group_id == group_id,
            user_group_members.c.user_id == user_id,
            user_group_members.c.status == "active",
        )
        .values(status="inactive", left_at=left_at)
    )
    if result.rowcount == 0:
        session.rollback()
        raise UserNotFoundError
    session.commit()
