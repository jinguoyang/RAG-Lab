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
from typing import Any


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


def _create_mock_graph_node(node_id: str, name: str, node_type: str) -> GraphNode:
    """创建模拟图节点。"""
    return GraphNode(
        node_id=node_id,
        name=name,
        node_type=node_type,
        properties={"mock": True},
    )


def _create_mock_graph_edge(
    edge_id: str,
    source_id: str,
    target_id: str,
    relation_type: str,
) -> GraphEdge:
    """创建模拟图边。"""
    return GraphEdge(
        edge_id=edge_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        properties={"mock": True},
    )


def graph_retrieval_multihop(
    query: str,
    graph_depth: int = 2,
    max_nodes: int = 50,
    path_mode: str = "entity-path",
) -> GraphRetrievalResult:
    """执行多跳图检索。

    ⚠️ 当前为模拟实现，返回占位数据。
    生产环境应使用 Neo4jGraphRetrievalProvider 执行真实图查询。

    Args:
        query: 查询
        graph_depth: 图深度
        max_nodes: 最大节点数
        path_mode: 路径模式

    Returns:
        图检索结果（当前为模拟数据）
    """
    import warnings
    warnings.warn(
        "graph_retrieval_multihop 使用模拟数据，生产环境请使用 Neo4jGraphRetrievalProvider",
        UserWarning,
        stacklevel=2,
    )
    # 模拟实现：创建简单的图结构
    nodes = []
    edges = []
    paths = []

    # 创建起始节点
    start_node = _create_mock_graph_node("start", query[:50], "Query")
    nodes.append(start_node)

    # 按深度扩展
    for depth in range(graph_depth):
        for i in range(min(3, max_nodes // graph_depth)):
            node_id = f"node_{depth}_{i}"
            node = _create_mock_graph_node(
                node_id,
                f"Entity {depth}.{i}",
                "Entity",
            )
            nodes.append(node)

            # 创建边
            source_id = "start" if depth == 0 else f"node_{depth-1}_{i}"
            edge = _create_mock_graph_edge(
                f"edge_{depth}_{i}",
                source_id,
                node_id,
                "RELATED_TO",
            )
            edges.append(edge)

    # 创建路径
    if nodes:
        path = GraphPath(
            path_id="path_0",
            nodes=nodes[:min(5, len(nodes))],
            edges=edges[:min(4, len(edges))],
            length=min(5, len(nodes)),
            summary=f"路径包含 {min(5, len(nodes))} 个节点",
        )
        paths.append(path)

    return GraphRetrievalResult(
        paths=paths,
        nodes=nodes[:max_nodes],
        edges=edges,
        associated_chunk_ids=[],
        permission_status="ok",
        metadata={
            "graphDepth": graph_depth,
            "maxNodes": max_nodes,
            "pathMode": path_mode,
        },
    )


def build_raptor_index(
    chunks: list[dict[str, Any]],
    max_levels: int = 3,
    use_llm: bool = False,
) -> RaptorIndex:
    """构建 RAPTOR 层级摘要索引。

    ⚠️ 当前为简化实现，仅做文本截断和拼接。
    生产环境应设置 use_llm=True 并接入 LLM Provider 生成真正摘要。

    Args:
        chunks: Chunk 列表
        max_levels: 最大层级数
        use_llm: 是否使用 LLM 生成摘要（当前未实现）

    Returns:
        RAPTOR 索引
    """
    if use_llm:
        import warnings
        warnings.warn(
            "RAPTOR LLM 摘要尚未实现，当前使用文本截断作为占位",
            UserWarning,
            stacklevel=2,
        )
    if not chunks:
        return RaptorIndex(
            document_id="empty",
            levels=0,
            summary_nodes=[],
        )

    summary_nodes = []
    document_id = chunks[0].get("documentId", "unknown")

    # Level 0: 叶子节点（原始 Chunk）
    leaf_nodes = []
    for i, chunk in enumerate(chunks):
        summary_id = f"summary_0_{i}"
        node = SummaryNode(
            summary_id=summary_id,
            level=0,
            content=chunk.get("content", "")[:200],
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

            node = SummaryNode(
                summary_id=summary_id,
                level=level,
                content=combined_content[:300],
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
