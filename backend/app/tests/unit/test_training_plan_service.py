"""training_plan_service 单元测试（LLM 生成 + 规则回退）。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.training_plan import AbilityGroupDTO, DocumentDTO
from app.services.training_plan_service import (
    _generate_plan_with_llm,
    _rule_based_plan,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _make_row(
    chunk_id: str,
    document_id: str,
    content: str = "test content",
    heading: str = "H1",
    document_name: str | None = None,
) -> dict:
    """构建模拟的 evidence row。"""
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "document_name": document_name,
        "chunk_index": 0,
        "section": "S1",
        "heading": heading,
        "content": content,
        "metadata": {"documentName": f"Doc {document_id}"},
    }


SAMPLE_ROWS = [
    _make_row("c1", "d1", "安全操作规程第一条"),
    _make_row("c2", "d1", "安全操作规程第二条"),
    _make_row("c3", "d2", "设备维护手册"),
    _make_row("c4", "d3", "应急处置指南"),
]


def _llm_json_response() -> str:
    """返回一个合法的 LLM JSON 输出。"""
    return """{
        "abilityGroups": [
            {"name": "基础认知", "description": "理解岗位基础"},
            {"name": "作业流程", "description": "掌握关键步骤"}
        ],
        "documents": [
            {"documentId": "d1", "title": "安全操作规程", "relevance": 0.95, "abilityGroup": "基础认知", "difficulty": "basic"},
            {"documentId": "d2", "title": "设备维护手册", "relevance": 0.80, "abilityGroup": "作业流程", "difficulty": "normal"},
            {"documentId": "d3", "title": "应急处置指南", "relevance": 0.70, "abilityGroup": "作业流程", "difficulty": "advanced"}
        ],
        "readingOrder": ["d1", "d2", "d3"],
        "recommendReason": "根据岗位需求推荐这三份文档。"
    }"""


# ---------------------------------------------------------------------------
# _rule_based_plan
# ---------------------------------------------------------------------------


class TestRuleBasedPlan:
    def test_returns_correct_groups(self):
        groups, docs, order, reason, chunk_ids = _rule_based_plan("安全员", SAMPLE_ROWS)
        assert len(groups) == 3
        assert groups[0].name == "基础认知"

    def test_deduplicates_documents(self):
        groups, docs, order, reason, chunk_ids = _rule_based_plan("安全员", SAMPLE_ROWS)
        doc_ids = [d.documentId for d in docs]
        assert len(doc_ids) == len(set(doc_ids))

    def test_reading_order_matches_documents(self):
        groups, docs, order, reason, chunk_ids = _rule_based_plan("安全员", SAMPLE_ROWS)
        assert order == [d.documentId for d in docs]

    def test_evidence_chunk_ids_from_rows(self):
        groups, docs, order, reason, chunk_ids = _rule_based_plan("安全员", SAMPLE_ROWS)
        assert chunk_ids == ["c1", "c2", "c3", "c4"]


# ---------------------------------------------------------------------------
# _generate_plan_with_llm - 成功场景
# ---------------------------------------------------------------------------


class TestGeneratePlanWithLlmSuccess:
    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_llm_success_returns_valid_plan(self, mock_audit, mock_llm):
        mock_llm.return_value = _llm_json_response()
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "负责安全管理", SAMPLE_ROWS, "app-1")

        assert result is not None
        groups, documents, reading_order, reason, chunk_ids = result
        assert len(groups) == 2
        assert groups[0].name == "基础认知"
        assert len(documents) == 3
        assert documents[0].documentId == "d1"
        assert reading_order == ["d1", "d2", "d3"]
        assert "推荐" in reason

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_llm_success_records_audit(self, mock_audit, mock_llm):
        mock_llm.return_value = _llm_json_response()
        session = MagicMock()

        _generate_plan_with_llm(session, "安全员", "负责安全管理", SAMPLE_ROWS, "app-1")

        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args
        assert call_kwargs[1]["skill_name"] == "buildLearningPlanDraft"
        assert call_kwargs[1]["status"] == "success"

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_llm_success_uses_evidence_chunk_ids(self, mock_audit, mock_llm):
        mock_llm.return_value = _llm_json_response()
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is not None
        _, _, _, _, chunk_ids = result
        assert chunk_ids == ["c1", "c2", "c3", "c4"]

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_llm_title_uses_document_name_not_page_heading(self, mock_audit, mock_llm):
        """LLM 返回页标题时，计划文档标题应以知识库文档名为准。"""
        rows = [
            _make_row(
                "c1",
                "d1",
                content="生产环境温湿度控制要求",
                heading="Page 1",
                document_name="生产环境安全操作规范.pdf",
            )
        ]
        mock_llm.return_value = """{
            "abilityGroups": [{"name": "生产环境管理", "description": "desc"}],
            "documents": [
                {"documentId": "d1", "title": "Page 1", "relevance": 0.9, "abilityGroup": "生产环境管理", "difficulty": "basic"}
            ],
            "readingOrder": ["d1"],
            "recommendReason": "test"
        }"""
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", rows, "app-1")

        assert result is not None
        _, documents, _, _, _ = result
        assert documents[0].title == "生产环境安全操作规范.pdf"


# ---------------------------------------------------------------------------
# _generate_plan_with_llm - LLM 调用失败回退
# ---------------------------------------------------------------------------


class TestGeneratePlanWithLlmCallFailure:
    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_llm_call_exception_returns_none(self, mock_audit, mock_llm):
        mock_llm.side_effect = Exception("connection timeout")
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is None

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_llm_call_failure_records_error_audit(self, mock_audit, mock_llm):
        mock_llm.side_effect = Exception("timeout")
        session = MagicMock()

        _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args
        assert call_kwargs[1]["status"] == "error"
        assert call_kwargs[1]["error_code"] == "LLM_CALL_FAILED"


# ---------------------------------------------------------------------------
# _generate_plan_with_llm - LLM 输出解析失败回退
# ---------------------------------------------------------------------------


class TestGeneratePlanWithLlmParseFailure:
    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_invalid_json_returns_none(self, mock_audit, mock_llm):
        mock_llm.return_value = "this is not json"
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is None

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_missing_required_keys_returns_none(self, mock_audit, mock_llm):
        mock_llm.return_value = '{"abilityGroups": []}'
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is None

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_parse_failure_records_error_audit(self, mock_audit, mock_llm):
        mock_llm.return_value = "not json"
        session = MagicMock()

        _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args
        assert call_kwargs[1]["status"] == "error"
        assert call_kwargs[1]["error_code"] == "LLM_PARSE_FAILED"


# ---------------------------------------------------------------------------
# _generate_plan_with_llm - documentId 验证
# ---------------------------------------------------------------------------


class TestGeneratePlanWithLlmDocumentIdValidation:
    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_invalid_document_id_is_skipped(self, mock_audit, mock_llm):
        """LLM 返回的 documentId 不在证据中时被跳过。"""
        llm_output = """{
            "abilityGroups": [{"name": "基础认知", "description": "desc"}],
            "documents": [
                {"documentId": "d1", "title": "Valid Doc", "relevance": 0.9, "abilityGroup": "基础认知", "difficulty": "basic"},
                {"documentId": "FAKE_ID", "title": "Fake Doc", "relevance": 0.8, "abilityGroup": "基础认知", "difficulty": "normal"}
            ],
            "readingOrder": ["d1", "FAKE_ID"],
            "recommendReason": "test reason"
        }"""
        mock_llm.return_value = llm_output
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is not None
        _, documents, reading_order, _, _ = result
        doc_ids = [d.documentId for d in documents]
        assert "FAKE_ID" not in doc_ids
        assert "d1" in doc_ids
        assert "FAKE_ID" not in reading_order

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_all_invalid_document_ids_returns_none(self, mock_audit, mock_llm):
        """LLM 返回的 documentId 全部无效时回退。"""
        llm_output = """{
            "abilityGroups": [{"name": "基础认知", "description": "desc"}],
            "documents": [
                {"documentId": "FAKE1", "title": "Fake1", "relevance": 0.9, "abilityGroup": "基础认知", "difficulty": "basic"},
                {"documentId": "FAKE2", "title": "Fake2", "relevance": 0.8, "abilityGroup": "基础认知", "difficulty": "normal"}
            ],
            "readingOrder": ["FAKE1", "FAKE2"],
            "recommendReason": "test reason"
        }"""
        mock_llm.return_value = llm_output
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is None

    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_valid_doc_ids_from_evidence_pass(self, mock_audit, mock_llm):
        """documentId 全部来自证据时正常通过。"""
        mock_llm.return_value = _llm_json_response()
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is not None
        _, documents, _, _, _ = result
        valid_ids = {"d1", "d2", "d3"}
        for doc in documents:
            assert doc.documentId in valid_ids


# ---------------------------------------------------------------------------
# _generate_plan_with_llm - readingOrder 补全
# ---------------------------------------------------------------------------


class TestGeneratePlanWithLlmReadingOrder:
    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_missing_docs_appended_to_reading_order(self, mock_audit, mock_llm):
        """LLM 遗漏的文档被补充到 readingOrder 末尾。"""
        llm_output = """{
            "abilityGroups": [{"name": "基础认知", "description": "desc"}],
            "documents": [
                {"documentId": "d1", "title": "Doc1", "relevance": 0.9, "abilityGroup": "基础认知", "difficulty": "basic"},
                {"documentId": "d2", "title": "Doc2", "relevance": 0.8, "abilityGroup": "基础认知", "difficulty": "normal"}
            ],
            "readingOrder": ["d1"],
            "recommendReason": "test"
        }"""
        mock_llm.return_value = llm_output
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is not None
        _, _, reading_order, _, _ = result
        assert "d1" in reading_order
        assert "d2" in reading_order


# ---------------------------------------------------------------------------
# _generate_plan_with_llm - difficulty 验证
# ---------------------------------------------------------------------------


class TestGeneratePlanWithLlmDifficulty:
    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_invalid_difficulty_defaults_to_normal(self, mock_audit, mock_llm):
        llm_output = """{
            "abilityGroups": [{"name": "基础认知", "description": "desc"}],
            "documents": [
                {"documentId": "d1", "title": "Doc1", "relevance": 0.9, "abilityGroup": "基础认知", "difficulty": "super_hard"}
            ],
            "readingOrder": ["d1"],
            "recommendReason": "test"
        }"""
        mock_llm.return_value = llm_output
        session = MagicMock()

        result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")

        assert result is not None
        _, documents, _, _, _ = result
        assert documents[0].difficulty == "normal"


# ---------------------------------------------------------------------------
# fallback 集成: _generate_plan_with_llm 返回 None 时 _rule_based_plan 兜底
# ---------------------------------------------------------------------------


class TestFallbackIntegration:
    @patch("app.services.training_plan_service.call_llm")
    @patch("app.services.training_plan_service.record_training_skill_call")
    def test_fallback_produces_valid_output(self, mock_audit, mock_llm):
        """LLM 失败后规则回退产生与直接调用规则相同的结果。"""
        mock_llm.side_effect = Exception("boom")
        session = MagicMock()

        llm_result = _generate_plan_with_llm(session, "安全员", "", SAMPLE_ROWS, "app-1")
        assert llm_result is None

        rule_result = _rule_based_plan("安全员", SAMPLE_ROWS)
        groups, docs, order, reason, chunk_ids = rule_result
        assert len(docs) > 0
        assert len(order) == len(docs)
        assert len(chunk_ids) == len(SAMPLE_ROWS)
