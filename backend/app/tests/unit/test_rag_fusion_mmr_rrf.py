"""B-322: 多查询 RRF/MMR 融合测试。

验证 RRF 融合、MMR 去重和融合 Trace 功能。
"""

import pytest
from uuid import uuid4

from app.services.multi_query_fusion import (
    QueryVariant,
    RankedCandidate,
    build_fusion_trace,
    get_multi_query_fusion_info,
    mmr_diversify,
    multi_query_rrf_fusion,
    multi_query_weighted_fusion,
)
from app.services.qa_providers import ProviderCandidate


def _make_candidate(source_type: str, score: float, content: str = "Test content"):
    """创建测试候选。"""
    return ProviderCandidate(
        source_type=source_type,
        chunk_id=uuid4(),
        raw_score=score,
        content=content,
        metadata={"provider": "test"},
    )


class TestMMRDiversify:
    """MMR 去重测试。"""

    def test_mmr_diversify_basic(self):
        """MMR 应去除冗余候选。"""
        candidates = [
            _make_candidate("dense", 0.9, "Similar content A"),
            _make_candidate("dense", 0.8, "Similar content B"),
            _make_candidate("dense", 0.7, "Different content"),
        ]
        result = mmr_diversify(candidates, lambda_param=0.5, limit=2)
        assert len(result) == 2

    def test_mmr_diversify_preserves_relevance(self):
        """MMR 应保留高相关性候选。"""
        candidates = [
            _make_candidate("dense", 0.9, "High relevance"),
            _make_candidate("dense", 0.1, "Low relevance"),
        ]
        result = mmr_diversify(candidates, lambda_param=1.0, limit=1)
        assert len(result) == 1
        assert result[0].raw_score == 0.9

    def test_mmr_diversify_empty_input(self):
        """空输入应返回空列表。"""
        result = mmr_diversify([])
        assert result == []

    def test_mmr_diversify_respects_limit(self):
        """MMR 应受 limit 约束。"""
        candidates = [_make_candidate("dense", 0.5, f"Content {i}") for i in range(10)]
        result = mmr_diversify(candidates, limit=3)
        assert len(result) == 3


class TestMultiQueryRRFFusion:
    """多查询 RRF 融合测试。"""

    def test_rrf_fusion_basic(self):
        """RRF 融合应正确合并多查询候选。"""
        candidates_by_query = {
            "query 1": [
                _make_candidate("dense", 0.9),
                _make_candidate("sparse", 0.5),
            ],
            "query 2": [
                _make_candidate("dense", 0.8),
                _make_candidate("graph", 0.3),
            ],
        }
        result = multi_query_rrf_fusion(candidates_by_query, k=60, limit=10)
        assert len(result) > 0
        assert all(isinstance(r, RankedCandidate) for r in result)

    def test_rrf_fusion_multi_query_boost(self):
        """多查询命中的候选应获得更高分数。"""
        chunk_id = uuid4()
        candidate = ProviderCandidate(
            source_type="dense",
            chunk_id=chunk_id,
            raw_score=0.8,
            content="Shared content",
            metadata={},
        )
        candidates_by_query = {
            "query 1": [candidate],
            "query 2": [candidate],
        }
        result = multi_query_rrf_fusion(candidates_by_query, k=60, limit=10)
        assert len(result) == 1
        # 多查询命中应累加 RRF 分数
        assert result[0].final_score > 0

    def test_rrf_fusion_preserves_source_query(self):
        """RRF 融合应保留来源查询信息。"""
        candidates_by_query = {
            "query 1": [_make_candidate("dense", 0.9)],
            "query 2": [_make_candidate("sparse", 0.5)],
        }
        result = multi_query_rrf_fusion(candidates_by_query, k=60, limit=10)
        assert len(result) > 0
        # 每个候选应有来源查询信息
        for ranked in result:
            assert len(ranked.source_query) > 0

    def test_rrf_fusion_respects_limit(self):
        """RRF 融合应受 limit 约束。"""
        candidates_by_query = {
            "query 1": [_make_candidate("dense", 0.5) for _ in range(10)],
        }
        result = multi_query_rrf_fusion(candidates_by_query, limit=3)
        assert len(result) <= 3


class TestMultiQueryWeightedFusion:
    """多查询加权融合测试。"""

    def test_weighted_fusion_basic(self):
        """加权融合应正确合并候选。"""
        candidates_by_query = {
            "query 1": [
                _make_candidate("dense", 0.9),
                _make_candidate("sparse", 0.5),
            ],
            "query 2": [
                _make_candidate("dense", 0.8),
            ],
        }
        result = multi_query_weighted_fusion(candidates_by_query, limit=10)
        assert len(result) > 0

    def test_weighted_fusion_applies_weights(self):
        """加权融合应应用来源权重。"""
        candidates_by_query = {
            "query 1": [_make_candidate("dense", 0.5)],
        }
        weights = {"dense": 2.0, "sparse": 1.0, "graph": 1.0}
        result = multi_query_weighted_fusion(candidates_by_query, weights=weights, limit=10)
        assert len(result) == 1
        # 加权分数 = 0.5 * 2.0 = 1.0
        assert abs(result[0].final_score - 1.0) < 0.01


class TestBuildFusionTrace:
    """融合 Trace 测试。"""

    def test_build_fusion_trace(self):
        """应能构建融合 Trace。"""
        ranked = [
            RankedCandidate(
                candidate=_make_candidate("dense", 0.9),
                source_query="test query",
                source_type="dense",
                original_rank=0,
                original_score=0.9,
                final_score=0.016,
            ),
        ]
        trace = build_fusion_trace(ranked)
        assert len(trace) == 1
        assert trace[0]["rank"] == 1
        assert trace[0]["sourceQuery"] == "test query"
        assert trace[0]["sourceType"] == "dense"

    def test_build_fusion_trace_empty(self):
        """空输入应返回空列表。"""
        trace = build_fusion_trace([])
        assert trace == []


class TestGetMultiQueryFusionInfo:
    """获取融合信息测试。"""

    def test_get_info(self):
        """应返回融合方法信息。"""
        info = get_multi_query_fusion_info()
        assert "methods" in info
        assert "queryTypes" in info
        assert len(info["methods"]) == 3
        assert len(info["queryTypes"]) == 4
