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


# ---------------------------------------------------------------------------
# Task 3: 文档与 ParseRevision 元数据落库
# ---------------------------------------------------------------------------


def test_version_dto_includes_image_fields():
    """DocumentVersionDTO 应支持 sourceModality 和 image 字段。"""
    from app.schemas.document import DocumentVersionDTO

    dto = DocumentVersionDTO(
        versionId="test-version-id",
        documentId="test-doc-id",
        versionNo=1,
        sourceFileId="test-file-id",
        status="active",
        parseStatus="success",
        denseIndexStatus="success",
        sparseIndexStatus="not_required",
        graphIndexStatus="not_required",
        retrievalReady=True,
        chunkCount=1,
        tokenCount=100,
        createdAt="2024-01-01T00:00:00",
        updatedAt="2024-01-01T00:00:00",
        sourceModality="image",
        image={"region": "full", "visionConfidence": "unknown"},
    )
    assert dto.sourceModality == "image"
    assert dto.image == {"region": "full", "visionConfidence": "unknown"}


def test_version_dto_text_document_has_no_image_fields():
    """普通文档 DocumentVersionDTO 的 image 字段应为 None。"""
    from app.schemas.document import DocumentVersionDTO

    dto = DocumentVersionDTO(
        versionId="test-version-id",
        documentId="test-doc-id",
        versionNo=1,
        sourceFileId="test-file-id",
        status="active",
        parseStatus="success",
        denseIndexStatus="success",
        sparseIndexStatus="not_required",
        graphIndexStatus="not_required",
        retrievalReady=True,
        chunkCount=1,
        tokenCount=100,
        createdAt="2024-01-01T00:00:00",
        updatedAt="2024-01-01T00:00:00",
    )
    assert dto.sourceModality is None
    assert dto.image is None


def test_to_version_dto_extracts_image_metadata():
    """_to_version_dto 应从 metadata 中提取图片 sourceModality 和 image 信息。"""
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.services.document_service import _to_version_dto

    row = {
        "version_id": uuid4(),
        "document_id": uuid4(),
        "version_no": 1,
        "source_file_id": uuid4(),
        "status": "active",
        "parse_status": "success",
        "dense_index_status": "success",
        "sparse_index_status": "not_required",
        "graph_index_status": "not_required",
        "retrieval_ready": True,
        "chunk_count": 1,
        "token_count": 100,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": {
            "sourceModality": "image",
            "visionTextProvider": "http",
            "image": {
                "region": "full",
                "visionConfidence": "unknown",
            },
        },
    }
    dto = _to_version_dto(row)
    assert dto.sourceModality == "image"
    assert dto.image == {"region": "full", "visionConfidence": "unknown"}


def test_to_version_dto_text_document_no_image():
    """普通文档 _to_version_dto 的 sourceModality 和 image 应为 None。"""
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.services.document_service import _to_version_dto

    row = {
        "version_id": uuid4(),
        "document_id": uuid4(),
        "version_no": 1,
        "source_file_id": uuid4(),
        "status": "active",
        "parse_status": "success",
        "dense_index_status": "success",
        "sparse_index_status": "not_required",
        "graph_index_status": "not_required",
        "retrieval_ready": True,
        "chunk_count": 1,
        "token_count": 100,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": {
            "parserName": "markdown",
        },
    }
    dto = _to_version_dto(row)
    assert dto.sourceModality is None
    assert dto.image is None


# ---------------------------------------------------------------------------
# Task 3 continued: run_ingest_job 生产端元数据验证
# ---------------------------------------------------------------------------


