"""培训模块统一 LLM 客户端测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.training_llm_client import call_llm


@patch("app.services.training_llm_client.httpx.post")
@patch("app.services.training_llm_client.get_settings")
def test_mimo_structured_call_can_disable_thinking(mock_settings, mock_post):
    """MiMo 的结构化任务应能关闭默认思考模式，避免推理耗尽输出预算。"""
    mock_settings.return_value = MagicMock(
        llm_endpoint="https://example.test/v1/chat/completions",
        llm_api_key="secret",
        llm_model="mimo-v2.5",
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"ok":true}'}}],
    }
    mock_post.return_value = mock_response

    result = call_llm(
        [{"role": "user", "content": "返回 JSON"}],
        max_tokens=128,
        disable_thinking=True,
    )

    assert result == '{"ok":true}'
    assert mock_post.call_args.kwargs["json"]["thinking"] == {"type": "disabled"}


@patch("app.services.training_llm_client.httpx.post")
@patch("app.services.training_llm_client.get_settings")
def test_non_mimo_call_does_not_send_thinking_extension(mock_settings, mock_post):
    """其他兼容模型不应收到 MiMo 专用扩展字段。"""
    mock_settings.return_value = MagicMock(
        llm_endpoint="https://example.test/v1/chat/completions",
        llm_api_key="secret",
        llm_model="other-model",
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
    }
    mock_post.return_value = mock_response

    call_llm(
        [{"role": "user", "content": "hello"}],
        disable_thinking=True,
    )

    assert "thinking" not in mock_post.call_args.kwargs["json"]
