"""LLM 讲解生成测试。"""
from unittest.mock import MagicMock, patch
import json

from app.services.app_runtime_service import _generate_explain_with_llm


class TestLLMExplainGeneration:
    @patch("app.services.app_runtime_service._build_provider_set")
    def test_generates_structured_explanation(self, mock_providers):
        llm_response = json.dumps({
            "summary": "安全操作的核心要点",
            "keyPoints": ["操作前检查设备状态", "佩戴防护装备", "遵守操作流程"],
        }, ensure_ascii=False)

        mock_llm = MagicMock()
        mock_llm._chat.return_value = llm_response
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_explain_with_llm("安全操作", "安全操作要求操作前检查设备状态，佩戴防护装备...")
        assert result is not None
        assert len(result["keyPoints"]) == 3
        assert "操作前检查" in result["keyPoints"][0]

    @patch("app.services.app_runtime_service._build_provider_set")
    def test_invalid_json_returns_none(self, mock_providers):
        mock_llm = MagicMock()
        mock_llm._chat.return_value = "invalid"
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_explain_with_llm("topic", "content")
        assert result is None