def _make_run_ingest_job_mocks():
    """为 run_ingest_job 构造最小 mock 环境，返回 (session, mock_create_rev) 及相关对象。"""
    from unittest.mock import MagicMock, patch
    from uuid import uuid4

    from app.services.document_parsing import ParsedDocument, ParsedChunk

    kb_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    file_id = uuid4()
    job_id = uuid4()
    user_id = uuid4()

    job_row = {
        "job_id": job_id,
        "kb_id": kb_id,
        "version_id": version_id,
        "document_id": doc_id,
        "status": "pending",
        "result_summary": {},
    }
    version_row = {
        "version_id": version_id,
        "document_id": doc_id,
        "source_file_id": file_id,
        "metadata": None,
    }
    document_row = {
        "document_id": doc_id,
        "kb_id": kb_id,
        "name": "test.png",
        "source_type": "upload",
        "active_version_id": version_id,
        "status": "active",
    }
    file_row = {
        "file_id": file_id,
        "file_name": "test.png",
        "file_hash": "abc123",
        "mime_type": "image/png",
    }

    parsed_doc = ParsedDocument(
        parser_name="vision_text",
        parser_version="1.0",
        source_file_name="test.png",
        mime_type="image/png",
        chunks=[
            ParsedChunk(
                content="image caption text",
                token_count=10,
                section=None,
                page_no=None,
                metadata={
                    "sourceModality": "image",
                    "parserName": "vision_text",
                    "region": "full",
                    "visionConfidence": "unknown",
                },
            )
        ],
    )

    current_user = MagicMock()
    current_user.user.userId = str(user_id)

    kb_row = {
        "kb_id": kb_id,
        "sparse_index_enabled": False,
        "graph_index_enabled": False,
        "sparse_required_for_activation": False,
        "graph_required_for_activation": False,
    }

    mock_settings = MagicMock()
    mock_settings.vision_text_provider = "http"
    mock_settings.vision_text_model = "gpt-4o-mini"
    mock_settings.vision_text_max_image_side = 1600
    mock_settings.llm_model = "gpt-4o"
    mock_settings.embedding_provider = "openai"
    mock_settings.embedding_model = "text-embedding-3-small"

    mock_provider_set = MagicMock()
    mock_provider_set.embedding.embed_query.return_value = [0.1] * 1536

    # session.execute side_effect: 按调用顺序返回不同结果
    chunk_id = uuid4()
    chunk_row = {
        "chunk_id": chunk_id,
        "version_id": version_id,
        "document_id": doc_id,
        "kb_id": kb_id,
        "chunk_index": 1,
        "content": "image caption text",
        "token_count": 10,
        "metadata": {},
        "status": "active",
    }

    def _select_result(mapping):
        r = MagicMock()
        r.mappings.return_value.first.return_value = mapping
        return r

    def _insert_result(mapping):
        r = MagicMock()
        r.mappings.return_value.one.return_value = mapping
        return r

    execute_returns = [
        _select_result(job_row),       # 1: select(ingest_jobs)
        _select_result(version_row),   # 2: select(document_versions)
        _select_result(document_row),  # 3: select(documents)
        _select_result(file_row),      # 4: select(stored_files)
        MagicMock(),                   # 5: update(ingest_jobs) started_at
        MagicMock(),                   # 6: update(document_versions) processing
        iter([]),                      # 7: select(chunks) old_chunk_ids → empty
        MagicMock(),                   # 8: delete(chunk_access_filters)
        MagicMock(),                   # 9: delete(graph_chunk_refs)
        MagicMock(),                   # 10: delete(chunks)
        _insert_result(chunk_row),     # 11: insert(chunks)
        MagicMock(),                   # 12: update(document_versions) final metadata
        _insert_result(job_row),       # 13: update(ingest_jobs) final
    ]
    call_idx = {"i": 0}
    captured_executes = []

    def execute_side_effect(stmt):
        captured_executes.append(stmt)
        idx = call_idx["i"]
        call_idx["i"] += 1
        if idx < len(execute_returns):
            return execute_returns[idx]
        return MagicMock()

    session = MagicMock()
    session.execute.side_effect = execute_side_effect

    return {
        "session": session,
        "current_user": current_user,
        "kb_row": kb_row,
        "job_id": job_id,
        "source_bytes": b"\x89PNG\r\n\x1a\n",
        "parsed_doc": parsed_doc,
        "mock_settings": mock_settings,
        "mock_provider_set": mock_provider_set,
        "captured_executes": captured_executes,
    }


