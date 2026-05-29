"""training_question_service LLM 辅助出题单元测试。"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.training_question import QuestionOptionDTO
from app.services.training_question_service import (
    _DEFAULT_SUBJECTIVE_RUBRIC,
    _build_llm_prompt,
    _generate_questions_with_llm,
    _validate_and_normalize_question,
)


# ---------------------------------------------------------------------------
# _build_llm_prompt
# ---------------------------------------------------------------------------


class TestBuildLlmPrompt:
    """_build_llm_prompt 测试集。"""

    def test_returns_two_messages(self):
        messages = _build_llm_prompt("安全工程师", 3, ["证据一", "证据二"])
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_system_message_contains_count(self):
        messages = _build_llm_prompt("测试岗", 5, [])
        assert "5" in messages[0]["content"]

    def test_user_message_contains_job_title(self):
        messages = _build_llm_prompt("数据分析师", 3, [])
        assert "数据分析师" in messages[1]["content"]

    def test_evidence_in_user_message(self):
        messages = _build_llm_prompt("岗", 2, ["证据A", "证据B"])
        user_content = messages[1]["content"]
        assert "[1] 证据A" in user_content
        assert "[2] 证据B" in user_content

    def test_empty_evidence_shows_placeholder(self):
        messages = _build_llm_prompt("岗", 2, [])
        user_content = messages[1]["content"]
        assert "无可用证据" in user_content


# ---------------------------------------------------------------------------
# _validate_and_normalize_question
# ---------------------------------------------------------------------------


class TestValidateAndNormalizeQuestion:
    """_validate_and_normalize_question 测试集。"""

    def test_valid_single_choice(self):
        raw = {
            "questionType": "single_choice",
            "content": "下列哪项正确？",
            "options": [
                {"label": "A", "text": "正确选项"},
                {"label": "B", "text": "错误选项"},
                {"label": "C", "text": "错误选项"},
                {"label": "D", "text": "错误选项"},
            ],
            "correctAnswer": "A",
            "explanation": "因为A正确。",
            "rubric": None,
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["questionType"] == "single_choice"
        assert len(result["options"]) == 4
        assert result["correctAnswer"] == "A"
        assert result["rubric"] is None

    def test_valid_true_false(self):
        raw = {
            "questionType": "true_false",
            "content": "判断题内容",
            "options": [{"label": "true", "text": "正确"}, {"label": "false", "text": "错误"}],
            "correctAnswer": "true",
            "explanation": "解释",
            "rubric": None,
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["questionType"] == "true_false"
        assert result["rubric"] is None

    def test_valid_subjective_with_rubric(self):
        rubric = {
            "totalScore": 100,
            "criteria": [
                {"name": "要点覆盖", "score": 60, "description": "覆盖关键要点"},
                {"name": "表达清晰", "score": 40, "description": "表述准确"},
            ],
        }
        raw = {
            "questionType": "subjective",
            "content": "请描述...",
            "options": [],
            "correctAnswer": None,
            "explanation": "按要点评分",
            "rubric": rubric,
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["questionType"] == "subjective"
        assert result["rubric"]["totalScore"] == 100

    def test_subjective_without_rubric_gets_default(self):
        """主观题没有 rubric 时应自动补充默认 rubric。"""
        raw = {
            "questionType": "subjective",
            "content": "请描述...",
            "options": [],
            "correctAnswer": None,
            "explanation": "解释",
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["questionType"] == "subjective"
        assert result["rubric"] == _DEFAULT_SUBJECTIVE_RUBRIC
        assert result["rubric"]["totalScore"] == 100
        assert len(result["rubric"]["criteria"]) > 0

    def test_subjective_with_empty_rubric_criteria_gets_default(self):
        """主观题 rubric 无 criteria 时应自动补充默认 rubric。"""
        raw = {
            "questionType": "subjective",
            "content": "请描述...",
            "options": [],
            "correctAnswer": None,
            "explanation": "解释",
            "rubric": {"totalScore": 100, "criteria": []},
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["rubric"] == _DEFAULT_SUBJECTIVE_RUBRIC

    def test_non_subjective_rubric_set_to_none(self):
        """非主观题的 rubric 应被置为 None。"""
        raw = {
            "questionType": "single_choice",
            "content": "题目",
            "options": [],
            "correctAnswer": "A",
            "explanation": "解释",
            "rubric": {"totalScore": 100, "criteria": [{"name": "x", "score": 10, "description": "y"}]},
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["rubric"] is None

    def test_invalid_question_type_returns_none(self):
        raw = {"questionType": "essay", "content": "题目", "options": [], "correctAnswer": None, "explanation": "解释"}
        assert _validate_and_normalize_question(raw) is None

    def test_empty_question_type_returns_none(self):
        raw = {"questionType": "", "content": "题目", "options": [], "correctAnswer": None, "explanation": "解释"}
        assert _validate_and_normalize_question(raw) is None

    def test_missing_question_type_returns_none(self):
        raw = {"content": "题目", "options": [], "correctAnswer": None, "explanation": "解释"}
        assert _validate_and_normalize_question(raw) is None

    def test_empty_content_returns_none(self):
        raw = {"questionType": "single_choice", "content": "", "options": [], "correctAnswer": "A", "explanation": "解释"}
        assert _validate_and_normalize_question(raw) is None

    def test_options_filtered_to_valid_only(self):
        """只有含 label/text 的 dict 才保留。"""
        raw = {
            "questionType": "single_choice",
            "content": "题目",
            "options": [
                {"label": "A", "text": "正确"},
                {"bad": "data"},
                "not a dict",
                {"label": "B", "text": "选项B"},
            ],
            "correctAnswer": "A",
            "explanation": "解释",
            "rubric": None,
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert len(result["options"]) == 2
        assert result["options"][0].label == "A"
        assert result["options"][1].label == "B"

    def test_missing_options_defaults_to_empty(self):
        raw = {
            "questionType": "subjective",
            "content": "题目",
            "correctAnswer": None,
            "explanation": "解释",
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["options"] == []

    def test_correct_answer_coerced_to_string(self):
        raw = {
            "questionType": "true_false",
            "content": "题目",
            "options": [],
            "correctAnswer": True,
            "explanation": "解释",
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["correctAnswer"] == "True"

    def test_none_values_preserved(self):
        raw = {
            "questionType": "subjective",
            "content": "题目",
            "options": [],
            "correctAnswer": None,
            "explanation": None,
        }
        result = _validate_and_normalize_question(raw)
        assert result is not None
        assert result["correctAnswer"] is None
        assert result["explanation"] is None


# ---------------------------------------------------------------------------
# _generate_questions_with_llm
# ---------------------------------------------------------------------------


class TestGenerateQuestionsWithLlm:
    """_generate_questions_with_llm 测试集。"""

    @patch("app.services.training_question_service.call_llm")
    def test_returns_none_when_llm_error(self, mock_llm):
        from app.services.training_llm_client import LLMCallError
        mock_llm.side_effect = LLMCallError("LLM endpoint 未配置。")
        result = _generate_questions_with_llm(
            MagicMock(), job_title="测试", count=3, evidence_summaries=[]
        )
        assert result is None

    @patch("app.services.training_question_service.record_training_skill_call")
    @patch("app.services.training_question_service.call_llm")
    def test_success_returns_normalized_questions(self, mock_llm, mock_record):
        llm_output = json.dumps([
            {
                "questionType": "single_choice",
                "content": "题目一",
                "options": [{"label": "A", "text": "对"}, {"label": "B", "text": "错"}],
                "correctAnswer": "A",
                "explanation": "解释",
                "rubric": None,
            },
            {
                "questionType": "subjective",
                "content": "题目二",
                "options": [],
                "correctAnswer": None,
                "explanation": "解释",
            },
        ], ensure_ascii=False)
        mock_llm.return_value = llm_output

        session = MagicMock()
        result = _generate_questions_with_llm(
            session, job_title="测试", count=2, evidence_summaries=["证据"]
        )
        assert result is not None
        assert len(result) == 2
        assert result[0]["questionType"] == "single_choice"
        assert result[1]["questionType"] == "subjective"
        assert result[1]["rubric"] == _DEFAULT_SUBJECTIVE_RUBRIC
        mock_record.assert_called_once()
        assert mock_record.call_args[1]["status"] == "success"

    @patch("app.services.training_question_service.record_training_skill_call")
    @patch("app.services.training_question_service.call_llm")
    def test_llm_error_returns_none(self, mock_llm, mock_record):
        from app.services.training_llm_client import LLMCallError
        mock_llm.side_effect = LLMCallError("connection failed")

        session = MagicMock()
        result = _generate_questions_with_llm(
            session, job_title="测试", count=2, evidence_summaries=[]
        )
        assert result is None
        mock_record.assert_called_once()
        assert mock_record.call_args[1]["status"] == "error"
        assert mock_record.call_args[1]["error_code"] == "LLM_ERROR"

    @patch("app.services.training_question_service.record_training_skill_call")
    @patch("app.services.training_question_service.call_llm")
    def test_invalid_json_returns_none(self, mock_llm, mock_record):
        mock_llm.return_value = "not json"

        session = MagicMock()
        result = _generate_questions_with_llm(
            session, job_title="测试", count=2, evidence_summaries=[]
        )
        assert result is None
        mock_record.assert_called_once()
        assert mock_record.call_args[1]["error_code"] == "LLM_PARSE_ERROR"

    @patch("app.services.training_question_service.record_training_skill_call")
    @patch("app.services.training_question_service.call_llm")
    def test_all_invalid_questions_returns_none(self, mock_llm, mock_record):
        """当所有题目校验失败时应返回 None。"""
        llm_output = json.dumps([
            {"questionType": "essay", "content": "题目", "options": [], "correctAnswer": None, "explanation": "解释"},
        ])
        mock_llm.return_value = llm_output

        session = MagicMock()
        result = _generate_questions_with_llm(
            session, job_title="测试", count=1, evidence_summaries=[]
        )
        assert result is None
        assert mock_record.call_args[1]["error_code"] == "LLM_VALIDATION_ERROR"

    @patch("app.services.training_question_service.record_training_skill_call")
    @patch("app.services.training_question_service.call_llm")
    def test_partial_valid_questions_returned(self, mock_llm, mock_record):
        """部分题目校验失败时，只返回有效的。"""
        llm_output = json.dumps([
            {
                "questionType": "single_choice",
                "content": "有效题目",
                "options": [{"label": "A", "text": "对"}],
                "correctAnswer": "A",
                "explanation": "解释",
                "rubric": None,
            },
            {"questionType": "essay", "content": "无效题型", "options": [], "correctAnswer": None, "explanation": "解释"},
        ])
        mock_llm.return_value = llm_output

        session = MagicMock()
        result = _generate_questions_with_llm(
            session, job_title="测试", count=2, evidence_summaries=[]
        )
        assert result is not None
        assert len(result) == 1
        assert result[0]["questionType"] == "single_choice"

    @patch("app.services.training_question_service.record_training_skill_call")
    @patch("app.services.training_question_service.call_llm")
    def test_fenced_json_parsed(self, mock_llm, mock_record):
        """LLM 返回 fenced code block 时应正常解析。"""
        llm_output = '```json\n[{"questionType": "true_false", "content": "判断题", "options": [{"label": "true", "text": "对"}], "correctAnswer": "true", "explanation": "解释"}]\n```'
        mock_llm.return_value = llm_output

        session = MagicMock()
        result = _generate_questions_with_llm(
            session, job_title="测试", count=1, evidence_summaries=[]
        )
        assert result is not None
        assert len(result) == 1
        assert result[0]["questionType"] == "true_false"

    @patch("app.services.training_question_service.record_training_skill_call")
    @patch("app.services.training_question_service.call_llm")
    def test_subjective_without_rubric_gets_default(self, mock_llm, mock_record):
        """LLM 返回的主观题缺少 rubric 时应自动补充。"""
        llm_output = json.dumps([
            {
                "questionType": "subjective",
                "content": "请描述...",
                "options": [],
                "correctAnswer": None,
                "explanation": "解释",
            },
        ])
        mock_llm.return_value = llm_output

        session = MagicMock()
        result = _generate_questions_with_llm(
            session, job_title="测试", count=1, evidence_summaries=["证据"]
        )
        assert result is not None
        assert len(result) == 1
        assert result[0]["questionType"] == "subjective"
        assert result[0]["rubric"] == _DEFAULT_SUBJECTIVE_RUBRIC
