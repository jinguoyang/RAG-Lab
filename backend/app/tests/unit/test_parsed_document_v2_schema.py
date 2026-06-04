"""B-319: ParsedDocumentV2 数据契约测试。

验证 ParsedDocumentV2 的数据结构、序列化和查询功能。
"""

import pytest

from app.services.parsed_document_v2 import (
    BoundingBox,
    DocumentBlock,
    ImageBlock,
    Page,
    ParsedDocumentV2,
    TableBlock,
    TableCell,
    compute_content_hash,
    create_parsed_document_v2,
    convert_parsed_document_to_v2,
)


class TestBoundingBox:
    """边界框测试。"""

    def test_bounding_box_creation(self):
        """应能创建边界框。"""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        assert bbox.x1 == 10
        assert bbox.y1 == 20
        assert bbox.x2 == 100
        assert bbox.y2 == 200

    def test_bounding_box_to_dict(self):
        """应能序列化为字典。"""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        d = bbox.to_dict()
        assert d == {"x1": 10, "y1": 20, "x2": 100, "y2": 200}

    def test_bounding_box_from_dict(self):
        """应能从字典反序列化。"""
        d = {"x1": 10, "y1": 20, "x2": 100, "y2": 200}
        bbox = BoundingBox.from_dict(d)
        assert bbox.x1 == 10
        assert bbox.y1 == 20


class TestTableCell:
    """表格单元格测试。"""

    def test_table_cell_creation(self):
        """应能创建表格单元格。"""
        cell = TableCell(row=0, col=0, text="Header")
        assert cell.row == 0
        assert cell.col == 0
        assert cell.text == "Header"
        assert cell.row_span == 1
        assert cell.col_span == 1

    def test_table_cell_with_span(self):
        """应支持合并单元格。"""
        cell = TableCell(row=0, col=0, text="Merged", row_span=2, col_span=3)
        assert cell.row_span == 2
        assert cell.col_span == 3

    def test_table_cell_to_dict(self):
        """应能序列化为字典。"""
        cell = TableCell(row=0, col=0, text="Header")
        d = cell.to_dict()
        assert d["row"] == 0
        assert d["col"] == 0
        assert d["text"] == "Header"
        assert d["rowSpan"] == 1
        assert d["colSpan"] == 1


class TestTableBlock:
    """表格块测试。"""

    def test_table_block_creation(self):
        """应能创建表格块。"""
        cells = [
            TableCell(row=0, col=0, text="Header 1"),
            TableCell(row=0, col=1, text="Header 2"),
            TableCell(row=1, col=0, text="Data 1"),
            TableCell(row=1, col=1, text="Data 2"),
        ]
        table = TableBlock(rows=2, cols=2, cells=cells)
        assert table.rows == 2
        assert table.cols == 2
        assert len(table.cells) == 4

    def test_table_block_to_dict(self):
        """应能序列化为字典。"""
        table = TableBlock(rows=1, cols=1, cells=[TableCell(row=0, col=0, text="Test")])
        d = table.to_dict()
        assert d["rows"] == 1
        assert d["cols"] == 1
        assert len(d["cells"]) == 1


class TestImageBlock:
    """图片块测试。"""

    def test_image_block_creation(self):
        """应能创建图片块。"""
        image = ImageBlock(caption="Test image", ocr_text="OCR text")
        assert image.caption == "Test image"
        assert image.ocr_text == "OCR text"

    def test_image_block_to_dict(self):
        """应能序列化为字典。"""
        image = ImageBlock(caption="Test")
        d = image.to_dict()
        assert d["caption"] == "Test"