def test_run_ingest_job_parse_revision_options_contain_source_modality():
    """run_ingest_job 处理图片时，ParseRevision.parse_options 应含 sourceModality='image'。"""
    from unittest.mock import patch

    from app.services.document_service import run_ingest_job

    env = _make_run_ingest_job_mocks()

    with (
        patch("app.services.document_service.parse_document", return_value=env["parsed_doc"]),
        patch("app.services.document_service.get_settings", return_value=env["mock_settings"]),
        patch("app.services.document_service.get_qa_run_providers", return_value=env["mock_provider_set"]),
        patch("app.services.document_service._update_ingest_progress"),
        patch("app.services.document_service.mark_graph_snapshots_stale"),
        patch("app.services.document_service._write_chunk_access_filters", return_value={}),
        patch("app.services.document_service.build_chunk_index_payload", return_value={"content": "x"}),
        patch("app.services.document_service._create_index_sync_job", return_value=(None, "success", None)),
        patch("app.services.document_service._read_ingest_chunk_revision", return_value=None),
        patch("app.services.document_service.create_parse_revision") as mock_create_rev,
    ):
        run_ingest_job(
            env["session"],
            env["current_user"],
            env["kb_row"],
            env["job_id"],
            source_bytes=env["source_bytes"],
        )

    mock_create_rev.assert_called_once()
    kwargs = mock_create_rev.call_args.kwargs
    assert kwargs["parse_options"] is not None
    assert kwargs["parse_options"]["sourceModality"] == "image"


def test_run_ingest_job_version_metadata_contains_vision_text_provider():
    """run_ingest_job 处理图片时，DocumentVersion.metadata 应含 visionTextProvider。"""
    from unittest.mock import patch

    import sqlalchemy as sa

    from app.services.document_service import run_ingest_job

    env = _make_run_ingest_job_mocks()

    with (
        patch("app.services.document_service.parse_document", return_value=env["parsed_doc"]),
        patch("app.services.document_service.get_settings", return_value=env["mock_settings"]),
        patch("app.services.document_service.get_qa_run_providers", return_value=env["mock_provider_set"]),
        patch("app.services.document_service._update_ingest_progress"),
        patch("app.services.document_service.mark_graph_snapshots_stale"),
        patch("app.services.document_service._write_chunk_access_filters", return_value={}),
        patch("app.services.document_service.build_chunk_index_payload", return_value={"content": "x"}),
        patch("app.services.document_service._create_index_sync_job", return_value=(None, "success", None)),
        patch("app.services.document_service._read_ingest_chunk_revision", return_value=None),
        patch("app.services.document_service.create_parse_revision"),
    ):
        run_ingest_job(
            env["session"],
            env["current_user"],
            env["kb_row"],
            env["job_id"],
            source_bytes=env["source_bytes"],
        )

    # 从 captured_executes 中找到包含 metadata 的 update(document_versions) 调用
    found_vision_provider = False
    for stmt in env["captured_executes"]:
        if isinstance(stmt, sa.Update):
            compiled = stmt.compile()
            meta = compiled.params.get("metadata")
            if isinstance(meta, dict) and "visionTextProvider" in meta:
                assert meta["visionTextProvider"] == "http"
                assert meta["sourceModality"] == "image"
                found_vision_provider = True
                break

    assert found_vision_provider, "DocumentVersion metadata 中未找到 visionTextProvider"


# ---------------------------------------------------------------------------
# Task 4: Image Chunk Ingest and Index Sync Verification
# ---------------------------------------------------------------------------


