"""B-320: 多视图 ChunkRevision 分块策略服务。

支持多种分块策略，每种策略生成独立的 ChunkRevision，可共存且可追溯。

分块策略:
- fixed: 固定长度分块（现有实现）
- heading: 按标题层级分块
- semantic: 语义分块（基于段落和主题）
- parent_child: 父子分块（小块精准检索 + 大块上下文）
- table_aware: 表格感知分块
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

from app.services.parsed_document_v2 import DocumentBlock, ParsedDocumentV2
from app.services.token_utils import estimate_tokens


class ChunkStrategy(str, Enum):
    """分块策略枚举。"""
    FIXED = "fixed"
    HEADING = "heading"
    SEMANTIC = "semantic"
    PARENT_CHILD = "parent_child"
    TABLE_AWARE = "table_aware"


@dataclass(frozen=True)
class ChunkRevision:
    """ChunkRevision 分块版本记录。"""

    chunk_revision_id: str
    document_id: str
    strategy: str
    chunk_view_type: str
    source_block_range: list[str]  # 源 block_id 列表
    chunk_count: int
    params: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkResult:
    """分块结果。"""

    chunk_id: str
    content: str
    token_count: int
    chunk_index: int
    section: str | None = None
    page_no: int | None = None
    source_block_ids: list[str] = field(default_factory=list)
    parent_chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# 向后兼容的别名
_estimate_tokens = estimate_tokens


def _fixed_chunking(
    blocks: list[DocumentBlock],
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> list[ChunkResult]:
    """固定长度分块策略。"""
    chunks: list[ChunkResult] = []
    buffer = ""
    current_block_ids: list[str] = []
    current_section: str | None = None
    current_page: int | None = None
    chunk_index = 0

    for block in blocks:
        if block.text:
            buffer += block.text + "\n"
            current_block_ids.append(block.block_id)
            if block.section:
                current_section = block.section
            if block.page_no:
                current_page = block.page_no

        while len(buffer) >= chunk_size:
            chunk_text = buffer[:chunk_size].strip()
            if chunk_text:
                chunks.append(ChunkResult(
                    chunk_id=f"chunk_{chunk_index}",
                    content=chunk_text,
                    token_count=_estimate_tokens(chunk_text),
                    chunk_index=chunk_index,
                    section=current_section,
                    page_no=current_page,
                    source_block_ids=list(current_block_ids),
                ))
                chunk_index += 1
            buffer = buffer[chunk_size - chunk_overlap:]
            current_block_ids = []

    # 处理剩余内容
    if buffer.strip():
        chunks.append(ChunkResult(
            chunk_id=f"chunk_{chunk_index}",
            content=buffer.strip(),
            token_count=_estimate_tokens(buffer.strip()),
            chunk_index=chunk_index,
            section=current_section,
            page_no=current_page,
            source_block_ids=list(current_block_ids),
        ))

    return chunks


def _heading_chunking(blocks: list[DocumentBlock]) -> list[ChunkResult]:
    """按标题层级分块策略。"""
    chunks: list[ChunkResult] = []
    current_chunk_blocks: list[DocumentBlock] = []
    chunk_index = 0

    def flush_chunk():
        nonlocal chunk_index
        if not current_chunk_blocks:
            return
        content = "\n".join(block.text for block in current_chunk_blocks if block.text)
        if content.strip():
            section = current_chunk_blocks[0].section
            page_no = current_chunk_blocks[0].page_no
            chunks.append(ChunkResult(
                chunk_id=f"chunk_{chunk_index}",
                content=content.strip(),
                token_count=_estimate_tokens(content),
                chunk_index=chunk_index,
                section=section,
                page_no=page_no,
                source_block_ids=[block.block_id for block in current_chunk_blocks],
            ))
            chunk_index += 1
        current_chunk_blocks.clear()

    for block in blocks:
        if block.block_type == "heading":
            flush_chunk()
            current_chunk_blocks.append(block)
        else:
            current_chunk_blocks.append(block)

    flush_chunk()
    return chunks


def _semantic_chunking(blocks: list[DocumentBlock]) -> list[ChunkResult]:
    """语义分块策略，基于段落和主题。"""
    # 语义分块：按段落分组，每个段落作为一个语义单元
    chunks: list[ChunkResult] = []
    chunk_index = 0

    for block in blocks:
        if block.text and block.text.strip():
            chunks.append(ChunkResult(
                chunk_id=f"chunk_{chunk_index}",
                content=block.text.strip(),
                token_count=_estimate_tokens(block.text),
                chunk_index=chunk_index,
                section=block.section,
                page_no=block.page_no,
                source_block_ids=[block.block_id],
            ))
            chunk_index += 1

    return chunks


def _parent_child_chunking(
    blocks: list[DocumentBlock],
    parent_size: int = 2000,
    child_size: int = 300,
) -> tuple[list[ChunkResult], list[ChunkResult]]:
    """父子分块策略，返回 (parent_chunks, child_chunks)。"""
    parent_chunks: list[ChunkResult] = []
    child_chunks: list[ChunkResult] = []
    parent_index = 0
    child_index = 0

    # 先生成父块
    buffer = ""
    current_block_ids: list[str] = []
    current_section: str | None = None
    current_page: int | None = None

    for block in blocks:
        if block.text:
            buffer += block.text + "\n"
            current_block_ids.append(block.block_id)
            if block.section:
                current_section = block.section
            if block.page_no:
                current_page = block.page_no

        while len(buffer) >= parent_size:
            chunk_text = buffer[:parent_size].strip()
            if chunk_text:
                parent_chunks.append(ChunkResult(
                    chunk_id=f"parent_{parent_index}",
                    content=chunk_text,
                    token_count=_estimate_tokens(chunk_text),
                    chunk_index=parent_index,
                    section=current_section,
                    page_no=current_page,
                    source_block_ids=list(current_block_ids),
                ))
                parent_index += 1
            buffer = buffer[parent_size:]
            current_block_ids = []

    if buffer.strip():
        parent_chunks.append(ChunkResult(
            chunk_id=f"parent_{parent_index}",
            content=buffer.strip(),
            token_count=_estimate_tokens(buffer.strip()),
            chunk_index=parent_index,
            section=current_section,
            page_no=current_page,
            source_block_ids=list(current_block_ids),
        ))

    # 从父块生成子块
    for parent in parent_chunks:
        child_buffer = parent.content
        local_index = 0
        while len(child_buffer) >= child_size:
            child_text = child_buffer[:child_size].strip()
            if child_text:
                child_chunks.append(ChunkResult(
                    chunk_id=f"child_{child_index}",
                    content=child_text,
                    token_count=_estimate_tokens(child_text),
                    chunk_index=child_index,
                    section=parent.section,
                    page_no=parent.page_no,
                    source_block_ids=parent.source_block_ids,
                    parent_chunk_id=parent.chunk_id,
                ))
                child_index += 1
            child_buffer = child_buffer[child_size:]
            local_index += 1

        if child_buffer.strip():
            child_chunks.append(ChunkResult(
                chunk_id=f"child_{child_index}",
                content=child_buffer.strip(),
                token_count=_estimate_tokens(child_buffer.strip()),
                chunk_index=child_index,
                section=parent.section,
                page_no=parent.page_no,
                source_block_ids=parent.source_block_ids,
                parent_chunk_id=parent.chunk_id,
            ))
            child_index += 1

    return parent_chunks, child_chunks


def _table_aware_chunking(blocks: list[DocumentBlock]) -> list[ChunkResult]:
    """表格感知分块策略，表格作为独立块。"""
    chunks: list[ChunkResult] = []
    chunk_index = 0

    for block in blocks:
        if block.block_type == "table" and block.table:
            # 表格作为独立块
            table_content = f"表格 ({block.table.rows}x{block.table.cols}):\n"
            for cell in block.table.cells:
                table_content += f"[{cell.row},{cell.col}] {cell.text}\n"

            chunks.append(ChunkResult(
                chunk_id=f"chunk_{chunk_index}",
                content=table_content.strip(),
                token_count=_estimate_tokens(table_content),
                chunk_index=chunk_index,
                section=block.section,
                page_no=block.page_no,
                source_block_ids=[block.block_id],
                metadata={"isTable": True, "tableRows": block.table.rows, "tableCols": block.table.cols},
            ))
            chunk_index += 1
        elif block.text:
            chunks.append(ChunkResult(
                chunk_id=f"chunk_{chunk_index}",
                content=block.text.strip(),
                token_count=_estimate_tokens(block.text),
                chunk_index=chunk_index,
                section=block.section,
                page_no=block.page_no,
                source_block_ids=[block.block_id],
            ))
            chunk_index += 1

    return chunks


def execute_chunking(
    doc: ParsedDocumentV2,
    strategy: str | ChunkStrategy,
    params: dict[str, Any] | None = None,
) -> tuple[list[ChunkResult], ChunkRevision]:
    """执行分块策略，返回分块结果和版本记录。

    Args:
        doc: ParsedDocumentV2 文档
        strategy: 分块策略
        params: 策略参数

    Returns:
        (chunks, chunk_revision) 元组
    """
    if isinstance(strategy, str):
        try:
            strategy = ChunkStrategy(strategy)
        except ValueError:
            strategy = ChunkStrategy.FIXED

    params = params or {}
    blocks = doc.blocks

    if strategy == ChunkStrategy.FIXED:
        chunks = _fixed_chunking(
            blocks,
            chunk_size=params.get("chunkSize", 900),
            chunk_overlap=params.get("chunkOverlap", 120),
        )
    elif strategy == ChunkStrategy.HEADING:
        chunks = _heading_chunking(blocks)
    elif strategy == ChunkStrategy.SEMANTIC:
        chunks = _semantic_chunking(blocks)
    elif strategy == ChunkStrategy.PARENT_CHILD:
        parent_chunks, child_chunks = _parent_child_chunking(
            blocks,
            parent_size=params.get("parentSize", 2000),
            child_size=params.get("childSize", 300),
        )
        # 合并父子块，子块通过 parent_chunk_id 关联
        chunks = parent_chunks + child_chunks
    elif strategy == ChunkStrategy.TABLE_AWARE:
        chunks = _table_aware_chunking(blocks)
    else:
        chunks = _fixed_chunking(blocks)

    # 创建 ChunkRevision
    chunk_revision = ChunkRevision(
        chunk_revision_id=str(uuid4()),
        document_id=doc.document_id,
        strategy=strategy.value,
        chunk_view_type=strategy.value,
        source_block_range=[block.block_id for block in blocks],
        chunk_count=len(chunks),
        params=params,
    )

    return chunks, chunk_revision


def get_available_strategies() -> list[dict[str, Any]]:
    """获取可用的分块策略列表。"""
    return [
        {
            "name": "fixed",
            "label": "固定长度分块",
            "description": "按固定字符数分块，适用于通用文档",
            "params": [
                {"key": "chunkSize", "label": "分块大小", "type": "number", "default": 900},
                {"key": "chunkOverlap", "label": "重叠大小", "type": "number", "default": 120},
            ],
        },
        {
            "name": "heading",
            "label": "标题分块",
            "description": "按标题层级分块，保留章节结构",
            "params": [],
        },
        {
            "name": "semantic",
            "label": "语义分块",
            "description": "按段落语义分块，每个段落作为独立语义单元",
            "params": [],
        },
        {
            "name": "parent_child",
            "label": "父子分块",
            "description": "大块提供上下文，小块精准检索",
            "params": [
                {"key": "parentSize", "label": "父块大小", "type": "number", "default": 2000},
                {"key": "childSize", "label": "子块大小", "type": "number", "default": 300},
            ],
        },
        {
            "name": "table_aware",
            "label": "表格感知分块",
            "description": "表格作为独立块，文本按段落分块",
            "params": [],
        },
    ]
