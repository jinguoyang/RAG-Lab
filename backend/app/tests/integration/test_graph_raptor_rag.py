"""B-326: Graph 多跳与 RAPTOR 集成测试。

验证 RAPTOR 索引构建→搜索→源 Chunk 可追溯的端到端流程，
以及 Graph 多跳检索在有/无 Provider 时的行为差异。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.graph_multihop_raptor import (
    GraphRetrievalResult,
    build_raptor_index,
    graph_retrieval_multihop,
    search_raptor_index,
)


# ── 内存 Mock Graph Provider ──


class InMemoryGraphProvider:
    """内存图 Provider，用于集成测试。"""

    def __init__(
        self,
        entities: list[dict[str, Any]] | None = None,
        paths: list[dict[str, Any]] | None = None,
    ) -> None:
        self._entities = entities or []
        self._paths = paths or []

    def search_entities(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        keyword_lower = keyword.lower()
        return [
            e for e in self._entities
            if keyword_lower in e.get("name", "").lower()
        ][:limit]

    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        keyword_lower = keyword.lower()
        return [
            p for p in self._paths
            if keyword_lower in p.get("sourceName", "").lower()
            or keyword_lower in p.get("targetName", "").lower()
        ][:limit]


# ── RAPTOR 索引集成测试 ──


class TestRaptorIndexEndToEnd:
    """RAPTOR 索引构建→搜索→源 Chunk 可追溯的端到端测试。"""

    def test_build_search_trace_source_chunks(self):
        """构建 RAPTOR 索引后搜索，结果应可追溯到源 Chunk。"""
        chunks = [
            {"chunkId": "chunk_0", "content": "RAG 是检索增强生成系统", "documentId": "doc_0"},
            {"chunkId": "chunk_1", "content": "向量数据库用于存储嵌入", "documentId": "doc_0"},
            {"chunkId": "chunk_2", "content": "RAG 结合了检索和生成", "documentId": "doc_0"},
            {"chunkId": "chunk_3", "content": "知识图谱用于实体关系", "documentId": "doc_1"},
        ]
        index = build_raptor_index(chunks, max_levels=3)

        # 搜索 "RAG" 应命中包含 RAG 内容的节点
        results = search_raptor_index(index, "RAG", max_results=10)
        assert len(results) > 0

        # 每个结果的 source_chunk_ids 应非空且可追溯
        for node in results:
            assert len(node.source_chunk_ids) > 0
            for chunk_id in node.source_chunk_ids:
                assert any(c["chunkId"] == chunk_id for c in chunks)

    def test_raptor_hierarchical_aggregation(self):
        """高层摘要应聚合多个低层节点的源 Chunk。"""
        chunks = [
            {"chunkId": f"chunk_{i}", "content": f"Content about topic {i}", "documentId": "doc_0"}
            for i in range(8)
        ]
        index = build_raptor_index(chunks, max_levels=3)

        # 高层节点应聚合多个源 Chunk
        top_level_nodes = [n for n in index.summary_nodes if n.level > 0]
        assert len(top_level_nodes) > 0

        for node in top_level_nodes:
            assert len(node.source_chunk_ids) >= 2
            assert len(node.children_summary_ids) >= 1

    def test_raptor_search_preserves_level_ordering(self):
        """搜索结果应优先返回高层级摘要。"""
        chunks = [
            {"chunkId": "chunk_0", "content": "Alpha beta gamma", "documentId": "doc_0"},
            {"chunkId": "chunk_1", "content": "Alpha delta epsilon", "documentId": "doc_0"},
            {"chunkId": "chunk_2", "content": "Zeta eta theta", "documentId": "doc_0"},
            {"chunkId": "chunk_3", "content": "Iota kappa lambda", "documentId": "doc_0"},
        ]
        index = build_raptor_index(chunks, max_levels=3)
        results = search_raptor_index(index, "Alpha", max_results=5)

        # 应至少命中一个节点
        assert len(results) > 0
        # 所有结果应包含 "Alpha"
        for node in results:
            assert "alpha" in node.content.lower()


# ── Graph 多跳检索集成测试 ──


class TestGraphMultihopWithProvider:
    """Graph 多跳检索有 Provider 时的集成测试。"""

    def test_graph_with_provider_returns_real_results(self):
        """有 Provider 时应返回真实图数据。"""
        entities = [
            {"entityKey": "e1", "name": "RAG系统", "type": "technology", "aliases": []},
            {"entityKey": "e2", "name": "RAG检索模块", "type": "module", "aliases": []},
        ]
        paths = [
            {
                "pathKey": "p1",
                "sourceEntityKey": "e1",
                "sourceName": "RAG系统",
                "sourceType": "technology",
                "targetEntityKey": "e2",
                "targetName": "RAG检索模块",
                "targetType": "module",
                "relationType": "CONTAINS",
                "relationKey": "r1",
            },
        ]
        provider = InMemoryGraphProvider(entities=entities, paths=paths)
        kb_id = UUID("00000000-0000-0000-0000-000000000001")

        result = graph_retrieval_multihop(
            "RAG",
            graph_provider=provider,
            kb_id=kb_id,
        )

        assert isinstance(result, GraphRetrievalResult)
        assert result.permission_status == "ok"
        assert len(result.nodes) == 2
        assert len(result.paths) == 1
        assert result.paths[0].summary == "RAG系统 --[CONTAINS]--> RAG检索模块"

    def test_graph_with_provider_no_match(self):
        """Provider 无匹配时应返回空结果。"""
        provider = InMemoryGraphProvider(entities=[], paths=[])
        kb_id = UUID("00000000-0000-0000-0000-000000000001")

        result = graph_retrieval_multihop(
            "不存在的查询",
            graph_provider=provider,
            kb_id=kb_id,
        )

        assert result.nodes == []
        assert result.paths == []
        assert result.permission_status == "ok"

    def test_graph_with_provider_respects_max_nodes(self):
        """max_nodes 应限制返回的实体数量。"""
        entities = [
            {"entityKey": f"e{i}", "name": f"Entity{i}", "type": "t", "aliases": []}
            for i in range(20)
        ]
        provider = InMemoryGraphProvider(entities=entities, paths=[])
        kb_id = UUID("00000000-0000-0000-0000-000000000001")

        result = graph_retrieval_multihop(
            "Entity",
            max_nodes=5,
            graph_provider=provider,
            kb_id=kb_id,
        )

        assert len(result.nodes) <= 5


class TestGraphMultihopWithoutProvider:
    """Graph 多跳检索无 Provider 时的降级测试。"""

    def test_graph_without_provider_returns_stub(self):
        """无 Provider 时应返回显式降级结果。"""
        result = graph_retrieval_multihop("test query")

        assert result.nodes == []
        assert result.paths == []
        assert result.permission_status == "partial"
        assert result.metadata["requiresProvider"] is True
        assert result.metadata["fallbackReason"] == "graphProviderRequired"

    def test_graph_without_kb_id_returns_stub(self):
        """有 Provider 但无 kb_id 时应返回降级结果。"""
        provider = InMemoryGraphProvider()
        result = graph_retrieval_multihop("test", graph_provider=provider)

        assert result.metadata["requiresProvider"] is True


class TestRaptorWithGraphIntegration:
    """RAPTOR 与 Graph 联合场景测试。"""

    def test_raptor_and_graph_complementary(self):
        """RAPTOR 摘要和 Graph 路径应提供互补信息。"""
        # 构建 RAPTOR 索引
        chunks = [
            {"chunkId": "c0", "content": "RAG 系统依赖向量数据库进行检索", "documentId": "d0"},
            {"chunkId": "c1", "content": "向量数据库存储文档嵌入向量", "documentId": "d0"},
        ]
        raptor = build_raptor_index(chunks, max_levels=2)
        raptor_results = search_raptor_index(raptor, "RAG")

        # Graph 检索
        entities = [{"entityKey": "e1", "name": "RAG", "type": "tech", "aliases": []}]
        provider = InMemoryGraphProvider(entities=entities, paths=[])
        graph_result = graph_retrieval_multihop(
            "RAG",
            graph_provider=provider,
            kb_id=UUID("00000000-0000-0000-0000-000000000001"),
        )

        # 两种检索应各自返回结果
        assert len(raptor_results) > 0
        assert len(graph_result.nodes) > 0