def test_run_ingest_job_image_chunk_content_not_empty():
    """图片 Chunk 入库后 content 应不为空。"""
    from unittest.mock import patch

    import sqlalchemy as sa

    from app.services.document_service import run_ingest_job

    env = _make_run_ingest_job_mocks()

    with (
        patch("app.services.document_service.parse_document", return_value=env["parsed_doc"]),
        patch("app.services.document_service.get_settings", return_value=env["mock_settings"]),
        patch("app.services.document_service.get_qa_run_providers", return_value=env["mock_provider_set"]),
        patch("app.services.document_service._update_ingest_progress"),
        patch("app.services.document_service.mark_graph_snapshots_stale"),
        patch("app.services.document_service._write_chunk_access_filters", return_value={}),
        patch("app.services.document_service.build_chunk_index_payload", return_value={"content": "x"}),
        patch("app.services.document_service._create_index_sync_job", return_value=(None, "success", None)),
        patch("app.services.document_service._read_ingest_chunk_revision", return_value=None),
        patch("app.services.document_service.create_parse_revision"),
    ):
        run_ingest_job(
            env["session"],
            env["current_user"],
            env["kb_row"],
            env["job_id"],
            source_bytes=env["source_bytes"],
        )

    # Find the chunk insert statement in captured executes
    found_chunk_insert = False
    for stmt in env["captured_executes"]:
        if isinstance(stmt, sa.Insert):
            compiled = stmt.compile()
            content = compiled.params.get("content")
            if content is not None and isinstance(content, str):
                assert content.strip() != "", "Chunk content should not be empty"
                found_chunk_insert = True
                break

    assert found_chunk_insert, "未找到 chunk insert 语句"


def test_run_ingest_job_image_chunk_metadata_source_modality():
    """图片 Chunk metadata 应含 sourceModality='image'。"""
    from unittest.mock import patch

    import sqlalchemy as sa

    from app.services.document_service import run_ingest_job

    env = _make_run_ingest_job_mocks()

    with (
        patch("app.services.document_service.parse_document", return_value=env["parsed_doc"]),
        patch("app.services.document_service.get_settings", return_value=env["mock_settings"]),
        patch("app.services.document_service.get_qa_run_providers", return_value=env["mock_provider_set"]),
        patch("app.services.document_service._update_ingest_progress"),
        patch("app.services.document_service.mark_graph_snapshots_stale"),
        patch("app.services.document_service._write_chunk_access_filters", return_value={}),
        patch("app.services.document_service.build_chunk_index_payload", return_value={"content": "x"}),
        patch("app.services.document_service._create_index_sync_job", return_value=(None, "success", None)),
        patch("app.services.document_service._read_ingest_chunk_revision", return_value=None),
        patch("app.services.document_service.create_parse_revision"),
    ):
        run_ingest_job(
            env["session"],
            env["current_user"],
            env["kb_row"],
            env["job_id"],
            source_bytes=env["source_bytes"],
        )

    found = False
    for stmt in env["captured_executes"]:
        if isinstance(stmt, sa.Insert):
            compiled = stmt.compile()
            meta = compiled.params.get("metadata")
            if isinstance(meta, dict) and "sourceModality" in meta:
                assert meta["sourceModality"] == "image"
                found = True
                break

    assert found, "Chunk metadata 中未找到 sourceModality='image'"


def test_run_ingest_job_image_chunk_metadata_source_file_name():
    """图片 Chunk metadata 应含 sourceFileName 为原始图片名。"""
    from unittest.mock import patch

    import sqlalchemy as sa

    from app.services.document_service import run_ingest_job

    env = _make_run_ingest_job_mocks()

    with (
        patch("app.services.document_service.parse_document", return_value=env["parsed_doc"]),
        patch("app.services.document_service.get_settings", return_value=env["mock_settings"]),
        patch("app.services.document_service.get_qa_run_providers", return_value=env["mock_provider_set"]),
        patch("app.services.document_service._update_ingest_progress"),
        patch("app.services.document_service.mark_graph_snapshots_stale"),
        patch("app.services.document_service._write_chunk_access_filters", return_value={}),
        patch("app.services.document_service.build_chunk_index_payload", return_value={"content": "x"}),
        patch("app.services.document_service._create_index_sync_job", return_value=(None, "success", None)),
        patch("app.services.document_service._read_ingest_chunk_revision", return_value=None),
        patch("app.services.document_service.create_parse_revision"),
    ):
        run_ingest_job(
            env["session"],
            env["current_user"],
            env["kb_row"],
            env["job_id"],
            source_bytes=env["source_bytes"],
        )

    found = False
    for stmt in env["captured_executes"]:
        if isinstance(stmt, sa.Insert):
            compiled = stmt.compile()
            meta = compiled.params.get("metadata")
            if isinstance(meta, dict) and "sourceFileName" in meta:
                assert meta["sourceFileName"] == "test.png"
                found = True
                break

    assert found, "Chunk metadata 中未找到 sourceFileName='test.png'"


