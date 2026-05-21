"""Task 1 & 2: VisionTextProvider 配置与图片解析集成测试。"""

import struct
import zlib
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.services.document_parsing import DocumentParseError, parse_document
from app.services.qa_providers import ProviderError
from app.services.vision_text_provider import (
    HttpVisionTextProvider,
    LocalVisionTextProvider,
    VisionTextProvider,
    get_vision_text_provider,
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


def test_vision_text_provider_base_raises_not_implemented():
    """VisionTextProvider 基类 extract_text 应抛出 NotImplementedError。"""
    provider = VisionTextProvider()
    with pytest.raises(NotImplementedError):
        provider.extract_text(b"fake-image-bytes")


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


# ---------------------------------------------------------------------------
# Task 2: 图片解析接入 document_parsing
# ---------------------------------------------------------------------------


def _make_tiny_png() -> bytes:
    """Create a minimal valid 1x1 white PNG for testing."""
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", len(ihdr_data)) + b"IHDR" + ihdr_data + ihdr_crc
    raw_data = b"\x00\xff\xff\xff"
    compressed = zlib.compress(raw_data)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
    return signature + ihdr + idat + iend


def test_get_vision_text_provider_local():
    """vision_text_provider=local 时应返回 LocalVisionTextProvider。"""
    settings = Settings(_env_file=None, RAG_LAB_VISION_TEXT_PROVIDER="local")
    provider = get_vision_text_provider(settings)
    assert isinstance(provider, LocalVisionTextProvider)


def test_get_vision_text_provider_http():
    """vision_text_provider=http 时应返回 HttpVisionTextProvider。"""
    settings = Settings(
        _env_file=None,
        RAG_LAB_VISION_TEXT_PROVIDER="http",
        RAG_LAB_LLM_ENDPOINT="https://llm.example.com/v1/chat/completions",
        RAG_LAB_LLM_API_KEY="sk-llm-key",
    )
    provider = get_vision_text_provider(settings)
    assert isinstance(provider, HttpVisionTextProvider)


def test_parse_png_returns_parsed_document():
    """上传 .png 应返回 ParsedDocument，parser_name 为 vision_text。"""
    png_bytes = _make_tiny_png()
    with patch("app.services.document_parsing.get_vision_text_provider") as mock_factory:
        mock_factory.return_value = LocalVisionTextProvider()
        result = parse_document("test.png", "image/png", png_bytes)

    assert result.parser_name == "vision_text"
    assert result.source_file_name == "test.png"
    assert len(result.chunks) >= 1


def test_parse_png_chunk_content_contains_caption_and_ocr():
    """图片 chunk content 应包含图片描述和 OCR 文本。"""
    png_bytes = _make_tiny_png()
    with patch("app.services.document_parsing.get_vision_text_provider") as mock_factory:
        mock_factory.return_value = LocalVisionTextProvider()
        result = parse_document("test.png", "image/png", png_bytes)

    all_content = " ".join(c.content for c in result.chunks)
    assert "本地 Vision Provider 测试 caption" in all_content
    assert "本地 Vision Provider 测试 OCR 文本" in all_content


def test_parse_png_chunk_metadata_has_image_fields():
    """图片 chunk metadata 应包含 sourceModality、region、visionConfidence。"""
    png_bytes = _make_tiny_png()
    with patch("app.services.document_parsing.get_vision_text_provider") as mock_factory:
        mock_factory.return_value = LocalVisionTextProvider()
        result = parse_document("test.png", "image/png", png_bytes)

    first_chunk = result.chunks[0]
    assert first_chunk.metadata["sourceModality"] == "image"
    assert first_chunk.metadata["parserName"] == "vision_text"
    assert first_chunk.metadata["region"] == "full"
    assert first_chunk.metadata["visionConfidence"] == "unknown"


def test_parse_image_empty_content_raises():
    """视觉 Provider 返回空内容时应抛出 PARSE_EMPTY_CONTENT。"""
    from app.services.vision_text_provider import VisionTextResult

    png_bytes = _make_tiny_png()
    empty_provider = LocalVisionTextProvider()
    empty_provider.extract_text = lambda _: VisionTextResult(caption="", ocr_text="", structured_summary="")
    with patch("app.services.document_parsing.get_vision_text_provider") as mock_factory:
        mock_factory.return_value = empty_provider
        with pytest.raises(DocumentParseError) as exc_info:
            parse_document("test.png", "image/png", png_bytes)
    assert exc_info.value.error_code == "PARSE_EMPTY_CONTENT"


def test_parse_unsupported_image_extension_raises():
    """非白名单图片格式（如 .bmp）应返回 UNSUPPORTED_FILE_TYPE。"""
    with pytest.raises(DocumentParseError) as exc_info:
        parse_document("test.bmp", "image/bmp", b"\x00")
    assert exc_info.value.error_code == "UNSUPPORTED_FILE_TYPE"


def test_parse_jpg_supported():
    """.jpg 应走图片解析分支。"""
    png_bytes = _make_tiny_png()  # 用 png bytes 做 fake，mock 后不会真正解码
    with patch("app.services.document_parsing.get_vision_text_provider") as mock_factory:
        mock_factory.return_value = LocalVisionTextProvider()
        result = parse_document("photo.jpg", "image/jpeg", png_bytes)

    assert result.parser_name == "vision_text"


def test_parse_jpeg_supported():
    """.jpeg 应走图片解析分支。"""
    png_bytes = _make_tiny_png()
    with patch("app.services.document_parsing.get_vision_text_provider") as mock_factory:
        mock_factory.return_value = LocalVisionTextProvider()
        result = parse_document("photo.jpeg", "image/jpeg", png_bytes)

    assert result.parser_name == "vision_text"


def test_parse_webp_supported():
    """.webp 应走图片解析分支。"""
    png_bytes = _make_tiny_png()
    with patch("app.services.document_parsing.get_vision_text_provider") as mock_factory:
        mock_factory.return_value = LocalVisionTextProvider()
        result = parse_document("photo.webp", "image/webp", png_bytes)

    assert result.parser_name == "vision_text"
