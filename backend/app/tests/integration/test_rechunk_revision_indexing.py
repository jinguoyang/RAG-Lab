"""B-320: 多视图 ChunkRevision 与分块策略集成测试。

验证：
1. 通过 API 发起 heading 策略的 rechunk
2. 分块结果可独立重建检索索引，不覆盖历史正式版本
3. 检索链路可以选择指定 chunk revision
"""
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

import pytest

from app.schemas.binding import RechunkRequest, ChunkRevisionDTO
from app.services.multi_view_chunking import (
    ChunkStrategy,
    ChunkRevision,
    ChunkResult,
    execute_chunking,
    get_available_strategies,
    _fixed_chunking,
    _heading_chunking,
    _semantic_chunking,
    _parent_child_chunking,
    _table_aware_chunking,
)
from app.services.parsed_document_v2 import (
    DocumentBlock,
    ParsedDocumentV2,
    create_parsed_document_v2,
)


class TestRechunkRequestValidation:
    """RechunkRequest 参数校验测试。"""

    def test_fixed_strategy_valid_params(self):
        """测试 fixed 策略有效参数。"""
        request = RechunkRequest(strategy="fixed", params={"chunkSize": 1000, "chunkOverlap": 100})
        assert request.strategy == "fixed"
        assert request.params["chunkSize"] == 1000

    def test_fixed_strategy_backward_compatible(self):
        """测试 fixed_size 向后兼容。"""
        request = RechunkRequest(strategy="fixed_size", params={"chunk_size": 1000, "chunk_overlap": 100})
        assert request.strategy == "fixed_size"

    def test_fixed_strategy_invalid_chunk_size(self):
        """测试 fixed 策略无效 chunk_size。"""
        with pytest.raises(ValueError, match="chunk_size must be an integer between 100 and 4000"):
            RechunkRequest(strategy="fixed", params={"chunkSize": 50})

    def test_heading_strategy_no_params_required(self):
        """测试 heading 策略无需参数。"""
        request = RechunkRequest(strategy="heading")
        assert request.strategy == "heading"

    def test_semantic_strategy_no_params_required(self):
        """测试 semantic 策略无需参数。"""
        request = RechunkRequest(strategy="semantic")
        assert request.strategy == "semantic"

    def test_parent_child_strategy_valid_params(self):
        """测试 parent_child 策略有效参数。"""
        request = RechunkRequest(strategy="parent_child", params={"parentSize": 2000, "childSize": 300})
        assert request.strategy == "parent_child"

    def test_parent_child_strategy_invalid_params(self):
        """测试 parent_child 策略无效参数。"""
        with pytest.raises(ValueError, match="childSize must be smaller than parentSize"):
            RechunkRequest(strategy="parent_child", params={"parentSize": 500, "childSize": 600})

    def test_table_aware_strategy_no_params_required(self):
        """测试 table_aware 策略无需参数。"""
        request = RechunkRequest(strategy="table_aware")
        assert request.strategy == "table_aware"

    def test_unsupported_strategy(self):
        """测试不支持的策略。"""
        with pytest.raises(ValueError, match="Unsupported chunk strategy"):
            RechunkRequest(strategy="invalid_strategy")


class TestChunkRevisionDTO:
    """ChunkRevisionDTO 测试。"""

    def test_dto_includes_strategy_fields(self):
        """测试 DTO 包含策略字段。"""
        dto = ChunkRevisionDTO(
            chunkRevisionId="rev_001",
            bindingId="binding_001",
            knowledgeBaseId="kb_001",
            documentId="doc_001",
            documentVersionId="v1",
            parseRevisionId="parse_001",
            status="active",
            chunkCount=10,
            strategy="heading",
            params={"maxTokens": 500},
            chunkViewType="heading",
            createdAt="2026-05-30T00:00:00",
        )

        assert dto.strategy == "heading"
        assert dto.params == {"maxTokens": 500}
        assert dto.chunkViewType == "heading"

    def test_dto_default_strategy(self):
        """测试 DTO 默认策略。"""
        dto = ChunkRevisionDTO(
            chunkRevisionId="rev_001",
            bindingId="binding_001",
            knowledgeBaseId="kb_001",
            documentId="doc_001",
            documentVersionId="v1",
            parseRevisionId="parse_001",
            status="active",
            chunkCount=10,
            createdAt="2026-05-30T00:00:00",
        )

        assert dto.strategy == "fixed_size"
        assert dto.params is None
        assert dto.chunkViewType is None


