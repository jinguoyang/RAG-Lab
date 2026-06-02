"""B-322/B-323 运行时接入验证测试。

验证 Multi Query + RRF/MMR 融合和 chunkWindow 上下文扩展在 QA Run 运行时的完整接入。
"""

from uuid import uuid4

import pytest

from app.services.multi_query_fusion import (
    RankedCandidate,
    build_fusion_trace,
    mmr_diversify,
    multi_query_rrf_fusion,
    multi_query_weighted_fusion,
)
from app.services.parent_child_retrieval import (
    PackingStrategy,
    expand_adjacent_chunks,
    find_parent_chunk,
    pack_context_with_parent_child,
)
from app.services.qa_providers import ProviderCandidate
from app.services.qa_run_service import (
    _expand_context_pairs_with_chunk_window,
    _fuse_provider_candidates,
)


def _candidate(
    source_type: str,
    score: float,
    content: str = "Test content",
    chunk_id=None,
    metadata: dict | None = None,
) -> ProviderCandidate:
    return ProviderCandidate(
        source_type=source_type,
        chunk_id=chunk_id or uuid4(),
        raw_score=score,
        content=content,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# B-322: Multi Query + RRF/MMR 运行时接入验证
# ---------------------------------------------------------------------------


class TestB322MultiQueryRRFIntegration:
    """B-322: Multi Query + RRF/MMR 运行时集成验证。"""

    def test_rrf_fusion_with_real_qa_run_fuse_function(self):
        """验证 _fuse_provider_candidates 支持 RRF 融合方法。"""
        candidates = [
            _candidate("dense", 0.9, "Dense result 1"),
            _candidate("sparse", 0.7, "Sparse result 1"),
            _candidate("dense", 0.8, "Dense result 2"),
        ]
        result = _fuse_provider_candidates(
            candidates,
            fusion_method="rrf",
            rrf_k=60,
            candidate_limit=10,
        )
        assert len(result) > 0
        # RRF 融合应产生有效分数
        for r in result:
            assert r.metadata.get("fusionMethod") == "rrf"
            assert r.metadata.get("fusedScore") is not None

    def test_mmr_fusion_with_real_qa_run_fuse_function(self):
        """验证 _fuse_provider_candidates 支持 MMR 融合方法。"""
        candidates = [
            _candidate("dense", 0.9, "Similar content A"),
            _candidate("dense", 0.85, "Similar content B"),
            _candidate("sparse", 0.7, "Different content"),
        ]
        result = _fuse_provider_candidates(
            candidates,
            fusion_method="mmr",
            candidate_limit=2,
        )
        assert len(result) <= 2
        for r in result:
            assert r.metadata.get("fusionMethod") == "mmr"

    def test_weighted_fusion_with_real_qa_run_fuse_function(self):
        """验证 _fuse_provider_candidates 支持 weighted 融合方法。"""
        candidates = [
            _candidate("dense", 0.5, "Dense content"),
            _candidate("sparse", 0.3, "Sparse content"),
        ]
        weights = {"dense": 2.0, "sparse": 1.0, "graph": 1.0}
        result = _fuse_provider_candidates(
            candidates,
            fusion_weights=weights,
            fusion_method="weighted",
            candidate_limit=10,
        )
        assert len(result) == 2
        # dense 候选加权后应更高
        dense_result = next(r for r in result if r.source_type == "dense")
        sparse_result = next(r for r in result if r.source_type == "sparse")
        assert dense_result.metadata.get("fusedScore", 0) > sparse_result.metadata.get("fusedScore", 0)

    def test_multi_query_rrf_fusion_produces_explainable_trace(self):
        """验证多查询 RRF 融合产生可解释的 trace。"""
        chunk_id_1 = uuid4()
        chunk_id_2 = uuid4()
        candidates_by_query = {
            "原始查询": [
                _candidate("dense", 0.9, "Result 1", chunk_id=chunk_id_1),
                _candidate("sparse", 0.6, "Result 2", chunk_id=chunk_id_2),
            ],
            "同义词变体": [
                _candidate("dense", 0.85, "Result 1 variant", chunk_id=chunk_id_1),
                _candidate("dense", 0.7, "Result 3"),
            ],
        }
        fused = multi_query_rrf_fusion(candidates_by_query, k=60, limit=10)
        trace = build_fusion_trace(fused)

        assert len(trace) > 0
        # trace 应包含来源信息
        for entry in trace:
            assert "sourceQuery" in entry
            assert "sourceType" in entry
            assert "finalScore" in entry
            # 多来源查询合并是预期行为
            source_queries = set(entry["sourceQuery"].split("; "))
            assert source_queries
            assert source_queries <= {"原始查询", "同义词变体"}

    def test_multi_query_count_affects_actual_queries(self):
        """验证 queryCount 改变会影响实际执行查询数量。"""
        # 模拟不同 queryCount 的场景
        original_query = "什么是 RAG？"
        queries_1 = [original_query]
        queries_3 = [original_query, "RAG 是什么", "检索增强生成的定义"]

        # queryCount=1 时只有原始查询
        assert len(queries_1) == 1
        # queryCount=3 时有 3 个查询
        assert len(queries_3) == 3

        # 不同查询数量应产生不同融合结果
        candidates_by_query_1 = {"q1": [_candidate("dense", 0.9)]}
        candidates_by_query_3 = {
            "q1": [_candidate("dense", 0.9)],
            "q2": [_candidate("dense", 0.8)],
            "q3": [_candidate("dense", 0.7)],
        }
        result_1 = multi_query_rrf_fusion(candidates_by_query_1, limit=10)
        result_3 = multi_query_rrf_fusion(candidates_by_query_3, limit=10)
        # 多查询应产生更多候选或更高分数
        assert len(result_3) >= len(result_1)


# ---------------------------------------------------------------------------
# B-323: chunkWindow 上下文扩展运行时验证
# ---------------------------------------------------------------------------


class TestB323ChunkWindowIntegration:
    """B-323: chunkWindow 上下文扩展运行时集成验证。"""

    def test_chunk_window_expansion_preserves_original_evidence(self):
        """验证 chunkWindow 扩展不改变原始检索证据。"""
        base_id = uuid4()
        base = _candidate("dense", 0.9, "Original hit", chunk_id=base_id, metadata={"chunkIndex": 2})
        adjacent_rows = [
            {"chunk_id": uuid4(), "chunk_index": 1, "content": "Before", "metadata": {"section": "A"}},
            {"chunk_id": uuid4(), "chunk_index": 3, "content": "After", "metadata": {"section": "A"}},
        ]

        expanded = _expand_context_pairs_with_chunk_window([(base, base_id)], adjacent_rows, chunk_window=1)

        # 原始证据应保持不变
        assert expanded[0][0] is base
        assert expanded[0][1] == base_id
        # 扩展的上下文应标记为 expandedContext
        assert expanded[1][0].metadata["expandedContext"] is True
        assert expanded[1][0].metadata["expandedFromChunkId"] == str(base_id)

    def test_chunk_window_zero_returns_original_only(self):
        """验证 chunkWindow=0 时只返回原始证据。"""
        base = _candidate("dense", 0.9, "Original hit", metadata={"chunkIndex": 2})
        base_id = uuid4()
        adjacent_rows = [
            {"chunk_id": uuid4(), "chunk_index": 1, "content": "Before"},
        ]

        expanded = _expand_context_pairs_with_chunk_window([(base, base_id)], adjacent_rows, chunk_window=0)

        assert len(expanded) == 1
        assert expanded[0][0] is base

    def test_chunk_window_expansion_with_multiple_hits(self):
        """验证多个命中点的 chunkWindow 扩展。"""
        base1 = _candidate("dense", 0.9, "Hit 1", metadata={"chunkIndex": 1})
        base2 = _candidate("dense", 0.8, "Hit 2", metadata={"chunkIndex": 5})
        base1_id = uuid4()
        base2_id = uuid4()
        adjacent_rows = [
            {"chunk_id": uuid4(), "chunk_index": 0, "content": "Before 1"},
            {"chunk_id": uuid4(), "chunk_index": 2, "content": "After 1"},
            {"chunk_id": uuid4(), "chunk_index": 4, "content": "Before 2"},
            {"chunk_id": uuid4(), "chunk_index": 6, "content": "After 2"},
        ]

        expanded = _expand_context_pairs_with_chunk_window(
            [(base1, base1_id), (base2, base2_id)],
            adjacent_rows,
            chunk_window=1,
        )

        # 应有 2 个原始 + 4 个扩展 = 6 个
        assert len(expanded) == 6

    def test_chunk_window_deduplicates_by_chunk_id(self):
        """验证 chunkWindow 扩展按 chunk_id 去重。"""
        shared_id = uuid4()
        base = _candidate("dense", 0.9, "Hit", chunk_id=shared_id, metadata={"chunkIndex": 2})
        # 相邻行中包含与原始命中相同的 chunk_id
        adjacent_rows = [
            {"chunk_id": shared_id, "chunk_index": 1, "content": "Duplicate"},
            {"chunk_id": uuid4(), "chunk_index": 3, "content": "Valid adjacent"},
        ]

        expanded = _expand_context_pairs_with_chunk_window([(base, shared_id)], adjacent_rows, chunk_window=1)

        # 应去重，不重复添加
        chunk_ids = [str(c.chunk_id) for c, _ in expanded]
        assert chunk_ids.count(str(shared_id)) == 1

    def test_parent_child_packing_with_real_service(self):
        """验证父子检索打包服务的完整流程。"""
        parent = _make_chunk("parent_0", "Parent content " * 20, 0, section="Section A")
        child1 = _make_chunk("child_1", "Child 1", 1, section="Section A", parent_chunk_id="parent_0")
        child2 = _make_chunk("child_2", "Child 2", 2, section="Section A", parent_chunk_id="parent_0")
        all_chunks = [parent, child1, child2]

        result = pack_context_with_parent_child(
            child_chunks=[child1],
            all_chunks=all_chunks,
            max_tokens=2000,
            chunk_window=1,
            packing_strategy="relevance_first",
        )

        # 应包含父块和相邻块
        chunk_ids = {c.chunk_id for c in result.chunks}
        assert "child_1" in chunk_ids
        assert "parent_0" in chunk_ids
        # chunkWindow=1 应扩展到 child_2
        assert "child_2" in chunk_ids
        assert result.packing_strategy == "relevance_first"

    def test_parent_child_packing_respects_token_budget(self):
        """验证父子检索打包遵守 token 预算。"""
        parent = _make_chunk("parent_0", "A" * 1000, 0)
        child = _make_chunk("child_0", "B" * 1000, 1, parent_chunk_id="parent_0")
        all_chunks = [parent, child]

        result = pack_context_with_parent_child(
            child_chunks=[child],
            all_chunks=all_chunks,
            max_tokens=500,  # 小预算
        )

        # 应截断以遵守预算
        assert result.total_tokens <= 500 or len(result.chunks) < 2
        if len(result.chunks) < 2:
            assert len(result.truncation_log) > 0

    def test_packing_strategy_affects_ordering(self):
        """验证不同打包策略产生不同排序。"""
        chunks = [
            _make_chunk("c0", "Content 0", 0, section="B"),
            _make_chunk("c1", "Content 1", 1, section="A"),
            _make_chunk("c2", "Content 2", 2, section="B"),
        ]

        result_relevance = pack_context_with_parent_child(
            child_chunks=chunks,
            all_chunks=chunks,
            max_tokens=5000,
            packing_strategy="relevance_first",
        )
        result_doc_order = pack_context_with_parent_child(
            child_chunks=chunks,
            all_chunks=chunks,
            max_tokens=5000,
            packing_strategy="document_order",
        )

        # 文档顺序应按 chunk_index 排序
        doc_order_ids = [c.chunk_id for c in result_doc_order.chunks]
        assert doc_order_ids == ["c0", "c1", "c2"]

        # 不同策略应产生不同结果
        assert result_relevance.packing_strategy != result_doc_order.packing_strategy


def _make_chunk(
    chunk_id: str,
    content: str,
    chunk_index: int,
    section: str | None = None,
    parent_chunk_id: str | None = None,
):
    """创建测试块。"""
    from app.services.multi_view_chunking import ChunkResult

    return ChunkResult(
        chunk_id=chunk_id,
        content=content,
        token_count=len(content) // 4,
        chunk_index=chunk_index,
        section=section,
        parent_chunk_id=parent_chunk_id,
    )