class TestDocumentBlock:
    """文档块测试。"""

    def test_document_block_creation(self):
        """应能创建文档块。"""
        block = DocumentBlock(
            block_id="block_0",
            block_type="paragraph",
            text="Test content",
            page_no=1,
        )
        assert block.block_id == "block_0"
        assert block.block_type == "paragraph"
        assert block.text == "Test content"
        assert block.page_no == 1

    def test_document_block_with_provenance(self):
        """应支持位置溯源信息。"""
        bbox = BoundingBox(x1=10, y1=20, x2=100, y2=200)
        block = DocumentBlock(
            block_id="block_0",
            block_type="paragraph",
            text="Test",
            page_no=1,
            char_start=0,
            char_end=10,
            bbox=bbox,
            confidence=0.95,
        )
        assert block.char_start == 0
        assert block.char_end == 10
        assert block.bbox is not None
        assert block.confidence == 0.95

    def test_document_block_with_section_path(self):
        """应支持章节路径。"""
        block = DocumentBlock(
            block_id="block_0",
            block_type="paragraph",
            text="Test",
            section="Chapter 1",
            section_path=["Chapter 1", "Section 1.1"],
        )
        assert block.section == "Chapter 1"
        assert len(block.section_path) == 2

    def test_document_block_with_table(self):
        """应支持嵌入表格。"""
        table = TableBlock(rows=1, cols=1, cells=[TableCell(row=0, col=0, text="Test")])
        block = DocumentBlock(
            block_id="block_0",
            block_type="table",
            text="Table content",
            table=table,
        )
        assert block.table is not None
        assert block.table.rows == 1

    def test_document_block_with_image(self):
        """应支持嵌入图片。"""
        image = ImageBlock(caption="Test image")
        block = DocumentBlock(
            block_id="block_0",
            block_type="image",
            text="Image description",
            image=image,
        )
        assert block.image is not None
        assert block.image.caption == "Test image"

    def test_document_block_to_dict(self):
        """应能序列化为字典。"""
        block = DocumentBlock(
            block_id="block_0",
            block_type="paragraph",
            text="Test",
            page_no=1,
        )
        d = block.to_dict()
        assert d["blockId"] == "block_0"
        assert d["blockType"] == "paragraph"
        assert d["text"] == "Test"
        assert d["pageNo"] == 1


class TestPage:
    """页面测试。"""

    def test_page_creation(self):
        """应能创建页面。"""
        page = Page(page_no=1, width=612, height=792, unit="point")
        assert page.page_no == 1
        assert page.width == 612
        assert page.height == 792
        assert page.unit == "point"

    def test_page_with_block_ids(self):
        """应支持块 ID 列表。"""
        page = Page(page_no=1, block_ids=["block_0", "block_1"])
        assert len(page.block_ids) == 2

    def test_page_to_dict(self):
        """应能序列化为字典。"""
        page = Page(page_no=1)
        d = page.to_dict()
        assert d["pageNo"] == 1
        assert d["unit"] == "point"


