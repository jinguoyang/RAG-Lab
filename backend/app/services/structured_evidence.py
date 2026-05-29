"""B-324: 表格与流程图结构化检索服务。

识别、索引和检索表格和流程图作为结构化证据，支持表格 QA、
流程步骤查询和带位置引用的结构化答案。

功能:
- 表格索引：整表摘要、行摘要、列名、关键单元格文本
- 流程图索引：节点、边、标签、bbox、原始图片引用
- 结构化证据检索，回退到页码和 bbox
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.parsed_document_v2 import (
    BoundingBox,
    DocumentBlock,
    ParsedDocumentV2,
    TableBlock,
    TableCell,
)


@dataclass(frozen=True)
class TableIndex:
    """表格索引。"""

    block_id: str
    document_id: str
    page_no: int | None
    rows: int
    cols: int
    column_names: list[str]
    summary: str
    row_summaries: list[str]
    cell_texts: list[str]
    bbox: BoundingBox | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class FlowchartIndex:
    """流程图索引。"""

    block_id: str
    document_id: str
    page_no: int | None
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    summary: str
    bbox: BoundingBox | None = None
    confidence: float = 1.0


@dataclass(frozen=True)
class StructuredEvidence:
    """结构化证据。"""

    evidence_id: str
    evidence_type: str  # table | flowchart
    block_id: str
    document_id: str
    page_no: int | None
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    bbox: BoundingBox | None = None
    confidence: float = 1.0


def _extract_column_names(table: TableBlock) -> list[str]:
    """提取表格列名。"""
    column_names = []
    if table.cells:
        # 第一行作为列名
        first_row_cells = [cell for cell in table.cells if cell.row == 0]
        first_row_cells.sort(key=lambda c: c.col)
        column_names = [cell.text.strip() for cell in first_row_cells]
    return column_names


def _generate_row_summary(table: TableBlock, row: int) -> str:
    """生成行摘要。"""
    row_cells = [cell for cell in table.cells if cell.row == row]
    row_cells.sort(key=lambda c: c.col)
    return " | ".join(cell.text.strip() for cell in row_cells if cell.text.strip())


def _generate_table_summary(table: TableBlock) -> str:
    """生成表格摘要。"""
    column_names = _extract_column_names(table)
    if column_names:
        return f"表格 ({table.rows}x{table.cols}): 列=[{', '.join(column_names)}]"
    return f"表格 ({table.rows}x{table.cols})"


def index_table_block(block: DocumentBlock, document_id: str) -> TableIndex:
    """索引表格块。

    Args:
        block: 文档块
        document_id: 文档 ID

    Returns:
        表格索引
    """
    if not block.table:
        raise ValueError("Block does not contain a table")

    table = block.table
    column_names = _extract_column_names(table)
    summary = _generate_table_summary(table)

    row_summaries = []
    for row in range(table.rows):
        row_summary = _generate_row_summary(table, row)
        if row_summary:
            row_summaries.append(row_summary)

    cell_texts = [cell.text.strip() for cell in table.cells if cell.text.strip()]

    return TableIndex(
        block_id=block.block_id,
        document_id=document_id,
        page_no=block.page_no,
        rows=table.rows,
        cols=table.cols,
        column_names=column_names,
        summary=summary,
        row_summaries=row_summaries,
        cell_texts=cell_texts,
        bbox=block.bbox,
        confidence=block.confidence,
    )


def index_flowchart_block(block: DocumentBlock, document_id: str) -> FlowchartIndex:
    """索引流程图块。

    Args:
        block: 文档块
        document_id: 文档 ID

    Returns:
        流程图索引
    """
    if not block.image:
        raise ValueError("Block does not contain an image")

    # 从 OCR 文本中提取节点和边
    nodes = []
    edges = []

    if block.image.ocr_text:
        # 简单的节点提取：按行分割
        lines = block.image.ocr_text.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                nodes.append({
                    "id": f"node_{i}",
                    "label": line,
                })

        # 简单的边提取：相邻节点连接
        for i in range(len(nodes) - 1):
            edges.append({
                "source": nodes[i]["id"],
                "target": nodes[i + 1]["id"],
                "label": "next",
            })

    summary = block.image.caption or block.text[:100]

    return FlowchartIndex(
        block_id=block.block_id,
        document_id=document_id,
        page_no=block.page_no,
        nodes=nodes,
        edges=edges,
        summary=summary,
        bbox=block.bbox,
        confidence=block.confidence,
    )


def build_structured_indexes(
    doc: ParsedDocumentV2,
) -> tuple[list[TableIndex], list[FlowchartIndex]]:
    """为文档构建结构化索引。

    Args:
        doc: ParsedDocumentV2 文档

    Returns:
        (table_indexes, flowchart_indexes) 元组
    """
    table_indexes = []
    flowchart_indexes = []

    for block in doc.blocks:
        if block.block_type == "table" and block.table:
            try:
                table_index = index_table_block(block, doc.document_id)
                table_indexes.append(table_index)
            except ValueError:
                pass

        elif block.block_type == "image" and block.image:
            try:
                flowchart_index = index_flowchart_block(block, doc.document_id)
                flowchart_indexes.append(flowchart_index)
            except ValueError:
                pass

    return table_indexes, flowchart_indexes


def search_tables_by_column(
    table_indexes: list[TableIndex],
    column_name: str,
) -> list[TableIndex]:
    """按列名搜索表格。

    Args:
        table_indexes: 表格索引列表
        column_name: 列名

    Returns:
        匹配的表格索引列表
    """
    results = []
    for table in table_indexes:
        if any(column_name.lower() in col.lower() for col in table.column_names):
            results.append(table)
    return results


def search_tables_by_cell(
    table_indexes: list[TableIndex],
    cell_text: str,
) -> list[TableIndex]:
    """按单元格内容搜索表格。

    Args:
        table_indexes: 表格索引列表
        cell_text: 单元格文本

    Returns:
        匹配的表格索引列表
    """
    results = []
    for table in table_indexes:
        if any(cell_text.lower() in cell.lower() for cell in table.cell_texts):
            results.append(table)
    return results


def search_tables_by_row(
    table_indexes: list[TableIndex],
    row_keyword: str,
) -> list[TableIndex]:
    """按行关键词搜索表格。

    Args:
        table_indexes: 表格索引列表
        row_keyword: 行关键词

    Returns:
        匹配的表格索引列表
    """
    results = []
    for table in table_indexes:
        if any(row_keyword.lower() in row.lower() for row in table.row_summaries):
            results.append(table)
    return results


def search_flowcharts_by_node(
    flowchart_indexes: list[FlowchartIndex],
    node_label: str,
) -> list[FlowchartIndex]:
    """按节点标签搜索流程图。

    Args:
        flowchart_indexes: 流程图索引列表
        node_label: 节点标签

    Returns:
        匹配的流程图索引列表
    """
    results = []
    for flowchart in flowchart_indexes:
        if any(node_label.lower() in node.get("label", "").lower() for node in flowchart.nodes):
            results.append(flowchart)
    return results


def search_flowcharts_by_step(
    flowchart_indexes: list[FlowchartIndex],
    step_label: str,
) -> list[FlowchartIndex]:
    """按步骤标签搜索流程图。

    Args:
        flowchart_indexes: 流程图索引列表
        step_label: 步骤标签

    Returns:
        匹配的流程图索引列表
    """
    results = []
    for flowchart in flowchart_indexes:
        if any(step_label.lower() in edge.get("label", "").lower() for edge in flowchart.edges):
            results.append(flowchart)
    return results


def table_index_to_evidence(table: TableIndex) -> StructuredEvidence:
    """将表格索引转换为结构化证据。"""
    content = table.summary
    if table.row_summaries:
        content += "\n" + "\n".join(table.row_summaries[:5])

    return StructuredEvidence(
        evidence_id=f"table_{table.block_id}",
        evidence_type="table",
        block_id=table.block_id,
        document_id=table.document_id,
        page_no=table.page_no,
        content=content,
        metadata={
            "rows": table.rows,
            "cols": table.cols,
            "columnNames": table.column_names,
        },
        bbox=table.bbox,
        confidence=table.confidence,
    )


def flowchart_index_to_evidence(flowchart: FlowchartIndex) -> StructuredEvidence:
    """将流程图索引转换为结构化证据。"""
    content = flowchart.summary
    if flowchart.nodes:
        content += "\n节点: " + ", ".join(node.get("label", "") for node in flowchart.nodes[:5])

    return StructuredEvidence(
        evidence_id=f"flowchart_{flowchart.block_id}",
        evidence_type="flowchart",
        block_id=flowchart.block_id,
        document_id=flowchart.document_id,
        page_no=flowchart.page_no,
        content=content,
        metadata={
            "nodeCount": len(flowchart.nodes),
            "edgeCount": len(flowchart.edges),
        },
        bbox=flowchart.bbox,
        confidence=flowchart.confidence,
    )


def get_structured_retrieval_info() -> dict[str, Any]:
    """获取结构化检索信息。"""
    return {
        "tableSearchMethods": [
            {"name": "column", "label": "按列名搜索"},
            {"name": "cell", "label": "按单元格搜索"},
            {"name": "row", "label": "按行关键词搜索"},
        ],
        "flowchartSearchMethods": [
            {"name": "node", "label": "按节点搜索"},
            {"name": "step", "label": "按步骤搜索"},
        ],
    }
