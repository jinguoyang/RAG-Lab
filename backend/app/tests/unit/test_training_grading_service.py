"""training_grading_service 单元测试。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.training_grading_service import (
    SubjectiveGradeResult,
    _clamp_score,
    _fallback_grade,
    grade_subjective_answer,
)


# ---------------------------------------------------------------------------
# SubjectiveGradeResult DTO
# ---------------------------------------------------------------------------


class TestSubjectiveGradeResult:
    """SubjectiveGradeResult 模型测试。"""

    def test_valid_result(self):
        result = SubjectiveGradeResult(score=85, reason="回答良好", matchedCriteria=["内容相关性"])
        assert result.score == 85
        assert result.reason == "回答良好"
        assert result.matchedCriteria == ["内容相关性"]
        assert result.needsManualReview is False

    def test_default_values(self):
        result = SubjectiveGradeResult(score=60, reason="一般")
        assert result.matchedCriteria == []
        assert result.needsManualReview is False

    def test_score_at_boundary(self):
        assert SubjectiveGradeResult(score=0, reason="最低").score == 0
        assert SubjectiveGradeResult(score=100, reason="最高").score == 100


# ---------------------------------------------------------------------------
# _clamp_score
# ---------------------------------------------------------------------------


class TestClampScore:
    """_clamp_score 边界测试。"""

    def test_normal_score(self):
        assert _clamp_score(75) == 75

    def test_below_zero(self):
        assert _clamp_score(-10) == 0

    def test_above_hundred(self):
        assert _clamp_score(150) == 100

    def test_string_number(self):
        assert _clamp_score("85") == 85

    def test_float_score(self):
        assert _clamp_score(85.7) == 85

    def test_invalid_value(self):
        assert _clamp_score(None) == 0
        assert _clamp_score("abc") == 0


# ---------------------------------------------------------------------------
# _fallback_grade
# ---------------------------------------------------------------------------


class TestFallbackGrade:
    """保守规则评分测试。"""

    def test_empty_answer(self):
        result = _fallback_grade("", None)
        assert result.score == 0
        assert result.needsManualReview is True
        assert "未提交" in result.reason

    def test_short_answer(self):
        result = _fallback_grade("短答案", None)
        assert result.score == 40
        assert result.needsManualReview is True

    def test_medium_answer(self):
        result = _fallback_grade("这是一个超过二十个字符的答案内容，需要再补充一些文字才能达到要求", None)
        assert result.score == 60
        assert result.needsManualReview is True

    def test_long_answer_with_rubric(self):
        rubric = {"criteria": [{"name": "测试", "score": 40, "description": "测试标准"}]}
        long_answer = "这是一个超过五十个字符的长答案，用于测试有 rubric 时的评分逻辑，应该得到更高的分数，需要继续补充更多内容来满足长度要求。"
        result = _fallback_grade(long_answer, rubric)
        assert result.score == 80
        assert result.needsManualReview is True


# ---------------------------------------------------------------------------
# grade_subjective_answer 集成测试（mock 数据库和 LLM）
# ---------------------------------------------------------------------------


class TestGradeSubjectiveAnswer:
    """grade_subjective_answer 主流程测试。"""

    def _make_question_row(self, question_type="subjective", rubric=None):
        """创建模拟的题目行。"""
        return {
            "question_id": str(uuid4()),
            "app_id": str(uuid4()),
            "question_type": question_type,
            "content": "请说明安全操作的关键步骤。",
            "rubric": rubric or {
                "totalScore": 100,
                "criteria": [
                    {"name": "依据准确", "score": 40, "description": "能引用知识库要求。"},
                    {"name": "流程完整", "score": 40, "description": "覆盖关键步骤。"},
                    {"name": "表达清晰", "score": 20, "description": "表述具体。"},
                ],
            },
            "evidence_chunk_ids": ["chunk-001"],
        }

    @patch("app.services.training_grading_service._call_llm")
    @patch("app.services.training_grading_service.record_training_skill_call")
    @patch("app.services.training_grading_service.select")
    def test_llm_grade_success(self, mock_select, mock_audit, mock_llm):
        """LLM 评分成功时应返回 LLM 结果。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = self._make_question_row()

        mock_llm.return_value = json.dumps({
            "score": 85,
            "reason": "回答覆盖了关键步骤，引用准确。",
            "matchedCriteria": ["依据准确", "流程完整"],
        })

        with patch("app.services.training_grading_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(llm_endpoint="http://test", llm_api_key="key", llm_model="model")
            result = grade_subjective_answer(
                mock_session,
                "q-001",
                "安全操作的关键步骤包括：1. 检查设备状态 2. 佩戴防护装备 3. 按规程操作",
                "app-001",
            )

        assert result.score == 85
        assert "覆盖" in result.reason
        assert "依据准确" in result.matchedCriteria
        assert result.needsManualReview is False
        mock_audit.assert_called_once()

    @patch("app.services.training_grading_service._call_llm")
    @patch("app.services.training_grading_service.record_training_skill_call")
    @patch("app.services.training_grading_service.select")
    def test_llm_failure_falls_back(self, mock_select, mock_audit, mock_llm):
        """LLM 失败时应回退到规则评分，needsManualReview 为 True。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = self._make_question_row()

        mock_llm.side_effect = RuntimeError("LLM 超时")

        with patch("app.services.training_grading_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(llm_endpoint="http://test", llm_api_key="key", llm_model="model")
            result = grade_subjective_answer(
                mock_session,
                "q-001",
                "安全操作很重要，需要认真执行。",
                "app-001",
            )

        assert result.score > 0
        assert result.needsManualReview is True
        assert "保守规则" in result.reason or "LLM" in result.reason
        mock_audit.assert_called_once()

    @patch("app.services.training_grading_service._call_llm")
    @patch("app.services.training_grading_service.record_training_skill_call")
    @patch("app.services.training_grading_service.select")
    def test_score_clamped_to_range(self, mock_select, mock_audit, mock_llm):
        """LLM 返回超出范围的分数时应被限制在 0-100。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = self._make_question_row()

        mock_llm.return_value = json.dumps({
            "score": 150,
            "reason": "超出范围测试",
            "matchedCriteria": [],
        })

        with patch("app.services.training_grading_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(llm_endpoint="http://test", llm_api_key="key", llm_model="model")
            result = grade_subjective_answer(
                mock_session,
                "q-001",
                "测试答案内容。",
                "app-001",
            )
        assert result.score == 100

    @patch("app.services.training_grading_service._call_llm")
    @patch("app.services.training_grading_service.record_training_skill_call")
    @patch("app.services.training_grading_service.select")
    def test_score_clamped_negative(self, mock_select, mock_audit, mock_llm):
        """LLM 返回负分时应被限制为 0。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = self._make_question_row()

        mock_llm.return_value = json.dumps({
            "score": -10,
            "reason": "负分测试",
            "matchedCriteria": [],
        })

        with patch("app.services.training_grading_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(llm_endpoint="http://test", llm_api_key="key", llm_model="model")
            result = grade_subjective_answer(
                mock_session,
                "q-001",
                "测试答案内容。",
                "app-001",
            )
        assert result.score == 0

    @patch("app.services.training_grading_service.select")
    def test_non_subjective_question_raises(self, mock_select):
        """非主观题应抛出 ValueError。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = self._make_question_row(
            question_type="single_choice"
        )

        with pytest.raises(ValueError, match="不是主观题"):
            grade_subjective_answer(
                mock_session,
                "q-001",
                "答案",
                "app-001",
            )

    @patch("app.services.training_grading_service.select")
    def test_question_not_found_raises(self, mock_select):
        """题目不存在时应抛出 ValueError。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        with pytest.raises(ValueError, match="不存在"):
            grade_subjective_answer(
                mock_session,
                "q-nonexistent",
                "答案",
                "app-001",
            )

    @patch("app.services.training_grading_service._call_llm")
    @patch("app.services.training_grading_service.record_training_skill_call")
    @patch("app.services.training_grading_service.select")
    def test_low_score_needs_manual_review(self, mock_select, mock_audit, mock_llm):
        """分数低于 60 时 needsManualReview 应为 True。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = self._make_question_row()

        mock_llm.return_value = json.dumps({
            "score": 45,
            "reason": "回答不够充分。",
            "matchedCriteria": [],
        })

        with patch("app.services.training_grading_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(llm_endpoint="http://test", llm_api_key="key", llm_model="model")
            result = grade_subjective_answer(
                mock_session,
                "q-001",
                "简短回答。",
                "app-001",
            )
        assert result.score == 45
        assert result.needsManualReview is True

    @patch("app.services.training_grading_service._call_llm")
    @patch("app.services.training_grading_service.record_training_skill_call")
    @patch("app.services.training_grading_service.select")
    def test_empty_rubric_uses_default(self, mock_select, mock_audit, mock_llm):
        """rubric 为空时应使用默认评分标准。"""
        mock_session = MagicMock()
        question_row = self._make_question_row(rubric=None)
        question_row["rubric"] = None
        mock_session.execute.return_value.mappings.return_value.first.return_value = question_row

        mock_llm.return_value = json.dumps({
            "score": 70,
            "reason": "回答尚可。",
            "matchedCriteria": ["内容相关性"],
        })

        with patch("app.services.training_grading_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(llm_endpoint="http://test", llm_api_key="key", llm_model="model")
            result = grade_subjective_answer(
                mock_session,
                "q-001",
                "这是一个超过二十个字符的答案。",
                "app-001",
            )
        assert result.score == 70
        mock_llm.assert_called_once()
