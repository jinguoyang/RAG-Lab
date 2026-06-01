"""Agent Runtime Task 1 & 2: 配置默认值与 ChatModel Adapter 测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import Settings


# ---------------------------------------------------------------------------
# Task 1: 配置默认值
# ---------------------------------------------------------------------------


def test_agent_runtime_defaults_to_legacy_and_disabled():
    settings = Settings(_env_file=None)

    assert settings.agent_runtime_enabled is False
    assert settings.agent_runtime_default_version == "legacy_v1"
    assert settings.agent_runtime_checkpoint_backend == "postgres"
    assert settings.agent_runtime_summary_trigger_tokens == 4000
    assert settings.agent_runtime_summary_keep_messages == 20


# ---------------------------------------------------------------------------
# Task 2: ChatModel Adapter
# ---------------------------------------------------------------------------


from app.services.agent_runtime.model_adapter import _openai_base_url, create_chat_model


def test_create_chat_model_uses_existing_openai_compatible_settings():
    settings = SimpleNamespace(
        llm_model="private-model",
        llm_endpoint="http://llm.local/v1/chat/completions",
        llm_api_key="secret",
    )
    with patch("app.services.agent_runtime.model_adapter.ChatOpenAI") as chat_model:
        create_chat_model(settings)

    chat_model.assert_called_once_with(
        model="private-model",
        api_key="secret",
        base_url="http://llm.local/v1",
        timeout=60,
        max_retries=2,
    )


def test_openai_base_url_removes_chat_completions_suffix():
    assert _openai_base_url("http://llm.local/v1/chat/completions") == "http://llm.local/v1"


def test_openai_base_url_handles_no_suffix():
    assert _openai_base_url("http://llm.local/v1") == "http://llm.local/v1"


def test_create_chat_model_raises_when_endpoint_missing():
    settings = SimpleNamespace(llm_model="m", llm_endpoint=None, llm_api_key="k")
    import pytest

    with pytest.raises(ValueError, match="LLM endpoint"):
        create_chat_model(settings)
