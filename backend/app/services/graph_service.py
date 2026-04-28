from uuid import UUID

from sqlalchemy import RowMapping, func, select
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.graph import (
    GraphCommunityDTO,
    GraphCommunitySearchResponse,
    GraphEntityDTO,
    GraphEntitySearchResponse,
    GraphPathDTO,
    GraphPathSearchResponse,
    GraphQueryDiagnosticsDTO,
    GraphSnapshotDTO,
    GraphSupportingChunkDTO,
    GraphSupportingChunksResponse,
)
from app.services.permission_service import has_kb_permission
from app.services.qa_providers import ProviderError, get_qa_run_providers
from app.tables import chunks, documents, graph_chunk_refs, graph_snapshots, knowledge_bases


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


def _preview(content: str, limit: int = 180) -> str:
    """生成支撑 Chunk 的安全预览，避免图诊断接口直接返回整段正文。"""
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit].rstrip()}..."


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


def _degraded_diagnostics(reason: str) -> GraphQueryDiagnosticsDTO:
    """构造稳定降级响应，避免向前端泄漏底层 Provider 异常细节。"""
    return GraphQueryDiagnosticsDTO(degraded=True, degradedReason=reason, provider="graph")


def _to_graph_entity_dto(entity_key: object, name: object, entity_type: object) -> GraphEntityDTO:
    """将 Neo4j 实体片段转换为页面可消费的实体摘要 DTO。"""
    return GraphEntityDTO(
        entityKey=str(entity_key) if entity_key else None,
        name=str(name or ""),
        type=str(entity_type) if entity_type else None,
    )


def _to_graph_path_dto(row: dict) -> GraphPathDTO:
    """将 Provider 路径查询结果转换为 API DTO，并保留支撑键用于回落查询。"""
    known_keys = {
        "pathKey",
        "sourceEntityKey",
        "sourceName",
        "sourceType",
        "targetEntityKey",
        "targetName",
        "targetType",
        "relationType",
        "nodeKey",
        "relationKey",
    }
    return GraphPathDTO(
        pathKey=str(row.get("pathKey") or row.get("relationKey") or ""),
        sourceEntity=_to_graph_entity_dto(row.get("sourceEntityKey"), row.get("sourceName"), row.get("sourceType")),
        targetEntity=_to_graph_entity_dto(row.get("targetEntityKey"), row.get("targetName"), row.get("targetType")),
        relationType=str(row.get("relationType") or "RELATED_TO"),
        hopCount=1,
        supportKeys={
            "nodeKey": str(row.get("nodeKey")) if row.get("nodeKey") else None,
            "relationKey": str(row.get("relationKey")) if row.get("relationKey") else None,
        },
        metadata={key: value for key, value in row.items() if key not in known_keys},
    )


def _to_graph_community_dto(row: dict) -> GraphCommunityDTO:
    """将 Provider 社区查询结果转换为 API DTO，并保留社区键用于回落查询。"""
    known_keys = {"communityKey", "title", "summary", "entityCount"}
    entity_count = row.get("entityCount")
    return GraphCommunityDTO(
        communityKey=str(row.get("communityKey") or ""),
        title=str(row.get("title") or row.get("communityKey") or ""),
        summary=str(row.get("summary") or ""),
        entityCount=int(entity_count) if entity_count is not None else None,
        supportKeys={"communityKey": str(row.get("communityKey")) if row.get("communityKey") else None},
        metadata={key: value for key, value in row.items() if key not in known_keys},
    )


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


def search_graph_paths(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    keyword: str,
    graph_snapshot_id: UUID | None,
    limit: int,
) -> GraphPathSearchResponse | None:
    """搜索图关系路径；Provider 不可用时安全降级为空结果。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    snapshot_id = graph_snapshot_id or _latest_success_snapshot_id(session, kb_id)
    diagnostics = GraphQueryDiagnosticsDTO(provider="graph")
    try:
        rows = get_qa_run_providers().graph.search_paths(kb_id, keyword, snapshot_id, limit)
    except ProviderError:
        rows = []
        diagnostics = _degraded_diagnostics("图 Provider 当前不可用，已返回空路径结果。")
    return GraphPathSearchResponse(
        items=[_to_graph_path_dto(row) for row in rows],
        graphSnapshotId=str(snapshot_id) if snapshot_id else None,
        diagnostics=diagnostics,
    )


def search_graph_communities(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    keyword: str | None,
    graph_snapshot_id: UUID | None,
    limit: int,
) -> GraphCommunitySearchResponse | None:
    """搜索图社区摘要；Provider 不可用时安全降级为空结果。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    snapshot_id = graph_snapshot_id or _latest_success_snapshot_id(session, kb_id)
    diagnostics = GraphQueryDiagnosticsDTO(provider="graph")
    try:
        rows = get_qa_run_providers().graph.search_communities(kb_id, keyword, snapshot_id, limit)
    except ProviderError:
        rows = []
        diagnostics = _degraded_diagnostics("图 Provider 当前不可用，已返回空社区结果。")
    return GraphCommunitySearchResponse(
        items=[_to_graph_community_dto(row) for row in rows],
        graphSnapshotId=str(snapshot_id) if snapshot_id else None,
        diagnostics=diagnostics,
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
    """查询图对象支撑 Chunk，并按 Chunk 正文权限做最终裁剪。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = graph_chunk_refs.c.graph_snapshot_id == graph_snapshot_id
    if node_key:
        condition = condition & (graph_chunk_refs.c.neo4j_node_key == node_key)
    if relation_key:
        condition = condition & (graph_chunk_refs.c.neo4j_relation_key == relation_key)
    if community_key:
        condition = condition & (graph_chunk_refs.c.community_key == community_key)

    ref_rows = list(session.execute(select(graph_chunk_refs).where(condition).limit(100)).mappings())
    if not ref_rows:
        return GraphSupportingChunksResponse(items=[], filteredCount=0)

    if not has_kb_permission(session, current_user, kb_id, "kb.chunk.read"):
        return GraphSupportingChunksResponse(items=[], filteredCount=len(ref_rows))

    chunk_ids = [row["chunk_id"] for row in ref_rows]
    chunk_rows = session.execute(
        select(
            chunks.c.chunk_id,
            chunks.c.document_id,
            chunks.c.chunk_index,
            chunks.c.content,
            chunks.c.security_level,
            documents.c.name.label("document_name"),
        )
        .select_from(chunks.join(documents, chunks.c.document_id == documents.c.document_id))
        .where(
            chunks.c.chunk_id.in_(chunk_ids),
            chunks.c.kb_id == kb_id,
            chunks.c.status == "active",
            documents.c.deleted_at.is_(None),
        )
        .limit(100)
    ).mappings()
    chunk_by_id = {row["chunk_id"]: row for row in chunk_rows}

    items = []
    for ref_row in ref_rows:
        chunk_row = chunk_by_id.get(ref_row["chunk_id"])
        if chunk_row is None:
            continue
        items.append(
            GraphSupportingChunkDTO(
                chunkId=str(chunk_row["chunk_id"]),
                documentId=str(chunk_row["document_id"]),
                documentName=chunk_row["document_name"],
                chunkIndex=chunk_row["chunk_index"],
                contentPreview=_preview(chunk_row["content"]),
                securityLevel=chunk_row["security_level"],
                refType=ref_row["ref_type"],
                metadata=ref_row["metadata"] or {},
            )
        )

    return GraphSupportingChunksResponse(
        items=items,
        filteredCount=max(len(ref_rows) - len(items), 0),
    )