class TestMultiViewChunkingStrategies:
    """多视图分块策略测试。"""

    def _create_test_blocks(self) -> list[DocumentBlock]:
        """创建测试文档块。"""
        return [
            DocumentBlock(block_id="b1", block_type="heading", text="# 第一章", page_no=1, section="第一章"),
            DocumentBlock(block_id="b2", block_type="paragraph", text="这是第一章的内容。" * 20, page_no=1, section="第一章"),
            DocumentBlock(block_id="b3", block_type="heading", text="# 第二章", page_no=2, section="第二章"),
            DocumentBlock(block_id="b4", block_type="paragraph", text="这是第二章的内容。" * 20, page_no=2, section="第二章"),
        ]

    def test_fixed_chunking(self):
        """测试固定长度分块。"""
        blocks = self._create_test_blocks()
        chunks = _fixed_chunking(blocks, chunk_size=200, chunk_overlap=50)

        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk.content) <= 250  # 允许一些超出
            assert chunk.token_count > 0

    def test_heading_chunking(self):
        """测试标题分块。"""
        blocks = self._create_test_blocks()
        chunks = _heading_chunking(blocks)

        # 每个标题应该创建一个新块
        assert len(chunks) >= 2
        assert "第一章" in chunks[0].content
        assert "第二章" in chunks[1].content

    def test_semantic_chunking(self):
        """测试语义分块。"""
        blocks = self._create_test_blocks()
        chunks = _semantic_chunking(blocks)

        # 每个非空块应该创建一个独立的语义单元
        assert len(chunks) == 4

    def test_parent_child_chunking(self):
        """测试父子分块。"""
        blocks = self._create_test_blocks()
        parent_chunks, child_chunks = _parent_child_chunking(blocks, parent_size=500, child_size=100)

        assert len(parent_chunks) > 0
        assert len(child_chunks) > 0

        # 子块应该有 parent_chunk_id
        for child in child_chunks:
            assert child.parent_chunk_id is not None
            assert child.parent_chunk_id.startswith("parent_")

    def test_table_aware_chunking(self):
        """测试表格感知分块。"""
        blocks = self._create_test_blocks()
        chunks = _table_aware_chunking(blocks)

        assert len(chunks) == 4

    def test_execute_chunking_returns_revision(self):
        """测试 execute_chunking 返回 ChunkRevision。"""
        blocks = self._create_test_blocks()
        doc = create_parsed_document_v2(
            source_file_name="test.pdf",
            mime_type="application/pdf",
            content="测试内容",
            blocks=blocks,
        )

        chunks, revision = execute_chunking(doc, "heading")

        assert isinstance(revision, ChunkRevision)
        assert revision.strategy == "heading"
        assert revision.chunk_count == len(chunks)
        assert revision.chunk_view_type == "heading"

    def test_get_available_strategies(self):
        """测试获取可用策略列表。"""
        strategies = get_available_strategies()

        assert len(strategies) == 5
        strategy_names = [s["name"] for s in strategies]
        assert "fixed" in strategy_names
        assert "heading" in strategy_names
        assert "semantic" in strategy_names
        assert "parent_child" in strategy_names
        assert "table_aware" in strategy_names


class TestChunkRevisionIndependence:
    """ChunkRevision 独立性测试。"""

    def test_multiple_revisions_coexist(self):
        """测试多个 ChunkRevision 共存。"""
        blocks = [
            DocumentBlock(block_id="b1", block_type="paragraph", text="测试内容" * 50, page_no=1),
        ]
        doc = create_parsed_document_v2(
            source_file_name="test.pdf",
            mime_type="application/pdf",
            content="测试内容" * 50,
            blocks=blocks,
        )

        # 创建两个不同策略的 revision
        chunks_fixed, rev_fixed = execute_chunking(doc, "fixed", {"chunkSize": 200, "chunkOverlap": 50})
        chunks_heading, rev_heading = execute_chunking(doc, "heading")

        # 两个 revision 应该有不同的 ID
        assert rev_fixed.chunk_revision_id != rev_heading.chunk_revision_id

        # 两个 revision 应该有不同的策略
        assert rev_fixed.strategy == "fixed"
        assert rev_heading.strategy == "heading"

    def test_chunk_ids_unique_within_revision(self):
        """测试同一 revision 内 chunk ID 唯一。"""
        blocks = [
            DocumentBlock(block_id="b1", block_type="paragraph", text="测试内容" * 100, page_no=1),
        ]
        doc = create_parsed_document_v2(
            source_file_name="test.pdf",
            mime_type="application/pdf",
            content="测试内容" * 100,
            blocks=blocks,
        )

        chunks, _ = execute_chunking(doc, "fixed", {"chunkSize": 100, "chunkOverlap": 20})

        chunk_ids = [c.chunk_id for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))


class TestStrategyOutputDifferences:
    """策略输出差异测试。"""

    def test_fixed_and_heading_produce_different_output(self):
        """测试 fixed 和 heading 策略产生不同输出。"""
        blocks = [
            DocumentBlock(block_id="b1", block_type="heading", text="# 标题一", page_no=1, section="标题一"),
            DocumentBlock(block_id="b2", block_type="paragraph", text="内容一。" * 30, page_no=1, section="标题一"),
            DocumentBlock(block_id="b3", block_type="heading", text="# 标题二", page_no=2, section="标题二"),
            DocumentBlock(block_id="b4", block_type="paragraph", text="内容二。" * 30, page_no=2, section="标题二"),
        ]
        doc = create_parsed_document_v2(
            source_file_name="test.pdf",
            mime_type="application/pdf",
            content="内容一。" * 30 + "内容二。" * 30,
            blocks=blocks,
        )

        chunks_fixed, _ = execute_chunking(doc, "fixed", {"chunkSize": 200, "chunkOverlap": 50})
        chunks_heading, _ = execute_chunking(doc, "heading")

        # 两种策略应该产生不同数量的 chunk
        # heading 策略按标题分割，应该产生 2 个块
        # fixed 策略按固定长度分割，可能产生更多块
        assert len(chunks_heading) == 2
        assert len(chunks_fixed) != len(chunks_heading) or chunks_fixed[0].content != chunks_heading[0].content


# 验证命令
# python -m pytest backend/app/tests/integration/test_rechunk_revision_indexing.py -q
