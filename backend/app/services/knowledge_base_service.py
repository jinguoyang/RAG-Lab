from uuid import UUID, uuid4

from sqlalchemy import RowMapping, and_, case, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.knowledge_base import (
    KbMemberBindingDTO,
    KbMemberCreateRequest,
    KbMemberSubjectOptionDTO,
    KbMemberUpdateRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDTO,
    RequiredForActivationDTO,
)
from app.services.permission_service import has_kb_permission, kb_visibility_condition
from app.tables import kb_member_bindings, knowledge_bases, user_groups, users


class KnowledgeBasePermissionError(Exception):
    """当前用户缺少执行知识库成员管理动作的权限。"""


class KnowledgeBaseNotFoundError(Exception):
    """知识库不存在或当前用户不可见。"""


class KbMemberBindingNotFoundError(Exception):
    """成员绑定不存在、已失效或不属于当前知识库。"""


class KbMemberBindingConflictError(Exception):
    """同一主体在当前知识库下已经存在有效成员绑定。"""


class KbMemberSubjectNotFoundError(Exception):
    """成员绑定的用户或用户组不存在、已删除或已禁用。"""


def _to_dto(row: RowMapping) -> KnowledgeBaseDTO:
    """将数据库 snake_case 行转换为前端接口使用的 camelCase DTO。"""
    return KnowledgeBaseDTO(
        kbId=str(row["kb_id"]),
        name=row["name"],
        description=row["description"],
        ownerId=str(row["owner_id"]),
        defaultSecurityLevel=row["default_security_level"],
        sparseIndexEnabled=row["sparse_index_enabled"],
        graphIndexEnabled=row["graph_index_enabled"],
        requiredForActivation=RequiredForActivationDTO(
            dense=True,
            sparse=row["sparse_required_for_activation"],
            graph=row["graph_required_for_activation"],
        ),
        status=row["status"],
        activeConfigRevisionId=(
            str(row["active_config_revision_id"]) if row["active_config_revision_id"] else None
        ),
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _visible_condition(current_user: CurrentUserResponse):
    """知识库可见性以后端权限解析为准，成员绑定后立即影响列表。"""
    return kb_visibility_condition(current_user)


def _ensure_kb_visible(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> None:
    """确认当前用户可见知识库；不可见资源按不存在处理。"""
    exists = session.execute(
        select(knowledge_bases.c.kb_id)
        .where(_visible_condition(current_user), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).scalar_one_or_none()
    if exists is None:
        raise KnowledgeBaseNotFoundError


def _ensure_member_manage_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> None:
    """成员变更是权限边界操作，必须先确认知识库可见并具备管理权限。"""
    _ensure_kb_visible(session, current_user, kb_id)
    if not has_kb_permission(session, current_user, kb_id, "kb.member.manage"):
        raise KnowledgeBasePermissionError


def _member_subject_name_expression():
    """生成成员主体展示名表达式，避免 API 层理解用户/用户组表结构。"""
    return case(
        (kb_member_bindings.c.subject_type == "user", users.c.display_name),
        else_=user_groups.c.name,
    ).label("subject_name")


def _member_subject_status_expression():
    """生成成员主体状态表达式，供前端展示禁用主体的只读提示。"""
    return case(
        (kb_member_bindings.c.subject_type == "user", users.c.status),
        else_=user_groups.c.status,
    ).label("subject_status")


def _member_base_select():
    """构造成员绑定查询，统一处理 user/group 两类主体的展示字段。"""
    return (
        select(
            kb_member_bindings,
            _member_subject_name_expression(),
            _member_subject_status_expression(),
        )
        .select_from(
            kb_member_bindings.outerjoin(
                users,
                and_(
                    kb_member_bindings.c.subject_type == "user",
                    kb_member_bindings.c.subject_id == users.c.user_id,
                ),
            ).outerjoin(
                user_groups,
                and_(
                    kb_member_bindings.c.subject_type == "group",
                    kb_member_bindings.c.subject_id == user_groups.c.group_id,
                ),
            )
        )
        .where(kb_member_bindings.c.status == "active")
    )


def _member_to_dto(row: RowMapping) -> KbMemberBindingDTO:
    """将成员绑定行转换为 P12 页面消费的 DTO。"""
    return KbMemberBindingDTO(
        bindingId=str(row["binding_id"]),
        kbId=str(row["kb_id"]),
        subjectType=row["subject_type"],
        subjectId=str(row["subject_id"]),
        subjectName=row["subject_name"] or str(row["subject_id"]),
        subjectStatus=row["subject_status"] or "unknown",
        kbRole=row["kb_role"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _ensure_subject_exists(session: Session, request: KbMemberCreateRequest) -> None:
    """绑定前校验主体存在且处于 active，避免产生不可解释的授权记录。"""
    if request.subjectType == "user":
        subject_table = users
        subject_id_column = users.c.user_id
    else:
        subject_table = user_groups
        subject_id_column = user_groups.c.group_id

    subject_id = session.execute(
        select(subject_id_column)
        .where(
            subject_id_column == request.subjectId,
            subject_table.c.status == "active",
            subject_table.c.deleted_at.is_(None),
        )
        .limit(1)
    ).scalar_one_or_none()
    if subject_id is None:
        raise KbMemberSubjectNotFoundError


def list_knowledge_bases(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int,
    page_size: int,
    keyword: str | None,
) -> PageResponse[KnowledgeBaseDTO]:
    """分页查询当前用户可见知识库，支撑平台工作台入口。"""
    condition = _visible_condition(current_user)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            knowledge_bases.c.name.ilike(keyword_pattern),
            knowledge_bases.c.description.ilike(keyword_pattern),
        )

    total = session.execute(
        select(func.count()).select_from(knowledge_bases).where(condition)
    ).scalar_one()
    rows = session.execute(
        select(knowledge_bases)
        .where(condition)
        .order_by(knowledge_bases.c.updated_at.desc(), knowledge_bases.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return PageResponse(
        items=[_to_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> KnowledgeBaseDTO | None:
    """读取单个可见知识库；不可见与不存在统一返回 None。"""
    row = session.execute(
        select(knowledge_bases)
        .where(_visible_condition(current_user), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    return _to_dto(row)


def create_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    request: KnowledgeBaseCreateRequest,
) -> KnowledgeBaseDTO:
    """创建知识库基础记录；完整成员绑定和权限矩阵在后续 backlog 落地。"""
    owner_id = request.ownerId or UUID(current_user.user.userId)
    activation = request.requiredForActivation or RequiredForActivationDTO(
        sparse=request.sparseIndexEnabled,
        graph=False,
    )
    kb_id = uuid4()

    row = session.execute(
        insert(knowledge_bases)
        .values(
            kb_id=kb_id,
            name=request.name,
            description=request.description,
            owner_id=owner_id,
            default_security_level=request.defaultSecurityLevel,
            sparse_index_enabled=request.sparseIndexEnabled,
            graph_index_enabled=request.graphIndexEnabled,
            sparse_required_for_activation=activation.sparse,
            graph_required_for_activation=activation.graph,
            status="active",
            metadata={},
            created_by=UUID(current_user.user.userId),
            updated_by=UUID(current_user.user.userId),
        )
        .returning(knowledge_bases)
    ).mappings().one()
    session.execute(
        insert(kb_member_bindings).values(
            binding_id=uuid4(),
            kb_id=kb_id,
            subject_type="user",
            subject_id=owner_id,
            kb_role="kb_owner",
            status="active",
            created_by=UUID(current_user.user.userId),
            updated_by=UUID(current_user.user.userId),
        )
    )
    session.commit()
    return _to_dto(row)


def count_visible_knowledge_bases(session: Session, current_user: CurrentUserResponse) -> int:
    """计算当前用户可见知识库数量，用于 `/auth/me` 能力摘要。"""
    return session.execute(
        select(func.count()).select_from(knowledge_bases).where(_visible_condition(current_user))
    ).scalar_one()


def list_kb_members(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    keyword: str | None,
    kb_role: str | None = None,
) -> PageResponse[KbMemberBindingDTO]:
    """分页返回知识库成员绑定；列表可读仍受知识库可见性约束。"""
    _ensure_kb_visible(session, current_user, kb_id)

    condition = kb_member_bindings.c.kb_id == kb_id
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            users.c.display_name.ilike(keyword_pattern),
            users.c.username.ilike(keyword_pattern),
            user_groups.c.name.ilike(keyword_pattern),
        )
    if kb_role:
        condition = condition & (kb_member_bindings.c.kb_role == kb_role)

    base_select = _member_base_select().where(condition)
    total = session.execute(
        select(func.count()).select_from(base_select.subquery())
    ).scalar_one()
    rows = session.execute(
        base_select.order_by(
            kb_member_bindings.c.created_at.desc(),
            kb_member_bindings.c.binding_id.desc(),
        )
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return PageResponse(
        items=[_member_to_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def search_kb_member_subjects(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    subject_type: str,
    keyword: str | None,
    limit: int,
) -> list[KbMemberSubjectOptionDTO]:
    """搜索可被绑定到知识库的用户或用户组，并标记已绑定主体。"""
    _ensure_member_manage_permission(session, current_user, kb_id)

    normalized_keyword = keyword.strip() if keyword else ""
    bound_subject_ids = set(
        session.execute(
            select(kb_member_bindings.c.subject_id).where(
                kb_member_bindings.c.kb_id == kb_id,
                kb_member_bindings.c.subject_type == subject_type,
                kb_member_bindings.c.status == "active",
            )
        ).scalars()
    )

    if subject_type == "user":
        condition = users.c.status == "active"
        condition = condition & users.c.deleted_at.is_(None)
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            condition = condition & or_(
                users.c.display_name.ilike(keyword_pattern),
                users.c.username.ilike(keyword_pattern),
                users.c.email.ilike(keyword_pattern),
            )

        rows = session.execute(
            select(
                users.c.user_id.label("subject_id"),
                users.c.display_name.label("label"),
                users.c.username,
                users.c.email,
                users.c.status,
            )
            .where(condition)
            .order_by(users.c.display_name.asc(), users.c.username.asc())
            .limit(limit)
        ).mappings()

        return [
            KbMemberSubjectOptionDTO(
                subjectType="user",
                subjectId=str(row["subject_id"]),
                label=row["label"],
                secondaryText=" · ".join(
                    part for part in (f"@{row['username']}", row["email"]) if part
                ),
                status=row["status"],
                isAlreadyBound=row["subject_id"] in bound_subject_ids,
            )
            for row in rows
        ]

    condition = user_groups.c.status == "active"
    condition = condition & user_groups.c.deleted_at.is_(None)
    if normalized_keyword:
        keyword_pattern = f"%{normalized_keyword}%"
        condition = condition & or_(
            user_groups.c.name.ilike(keyword_pattern),
            user_groups.c.description.ilike(keyword_pattern),
        )

    rows = session.execute(
        select(
            user_groups.c.group_id.label("subject_id"),
            user_groups.c.name.label("label"),
            user_groups.c.description,
            user_groups.c.status,
        )
        .where(condition)
        .order_by(user_groups.c.name.asc())
        .limit(limit)
    ).mappings()

    return [
        KbMemberSubjectOptionDTO(
            subjectType="group",
            subjectId=str(row["subject_id"]),
            label=row["label"],
            secondaryText=row["description"],
            status=row["status"],
            isAlreadyBound=row["subject_id"] in bound_subject_ids,
        )
        for row in rows
    ]


def create_kb_member(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: KbMemberCreateRequest,
) -> KbMemberBindingDTO:
    """创建知识库成员绑定；同一主体在同一知识库只允许一个有效角色。"""
    _ensure_member_manage_permission(session, current_user, kb_id)
    _ensure_subject_exists(session, request)

    duplicate = session.execute(
        select(kb_member_bindings.c.binding_id)
        .where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.subject_type == request.subjectType,
            kb_member_bindings.c.subject_id == request.subjectId,
            kb_member_bindings.c.status == "active",
        )
        .limit(1)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise KbMemberBindingConflictError

    binding_id = uuid4()
    session.execute(
        insert(kb_member_bindings).values(
            binding_id=binding_id,
            kb_id=kb_id,
            subject_type=request.subjectType,
            subject_id=request.subjectId,
            kb_role=request.kbRole,
            status="active",
            created_by=UUID(current_user.user.userId),
            updated_by=UUID(current_user.user.userId),
        )
    )
    session.commit()
    return get_kb_member(session, current_user, kb_id, binding_id)


def get_kb_member(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> KbMemberBindingDTO:
    """读取单个有效成员绑定，用于创建和更新后返回最新 DTO。"""
    _ensure_kb_visible(session, current_user, kb_id)
    row = session.execute(
        _member_base_select().where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.binding_id == binding_id,
        )
    ).mappings().first()
    if row is None:
        raise KbMemberBindingNotFoundError
    return _member_to_dto(row)


def update_kb_member_role(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
    request: KbMemberUpdateRequest,
) -> KbMemberBindingDTO:
    """修改知识库成员角色，不改变绑定主体和历史创建信息。"""
    _ensure_member_manage_permission(session, current_user, kb_id)
    result = session.execute(
        update(kb_member_bindings)
        .where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.binding_id == binding_id,
            kb_member_bindings.c.status == "active",
        )
        .values(
            kb_role=request.kbRole,
            updated_by=UUID(current_user.user.userId),
            updated_at=func.now(),
        )
    )
    if result.rowcount == 0:
        session.rollback()
        raise KbMemberBindingNotFoundError
    session.commit()
    return get_kb_member(session, current_user, kb_id, binding_id)


def remove_kb_member(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> None:
    """移除成员时仅将绑定置为 inactive，保留授权变更审计线索。"""
    _ensure_member_manage_permission(session, current_user, kb_id)
    result = session.execute(
        update(kb_member_bindings)
        .where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.binding_id == binding_id,
            kb_member_bindings.c.status == "active",
        )
        .values(
            status="inactive",
            updated_by=UUID(current_user.user.userId),
            updated_at=func.now(),
        )
    )
    if result.rowcount == 0:
        session.rollback()
        raise KbMemberBindingNotFoundError
    session.commit()
