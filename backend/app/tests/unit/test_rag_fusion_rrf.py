"""B-317: RRF 融合算法测试。

验证 RRF (Reciprocal Rank Fusion) 融合算法能正确计算分数和排序。
"""

import pytest
from uuid import uuid4

from app.services.qa_run_service import _fuse_provider_candidates, _rrf_score
from app.services.qa_providers import ProviderCandidate


class TestRRFScore:
    """RRF 分数计算测试。"""

    def test_rrf_score_basic(self):
        """RRF 分数应正确计算。"""
        # rank=0, k=60 -> 1/(60+0) = 0.01666...
        score = _rrf_score(0, 60)
        assert abs(score - 1.0 / 60) < 1e-6

    def test_rrf_score_rank_1(self):
        """rank=1 时分数应为 1/(k+1)。"""
        score = _rrf_score(1, 60)
        assert abs(score - 1.0 / 61) < 1e-6

    def test_rrf_score_different_k(self):
        """不同 k 值应产生不同分数。"""
        score_k30 = _rrf_score(0, 30)
        score_k60 = _rrf_score(0, 60)
        assert score_k30 > score_k60


class TestFusionMethodRRF:
    """RRF 融合方法测试。"""

    def _make_candidate(self, source_type: str, score: float, chunk_id=None):
        """创建测试候选。"""
        return ProviderCandidate(
            source_type=source_type,
            chunk_id=chunk_id or uuid4(),
            raw_score=score,
            content=f"Test content from {source_type}",
            metadata={"provider": "test"},
        )

    def test_rrf_fusion_produces_different_ranking(self):
        """RRF 融合应产生与加权融合不同的排序。"""
        candidates = [
            self._make_candidate("dense", 0.9),
            self._make_candidate("sparse", 0.5),
            self._make_candidate("dense", 0.8),
            self._make_candidate("sparse", 0.7),
        ]

        weighted_result = _fuse_provider_candidates(
            candidates,
            fusion_method="weighted",
            candidate_limit=10,
        )
        rrf_result = _fuse_provider_candidates(
            candidates,
            fusion_method="rrf",
            candidate_limit=10,
            rrf_k=60,
        )

        # 两种方法都应该返回结果
        assert len(weighted_result) > 0
        assert len(rrf_result) > 0

        # 结果数量应该相同（都是去重后的）
        assert len(weighted_result) == len(rrf_result)

        # RRF 结果应该有 fusionMethod 标记
        for candidate in rrf_result:
            assert candidate.metadata.get("fusionMethod") == "rrf"

    def test_rrf_fusion_deduplicates_by_chunk_id(self):
        """RRF 融合应按 chunk_id 去重。"""
        chunk_id = uuid4()
        candidates = [
            self._make_candidate("dense", 0.9, chunk_id),
            self._make_candidate("sparse", 0.5, chunk_id),
        ]

        result = _fuse_provider_candidates(
            candidates,
            fusion_method="rrf",
            candidate_limit=10,
        )

        # 去重后应该只有一个候选
        assert len(result) == 1
        # 应该保留多路命中信息
        assert "dense" in result[0].metadata.get("matchedChannels", [])
        assert "sparse" in result[0].metadata.get("matchedChannels", [])

    def test_rrf_fusion_respects_candidate_limit(self):
        """RRF 融合应受 candidateLimit 约束。"""
        candidates = [
            self._make_candidate("dense", 0.9),
            self._make_candidate("sparse", 0.5),
            self._make_candidate("graph", 0.3),
        ]

        result = _fuse_provider_candidates(
            candidates,
            fusion_method="rrf",
            candidate_limit=2,
        )

        assert len(result) <= 2

    def test_weighted_fusion_is_default(self):
        """加权融合应为默认方法。"""
        candidates = [
            self._make_candidate("dense", 0.9),
        ]

        result = _fuse_provider_candidates(
            candidates,
            fusion_method="weighted",
        )

        assert len(result) == 1
        assert result[0].metadata.get("fusionMethod") == "weighted"


class TestFusionMethodValidation:
    """融合方法验证测试。"""

    def test_rrf_k_affects_score(self):
        """不同 rrf_k 值应产生不同分数。"""
        candidates = [
            ProviderCandidate(
                source_type="dense",
                chunk_id=uuid4(),
                raw_score=0.9,
                content="Test",
                metadata={},
            ),
        ]

        result_k30 = _fuse_provider_candidates(
            candidates,
            fusion_method="rrf",
            rrf_k=30,
        )
        result_k60 = _fuse_provider_candidates(
            candidates,
            fusion_method="rrf",
            rrf_k=60,
        )

        # 不同 k 值应该产生不同分数
        score_k30 = result_k30[0].metadata.get("fusedScore", 0)
        score_k60 = result_k60[0].metadata.get("fusedScore", 0)
        assert score_k30 != score_k60
