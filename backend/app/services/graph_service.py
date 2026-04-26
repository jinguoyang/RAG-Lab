from uuid import UUID

from sqlalchemy import RowMapping, func, select
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.graph import (
    GraphEntityDTO,
    GraphEntitySearchResponse,
    GraphSnapshotDTO,
    GraphSupportingChunkDTO,
    GraphSupportingChunksResponse,
)
from app.services.qa_providers import ProviderError, get_qa_run_providers
from app.tables import graph_chunk_refs, graph_snapshots, knowledge_bases


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用开发期最小权限：平台管理员可访问全部知识库。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库；图接口不可泄漏不可见知识库存在性。"""
    condition = (knowledge_bases.c.deleted_at.is_(None)) & (knowledge_bases.c.kb_id == kb_id)
    if not _is_platform_admin(current_user):
        condition = condition & (knowledge_bases.c.owner_id == UUID(current_user.user.userId))
    return session.execute(select(knowledge_bases).where(condition).limit(1)).mappings().first()


def _to_graph_snapshot_dto(row: RowMapping) -> GraphSnapshotDTO:
    """转换 GraphSnapshot 数据库行为 API DTO。"""
    return GraphSnapshotDTO(
        graphSnapshotId=str(row["graph_snapshot_id"]),
        kbId=str(row["kb_id"]),
        status=row["status"],
        sourceScope=row["source_scope"],
        neo4jGraphKey=row["neo4j_graph_key"],
        staleReason=row["stale_reason"],
        staleAt=row["stale_at"].isoformat() if row["stale_at"] else None,
        entityCount=row["entity_count"],
        relationCount=row["relation_count"],
        communityCount=row["community_count"],
        jobId=str(row["job_id"]) if row["job_id"] else None,
        errorMessage=row["error_message"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def list_graph_snapshots(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    status: str | None,
) -> PageResponse[GraphSnapshotDTO] | None:
    """分页查询图快照元数据，默认按更新时间倒序。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = graph_snapshots.c.kb_id == kb_id
    if status:
        condition = condition & (graph_snapshots.c.status == status)
    total = session.execute(select(func.count()).select_from(graph_snapshots).where(condition)).scalar_one()
    rows = session.execute(
        select(graph_snapshots)
        .where(condition)
        .order_by(graph_snapshots.c.updated_at.desc(), graph_snapshots.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_graph_snapshot_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_graph_snapshot(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    graph_snapshot_id: UUID,
) -> GraphSnapshotDTO | None:
    """读取单个图快照元数据。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    row = session.execute(
        select(graph_snapshots)
        .where(graph_snapshots.c.kb_id == kb_id, graph_snapshots.c.graph_snapshot_id == graph_snapshot_id)
        .limit(1)
    ).mappings().first()
    return _to_graph_snapshot_dto(row) if row else None


def _latest_success_snapshot_id(session: Session, kb_id: UUID) -> UUID | None:
    row = session.execute(
        select(graph_snapshots.c.graph_snapshot_id)
        .where(graph_snapshots.c.kb_id == kb_id, graph_snapshots.c.status == "success")
        .order_by(graph_snapshots.c.updated_at.desc())
        .limit(1)
    ).first()
    return row[0] if row else None


def search_graph_entities(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    keyword: str,
    graph_snapshot_id: UUID | None,
    limit: int,
) -> GraphEntitySearchResponse | None:
    """搜索图实体；Neo4j 未启用时返回空列表而不是伪造实体。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    snapshot_id = graph_snapshot_id or _latest_success_snapshot_id(session, kb_id)
    try:
        items = get_qa_run_providers().graph.search_entities(kb_id, keyword, snapshot_id, limit)
    except ProviderError:
        items = []
    return GraphEntitySearchResponse(
        items=[
            GraphEntityDTO(
                entityKey=item.get("entityKey"),
                name=str(item.get("name") or ""),
                type=item.get("type"),
                aliases=item.get("aliases"),
                metadata={key: value for key, value in item.items() if key not in {"entityKey", "name", "type", "aliases"}},
            )
            for item in items
            if item.get("name")
        ],
        graphSnapshotId=str(snapshot_id) if snapshot_id else None,
    )


def list_supporting_chunks(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    graph_snapshot_id: UUID,
    node_key: str | None,
    relation_key: str | None,
    community_key: str | None,
) -> GraphSupportingChunksResponse | None:
    """查询图对象支撑 Chunk 引用；正文权限裁剪待 Chunk 真值表落地后补齐。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = graph_chunk_refs.c.graph_snapshot_id == graph_snapshot_id
    if node_key:
        condition = condition & (graph_chunk_refs.c.neo4j_node_key == node_key)
    if relation_key:
        condition = condition & (graph_chunk_refs.c.neo4j_relation_key == relation_key)
    if community_key:
        condition = condition & (graph_chunk_refs.c.community_key == community_key)

    rows = session.execute(select(graph_chunk_refs).where(condition).limit(100)).mappings()
    return GraphSupportingChunksResponse(
        items=[
            GraphSupportingChunkDTO(
                chunkId=str(row["chunk_id"]),
                refType=row["ref_type"],
                metadata=row["metadata"],
            )
            for row in rows
        ],
        filteredCount=0,
    )
