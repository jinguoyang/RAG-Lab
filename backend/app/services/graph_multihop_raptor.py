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


def graph_retrieval_multihop(
    query: str,
    graph_depth: int = 2,
    max_nodes: int = 50,
    path_mode: str = "entity-path",
) -> GraphRetrievalResult:
    """返回图多跳能力的显式降级结果。

    真实生产检索应通过 Neo4jGraphRetrievalProvider 执行。此函数不再
    伪造节点和路径，避免测试或上层链路把 mock 数据误判为真实图证据。

    Args:
        query: 查询
        graph_depth: 图深度
        max_nodes: 最大节点数
        path_mode: 路径模式

    Returns:
        无 Provider 时的显式降级结果
    """
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
