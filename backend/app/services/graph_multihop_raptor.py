"""B-326: Graph 多跳与 RAPTOR 层级摘要服务。

增强图检索，支持受控的 graphDepth、路径模式、节点限制和
RAPTOR 层级摘要索引，用于跨文档多跳关系和长文档主题聚合。

功能:
- Neo4j 图检索：graphDepth、路径模式、节点限制
- 图结果格式：路径、节点、边、关联 Chunk、权限状态
- RAPTOR / 层级摘要索引
- 图路径和摘要证据回落到原始 Chunk 或 ParsedDocumentV2 块
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID


class GraphProviderLike(Protocol):
    """图 Provider 最小接口，用于 graph_retrieval_multihop 委托。"""

    def search_entities(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """按关键词搜索图实体。"""
        ...

    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """按关键词搜索图关系路径。"""
        ...


@dataclass(frozen=True)
class GraphNode:
    """图节点。"""

    node_id: str
    name: str
    node_type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """图边。"""

    edge_id: str
    source_id: str
    target_id: str
    relation_type: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphPath:
    """图路径。"""

    path_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    length: int
    summary: str = ""


@dataclass(frozen=True)
class GraphRetrievalResult:
    """图检索结果。"""

    paths: list[GraphPath]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    associated_chunk_ids: list[str]
    permission_status: str  # ok | partial | denied
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SummaryNode:
    """RAPTOR 摘要节点。"""

    summary_id: str
    level: int  # 0=leaf, 1=first level summary, ...
    content: str
    source_chunk_ids: list[str]
    children_summary_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RaptorIndex:
    """RAPTOR 层级摘要索引。"""

    document_id: str
    levels: int
    summary_nodes: list[SummaryNode]
    metadata: dict[str, Any] = field(default_factory=dict)


def graph_retrieval_multihop(
    query: str,
    graph_depth: int = 2,
    max_nodes: int = 50,
    path_mode: str = "entity-path",
    *,
    graph_provider: GraphProviderLike | None = None,
    kb_id: UUID | None = None,
    graph_snapshot_id: UUID | None = None,
) -> GraphRetrievalResult:
    """图多跳检索：有 Provider 时委托真实图查询，否则返回显式降级结果。

    Args:
        query: 查询
        graph_depth: 图深度（传递给 Provider 的 max_nodes 上限倍数）
        max_nodes: 最大节点数
        path_mode: 路径模式
        graph_provider: 可选的图检索 Provider
        kb_id: 知识库 ID（Provider 调用必需）
        graph_snapshot_id: 图快照 ID

    Returns:
        图检索结果
    """
    if graph_provider is None or kb_id is None:
        return GraphRetrievalResult(
            paths=[],
            nodes=[],
            edges=[],
            associated_chunk_ids=[],
            permission_status="partial",
            metadata={
                "query": query,
                "graphDepth": graph_depth,
                "maxNodes": max_nodes,
                "pathMode": path_mode,
                "requiresProvider": True,
                "fallbackReason": "graphProviderRequired",
            },
        )

    # 委托 Provider 执行真实图检索
    entities = graph_provider.search_entities(kb_id, query, graph_snapshot_id, max_nodes)
    paths_data = graph_provider.search_paths(kb_id, query, graph_snapshot_id, max_nodes * graph_depth)

    # 转换实体为 GraphNode
    nodes = [
        GraphNode(
            node_id=e.get("entityKey", ""),
            name=e.get("name", ""),
            node_type=e.get("type", "entity"),
            properties={"aliases": e.get("aliases", [])},
        )
        for e in entities
    ]

    # 转换路径为 GraphEdge 和 GraphPath
    edges = []
    paths = []
    chunk_ids: set[str] = set()
    for p in paths_data:
        edge = GraphEdge(
            edge_id=p.get("pathKey", p.get("relationKey", "")),
            source_id=p.get("sourceEntityKey", ""),
            target_id=p.get("targetEntityKey", ""),
            relation_type=p.get("relationType", "RELATED_TO"),
        )
        edges.append(edge)

        source_node = GraphNode(
            node_id=p.get("sourceEntityKey", ""),
            name=p.get("sourceName", ""),
            node_type=p.get("sourceType", "entity"),
        )
        target_node = GraphNode(
            node_id=p.get("targetEntityKey", ""),
            name=p.get("targetName", ""),
            node_type=p.get("targetType", "entity"),
        )
        gp = GraphPath(
            path_id=p.get("pathKey", ""),
            nodes=[source_node, target_node],
            edges=[edge],
            length=1,
            summary=f"{source_node.name} --[{edge.relation_type}]--> {target_node.name}",
        )
        paths.append(gp)

    return GraphRetrievalResult(
        paths=paths,
        nodes=nodes,
        edges=edges,
        associated_chunk_ids=list(chunk_ids),
        permission_status="ok",
        metadata={
            "query": query,
            "graphDepth": graph_depth,
            "maxNodes": max_nodes,
            "pathMode": path_mode,
            "entityCount": len(nodes),
            "pathCount": len(paths),
        },
    )


def build_raptor_index(
    chunks: list[dict[str, Any]],
    max_levels: int = 3,
    use_llm: bool = False,
    summarizer: Callable[[str, dict[str, Any]], str] | None = None,
) -> RaptorIndex:
    """构建 RAPTOR 层级摘要索引。

    未提供 summarizer 时使用可解释的 extractive 摘要；启用 use_llm 时
    必须显式传入 summarizer，避免把文本截断伪装成 LLM 摘要。

    Args:
        chunks: Chunk 列表
        max_levels: 最大层级数
        use_llm: 是否使用外部 summarizer 生成摘要
        summarizer: 摘要函数，接收文本和元数据

    Returns:
        RAPTOR 索引
    """
    if use_llm and summarizer is None:
        raise ValueError("use_llm=True requires an explicit summarizer")
    if not chunks:
        return RaptorIndex(
            document_id="empty",
            levels=0,
            summary_nodes=[],
            metadata={"summaryMode": "empty"},
        )

    summary_nodes = []
    document_id = chunks[0].get("documentId", "unknown")

    # Level 0: 叶子节点（原始 Chunk）
    leaf_nodes = []
    for i, chunk in enumerate(chunks):
        summary_id = f"summary_0_{i}"
        source_content = chunk.get("content", "")
        content = summarizer(source_content, {"level": 0, "chunkId": chunk.get("chunkId")}) if use_llm and summarizer else source_content[:200]
        node = SummaryNode(
            summary_id=summary_id,
            level=0,
            content=content,
            source_chunk_ids=[chunk.get("chunkId", f"chunk_{i}")],
        )
        summary_nodes.append(node)
        leaf_nodes.append(node)

    # 更高层级：聚合摘要
    current_level_nodes = leaf_nodes
    for level in range(1, max_levels):
        if len(current_level_nodes) <= 1:
            break

        next_level_nodes = []
        for i in range(0, len(current_level_nodes), 2):
            children = current_level_nodes[i:i+2]
            combined_content = " ".join(child.content[:100] for child in children)
            summary_id = f"summary_{level}_{len(next_level_nodes)}"
            content = (
                summarizer(combined_content, {"level": level, "children": [child.summary_id for child in children]})
                if use_llm and summarizer
                else combined_content[:300]
            )

            node = SummaryNode(
                summary_id=summary_id,
                level=level,
                content=content,
                source_chunk_ids=[
                    chunk_id
                    for child in children
                    for chunk_id in child.source_chunk_ids
                ],
                children_summary_ids=[child.summary_id for child in children],
            )
            summary_nodes.append(node)
            next_level_nodes.append(node)

        current_level_nodes = next_level_nodes

    return RaptorIndex(
        document_id=document_id,
        levels=max_levels,
        summary_nodes=summary_nodes,
        metadata={
            "chunkCount": len(chunks),
            "summaryNodeCount": len(summary_nodes),
            "summaryMode": "llm" if use_llm else "extractive",
        },
    )


def search_raptor_index(
    raptor_index: RaptorIndex,
    query: str,
    max_results: int = 5,
) -> list[SummaryNode]:
    """搜索 RAPTOR 索引。

    Args:
        raptor_index: RAPTOR 索引
        query: 查询
        max_results: 最大结果数

    Returns:
        匹配的摘要节点列表
    """
    query_lower = query.lower()
    results = []

    # 按层级从高到低搜索
    for level in range(raptor_index.levels - 1, -1, -1):
        level_nodes = [
            node for node in raptor_index.summary_nodes
            if node.level == level
        ]

        for node in level_nodes:
            if query_lower in node.content.lower():
                results.append(node)
                if len(results) >= max_results:
                    return results

    return results


def get_graph_multihop_info() -> dict[str, Any]:
    """获取图多跳检索信息。"""
    return {
        "pathModes": [
            {"name": "entity-path", "label": "实体路径", "description": "基于实体关系的路径搜索"},
            {"name": "community-summary", "label": "社区摘要", "description": "基于社区的摘要搜索"},
            {"name": "path-and-community", "label": "路径+社区", "description": "结合路径和社区的搜索"},
        ],
        "maxGraphDepth": 4,
        "maxNodes": 200,
        "raptorLevels": 5,
    }
