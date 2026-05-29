"""B-326: Graph 多跳检索测试。

验证图多跳检索、RAPTOR 索引构建和搜索功能。
"""

import pytest

from app.services.graph_multihop_raptor import (
    GraphRetrievalResult,
    RaptorIndex,
    SummaryNode,
    build_raptor_index,
    get_graph_multihop_info,
    graph_retrieval_multihop,
    search_raptor_index,
)


class TestGraphRetrievalMultihop:
    """图多跳检索测试。"""

    def test_graph_retrieval_basic(self):
        """应能执行图检索。"""
        result = graph_retrieval_multihop("test query", graph_depth=2)
        assert result is not None
        assert len(result.nodes) > 0
        assert len(result.edges) > 0

    def test_graph_retrieval_respects_depth(self):
        """应受 graph_depth 约束。"""
        result_depth1 = graph_retrieval_multihop("test", graph_depth=1)
        result_depth2 = graph_retrieval_multihop("test", graph_depth=2)
        # 更深的图应该有更多节点
        assert len(result_depth2.nodes) >= len(result_depth1.nodes)

    def test_graph_retrieval_respects_max_nodes(self):
        """应受 max_nodes 约束。"""
        result = graph_retrieval_multihop("test", graph_depth=3, max_nodes=5)
        assert len(result.nodes) <= 5

    def test_graph_retrieval_has_paths(self):
        """应返回路径。"""
        result = graph_retrieval_multihop("test", graph_depth=2)
        assert len(result.paths) > 0
        assert result.paths[0].length > 0

    def test_graph_retrieval_permission_status(self):
        """应返回权限状态。"""
        result = graph_retrieval_multihop("test")
        assert result.permission_status in ["ok", "partial", "denied"]

    def test_graph_retrieval_metadata(self):
        """应包含元数据。"""
        result = graph_retrieval_multihop("test", graph_depth=2, max_nodes=10)
        assert "graphDepth" in result.metadata
        assert "maxNodes" in result.metadata


class TestBuildRaptorIndex:
    """RAPTOR 索引构建测试。"""

    def test_build_raptor_index_basic(self):
        """应能构建 RAPTOR 索引。"""
        chunks = [
            {"chunkId": "chunk_0", "content": "Content 0", "documentId": "doc_0"},
            {"chunkId": "chunk_1", "content": "Content 1", "documentId": "doc_0"},
            {"chunkId": "chunk_2", "content": "Content 2", "documentId": "doc_0"},
            {"chunkId": "chunk_3", "content": "Content 3", "documentId": "doc_0"},
        ]
        index = build_raptor_index(chunks, max_levels=3)
        assert index is not None
        assert index.document_id == "doc_0"
        assert len(index.summary_nodes) > 0

    def test_build_raptor_index_has_levels(self):
        """应包含多个层级。"""
        chunks = [
            {"chunkId": f"chunk_{i}", "content": f"Content {i}", "documentId": "doc_0"}
            for i in range(8)
        ]
        index = build_raptor_index(chunks, max_levels=3)
        levels = {node.level for node in index.summary_nodes}
        assert 0 in levels  # 叶子节点
        assert len(levels) > 1

    def test_build_raptor_index_empty_chunks(self):
        """空 Chunk 应返回空索引。"""
        index = build_raptor_index([])
        assert index.levels == 0
        assert len(index.summary_nodes) == 0

    def test_build_raptor_index_single_chunk(self):
        """单个 Chunk 应只有一层。"""
        chunks = [{"chunkId": "chunk_0", "content": "Content", "documentId": "doc_0"}]
        index = build_raptor_index(chunks, max_levels=3)
        assert len(index.summary_nodes) == 1
        assert index.summary_nodes[0].level == 0

    def test_build_raptor_index_source_chunk_ids(self):
        """摘要节点应包含源 Chunk ID。"""
        chunks = [
            {"chunkId": "chunk_0", "content": "Content 0", "documentId": "doc_0"},
            {"chunkId": "chunk_1", "content": "Content 1", "documentId": "doc_0"},
        ]
        index = build_raptor_index(chunks, max_levels=2)
        leaf_nodes = [n for n in index.summary_nodes if n.level == 0]
        assert len(leaf_nodes) == 2
        assert "chunk_0" in leaf_nodes[0].source_chunk_ids


class TestSearchRaptorIndex:
    """RAPTOR 索引搜索测试。"""

    def test_search_raptor_index_basic(self):
        """应能搜索 RAPTOR 索引。"""
        chunks = [
            {"chunkId": "chunk_0", "content": "RAG system", "documentId": "doc_0"},
            {"chunkId": "chunk_1", "content": "Vector database", "documentId": "doc_0"},
        ]
        index = build_raptor_index(chunks, max_levels=2)
        results = search_raptor_index(index, "RAG")
        assert len(results) > 0

    def test_search_raptor_index_no_match(self):
        """不匹配时应返回空列表。"""
        chunks = [
            {"chunkId": "chunk_0", "content": "Content", "documentId": "doc_0"},
        ]
        index = build_raptor_index(chunks, max_levels=2)
        results = search_raptor_index(index, "nonexistent")
        assert len(results) == 0

    def test_search_raptor_index_respects_max_results(self):
        """应受 max_results 约束。"""
        chunks = [
            {"chunkId": f"chunk_{i}", "content": f"Content {i}", "documentId": "doc_0"}
            for i in range(10)
        ]
        index = build_raptor_index(chunks, max_levels=3)
        results = search_raptor_index(index, "Content", max_results=3)
        assert len(results) <= 3


class TestGetGraphMultihopInfo:
    """获取图多跳信息测试。"""

    def test_get_graph_multihop_info(self):
        """应返回图多跳信息。"""
        info = get_graph_multihop_info()
        assert "pathModes" in info
        assert "maxGraphDepth" in info
        assert "maxNodes" in info
        assert "raptorLevels" in info
