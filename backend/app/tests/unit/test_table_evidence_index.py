"""B-324: 表格结构化检索测试。

验证表格索引构建、搜索和证据生成功能。
"""

import pytest

from app.services.structured_evidence import (
    TableIndex,
    build_structured_indexes,
    flowchart_index_to_evidence,
    get_structured_retrieval_info,
    index_table_block,
    search_flowcharts_by_node,
    search_tables_by_cell,
    search_tables_by_column,
    search_tables_by_row,
    table_index_to_evidence,
)
from app.services.parsed_document_v2 import (
    BoundingBox,
    DocumentBlock,
    ImageBlock,
    TableBlock,
    TableCell,
    create_parsed_document_v2,
)


class TestIndexTableBlock:
    """表格块索引测试。"""

    def test_index_table_block(self):
        """应能索引表格块。"""
        table = TableBlock(
            rows=2,
            cols=2,
            cells=[
                TableCell(row=0, col=0, text="Name"),
                TableCell(row=0, col=1, text="Age"),
                TableCell(row=1, col=0, text="Alice"),
                TableCell(row=1, col=1, text="30"),
            ],
        )
        block = DocumentBlock(
            block_id="block_0",
            block_type="table",
            text="Table content",
            table=table,
        )
        index = index_table_block(block, "doc_0")
        assert index.rows == 2
        assert index.cols == 2
        assert "Name" in index.column_names
        assert "Age" in index.column_names

    def test_index_table_block_generates_summary(self):
        """应生成表格摘要。"""
        table = TableBlock(
            rows=1,
            cols=1,
            cells=[TableCell(row=0, col=0, text="Test")],
        )
        block = DocumentBlock(
            block_id="block_0",
            block_type="table",
            text="Table",
            table=table,
        )
        index = index_table_block(block, "doc_0")
        assert len(index.summary) > 0

    def test_index_table_block_generates_row_summaries(self):
        """应生成行摘要。"""
        table = TableBlock(
            rows=2,
            cols=2,
            cells=[
                TableCell(row=0, col=0, text="A"),
                TableCell(row=0, col=1, text="B"),
                TableCell(row=1, col=0, text="C"),
                TableCell(row=1, col=1, text="D"),
            ],
        )
        block = DocumentBlock(
            block_id="block_0",
            block_type="table",
            text="Table",
            table=table,
        )
        index = index_table_block(block, "doc_0")
        assert len(index.row_summaries) == 2


class TestBuildStructuredIndexes:
    """结构化索引构建测试。"""

    def test_build_structured_indexes(self):
        """应能构建结构化索引。"""
        table = TableBlock(
            rows=1,
            cols=1,
            cells=[TableCell(row=0, col=0, text="Test")],
        )
        blocks = [
            DocumentBlock(
                block_id="block_0",
                block_type="table",
                text="Table",
                table=table,
            ),
            DocumentBlock(
                block_id="block_1",
                block_type="paragraph",
                text="Text content",
            ),
        ]
        doc = create_parsed_document_v2(
            source_file_name="test.txt",
            mime_type="text/plain",
            content="Table\nText content",
            blocks=blocks,
        )
        table_indexes, flowchart_indexes = build_structured_indexes(doc)
        assert len(table_indexes) == 1
        assert len(flowchart_indexes) == 0


class TestSearchTablesByColumn:
    """按列名搜索表格测试。"""

    def test_search_tables_by_column(self):
        """应能按列名搜索。"""
        table = TableIndex(
            block_id="block_0",
            document_id="doc_0",
            page_no=1,
            rows=1,
            cols=2,
            column_names=["Name", "Age"],
            summary="Test",
            row_summaries=[],
            cell_texts=[],
        )
        results = search_tables_by_column([table], "Name")
        assert len(results) == 1

    def test_search_tables_by_column_no_match(self):
        """不匹配时应返回空列表。"""
        table = TableIndex(
            block_id="block_0",
            document_id="doc_0",
            page_no=1,
            rows=1,
            cols=1,
            column_names=["Name"],
            summary="Test",
            row_summaries=[],
            cell_texts=[],
        )
        results = search_tables_by_column([table], "Age")
        assert len(results) == 0


class TestSearchTablesByCell:
    """按单元格搜索表格测试。"""

    def test_search_tables_by_cell(self):
        """应能按单元格内容搜索。"""
        table = TableIndex(
            block_id="block_0",
            document_id="doc_0",
            page_no=1,
            rows=1,
            cols=1,
            column_names=[],
            summary="Test",
            row_summaries=[],
            cell_texts=["Alice", "30"],
        )
        results = search_tables_by_cell([table], "Alice")
        assert len(results) == 1


class TestSearchTablesByRow:
    """按行关键词搜索表格测试。"""

    def test_search_tables_by_row(self):
        """应能按行关键词搜索。"""
        table = TableIndex(
            block_id="block_0",
            document_id="doc_0",
            page_no=1,
            rows=1,
            cols=1,
            column_names=[],
            summary="Test",
            row_summaries=["Alice | 30"],
            cell_texts=[],
        )
        results = search_tables_by_row([table], "Alice")
        assert len(results) == 1


class TestSearchFlowchartsByNode:
    """按节点搜索流程图测试。"""

    def test_search_flowcharts_by_node(self):
        """应能按节点标签搜索。"""
        from app.services.structured_evidence import FlowchartIndex

        flowchart = FlowchartIndex(
            block_id="block_0",
            document_id="doc_0",
            page_no=1,
            nodes=[{"id": "n0", "label": "Start"}, {"id": "n1", "label": "End"}],
            edges=[],
            summary="Test",
        )
        results = search_flowcharts_by_node([flowchart], "Start")
        assert len(results) == 1


class TestTableIndexToEvidence:
    """表格证据生成测试。"""

    def test_table_index_to_evidence(self):
        """应能生成结构化证据。"""
        table = TableIndex(
            block_id="block_0",
            document_id="doc_0",
            page_no=1,
            rows=1,
            cols=1,
            column_names=["Name"],
            summary="Test table",
            row_summaries=["Alice"],
            cell_texts=["Alice"],
        )
        evidence = table_index_to_evidence(table)
        assert evidence.evidence_type == "table"
        assert "Test table" in evidence.content


class TestGetStructuredRetrievalInfo:
    """获取检索信息测试。"""

    def test_get_structured_retrieval_info(self):
        """应返回检索方法信息。"""
        info = get_structured_retrieval_info()
        assert "tableSearchMethods" in info
        assert "flowchartSearchMethods" in info
