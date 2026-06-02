"""B-319: ParsedDocumentV2 统一文档解析输出契约。

ParsedDocumentV2 是文档解析的统一输出格式，保留页面、块、段落、表格、图片/流程图
的位置溯源信息，供精确引用、表格检索和答案校验使用。

坐标系统:
- pageNo: 页码，从 1 开始
- bbox: [x1, y1, x2, y2]，左上角为原点，单位为点 (point, 1/72 inch)
- 所有坐标相对于页面坐标系
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class BoundingBox:
    """边界框，表示元素在页面上的位置。"""

    x1: float  # 左上角 x
    y1: float  # 左上角 y
    x2: float  # 右下角 x
    y2: float  # 右下角 y

    def to_dict(self) -> dict[str, float]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> BoundingBox:
        return cls(
            x1=float(data.get("x1", 0)),
            y1=float(data.get("y1", 0)),
            x2=float(data.get("x2", 0)),
            y2=float(data.get("y2", 0)),
        )


@dataclass(frozen=True)
class TableCell:
    """表格单元格。"""

    row: int
    col: int
    text: str
    row_span: int = 1
    col_span: int = 1
    bbox: BoundingBox | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "row": self.row,
            "col": self.col,
            "text": self.text,
            "rowSpan": self.row_span,
            "colSpan": self.col_span,
        }
        if self.bbox:
            result["bbox"] = self.bbox.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableCell":
        """从持久化字典恢复表格单元格。"""
        return cls(
            row=int(data.get("row", 0)),
            col=int(data.get("col", 0)),
            text=str(data.get("text", "")),
            row_span=int(data.get("rowSpan", 1)),
            col_span=int(data.get("colSpan", 1)),
            bbox=BoundingBox.from_dict(data["bbox"]) if data.get("bbox") else None,
        )


@dataclass(frozen=True)
class TableBlock:
    """表格块，包含行、列和单元格。"""

    rows: int
    cols: int
    cells: list[TableCell] = field(default_factory=list)
    caption: str | None = None
    bbox: BoundingBox | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "rows": self.rows,
            "cols": self.cols,
            "cells": [cell.to_dict() for cell in self.cells],
        }
        if self.caption:
            result["caption"] = self.caption
        if self.bbox:
            result["bbox"] = self.bbox.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableBlock":
        """从持久化字典恢复表格块。"""
        return cls(
            rows=int(data.get("rows", 0)),
            cols=int(data.get("cols", 0)),
            cells=[TableCell.from_dict(item) for item in data.get("cells", [])],
            caption=data.get("caption"),
            bbox=BoundingBox.from_dict(data["bbox"]) if data.get("bbox") else None,
        )


@dataclass(frozen=True)
class ImageBlock:
    """图片/流程图块。"""

    caption: str | None = None
    ocr_text: str | None = None
    alt_text: str | None = None
    bbox: BoundingBox | None = None
    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.caption:
            result["caption"] = self.caption
        if self.ocr_text:
            result["ocrText"] = self.ocr_text
        if self.alt_text:
            result["altText"] = self.alt_text
        if self.bbox:
            result["bbox"] = self.bbox.to_dict()
        if self.width is not None:
            result["width"] = self.width
        if self.height is not None:
            result["height"] = self.height
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageBlock":
        """从持久化字典恢复图片/流程图块。"""
        return cls(
            caption=data.get("caption"),
            ocr_text=data.get("ocrText"),
            alt_text=data.get("altText"),
            bbox=BoundingBox.from_dict(data["bbox"]) if data.get("bbox") else None,
            width=int(data["width"]) if data.get("width") is not None else None,
            height=int(data["height"]) if data.get("height") is not None else None,
        )


@dataclass(frozen=True)
class DocumentBlock:
    """文档块，是 ParsedDocumentV2 的基本单位。"""

    block_id: str
    block_type: str  # paragraph | heading | table | image | list | code | ...
    text: str
    page_no: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: BoundingBox | None = None
    confidence: float = 1.0
    section: str | None = None
    section_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    table: TableBlock | None = None
    image: ImageBlock | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "blockId": self.block_id,
            "blockType": self.block_type,
            "text": self.text,
            "confidence": self.confidence,
        }
        if self.page_no is not None:
            result["pageNo"] = self.page_no
        if self.char_start is not None:
            result["charStart"] = self.char_start
        if self.char_end is not None:
            result["charEnd"] = self.char_end
        if self.bbox:
            result["bbox"] = self.bbox.to_dict()
        if self.section:
            result["section"] = self.section
        if self.section_path:
            result["sectionPath"] = self.section_path
        if self.metadata:
            result["metadata"] = self.metadata
        if self.table:
            result["table"] = self.table.to_dict()
        if self.image:
            result["image"] = self.image.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentBlock":
        """从持久化字典恢复文档块。"""
        return cls(
            block_id=str(data.get("blockId", "")),
            block_type=str(data.get("blockType", "paragraph")),
            text=str(data.get("text", "")),
            page_no=int(data["pageNo"]) if data.get("pageNo") is not None else None,
            char_start=int(data["charStart"]) if data.get("charStart") is not None else None,
            char_end=int(data["charEnd"]) if data.get("charEnd") is not None else None,
            bbox=BoundingBox.from_dict(data["bbox"]) if data.get("bbox") else None,
            confidence=float(data.get("confidence", 1.0)),
            section=data.get("section"),
            section_path=list(data.get("sectionPath") or []),
            metadata=dict(data.get("metadata") or {}),
            table=TableBlock.from_dict(data["table"]) if data.get("table") else None,
            image=ImageBlock.from_dict(data["image"]) if data.get("image") else None,
        )


@dataclass(frozen=True)
class Page:
    """页面信息。"""

    page_no: int
    width: float | None = None
    height: float | None = None
    unit: str = "point"  # point | pixel | mm
    block_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"pageNo": self.page_no}
        if self.width is not None:
            result["width"] = self.width
        if self.height is not None:
            result["height"] = self.height
        result["unit"] = self.unit
        if self.block_ids:
            result["blockIds"] = self.block_ids
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Page":
        """从持久化字典恢复页面信息。"""
        return cls(
            page_no=int(data.get("pageNo", 1)),
            width=float(data["width"]) if data.get("width") is not None else None,
            height=float(data["height"]) if data.get("height") is not None else None,
            unit=str(data.get("unit", "point")),
            block_ids=list(data.get("blockIds") or []),
        )


@dataclass
class ParsedDocumentV2:
    """ParsedDocumentV2 统一文档解析输出契约。

    保留页面、块、段落、表格、图片/流程图的位置溯源信息，
    供精确引用、表格检索和答案校验使用。
    """

    document_id: str
    source_file_name: str
    mime_type: str | None
    content_hash: str
    parse_version: str
    provider_name: str
    provider_version: str
    pages: list[Page] = field(default_factory=list)
    blocks: list[DocumentBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "documentId": self.document_id,
            "sourceFileName": self.source_file_name,
            "mimeType": self.mime_type,
            "contentHash": self.content_hash,
            "parseVersion": self.parse_version,
            "providerName": self.provider_name,
            "providerVersion": self.provider_version,
            "pages": [page.to_dict() for page in self.pages],
            "blocks": [block.to_dict() for block in self.blocks],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedDocumentV2":
        """从持久化字典恢复统一解析契约，保证序列化结果可重放。"""
        return cls(
            document_id=data["documentId"],
            source_file_name=data["sourceFileName"],
            mime_type=data.get("mimeType"),
            content_hash=data["contentHash"],
            parse_version=data["parseVersion"],
            provider_name=data["providerName"],
            provider_version=data["providerVersion"],
            pages=[Page.from_dict(item) for item in data.get("pages", [])],
            blocks=[DocumentBlock.from_dict(item) for item in data.get("blocks", [])],
            metadata=dict(data.get("metadata") or {}),
        )

    def get_block_by_id(self, block_id: str) -> DocumentBlock | None:
        """根据 block_id 获取块。"""
        for block in self.blocks:
            if block.block_id == block_id:
                return block
        return None

    def get_blocks_by_page(self, page_no: int) -> list[DocumentBlock]:
        """获取指定页面的所有块。"""
        return [block for block in self.blocks if block.page_no == page_no]

    def get_blocks_by_type(self, block_type: str) -> list[DocumentBlock]:
        """获取指定类型的所有块。"""
        return [block for block in self.blocks if block.block_type == block_type]

    def get_table_blocks(self) -> list[DocumentBlock]:
        """获取所有表格块。"""
        return self.get_blocks_by_type("table")

    def get_image_blocks(self) -> list[DocumentBlock]:
        """获取所有图片块。"""
        return self.get_blocks_by_type("image")


def compute_content_hash(content: str) -> str:
    """计算内容哈希。"""
    return sha256(content.encode("utf-8")).hexdigest()


def create_parsed_document_v2(
    source_file_name: str,
    mime_type: str | None,
    content: str,
    blocks: list[DocumentBlock],
    pages: list[Page] | None = None,
    provider_name: str = "basic",
    provider_version: str = "1.0",
    parse_version: str = "v2",
    metadata: dict[str, Any] | None = None,
) -> ParsedDocumentV2:
    """创建 ParsedDocumentV2 实例。"""
    content_hash = compute_content_hash(content)
    document_id = str(uuid4())

    # 如果没有提供页面信息，从块中推断
    if pages is None:
        page_nos = sorted(set(block.page_no for block in blocks if block.page_no is not None))
        pages = [
            Page(page_no=page_no, block_ids=[block.block_id for block in blocks if block.page_no == page_no])
            for page_no in page_nos
        ]
        if not pages:
            pages = [Page(page_no=1, block_ids=[block.block_id for block in blocks])]

    return ParsedDocumentV2(
        document_id=document_id,
        source_file_name=source_file_name,
        mime_type=mime_type,
        content_hash=content_hash,
        parse_version=parse_version,
        provider_name=provider_name,
        provider_version=provider_version,
        pages=pages,
        blocks=blocks,
        metadata=metadata or {},
    )


def convert_parsed_document_to_v2(
    parsed_doc: Any,  # ParsedDocument from document_parsing
    provider_name: str | None = None,
    provider_version: str | None = None,
) -> ParsedDocumentV2:
    """将旧版 ParsedDocument 转换为 ParsedDocumentV2。"""
    blocks = []
    for i, chunk in enumerate(parsed_doc.chunks):
        block = DocumentBlock(
            block_id=f"block_{i}",
            block_type="paragraph",
            text=chunk.content,
            page_no=chunk.page_no,
            char_start=None,
            char_end=None,
            section=chunk.section,
            metadata=chunk.metadata if hasattr(chunk, "metadata") else {},
        )
        blocks.append(block)

    content = "\n".join(chunk.content for chunk in parsed_doc.chunks)
    return create_parsed_document_v2(
        source_file_name=parsed_doc.source_file_name,
        mime_type=parsed_doc.mime_type,
        content=content,
        blocks=blocks,
        provider_name=provider_name or parsed_doc.parser_name,
        provider_version=provider_version or parsed_doc.parser_version,
        parse_version=parsed_doc.parser_version,
    )
