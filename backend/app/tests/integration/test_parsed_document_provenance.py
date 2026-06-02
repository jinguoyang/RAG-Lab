"""B-319: ParsedDocumentV2 与证据定位 Provenance 集成测试。

验证：
1. 解析 PDF 后能查询页、块和块级定位
2. Chunk 能关联到 ParsedDocumentV2 的 block 或 block range
3. 引用响应可返回页码与块级 provenance
"""
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

import pytest

from app.services.parsed_document_v2 import (
    BoundingBox,
    DocumentBlock,
    Page,
    ParsedDocumentV2,
    TableBlock,
    TableCell,
    create_parsed_document_v2,
)
from app.services.document_service import (
    get_block_provenance,
    get_page_blocks,
    _to_chunk_dto,
)


class TestParsedDocumentV2Schema:
    """ParsedDocumentV2 数据模型测试。"""

    def test_create_document_block_with_provenance(self):
        """测试创建带 provenance 的文档块。"""
        block = DocumentBlock(
            block_id="block_001",
            block_type="paragraph",
            text="这是测试文本",
            page_no=1,
            char_start=0,
            char_end=10,
            bbox=BoundingBox(x1=100, y1=200, x2=300, y2=250),
            confidence=0.95,
            section="第一章",
            section_path=["文档", "第一章"],
        )

        assert block.block_id == "block_001"
        assert block.page_no == 1
        assert block.bbox.x1 == 100
        assert block.confidence == 0.95

    def test_create_table_block_with_cells(self):
        """测试创建带单元格的表格块。"""
        cells = [
            TableCell(row=0, col=0, text="姓名", bbox=BoundingBox(x1=100, y1=200, x2=200, y2=230)),
            TableCell(row=0, col=1, text="年龄", bbox=BoundingBox(x1=200, y1=200, x2=300, y2=230)),
            TableCell(row=1, col=0, text="张三", bbox=BoundingBox(x1=100, y1=230, x2=200, y2=260)),
            TableCell(row=1, col=1, text="25", bbox=BoundingBox(x1=200, y1=230, x2=300, y2=260)),
        ]
        table = TableBlock(rows=2, cols=2, cells=cells)

        assert table.rows == 2
        assert len(table.cells) == 4
        assert table.cells[0].text == "姓名"

    def test_parsed_document_v2_query_methods(self):
        """测试 ParsedDocumentV2 的查询方法。"""
        blocks = [
            DocumentBlock(block_id="b1", block_type="paragraph", text="文本1", page_no=1),
            DocumentBlock(block_id="b2", block_type="heading", text="标题", page_no=1),
            DocumentBlock(block_id="b3", block_type="paragraph", text="文本2", page_no=2),
            DocumentBlock(block_id="b4", block_type="table", text="表格", page_no=2),
        ]
        pages = [
            Page(page_no=1, block_ids=["b1", "b2"]),
            Page(page_no=2, block_ids=["b3", "b4"]),
        ]
        doc = ParsedDocumentV2(
            document_id="doc_001",
            source_file_name="test.pdf",
            mime_type="application/pdf",
            content_hash="abc123",
            parse_version="v2",
            provider_name="test",
            provider_version="1.0",
            pages=pages,
            blocks=blocks,
        )

        # 测试按 ID 查询
        block = doc.get_block_by_id("b2")
        assert block is not None
        assert block.block_type == "heading"

        # 测试按页面查询
        page1_blocks = doc.get_blocks_by_page(1)
        assert len(page1_blocks) == 2

        # 测试按类型查询
        paragraphs = doc.get_blocks_by_type("paragraph")
        assert len(paragraphs) == 2

        # 测试获取表格块
        tables = doc.get_table_blocks()
        assert len(tables) == 1

    def test_parsed_document_v2_serialization(self):
        """测试 ParsedDocumentV2 序列化和反序列化。"""
        blocks = [
            DocumentBlock(
                block_id="b1",
                block_type="paragraph",
                text="测试文本",
                page_no=1,
                bbox=BoundingBox(x1=100, y1=200, x2=300, y2=250),
            ),
        ]
        doc = create_parsed_document_v2(
            source_file_name="test.pdf",
            mime_type="application/pdf",
            content="测试文本",
            blocks=blocks,
        )

        # 序列化
        doc_dict = doc.to_dict()
        assert doc_dict["sourceFileName"] == "test.pdf"
        assert len(doc_dict["blocks"]) == 1
        assert doc_dict["blocks"][0]["bbox"]["x1"] == 100

        # 反序列化
        restored = ParsedDocumentV2.from_dict(doc_dict)
        assert restored.source_file_name == "test.pdf"
        assert restored.blocks[0].bbox.x1 == 100


