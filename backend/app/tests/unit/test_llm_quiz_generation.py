"""LLM 测验生成测试。"""
from unittest.mock import MagicMock, patch
import json

import pytest

from app.services.app_runtime_service import _generate_quiz_with_llm


class TestLLMQuizGeneration:
    """_generate_quiz_with_llm 应调用 LLM 生成结构化测验。"""

    @patch("app.services.app_runtime_service._build_provider_set")
    def test_generates_valid_quiz_json(self, mock_providers):
        """LLM 返回有效 JSON 时，应解析为标准 quiz 结构。"""
        llm_response = json.dumps({
            "questions": [
                {
                    "questionId": "q1",
                    "type": "single_choice",
                    "stem": "根据安全规程，操作前应首先做什么？",
                    "options": ["检查设备状态", "直接开始操作", "通知同事", "记录时间"],
                    "correctAnswer": "检查设备状态",
                    "explanation": "安全规程要求操作前必须先检查设备状态。",
                }
            ]
        }, ensure_ascii=False)

        mock_llm = MagicMock()
        mock_llm._chat.return_value = llm_response
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_quiz_with_llm("安全操作", "安全规程要求操作前检查设备...", 1, "normal")
        assert "questions" in result
        assert len(result["questions"]) == 1
        assert result["questions"][0]["type"] == "single_choice"
        assert result["questions"][0]["correctAnswer"] == "检查设备状态"

    @patch("app.services.app_runtime_service._build_provider_set")
    def test_llm_invalid_json_falls_back(self, mock_providers):
        """LLM 返回无效 JSON 时，应返回 None。"""
        mock_llm = MagicMock()
        mock_llm._chat.return_value = "not valid json"
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_quiz_with_llm("topic", "answer", 2, "normal")
        assert result is None
