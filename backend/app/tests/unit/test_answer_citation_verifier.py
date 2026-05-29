"""B-327: Answer/Citation Verifier 测试。

验证答案校验、引用校验和置信度评分功能。
"""

import pytest

from app.services.answer_citation_verifier import (
    AnswerVerification,
    VerificationStatus,
    calculate_faithfulness_score,
    decide_action,
    get_verifier_info,
    verify_answer,
    verify_answer_has_citations,
    verify_citation_exists,
    verify_evidence_sufficiency,
    verify_answer_not_hallucinated,
)


class TestVerifyCitationExists:
    """引用存在性校验测试。"""

    def test_verify_citation_exists_valid(self):
        """有效引用应通过校验。"""
        citation = {
            "citationId": "cite_0",
            "documentId": "doc_0",
            "pageNo": 1,
            "blockId": "block_0",
        }
        evidence = [{"documentId": "doc_0", "blockId": "block_0", "content": "Test"}]
        result = verify_citation_exists(citation, evidence)
        assert result.is_valid is True

    def test_verify_citation_exists_missing_location(self):
        """缺少定位信息应校验失败。"""
        citation = {"citationId": "cite_0"}
        evidence = [{"documentId": "doc_0", "content": "Test"}]
        result = verify_citation_exists(citation, evidence)
        assert result.is_valid is False
        assert len(result.issues) > 0

    def test_verify_citation_exists_not_found(self):
        """引用未指向可用证据应校验失败。"""
        citation = {"citationId": "cite_0", "documentId": "doc_1"}
        evidence = [{"documentId": "doc_0", "content": "Test"}]
        result = verify_citation_exists(citation, evidence)
        assert result.is_valid is False


class TestVerifyAnswerHasCitations:
    """引用存在性测试。"""

    def test_verify_answer_has_citations(self):
        """有引用时应通过。"""
        result = verify_answer_has_citations("Answer", [{"id": "cite_0"}])
        assert result.status == VerificationStatus.PASS

    def test_verify_answer_no_citations(self):
        """无引用时应失败。"""
        result = verify_answer_has_citations("Answer", [])
        assert result.status == VerificationStatus.FAIL


class TestVerifyEvidenceSufficiency:
    """证据充分性测试。"""

    def test_verify_evidence_sufficient(self):
        """证据充分时应通过。"""
        evidence = [{"content": "Evidence 1"}, {"content": "Evidence 2"}]
        result = verify_evidence_sufficiency("Answer", evidence, min_evidence=1)
        assert result.status == VerificationStatus.PASS

    def test_verify_evidence_insufficient(self):
        """证据不足时应失败。"""
        result = verify_evidence_sufficiency("Answer", [], min_evidence=1)
        assert result.status == VerificationStatus.FAIL


class TestVerifyAnswerNotHallucinated:
    """幻觉检查测试。"""

    def test_verify_no_hallucination(self):
        """答案与证据一致时应通过。"""
        evidence = [{"content": "RAG is a system for retrieval augmented generation"}]
        answer = "RAG is a retrieval augmented generation system"
        result = verify_answer_not_hallucinated(answer, evidence)
        assert result.status in [VerificationStatus.PASS, VerificationStatus.WARNING]

    def test_verify_no_evidence(self):
        """无证据时应警告。"""
        result = verify_answer_not_hallucinated("Answer", [])
        assert result.status == VerificationStatus.WARNING


class TestCalculateFaithfulnessScore:
    """置信度分数计算测试。"""

    def test_calculate_faithfulness_score_pass(self):
        """全部通过时应返回高分。"""
        from app.services.answer_citation_verifier import VerificationResult
        results = [
            VerificationResult(check_name="test", status=VerificationStatus.PASS, message="OK"),
        ]
        score = calculate_faithfulness_score(results)
        assert score >= 0.8

    def test_calculate_faithfulness_score_fail(self):
        """有失败时应返回低分。"""
        from app.services.answer_citation_verifier import VerificationResult
        results = [
            VerificationResult(check_name="test", status=VerificationStatus.FAIL, message="Failed"),
        ]
        score = calculate_faithfulness_score(results)
        assert score < 0.8

    def test_calculate_faithfulness_score_empty(self):
        """空结果应返回 0。"""
        score = calculate_faithfulness_score([])
        assert score == 0.0


class TestDecideAction:
    """动作决策测试。"""

    def test_decide_action_pass(self):
        """高分时应通过。"""
        action = decide_action(0.9)
        assert action == "pass"

    def test_decide_action_degrade(self):
        """中分时应降级。"""
        action = decide_action(0.6)
        assert action == "degrade"

    def test_decide_action_clarify(self):
        """低分时应澄清。"""
        action = decide_action(0.3)
        assert action == "clarify"

    def test_decide_action_refuse(self):
        """极低分时应拒绝。"""
        action = decide_action(0.1)
        assert action == "refuse"


class TestVerifyAnswer:
    """答案校验测试。"""

    def test_verify_answer_pass(self):
        """有效答案应通过。"""
        answer = "RAG is a retrieval augmented generation system"
        evidence = [
            {"documentId": "doc_0", "blockId": "block_0", "content": "RAG is retrieval augmented generation"},
        ]
        citations = [
            {"citationId": "cite_0", "documentId": "doc_0", "blockId": "block_0"},
        ]
        result = verify_answer(answer, evidence, citations)
        assert result.is_verified is True
        assert result.suggested_action == "pass"

    def test_verify_answer_no_citations(self):
        """无引用时应失败或降级。"""
        answer = "RAG is a system"
        evidence = [{"content": "RAG is retrieval augmented generation"}]
        result = verify_answer(answer, evidence, [])
        assert result.is_verified is False
        assert result.suggested_action in ["degrade", "clarify", "refuse"]

    def test_verify_answer_degraded(self):
        """低置信度时应降级或澄清。"""
        answer = "Some answer"
        evidence = []
        citations = [{"citationId": "cite_0", "documentId": "doc_0"}]
        result = verify_answer(answer, evidence, citations, min_faithfulness_score=0.9)
        assert result.suggested_action in ["degrade", "clarify", "refuse"]
        assert result.degraded_answer is not None or result.clarification_question is not None

    def test_verify_answer_with_clarification(self):
        """需要澄清时应返回澄清问题。"""
        answer = "Answer"
        evidence = []
        citations = []
        result = verify_answer(answer, evidence, citations)
        if result.suggested_action == "clarify":
            assert result.clarification_question is not None


class TestGetVerifierInfo:
    """获取校验器信息测试。"""

    def test_get_verifier_info(self):
        """应返回校验器信息。"""
        info = get_verifier_info()
        assert "checks" in info
        assert "actions" in info
        assert "minFaithfulnessScore" in info
