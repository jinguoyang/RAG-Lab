"""B-325: Corrective RAG 控制器测试。

验证证据评估、纠正决策和 Corrective RAG 执行功能。
"""

import pytest
from uuid import uuid4

from app.services.corrective_rag import (
    CorrectiveAction,
    EvidenceAssessment,
    assess_evidence,
    decide_corrective_action,
    execute_corrective_rag,
    get_corrective_rag_info,
)
from app.services.qa_providers import ProviderCandidate


def _make_candidate(score: float = 0.8, content: str = "Test content", metadata: dict = None):
    """创建测试候选。"""
    return ProviderCandidate(
        source_type="dense",
        chunk_id=uuid4(),
        raw_score=score,
        content=content,
        metadata=metadata or {"documentId": "doc_0", "chunkId": "chunk_0"},
    )


class TestAssessEvidence:
    """证据评估测试。"""

    def test_assess_evidence_empty(self):
        """空候选应返回低充分性。"""
        assessment = assess_evidence([], "test query")
        assert assessment.overall_sufficiency < 0.5

    def test_assess_evidence_good_candidates(self):
        """好的候选应返回高充分性。"""
        candidates = [
            _make_candidate(0.9, "test query content"),
            _make_candidate(0.8, "more test content"),
        ]
        assessment = assess_evidence(candidates, "test query")
        assert assessment.overall_sufficiency > 0.5

    def test_assess_evidence_low_relevance(self):
        """低相关性候选应返回低充分性。"""
        candidates = [_make_candidate(0.1, "low relevance")]
        assessment = assess_evidence(candidates, "test query")
        assert assessment.overall_sufficiency < 0.7

    def test_assess_evidence_with_issues(self):
        """应识别问题。"""
        candidates = [_make_candidate(0.1, "")]
        assessment = assess_evidence(candidates, "test query")
        assert len(assessment.issues) > 0


class TestDecideCorrectiveAction:
    """纠正决策测试。"""

    def test_decide_proceed_when_sufficient(self):
        """证据充分时应继续生成。"""
        assessment = EvidenceAssessment(
            coverage_score=0.8,
            relevance_score=0.8,
            conflict_score=0.0,
            permission_status="ok",
            citation_locatability=0.8,
            overall_sufficiency=0.8,
        )
        decision = decide_corrective_action(assessment, current_round=0)
        assert decision.action == CorrectiveAction.PROCEED_TO_GENERATION

    def test_decide_rewrite_query_when_low_coverage(self):
        """低覆盖度时应重写查询。"""
        assessment = EvidenceAssessment(
            coverage_score=0.3,
            relevance_score=0.8,
            conflict_score=0.0,
            permission_status="ok",
            citation_locatability=0.8,
            overall_sufficiency=0.5,
        )
        decision = decide_corrective_action(assessment, current_round=0)
        assert decision.action == CorrectiveAction.REWRITE_QUERY

    def test_decide_expand_scope_when_low_relevance(self):
        """低相关性时应扩展范围。"""
        assessment = EvidenceAssessment(
            coverage_score=0.8,
            relevance_score=0.2,
            conflict_score=0.0,
            permission_status="ok",
            citation_locatability=0.8,
            overall_sufficiency=0.5,
        )
        decision = decide_corrective_action(assessment, current_round=0)
        assert decision.action == CorrectiveAction.EXPAND_SCOPE

    def test_decide_answer_insufficient_at_max_rounds(self):
        """达到最大轮次且证据不足时应拒绝回答。"""
        assessment = EvidenceAssessment(
            coverage_score=0.1,
            relevance_score=0.1,
            conflict_score=0.0,
            permission_status="ok",
            citation_locatability=0.1,
            overall_sufficiency=0.1,
        )
        decision = decide_corrective_action(assessment, current_round=2, max_rounds=2)
        assert decision.action == CorrectiveAction.ANSWER_INSUFFICIENT

    def test_decide_proceed_at_max_rounds_if_ok(self):
        """达到最大轮次但证据基本充分时应继续生成。"""
        assessment = EvidenceAssessment(
            coverage_score=0.6,
            relevance_score=0.6,
            conflict_score=0.0,
            permission_status="ok",
            citation_locatability=0.6,
            overall_sufficiency=0.6,
        )
        decision = decide_corrective_action(assessment, current_round=2, max_rounds=2)
        assert decision.action == CorrectiveAction.PROCEED_TO_GENERATION


class TestExecuteCorrectiveRAG:
    """执行 Corrective RAG 测试。"""

    def test_execute_corrective_rag_basic(self):
        """应能执行 Corrective RAG。"""
        candidates = [
            _make_candidate(0.8, "test content"),
        ]
        decision, trace = execute_corrective_rag(candidates, "test query")
        assert decision is not None
        assert trace is not None
        assert trace.round == 0

    def test_execute_corrective_rag_empty_candidates(self):
        """空候选应返回纠正决策。"""
        decision, trace = execute_corrective_rag([], "test query")
        assert decision.action in [
            CorrectiveAction.REWRITE_QUERY,
            CorrectiveAction.ANSWER_INSUFFICIENT,
            CorrectiveAction.PROCEED_TO_GENERATION,
        ]

    def test_execute_corrective_rag_max_rounds(self):
        """应支持最大轮次限制。"""
        candidates = [_make_candidate(0.3, "low quality")]
        decision, trace = execute_corrective_rag(
            candidates,
            "test query",
            current_round=2,
            max_rounds=2,
        )
        assert decision.action in [
            CorrectiveAction.ANSWER_INSUFFICIENT,
            CorrectiveAction.PROCEED_TO_GENERATION,
        ]


class TestGetCorrectiveRAGInfo:
    """获取信息测试。"""

    def test_get_corrective_rag_info(self):
        """应返回 Corrective RAG 信息。"""
        info = get_corrective_rag_info()
        assert "actions" in info
        assert "maxRounds" in info
        assert "scoringMethods" in info
        assert info["maxRounds"] == 2
