"""Task 1: VisionTextProvider 配置与 Provider 抽象测试。"""

import pytest

from app.core.config import Settings
from app.services.qa_providers import ProviderError
from app.services.vision_text_provider import (
    HttpVisionTextProvider,
    LocalVisionTextProvider,
    VisionTextProvider,
)


def test_vision_settings_inherit_llm_config():
    """默认视觉配置应继承 LLM 配置，当 vision_text_* 为 None 时回落到 llm_*。"""
    settings = Settings(
        _env_file=None,
        RAG_LAB_LLM_PROVIDER="http",
        RAG_LAB_LLM_ENDPOINT="https://llm.example.com/v1/chat/completions",
        RAG_LAB_LLM_API_KEY="sk-llm-key",
        RAG_LAB_LLM_MODEL="gpt-4o",
    )
    assert settings.vision_text_provider == "http"
    assert settings.vision_text_endpoint is None
    assert settings.vision_text_api_key is None
    assert settings.vision_text_model is None
    assert settings.vision_text_max_image_side == 1600


def test_vision_settings_explicit_override():
    """显式设置视觉配置应覆盖 LLM 配置。"""
    settings = Settings(
        _env_file=None,
        RAG_LAB_VISION_TEXT_PROVIDER="http",
        RAG_LAB_VISION_TEXT_ENDPOINT="https://vision.example.com/v1/chat/completions",
        RAG_LAB_VISION_TEXT_API_KEY="sk-vision-key",
        RAG_LAB_VISION_TEXT_MODEL="gpt-4o-mini",
        RAG_LAB_VISION_TEXT_MAX_IMAGE_SIDE=1024,
    )
    assert settings.vision_text_endpoint == "https://vision.example.com/v1/chat/completions"
    assert settings.vision_text_api_key == "sk-vision-key"
    assert settings.vision_text_model == "gpt-4o-mini"
    assert settings.vision_text_max_image_side == 1024


def test_vision_text_provider_is_abstract():
    """VisionTextProvider 是抽象基类，不能直接实例化。"""
    with pytest.raises(TypeError):
        VisionTextProvider()  # type: ignore[abstract]


def test_local_vision_text_provider_returns_stable_data():
    """LocalVisionTextProvider 应返回固定的测试数据。"""
    provider = LocalVisionTextProvider()
    result = provider.extract_text(b"fake-image-bytes")
    assert result.caption == "本地 Vision Provider 测试 caption"
    assert result.ocr_text == "本地 Vision Provider 测试 OCR 文本"
    assert result.structured_summary == "本地 Vision Provider 测试结构化摘要"


def test_local_vision_text_provider_returns_dict():
    """LocalVisionTextProvider.extract_text 返回值可序列化为 dict。"""
    provider = LocalVisionTextProvider()
    result = provider.extract_text(b"fake-image-bytes")
    data = result.model_dump()
    assert "caption" in data
    assert "ocr_text" in data
    assert "structured_summary" in data


def test_http_vision_text_provider_inherits_llm_config():
    """HttpVisionTextProvider 为空配置时应继承 LLM endpoint/key/model。"""
    settings = Settings(
        _env_file=None,
        RAG_LAB_LLM_PROVIDER="http",
        RAG_LAB_LLM_ENDPOINT="https://llm.example.com/v1/chat/completions",
        RAG_LAB_LLM_API_KEY="sk-llm-key",
        RAG_LAB_LLM_MODEL="gpt-4o",
        RAG_LAB_VISION_TEXT_PROVIDER="http",
    )
    provider = HttpVisionTextProvider(settings)
    assert provider._endpoint == "https://llm.example.com/v1/chat/completions"
    assert provider._api_key == "sk-llm-key"
    assert provider._model == "gpt-4o"


def test_http_vision_text_provider_explicit_config():
    """HttpVisionTextProvider 显式配置应优先于 LLM 配置。"""
    settings = Settings(
        _env_file=None,
        RAG_LAB_LLM_ENDPOINT="https://llm.example.com/v1/chat/completions",
        RAG_LAB_LLM_API_KEY="sk-llm-key",
        RAG_LAB_LLM_MODEL="gpt-4o",
        RAG_LAB_VISION_TEXT_PROVIDER="http",
        RAG_LAB_VISION_TEXT_ENDPOINT="https://vision.example.com/v1/chat/completions",
        RAG_LAB_VISION_TEXT_API_KEY="sk-vision-key",
        RAG_LAB_VISION_TEXT_MODEL="gpt-4o-mini",
    )
    provider = HttpVisionTextProvider(settings)
    assert provider._endpoint == "https://vision.example.com/v1/chat/completions"
    assert provider._api_key == "sk-vision-key"
    assert provider._model == "gpt-4o-mini"


def test_http_vision_text_provider_requires_endpoint():
    """HttpVisionTextProvider 无 endpoint 时应抛出 ProviderError。"""
    settings = Settings(_env_file=None, RAG_LAB_VISION_TEXT_PROVIDER="http")
    with pytest.raises(ProviderError):
        HttpVisionTextProvider(settings)
