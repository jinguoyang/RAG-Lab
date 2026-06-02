"""B-327: Answer/Citation Verifier 集成测试。

验证完整校验链：答案 + 证据 + 引用 → verify_answer() → 状态和动作决策。
覆盖通过、降级、澄清和拒绝四种场景。
"""

from __future__ import annotations

from app.services.answer_citation_verifier import (
    get_verifier_info,
    verify_answer,
    verify_citation_exists,
)


class TestVerifiedAnswerPassScenario:
    """校验通过场景：答案有引用、证据充分、无幻觉。"""

    def test_valid_answer_passes_all_checks(self):
        """完整有效答案应通过所有校验。"""
        answer = "RAG 是 Retrieval Augmented Generation 的缩写，用于增强大模型的知识检索能力。"
        evidence = [
            {
                "documentId": "doc_0",
                "blockId": "block_0",
                "content": "RAG（Retrieval Augmented Generation）是一种检索增强生成技术。",
            },
        ]
        citations = [
            {"citationId": "cite_0", "documentId": "doc_0", "blockId": "block_0"},
        ]

        result = verify_answer(answer, evidence, citations)

        assert result.is_verified is True
        assert result.suggested_action == "pass"
        assert result.faithfulness_score >= 0.8
        assert result.degraded_answer is None
        assert result.clarification_question is None

    def test_multiple_citations_all_valid(self):
        """多个有效引用应全部通过校验。"""
        answer = "系统支持 Dense 和 Sparse 两种检索方式。"
        evidence = [
            {"documentId": "doc_0", "blockId": "b0", "content": "Dense retrieval 使用向量嵌入"},
            {"documentId": "doc_1", "blockId": "b1", "content": "Sparse retrieval 使用关键词匹配"},
        ]
        citations = [
            {"citationId": "c0", "documentId": "doc_0", "blockId": "b0"},
            {"citationId": "c1", "documentId": "doc_1", "blockId": "b1"},
        ]

        result = verify_answer(answer, evidence, citations)

        assert result.is_verified is True
        assert len(result.citation_verifications) == 2
        assert all(cv.is_valid for cv in result.citation_verifications)


class TestVerifiedAnswerDegradedScenario:
    """降级场景：证据不足或引用缺失。"""

    def test_no_citations_triggers_degrade_or_refuse(self):
        """无引用答案应触发降级或拒绝。"""
        answer = "RAG 是一种检索增强生成技术。"
        evidence = [{"content": "RAG 相关内容"}]

        result = verify_answer(answer, evidence, [])

        assert result.is_verified is False
        assert result.suggested_action in ("degrade", "clarify", "refuse")

    def test_insufficient_evidence_triggers_degrade(self):
        """证据不足时应触发降级。"""
        answer = "答案内容"
        evidence = []
        citations = [{"citationId": "c0", "documentId": "doc_0", "blockId": "b0"}]

        result = verify_answer(answer, evidence, citations, min_evidence=2)

        assert result.is_verified is False
        assert result.suggested_action in ("degrade", "clarify", "refuse")

    def test_degraded_answer_is_generated(self):
        """降级时应生成降级答案。"""
        answer = "Some answer"
        evidence = []
        citations = [{"citationId": "c0", "documentId": "doc_0"}]

        result = verify_answer(answer, evidence, citations, min_faithfulness_score=0.9)

        if result.suggested_action == "degrade":
            assert result.degraded_answer is not None


class TestVerifiedAnswerRefuseScenario:
    """拒绝场景：引用不存在或越权。"""

    def test_citation_not_in_evidence(self):
        """引用指向不存在的证据时应校验失败。"""
        answer = "答案内容"
        evidence = [{"documentId": "doc_other", "blockId": "b99", "content": "无关内容"}]
        citations = [{"citationId": "c0", "documentId": "doc_0", "blockId": "b0"}]

        result = verify_answer(answer, evidence, citations)

        invalid_citations = [cv for cv in result.citation_verifications if not cv.is_valid]
        assert len(invalid_citations) > 0

    def test_citation_missing_location_info(self):
        """引用缺少定位信息时应校验失败。"""
        citation = {"citationId": "c0"}
        evidence = [{"documentId": "doc_0", "content": "test"}]

        cv = verify_citation_exists(citation, evidence)

        assert cv.is_valid is False
        assert len(cv.issues) > 0


class TestVerifiedAnswerClarifyScenario:
    """澄清场景：置信度极低时应返回澄清问题。"""

    def test_very_low_faithfulness_triggers_clarify_or_refuse(self):
        """极低置信度应触发澄清或拒绝。"""
        answer = "完全无关的答案"
        evidence = []
        citations = []

        result = verify_answer(answer, evidence, citations, min_faithfulness_score=0.9)

        assert result.suggested_action in ("clarify", "refuse")
        if result.suggested_action == "clarify":
            assert result.clarification_question is not None


class TestVerificationTraceIntegration:
    """校验 Trace 集成测试：验证 trace 结构与 qa_run_service 兼容。"""

    def test_trace_structure_matches_expected_format(self):
        """verify_answer 返回结构应与 _build_answer_verification_trace 兼容。"""
        answer = "RAG 是检索增强生成系统"
        evidence = [
            {"documentId": "doc_0", "blockId": "b0", "content": "RAG 检索增强生成"},
        ]
        citations = [
            {"citationId": "c0", "documentId": "doc_0", "blockId": "b0"},
        ]

        result = verify_answer(answer, evidence, citations)

        # 模拟 _build_answer_verification_trace 的结构
        trace = {
            "verified": result.is_verified,
            "status": result.status.value,
            "faithfulnessScore": result.faithfulness_score,
            "suggestedAction": result.suggested_action,
            "degradedAnswer": result.degraded_answer,
            "clarificationQuestion": result.clarification_question,
            "checks": [
                {
                    "name": item.check_name,
                    "status": item.status.value,
                    "message": item.message,
                }
                for item in result.verification_results
            ],
            "citationChecks": [
                {
                    "citationId": item.citation_id,
                    "valid": item.is_valid,
                    "issues": item.issues,
                }
                for item in result.citation_verifications
            ],
        }

        # 验证 trace 结构完整性
        assert "verified" in trace
        assert "status" in trace
        assert "faithfulnessScore" in trace
        assert "suggestedAction" in trace
        assert "checks" in trace
        assert "citationChecks" in trace
        assert isinstance(trace["checks"], list)
        assert isinstance(trace["citationChecks"], list)
        assert len(trace["checks"]) > 0

    def test_refuse_action_in_trace(self):
        """拒绝动作在 trace 中应正确反映。"""
        answer = "无支撑答案"
        evidence = []
        citations = []

        result = verify_answer(answer, evidence, citations)

        trace = {
            "verified": result.is_verified,
            "suggestedAction": result.suggested_action,
        }

        if result.suggested_action == "refuse":
            assert trace["verified"] is False


class TestVerifierInfoIntegration:
    """校验器信息接口集成测试。"""

    def test_verifier_info_has_required_fields(self):
        """校验器信息应包含所有必要字段。"""
        info = get_verifier_info()

        assert "checks" in info
        assert "actions" in info
        assert "minFaithfulnessScore" in info

        check_names = {c["name"] for c in info["checks"]}
        assert "citation_presence" in check_names
        assert "evidence_sufficiency" in check_names
        assert "hallucination_check" in check_names

        action_names = {a["name"] for a in info["actions"]}
        assert "pass" in action_names
        assert "degrade" in action_names
        assert "clarify" in action_names
        assert "refuse" in action_names