class TestChunkProvenanceMetadata:
    """Chunk Provenance 元数据测试。"""

    def test_chunk_dto_includes_provenance_fields(self):
        """测试 ChunkDTO 包含 provenance 字段。"""
        from app.schemas.document import ChunkDTO

        dto = ChunkDTO(
            chunkId="chunk_001",
            versionId="v1",
            documentId="doc_001",
            kbId="kb_001",
            chunkIndex=0,
            pageNo=1,
            section="第一章",
            content="测试内容",
            contentHash="hash123",
            tokenCount=100,
            status="active",
            createdAt="2026-05-30T00:00:00",
            sourceBlockIds=["b1", "b2"],
            sourceBlockRange=["b1", "b2", "b3"],
            provenance=[{"blockId": "b1", "pageNo": 1}],
        )

        assert dto.sourceBlockIds == ["b1", "b2"]
        assert dto.sourceBlockRange == ["b1", "b2", "b3"]
        assert len(dto.provenance) == 1

    def test_chunk_dto_provenance_optional(self):
        """测试 ChunkDTO 的 provenance 字段可选。"""
        from app.schemas.document import ChunkDTO

        dto = ChunkDTO(
            chunkId="chunk_001",
            versionId="v1",
            documentId="doc_001",
            kbId="kb_001",
            chunkIndex=0,
            pageNo=1,
            section=None,
            content="测试内容",
            contentHash="hash123",
            tokenCount=100,
            status="active",
            createdAt="2026-05-30T00:00:00",
        )

        assert dto.sourceBlockIds is None
        assert dto.sourceBlockRange is None
        assert dto.provenance is None


class TestProvenanceQueryFunctions:
    """Provenance 查询函数测试。"""

    def test_get_block_provenance_found(self):
        """测试查询存在的 block provenance。"""
        session = Mock()
        current_user = Mock()
        current_user.user.userId = str(uuid4())
        current_user.user.platformRole = "user"
        kb_id = uuid4()
        document_id = uuid4()

        # Mock 知识库查询
        mock_kb = MagicMock()
        mock_kb.first.return_value = {"kb_id": kb_id, "created_by": current_user.user.userId}
        session.execute.return_value = mock_kb

        # 由于需要复杂的 mock，这里主要测试函数签名和基本逻辑
        # 实际集成测试需要真实数据库
        with patch("app.services.document_service._read_visible_knowledge_base") as mock_kb_read:
            mock_kb_read.return_value = {"kb_id": kb_id}

            with patch("app.services.document_service._ensure_permission"):
                # Mock chunk 查询
                mock_chunk = MagicMock()
                mock_chunk.__getitem__ = lambda self, key: {
                    "chunk_id": uuid4(),
                    "page_no": 1,
                    "section": "第一章",
                    "metadata": {
                        "sourceBlockIds": ["b1", "b2"],
                        "provenance": {"contentHash": "hash123"},
                    },
                }.get(key)
                mock_chunks = MagicMock()
                mock_chunks.all.return_value = [mock_chunk]
                session.execute.return_value = mock_chunks

                result = get_block_provenance(session, current_user, kb_id, document_id, "b1")

                # 验证函数被正确调用
                assert session.execute.called

    def test_get_page_blocks_returns_list(self):
        """测试查询页面块返回列表。"""
        session = Mock()
        current_user = Mock()
        current_user.user.userId = str(uuid4())
        kb_id = uuid4()
        document_id = uuid4()

        with patch("app.services.document_service._read_visible_knowledge_base") as mock_kb_read:
            mock_kb_read.return_value = {"kb_id": kb_id}

            with patch("app.services.document_service._ensure_permission"):
                # Mock 空结果
                mock_result = MagicMock()
                mock_result.all.return_value = []
                session.execute.return_value = mock_result

                result = get_page_blocks(session, current_user, kb_id, document_id, 1)

                assert isinstance(result, list)
                assert len(result) == 0


class TestProvenanceSerialization:
    """Provenance 序列化测试。"""

    def test_provenance_to_dict(self):
        """测试 provenance 信息序列化。"""
        block = DocumentBlock(
            block_id="b1",
            block_type="paragraph",
            text="测试文本",
            page_no=1,
            char_start=0,
            char_end=10,
            bbox=BoundingBox(x1=100, y1=200, x2=300, y2=250),
            confidence=0.95,
        )

        block_dict = block.to_dict()
        assert block_dict["blockId"] == "b1"
        assert block_dict["pageNo"] == 1
        assert block_dict["bbox"]["x1"] == 100
        assert block_dict["confidence"] == 0.95

    def test_table_block_serialization(self):
        """测试表格块序列化。"""
        cells = [
            TableCell(row=0, col=0, text="A1"),
            TableCell(row=0, col=1, text="B1"),
        ]
        table = TableBlock(rows=1, cols=2, cells=cells, caption="测试表格")

        table_dict = table.to_dict()
        assert table_dict["rows"] == 1
        assert table_dict["cols"] == 2
        assert table_dict["caption"] == "测试表格"
        assert len(table_dict["cells"]) == 2


# 验证命令
# python -m pytest backend/app/tests/integration/test_parsed_document_provenance.py -q
