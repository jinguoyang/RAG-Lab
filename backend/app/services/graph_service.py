from uuid import UUID

from sqlalchemy import RowMapping, func, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.graph import (
    GraphEntityDTO,
    GraphEntitySearchResponse,
    GraphCommunityDTO,
    GraphCommunitySearchResponse,
    GraphPathDTO,
    GraphPathSearchResponse,
    GraphQueryDiagnosticsDTO,
    GraphSnapshotDTO,
    GraphSupportingChunkDTO,
    GraphSupportingChunksResponse,
)
from app.services.qa_providers import ProviderError, get_qa_run_providers
from app.services.permission_service import has_kb_permission
from app.tables import chunks, document_versions, documents, graph_chunk_refs, graph_snapshots, knowledge_bases


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用开发期最小权限：平台管理员可访问全部知识库。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库；图接口不可泄漏不可见知识库存在性。"""
    row = session.execute(
        select(knowledge_bases)
        .where(knowledge_bases.c.deleted_at.is_(None), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    if _is_platform_admin(current_user) or has_kb_permission(session, current_user, kb_id, "kb.view"):
        return row
    return None


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


def _degraded_diagnostics(reason: str) -> GraphQueryDiagnosticsDTO:
    """构造稳定降级诊断，不向前端泄漏 Provider 内部异常。"""
    return GraphQueryDiagnosticsDTO(degraded=True, degradedReason=reason, provider="graph")


def _to_graph_entity_dto(item: dict, key_name: str = "entityKey", name_key: str = "name", type_key: str = "type") -> GraphEntityDTO:
    """将 Provider 返回的实体片段归一化为 GraphEntityDTO。"""
    return GraphEntityDTO(
        entityKey=item.get(key_name),
        name=str(item.get(name_key) or ""),
        type=item.get(type_key),
        aliases=item.get("aliases"),
        metadata={
            key: value
            for key, value in item.items()
            if key not in {key_name, name_key, type_key, "aliases"}
        },
    )


def _to_graph_path_dto(item: dict) -> GraphPathDTO:
    """将 Provider 路径摘要转换为接口 DTO。"""
    source_entity = GraphEntityDTO(
        entityKey=item.get("sourceEntityKey"),
        name=str(item.get("sourceName") or "Unknown source"),
        type=item.get("sourceType"),
    )
    target_entity = GraphEntityDTO(
        entityKey=item.get("targetEntityKey"),
        name=str(item.get("targetName") or "Unknown target"),
        type=item.get("targetType"),
    )
    return GraphPathDTO(
        pathKey=str(item.get("pathKey") or f"{source_entity.entityKey}->{target_entity.entityKey}"),
        sourceEntity=source_entity,
        targetEntity=target_entity,
        relationType=str(item.get("relationType") or "RELATED_TO"),
        hopCount=int(item.get("hopCount") or 1),
        supportKeys={
            "nodeKey": item.get("nodeKey"),
            "relationKey": item.get("relationKey") or item.get("pathKey"),
            "communityKey": item.get("communityKey"),
        },
        metadata={
            key: value
            for key, value in item.items()
            if key
            not in {
                "pathKey",
                "sourceEntityKey",
                "sourceName",
                "sourceType",
                "targetEntityKey",
                "targetName",
                "targetType",
                "relationType",
                "hopCount",
                "nodeKey",
                "relationKey",
                "communityKey",
            }
        },
    )


def _to_graph_community_dto(item: dict) -> GraphCommunityDTO:
    """将 Provider 社区摘要转换为接口 DTO。"""
    community_key = str(item.get("communityKey") or item.get("communityKeyForSupport") or "")
    return GraphCommunityDTO(
        communityKey=community_key,
        title=str(item.get("title") or community_key or "Community"),
        summary=str(item.get("summary") or ""),
        entityCount=item.get("entityCount"),
        supportKeys={
            "nodeKey": item.get("nodeKey"),
            "relationKey": item.get("relationKey"),
            "communityKey": community_key,
        },
        metadata={
            key: value
            for key, value in item.items()
            if key not in {"communityKey", "communityKeyForSupport", "title", "summary", "entityCount", "nodeKey", "relationKey"}
        },
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


def mark_graph_snapshots_stale(
    session: Session,
    kb_id: UUID,
    reason: str,
    current_user: CurrentUserResponse,
) -> None:
    """将当前知识库的成功图快照统一标记为 stale，避免图谱滞后时仍被当作新鲜数据。"""
    session.execute(
        update(graph_snapshots)
        .where(graph_snapshots.c.kb_id == kb_id, graph_snapshots.c.status == "success")
        .values(
            status="stale",
            stale_reason=reason,
            stale_at=func.now(),
            updated_at=func.now(),
            updated_by=UUID(current_user.user.userId),
        )
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
        items=[_to_graph_entity_dto(item) for item in items if item.get("name")],
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
    """搜索图路径摘要；Provider 不可用时返回空结果和降级诊断。"""
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
    """搜索图社区摘要；Provider 不可用时返回空结果和降级诊断。"""
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
    """查询图对象支撑 Chunk，并按快照归属和正文读取权限裁剪。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    snapshot_row = session.execute(
        select(graph_snapshots.c.graph_snapshot_id).where(
            graph_snapshots.c.graph_snapshot_id == graph_snapshot_id,
            graph_snapshots.c.kb_id == kb_id,
        )
    ).mappings().first()
    if snapshot_row is None:
        return None

    condition = graph_chunk_refs.c.graph_snapshot_id == graph_snapshot_id
    if node_key:
        condition = condition & (graph_chunk_refs.c.neo4j_node_key == node_key)
    if relation_key:
        condition = condition & (graph_chunk_refs.c.neo4j_relation_key == relation_key)
    if community_key:
        condition = condition & (graph_chunk_refs.c.community_key == community_key)

    ref_rows = list(session.execute(select(graph_chunk_refs).where(condition).limit(100)).mappings())
    if not has_kb_permission(session, current_user, kb_id, "kb.chunk.read"):
        return GraphSupportingChunksResponse(items=[], filteredCount=len(ref_rows))

    chunk_ids = [row["chunk_id"] for row in ref_rows]
    if not chunk_ids:
        return GraphSupportingChunksResponse(items=[], filteredCount=0)

    chunk_rows = session.execute(
        select(
            chunks,
            documents.c.name.label("document_name"),
        )
        .select_from(
            chunks.join(document_versions, chunks.c.version_id == document_versions.c.version_id).join(
                documents,
                chunks.c.document_id == documents.c.document_id,
            )
        )
        .where(
            chunks.c.chunk_id.in_(chunk_ids),
            chunks.c.kb_id == kb_id,
            chunks.c.status == "active",
            document_versions.c.status == "active",
            documents.c.deleted_at.is_(None),
        )
    ).mappings()
    chunks_by_id = {row["chunk_id"]: row for row in chunk_rows}

    items: list[GraphSupportingChunkDTO] = []
    for row in ref_rows:
        chunk_row = chunks_by_id.get(row["chunk_id"])
        chunk_metadata = chunk_row["metadata"] if chunk_row else None
        governance = chunk_metadata.get("governance") if isinstance(chunk_metadata, dict) else None
        if chunk_row is None or (isinstance(governance, dict) and governance.get("excluded") is True):
            continue
        metadata = {
            **(row["metadata"] or {}),
            "versionId": str(chunk_row["version_id"]),
        }
        items.append(
            GraphSupportingChunkDTO(
                chunkId=str(row["chunk_id"]),
                documentId=str(chunk_row["document_id"]),
                documentName=chunk_row["document_name"],
                chunkIndex=chunk_row["chunk_index"],
                contentPreview=chunk_row["content"][:240],
                securityLevel=chunk_row["security_level"],
                refType=row["ref_type"],
                metadata=metadata,
            )
        )
    filtered_count = len(ref_rows) - len(items)
    return GraphSupportingChunksResponse(
        items=items,
        filteredCount=filtered_count,
    )
