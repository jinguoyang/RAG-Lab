"""B-323: 父子检索与上下文打包测试。

验证父子检索、相邻块扩展和上下文打包功能。
"""

import pytest

from app.services.parent_child_retrieval import (
    PackedContext,
    PackingStrategy,
    expand_adjacent_chunks,
    find_parent_chunk,
    get_packing_strategies,
    pack_context_document_order,
    pack_context_relevance_first,
    pack_context_section_grouped,
    pack_context_with_parent_child,
)
from app.services.multi_view_chunking import ChunkResult


def _make_chunk(chunk_id: str, content: str, chunk_index: int, section: str = None, parent_chunk_id: str = None):
    """创建测试块。"""
    return ChunkResult(
        chunk_id=chunk_id,
        content=content,
        token_count=len(content) // 4,
        chunk_index=chunk_index,
        section=section,
        parent_chunk_id=parent_chunk_id,
    )


class TestFindParentChunk:
    """父块查找测试。"""

    def test_find_parent_by_parent_chunk_id(self):
        """应能通过 parent_chunk_id 查找父块。"""
        parent = _make_chunk("parent_0", "Parent content", 0)
        child = _make_chunk("child_0", "Child content", 1, parent_chunk_id="parent_0")
        all_chunks = [parent, child]

        result = find_parent_chunk(child, all_chunks)
        assert result is not None
        assert result.chunk_id == "parent_0"

    def test_find_parent_by_section(self):
        """应能通过 section 查找父块。"""
        parent = _make_chunk("parent_0", "Parent content", 0, section="Section 1")
        child = _make_chunk("child_0", "Child content", 1, section="Section 1")
        all_chunks = [parent, child]

        result = find_parent_chunk(child, all_chunks)
        assert result is not None
        assert result.chunk_id == "parent_0"

    def test_find_parent_not_found(self):
        """未找到父块时应返回 None。"""
        child = _make_chunk("child_0", "Child content", 0)
        result = find_parent_chunk(child, [])
        assert result is None


class TestExpandAdjacentChunks:
    """相邻块扩展测试。"""

    def test_expand_adjacent_chunks(self):
        """应能扩展相邻块。"""
        chunks = [
            _make_chunk("chunk_0", "Content 0", 0),
            _make_chunk("chunk_1", "Content 1", 1),
            _make_chunk("chunk_2", "Content 2", 2),
            _make_chunk("chunk_3", "Content 3", 3),
        ]
        target = chunks[1]
        result = expand_adjacent_chunks(target, chunks, window=1)
        assert len(result) == 3  # chunk_0, chunk_1, chunk_2
        assert result[0].chunk_id == "chunk_0"
        assert result[1].chunk_id == "chunk_1"
        assert result[2].chunk_id == "chunk_2"

    def test_expand_adjacent_chunks_at_boundary(self):
        """边界情况应正确处理。"""
        chunks = [
            _make_chunk("chunk_0", "Content 0", 0),
            _make_chunk("chunk_1", "Content 1", 1),
        ]
        target = chunks[0]
        result = expand_adjacent_chunks(target, chunks, window=1)
        assert len(result) == 2

    def test_expand_adjacent_chunks_window_zero(self):
        """window=0 时应只返回目标块。"""
        chunks = [
            _make_chunk("chunk_0", "Content 0", 0),
            _make_chunk("chunk_1", "Content 1", 1),
        ]
        result = expand_adjacent_chunks(chunks[0], chunks, window=0)
        assert len(result) == 1


