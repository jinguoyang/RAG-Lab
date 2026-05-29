"""B-320: 多视图 ChunkRevision 分块策略测试。

验证不同分块策略能正确分块，并生成可追溯的 ChunkRevision。
"""

import pytest

from app.services.multi_view_chunking import (
    ChunkStrategy,
    execute_chunking,
    get_available_strategies,
    _fixed_chunking,
    _heading_chunking,
    _semantic_chunking,
    _table_aware_chunking,
)
from app.services.parsed_document_v2 import (
    DocumentBlock,
    Page,
    TableBlock,
    TableCell,
    create_parsed_document_v2,
)


class TestFixedChunking:
    """固定长度分块测试。"""

    def test_fixed_chunking_basic(self):
        """固定分块应按大小分割。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="paragraph", text="A" * 500),
            DocumentBlock(block_id="b1", block_type="paragraph", text="B" * 500),
        ]
        chunks = _fixed_chunking(blocks, chunk_size=300, chunk_overlap=50)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) <= 350  # chunk_size + some tolerance

    def test_fixed_chunking_preserves_sections(self):
        """固定分块应保留章节信息。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="paragraph", text="Content", section="Section 1"),
        ]
        chunks = _fixed_chunking(blocks, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].section == "Section 1"

    def test_fixed_chunking_empty_blocks(self):
        """空块应被跳过。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="paragraph", text=""),
            DocumentBlock(block_id="b1", block_type="paragraph", text="Content"),
        ]
        chunks = _fixed_chunking(blocks, chunk_size=1000)
        assert len(chunks) == 1


class TestHeadingChunking:
    """标题分块测试。"""

    def test_heading_chunking_splits_at_headings(self):
        """标题分块应在标题处分割。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="heading", text="Chapter 1"),
            DocumentBlock(block_id="b1", block_type="paragraph", text="Content 1"),
            DocumentBlock(block_id="b2", block_type="heading", text="Chapter 2"),
            DocumentBlock(block_id="b3", block_type="paragraph", text="Content 2"),
        ]
        chunks = _heading_chunking(blocks)
        assert len(chunks) == 2
        assert "Chapter 1" in chunks[0].content
        assert "Chapter 2" in chunks[1].content

    def test_heading_chunking_no_headings(self):
        """无标题时应作为一个块。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="paragraph", text="Content 1"),
            DocumentBlock(block_id="b1", block_type="paragraph", text="Content 2"),
        ]
        chunks = _heading_chunking(blocks)
        assert len(chunks) == 1


class TestSemanticChunking:
    """语义分块测试。"""

    def test_semantic_chunking_per_paragraph(self):
        """语义分块应按段落分割。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="paragraph", text="Paragraph 1"),
            DocumentBlock(block_id="b1", block_type="paragraph", text="Paragraph 2"),
            DocumentBlock(block_id="b2", block_type="paragraph", text="Paragraph 3"),
        ]
        chunks = _semantic_chunking(blocks)
        assert len(chunks) == 3

    def test_semantic_chunking_skips_empty(self):
        """语义分块应跳过空段落。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="paragraph", text="Content"),
            DocumentBlock(block_id="b1", block_type="paragraph", text=""),
        ]
        chunks = _semantic_chunking(blocks)
        assert len(chunks) == 1


class TestTableAwareChunking:
    """表格感知分块测试。"""

    def test_table_aware_chunking_preserves_tables(self):
        """表格感知分块应保留表格结构。"""
        table = TableBlock(
            rows=2,
            cols=2,
            cells=[
                TableCell(row=0, col=0, text="H1"),
                TableCell(row=0, col=1, text="H2"),
                TableCell(row=1, col=0, text="D1"),
                TableCell(row=1, col=1, text="D2"),
            ],
        )
        blocks = [
            DocumentBlock(block_id="b0", block_type="table", text="Table", table=table),
            DocumentBlock(block_id="b1", block_type="paragraph", text="Text content"),
        ]
        chunks = _table_aware_chunking(blocks)
        assert len(chunks) == 2
        assert chunks[0].metadata.get("isTable") is True
        assert chunks[1].metadata.get("isTable") is None


class TestExecuteChunking:
    """执行分块测试。"""

    def _create_test_doc(self):
        """创建测试文档。"""
        blocks = [
            DocumentBlock(block_id="b0", block_type="heading", text="Title", page_no=1),
            DocumentBlock(block_id="b1", block_type="paragraph", text="Content " * 100, page_no=1),
        ]
        return create_parsed_document_v2(
            source_file_name="test.txt",
            mime_type="text/plain",
            content="Title\n" + "Content " * 100,
            blocks=blocks,
        )

    def test_execute_chunking_fixed(self):
        """应能执行固定分块策略。"""
        doc = self._create_test_doc()
        chunks, revision = execute_chunking(doc, ChunkStrategy.FIXED)
        assert len(chunks) > 0
        assert revision.strategy == "fixed"
        assert revision.chunk_count == len(chunks)

    def test_execute_chunking_heading(self):
        """应能执行标题分块策略。"""
        doc = self._create_test_doc()
        chunks, revision = execute_chunking(doc, ChunkStrategy.HEADING)
        assert len(chunks) > 0
        assert revision.strategy == "heading"

    def test_execute_chunking_semantic(self):
        """应能执行语义分块策略。"""
        doc = self._create_test_doc()
        chunks, revision = execute_chunking(doc, ChunkStrategy.SEMANTIC)
        assert len(chunks) > 0
        assert revision.strategy == "semantic"

    def test_execute_chunking_table_aware(self):
        """应能执行表格感知分块策略。"""
        doc = self._create_test_doc()
        chunks, revision = execute_chunking(doc, ChunkStrategy.TABLE_AWARE)
        assert len(chunks) > 0
        assert revision.strategy == "table_aware"

    def test_execute_chunking_with_params(self):
        """应支持自定义参数。"""
        doc = self._create_test_doc()
        chunks, revision = execute_chunking(
            doc,
            ChunkStrategy.FIXED,
            params={"chunkSize": 500, "chunkOverlap": 50},
        )
        assert len(chunks) > 0
        assert revision.params.get("chunkSize") == 500

    def test_execute_chunking_string_strategy(self):
        """应支持字符串格式的策略。"""
        doc = self._create_test_doc()
        chunks, revision = execute_chunking(doc, "fixed")
        assert len(chunks) > 0

    def test_execute_chunking_invalid_strategy_falls_back(self):
        """无效策略应回退到固定分块。"""
        doc = self._create_test_doc()
        chunks, revision = execute_chunking(doc, "invalid")
        assert len(chunks) > 0
        assert revision.strategy == "fixed"

    def test_chunk_revision_has_document_id(self):
        """ChunkRevision 应包含 document_id。"""
        doc = self._create_test_doc()
        _, revision = execute_chunking(doc, ChunkStrategy.FIXED)
        assert revision.document_id == doc.document_id

    def test_chunk_revision_has_source_block_range(self):
        """ChunkRevision 应包含源 block_id 列表。"""
        doc = self._create_test_doc()
        _, revision = execute_chunking(doc, ChunkStrategy.FIXED)
        assert len(revision.source_block_range) == 2


class TestGetAvailableStrategies:
    """获取可用策略测试。"""

    def test_get_available_strategies(self):
        """应返回所有可用策略。"""
        strategies = get_available_strategies()
        assert len(strategies) == 5
        names = {s["name"] for s in strategies}
        assert "fixed" in names
        assert "heading" in names
        assert "semantic" in names
        assert "parent_child" in names
        assert "table_aware" in names

    def test_strategy_has_required_fields(self):
        """每个策略应包含必要字段。"""
        strategies = get_available_strategies()
        for strategy in strategies:
            assert "name" in strategy
            assert "label" in strategy
            assert "description" in strategy
            assert "params" in strategy
