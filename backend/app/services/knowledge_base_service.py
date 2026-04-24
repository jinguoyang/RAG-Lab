from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, or_, select
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDTO,
    RequiredForActivationDTO,
)
from app.tables import knowledge_bases


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


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """判断开发期当前用户是否具备平台管理员能力。"""
    return current_user.user.platformRole == "platform_admin"


def _visible_condition(current_user: CurrentUserResponse):
    """E1 阶段的最小可见性：管理员看全部，普通用户看自己负责的知识库。"""
    if _is_platform_admin(current_user):
        return knowledge_bases.c.deleted_at.is_(None)
    return (knowledge_bases.c.deleted_at.is_(None)) & (
        knowledge_bases.c.owner_id == UUID(current_user.user.userId)
    )


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
    session.commit()
    return _to_dto(row)


def count_visible_knowledge_bases(session: Session, current_user: CurrentUserResponse) -> int:
    """计算当前用户可见知识库数量，用于 `/auth/me` 能力摘要。"""
    return session.execute(
        select(func.count()).select_from(knowledge_bases).where(_visible_condition(current_user))
    ).scalar_one()