def test_run_ingest_job_image_dense_payload_contains_content_and_filters():
    """图片 Chunk 的 Dense payload 应包含 chunk 文本和过滤字段。"""
    from unittest.mock import patch

    from app.services.document_service import run_ingest_job

    env = _make_run_ingest_job_mocks()

    captured_payloads = []

    def capture_payload(*args, **kwargs):
        captured_payloads.append({"args": args, "kwargs": kwargs})
        return {"content": "x"}

    with (
        patch("app.services.document_service.parse_document", return_value=env["parsed_doc"]),
        patch("app.services.document_service.get_settings", return_value=env["mock_settings"]),
        patch("app.services.document_service.get_qa_run_providers", return_value=env["mock_provider_set"]),
        patch("app.services.document_service._update_ingest_progress"),
        patch("app.services.document_service.mark_graph_snapshots_stale"),
        patch("app.services.document_service._write_chunk_access_filters", return_value={}),
        patch("app.services.document_service.build_chunk_index_payload", side_effect=capture_payload),
        patch("app.services.document_service._create_index_sync_job", return_value=(None, "success", None)),
        patch("app.services.document_service._read_ingest_chunk_revision", return_value=None),
        patch("app.services.document_service.create_parse_revision"),
    ):
        run_ingest_job(
            env["session"],
            env["current_user"],
            env["kb_row"],
            env["job_id"],
            source_bytes=env["source_bytes"],
        )

    assert len(captured_payloads) >= 1, "build_chunk_index_payload 未被调用"
    payload = captured_payloads[0]
    chunk_row = payload["args"][0]
    # Chunk content should be the image caption text
    assert chunk_row["content"] == "image caption text"
    # Dense payload should include document_status and version_status
    assert payload["kwargs"]["document_status"] == "active"
    assert payload["kwargs"]["version_status"] == "active"
    # access_filter should be passed (mocked as {})
    assert isinstance(payload["kwargs"]["access_filter"], dict)
    # embedding should be present
    assert len(payload["kwargs"]["embedding"]) == 1536


def test_run_ingest_job_image_chunk_no_visual_index():
    """图片 Chunk 入库不应创建 Visual Index，只用 milvus。"""
    from unittest.mock import patch

    from app.services.document_service import run_ingest_job

    env = _make_run_ingest_job_mocks()

    with (
        patch("app.services.document_service.parse_document", return_value=env["parsed_doc"]),
        patch("app.services.document_service.get_settings", return_value=env["mock_settings"]),
        patch("app.services.document_service.get_qa_run_providers", return_value=env["mock_provider_set"]),
        patch("app.services.document_service._update_ingest_progress"),
        patch("app.services.document_service.mark_graph_snapshots_stale"),
        patch("app.services.document_service._write_chunk_access_filters", return_value={}),
        patch("app.services.document_service.build_chunk_index_payload", return_value={"content": "x"}),
        patch("app.services.document_service._create_index_sync_job") as mock_sync,
        patch("app.services.document_service._read_ingest_chunk_revision", return_value=None),
        patch("app.services.document_service.create_parse_revision"),
    ):
        mock_sync.return_value = (None, "success", None)
        run_ingest_job(
            env["session"],
            env["current_user"],
            env["kb_row"],
            env["job_id"],
            source_bytes=env["source_bytes"],
        )

    # Verify only milvus sync was called (no visual index)
    called_targets = []
    for call in mock_sync.call_args_list:
        # _create_index_sync_job(session, kb_row, current_user, target_store, ...)
        # target_store is the 4th positional arg (index 3)
        if len(call.args) >= 4:
            called_targets.append(call.args[3])

    assert "milvus" in called_targets, "应调用 milvus 索引同步"
    assert "visual" not in called_targets, "不应创建 Visual Index"
    assert "vision" not in called_targets, "不应创建 Vision Index"