class TestParsedDocumentV2:
    """ParsedDocumentV2 测试。"""

    def _create_test_document(self) -> ParsedDocumentV2:
        """创建测试文档。"""
        blocks = [
            DocumentBlock(
                block_id="block_0",
                block_type="heading",
                text="Chapter 1",
                page_no=1,
                section="Chapter 1",
            ),
            DocumentBlock(
                block_id="block_1",
                block_type="paragraph",
                text="This is paragraph 1.",
                page_no=1,
                section="Chapter 1",
                section_path=["Chapter 1"],
            ),
            DocumentBlock(
                block_id="block_2",
                block_type="table",
                text="Table content",
                page_no=2,
                table=TableBlock(
                    rows=2,
                    cols=2,
                    cells=[
                        TableCell(row=0, col=0, text="Header 1"),
                        TableCell(row=0, col=1, text="Header 2"),
                        TableCell(row=1, col=0, text="Data 1"),
                        TableCell(row=1, col=1, text="Data 2"),
                    ],
                ),
            ),
        ]
        return create_parsed_document_v2(
            source_file_name="test.pdf",
            mime_type="application/pdf",
            content="Chapter 1\nThis is paragraph 1.\nTable content",
            blocks=blocks,
        )

    def test_parsed_document_v2_creation(self):
        """应能创建 ParsedDocumentV2。"""
        doc = self._create_test_document()
        assert doc.source_file_name == "test.pdf"
        assert doc.mime_type == "application/pdf"
        assert len(doc.blocks) == 3
        assert len(doc.pages) > 0

    def test_parsed_document_v2_content_hash(self):
        """应自动计算内容哈希。"""
        doc = self._create_test_document()
        assert len(doc.content_hash) == 64  # SHA-256 hex digest

    def test_parsed_document_v2_get_block_by_id(self):
        """应能根据 block_id 获取块。"""
        doc = self._create_test_document()
        block = doc.get_block_by_id("block_0")
        assert block is not None
        assert block.text == "Chapter 1"

    def test_parsed_document_v2_get_block_by_id_not_found(self):
        """不存在的 block_id 应返回 None。"""
        doc = self._create_test_document()
        block = doc.get_block_by_id("nonexistent")
        assert block is None

    def test_parsed_document_v2_get_blocks_by_page(self):
        """应能获取指定页面的所有块。"""
        doc = self._create_test_document()
        page_1_blocks = doc.get_blocks_by_page(1)
        assert len(page_1_blocks) == 2
        page_2_blocks = doc.get_blocks_by_page(2)
        assert len(page_2_blocks) == 1

    def test_parsed_document_v2_get_blocks_by_type(self):
        """应能获取指定类型的所有块。"""
        doc = self._create_test_document()
        headings = doc.get_blocks_by_type("heading")
        assert len(headings) == 1
        paragraphs = doc.get_blocks_by_type("paragraph")
        assert len(paragraphs) == 1
        tables = doc.get_blocks_by_type("table")
        assert len(tables) == 1

    def test_parsed_document_v2_get_table_blocks(self):
        """应能获取所有表格块。"""
        doc = self._create_test_document()
        tables = doc.get_table_blocks()
        assert len(tables) == 1
        assert tables[0].table is not None

    def test_parsed_document_v2_get_image_blocks(self):
        """应能获取所有图片块。"""
        doc = self._create_test_document()
        images = doc.get_image_blocks()
        assert len(images) == 0

    def test_parsed_document_v2_to_dict(self):
        """应能序列化为字典。"""
        doc = self._create_test_document()
        d = doc.to_dict()
        assert "documentId" in d
        assert "sourceFileName" in d
        assert "blocks" in d
        assert "pages" in d
        assert len(d["blocks"]) == 3


class TestConvertParsedDocumentToV2:
    """旧版 ParsedDocument 转换测试。"""

    def test_convert_parsed_document(self):
        """应能转换旧版 ParsedDocument（兼容 chunks 格式）。"""
        from app.services.document_parsing import ParsedDocument, ParsedChunk

        old_doc = ParsedDocument(
            parser_name="test_parser",
            parser_version="1.0",
            source_file_name="test.txt",
            mime_type="text/plain",
            blocks=[],  # 新格式为空，回退到 chunks
            chunks=[
                ParsedChunk(
                    content="Chunk 1",
                    token_count=10,
                    section="Section 1",
                    page_no=1,
                ),
                ParsedChunk(
                    content="Chunk 2",
                    token_count=10,
                    section="Section 2",
                    page_no=2,
                ),
            ],
        )

        new_doc = convert_parsed_document_to_v2(old_doc)
        assert new_doc.source_file_name == "test.txt"
        assert len(new_doc.blocks) == 2
        assert new_doc.blocks[0].text == "Chunk 1"
        assert new_doc.blocks[0].page_no == 1
        assert new_doc.blocks[1].text == "Chunk 2"
        assert new_doc.blocks[1].page_no == 2


class TestComputeContentHash:
    """内容哈希测试。"""

    def test_compute_content_hash(self):
        """应能计算内容哈希。"""
        hash1 = compute_content_hash("test content")
        hash2 = compute_content_hash("test content")
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_different_content_different_hash(self):
        """不同内容应产生不同哈希。"""
        hash1 = compute_content_hash("content 1")
        hash2 = compute_content_hash("content 2")
        assert hash1 != hash2
