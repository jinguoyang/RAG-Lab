"""B-321: Contextual Chunking 缓存测试。

验证上下文分块缓存的存取、失效和统计功能。
"""

import pytest

from app.services.contextual_chunking import (
    ContextualChunkingCache,
    ContextualMetadata,
    generate_contextual_metadata,
    generate_contextual_metadata_with_cache,
    get_contextual_cache,
    get_contextual_chunking_stats,
)
from app.services.multi_view_chunking import ChunkResult
from app.services.parsed_document_v2 import DocumentBlock, create_parsed_document_v2


class TestContextualChunkingCache:
    """上下文分块缓存测试。"""

    def test_cache_put_and_get(self):
        """应能存取缓存。"""
        cache = ContextualChunkingCache()
        metadata = ContextualMetadata(
            chunk_id="chunk_0",
            contextual_summary="Test summary",
            section_path=["Section 1"],
            document_brief="Test brief",
        )
        cache.put("doc_hash", "chunk_0", "rev_0", "v1", "local", metadata)
        result = cache.get("doc_hash", "chunk_0", "rev_0", "v1", "local")
        assert result is not None
        assert result.contextual_summary == "Test summary"

    def test_cache_miss(self):
        """缓存未命中应返回 None。"""
        cache = ContextualChunkingCache()
        result = cache.get("doc_hash", "chunk_0", "rev_0", "v1", "local")
        assert result is None

    def test_cache_invalidate_by_doc_hash(self):
        """应能按文档哈希失效缓存。"""
        cache = ContextualChunkingCache()
        metadata = ContextualMetadata(
            chunk_id="chunk_0",
            contextual_summary="Test",
            section_path=[],
            document_brief="Test",
        )
        cache.put("doc_hash_1", "chunk_0", "rev_0", "v1", "local", metadata)
        cache.put("doc_hash_2", "chunk_1", "rev_0", "v1", "local", metadata)

        removed = cache.invalidate_by_doc_hash("doc_hash_1")
        assert removed == 1
        assert cache.get("doc_hash_1", "chunk_0", "rev_0", "v1", "local") is None
        assert cache.get("doc_hash_2", "chunk_1", "rev_0", "v1", "local") is not None

    def test_cache_invalidate_by_chunk_revision(self):
        """应能按分块版本失效缓存。"""
        cache = ContextualChunkingCache()
        metadata = ContextualMetadata(
            chunk_id="chunk_0",
            contextual_summary="Test",
            section_path=[],
            document_brief="Test",
        )
        cache.put("doc_hash", "chunk_0", "rev_0", "v1", "local", metadata)
        cache.put("doc_hash", "chunk_1", "rev_1", "v1", "local", metadata)

        removed = cache.invalidate_by_chunk_revision("rev_0")
        assert removed == 1
        assert cache.get("doc_hash", "chunk_0", "rev_0", "v1", "local") is None
        assert cache.get("doc_hash", "chunk_1", "rev_1", "v1", "local") is not None

    def test_cache_clear(self):
        """应能清空缓存。"""
        cache = ContextualChunkingCache()
        metadata = ContextualMetadata(
            chunk_id="chunk_0",
            contextual_summary="Test",
            section_path=[],
            document_brief="Test",
        )
        cache.put("doc_hash", "chunk_0", "rev_0", "v1", "local", metadata)
        cache.clear()
        assert cache.size() == 0

    def test_cache_size(self):
        """应能获取缓存大小。"""
        cache = ContextualChunkingCache()
        assert cache.size() == 0
        metadata = ContextualMetadata(
            chunk_id="chunk_0",
            contextual_summary="Test",
            section_path=[],
            document_brief="Test",
        )
        cache.put("doc_hash", "chunk_0", "rev_0", "v1", "local", metadata)
        assert cache.size() == 1


class TestGenerateContextualMetadata:
    """上下文元数据生成测试。"""

    def _create_test_doc_and_chunks(self):
        """创建测试文档和分块。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="heading", text="Title", page_no=1),
            DocumentBlock(block_id="b1", block_type="paragraph", text="Content " * 50, page_no=1),
        ]
        doc = create_parsed_document_v2(
            source_file_name="test.txt",
            mime_type="text/plain",
            content="Title\n" + "Content " * 50,
            blocks=blocks,
        )
        chunks = [
            ChunkResult(
                chunk_id="chunk_0",
                content="Content " * 50,
                token_count=100,
                chunk_index=0,
                section="Title",
                page_no=1,
                source_block_ids=["b0", "b1"],
            ),
        ]
        return doc, chunks

    def test_generate_contextual_metadata(self):
        """应能生成上下文元数据。"""
        doc, chunks = self._create_test_doc_and_chunks()
        results = generate_contextual_metadata(doc, chunks, "rev_0")
        assert len(results) == 1
        assert results[0].chunk_id == "chunk_0"
        assert len(results[0].contextual_summary) > 0
        assert len(results[0].document_brief) > 0

    def test_generate_contextual_metadata_with_section(self):
        """应能提取章节路径。"""
        doc, chunks = self._create_test_doc_and_chunks()
        results = generate_contextual_metadata(doc, chunks, "rev_0")
        assert len(results[0].section_path) > 0
        assert "Title" in results[0].section_path

    def test_generate_contextual_metadata_with_generation_meta(self):
        """应包含生成元数据。"""
        doc, chunks = self._create_test_doc_and_chunks()
        results = generate_contextual_metadata(
            doc, chunks, "rev_0", prompt_version="v2", model_version="gpt-4"
        )
        meta = results[0].generation_meta
        assert meta["promptVersion"] == "v2"
        assert meta["modelVersion"] == "gpt-4"


class TestGenerateContextualMetadataWithCache:
    """带缓存的上下文元数据生成测试。"""

    def _create_test_doc_and_chunks(self):
        """创建测试文档和分块。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="paragraph", text="Content " * 50),
        ]
        doc = create_parsed_document_v2(
            source_file_name="test.txt",
            mime_type="text/plain",
            content="Content " * 50,
            blocks=blocks,
        )
        chunks = [
            ChunkResult(
                chunk_id="chunk_0",
                content="Content " * 50,
                token_count=100,
                chunk_index=0,
                source_block_ids=["b0"],
            ),
        ]
        return doc, chunks

    def test_generate_with_cache(self):
        """应能使用缓存。"""
        # 清空缓存
        get_contextual_cache().clear()

        doc, chunks = self._create_test_doc_and_chunks()
        results1 = generate_contextual_metadata_with_cache(doc, chunks, "rev_0")
        assert len(results1) == 1

        # 第二次应使用缓存
        results2 = generate_contextual_metadata_with_cache(doc, chunks, "rev_0")
        assert len(results2) == 1
        assert results1[0].contextual_summary == results2[0].contextual_summary

    def test_generate_force_regenerate(self):
        """应能强制重新生成。"""
        get_contextual_cache().clear()

        doc, chunks = self._create_test_doc_and_chunks()
        results1 = generate_contextual_metadata_with_cache(doc, chunks, "rev_0")
        results2 = generate_contextual_metadata_with_cache(
            doc, chunks, "rev_0", force_regenerate=True
        )
        assert len(results2) == 1


class TestGetContextualChunkingStats:
    """上下文分块统计测试。"""

    def test_get_stats(self):
        """应能获取统计信息。"""
        stats = get_contextual_chunking_stats()
        assert "cacheSize" in stats
        assert "promptVersions" in stats
        assert "supportedModels" in stats