class TestPackContextRelevanceFirst:
    """相关性优先打包测试。"""

    def test_pack_context_relevance_first(self):
        """应按相关性打包。"""
        chunks = [
            _make_chunk("chunk_0", "High relevance", 0),
            _make_chunk("chunk_1", "Medium relevance", 1),
            _make_chunk("chunk_2", "Low relevance", 2),
        ]
        result = pack_context_relevance_first(chunks, max_tokens=1000)
        assert len(result.chunks) == 3
        assert result.packing_strategy == "relevance_first"

    def test_pack_context_relevance_first_truncates(self):
        """超过 token 预算时应截断。"""
        chunks = [
            _make_chunk("chunk_0", "A" * 500, 0),
            _make_chunk("chunk_1", "B" * 500, 1),
        ]
        result = pack_context_relevance_first(chunks, max_tokens=200)
        assert len(result.chunks) < 2
        assert len(result.truncation_log) > 0


class TestPackContextDocumentOrder:
    """文档顺序打包测试。"""

    def test_pack_context_document_order(self):
        """应按文档顺序打包。"""
        chunks = [
            _make_chunk("chunk_2", "Content 2", 2),
            _make_chunk("chunk_0", "Content 0", 0),
            _make_chunk("chunk_1", "Content 1", 1),
        ]
        result = pack_context_document_order(chunks, max_tokens=1000)
        assert result.chunks[0].chunk_id == "chunk_0"
        assert result.chunks[1].chunk_id == "chunk_1"
        assert result.chunks[2].chunk_id == "chunk_2"


class TestPackContextSectionGrouped:
    """章节分组打包测试。"""

    def test_pack_context_section_grouped(self):
        """应按章节分组打包。"""
        chunks = [
            _make_chunk("chunk_0", "Content 0", 0, section="Section A"),
            _make_chunk("chunk_1", "Content 1", 1, section="Section B"),
            _make_chunk("chunk_2", "Content 2", 2, section="Section A"),
        ]
        result = pack_context_section_grouped(chunks, max_tokens=1000)
        assert result.packing_strategy == "section_grouped"


class TestPackContextWithParentChild:
    """父子检索打包测试。"""

    def test_pack_context_with_parent_child(self):
        """父子检索应包含父块。"""
        parent = _make_chunk("parent_0", "Parent content " * 10, 0)
        child = _make_chunk("child_0", "Child content", 1, parent_chunk_id="parent_0")
        all_chunks = [parent, child]

        result = pack_context_with_parent_child(
            child_chunks=[child],
            all_chunks=all_chunks,
            max_tokens=1000,
        )
        assert len(result.chunks) >= 2  # 子块 + 父块
        chunk_ids = {c.chunk_id for c in result.chunks}
        assert "child_0" in chunk_ids
        assert "parent_0" in chunk_ids

    def test_pack_context_with_chunk_window(self):
        """chunkWindow 应扩展相邻块。"""
        chunks = [
            _make_chunk("chunk_0", "Content 0", 0),
            _make_chunk("chunk_1", "Content 1", 1),
            _make_chunk("chunk_2", "Content 2", 2),
        ]
        result = pack_context_with_parent_child(
            child_chunks=[chunks[1]],
            all_chunks=chunks,
            max_tokens=1000,
            chunk_window=1,
        )
        assert len(result.chunks) == 3

    def test_pack_context_with_different_strategies(self):
        """不同策略应产生不同结果。"""
        chunks = [
            _make_chunk("chunk_0", "Content 0", 0, section="A"),
            _make_chunk("chunk_1", "Content 1", 1, section="B"),
        ]
        result1 = pack_context_with_parent_child(
            child_chunks=chunks,
            all_chunks=chunks,
            max_tokens=1000,
            packing_strategy="relevance_first",
        )
        result2 = pack_context_with_parent_child(
            child_chunks=chunks,
            all_chunks=chunks,
            max_tokens=1000,
            packing_strategy="document_order",
        )
        assert result1.packing_strategy != result2.packing_strategy


class TestGetPackingStrategies:
    """获取打包策略测试。"""

    def test_get_packing_strategies(self):
        """应返回所有可用策略。"""
        strategies = get_packing_strategies()
        assert len(strategies) == 3
        names = {s["name"] for s in strategies}
        assert "relevance_first" in names
        assert "document_order" in names
        assert "section_grouped" in names
