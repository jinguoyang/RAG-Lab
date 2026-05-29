"""B-318: 文档解析 Provider 路由服务。

根据文件类型、质量需求、租户配置和成本策略选择合适的解析器。
所有解析器输出统一为 ParsedDocumentV2 契约。

路由策略：
- default: 默认策略，优先使用基础解析器
- low-cost: 低成本策略，仅使用本地解析器
- high-quality: 高质量策略，优先使用布局分析和 OCR
- strong-ocr: 强 OCR 策略，适用于扫描件
- table-priority: 表格优先策略，优先识别表格结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

from app.services.document_parsing import (
    DocumentParseError,
    ParsedChunk,
    ParsedDocument,
    parse_document,
)


class ParseStrategy(str, Enum):
    """解析路由策略枚举。"""
    DEFAULT = "default"
    LOW_COST = "low-cost"
    HIGH_QUALITY = "high-quality"
    STRONG_OCR = "strong-ocr"
    TABLE_PRIORITY = "table-priority"


@dataclass(frozen=True)
class ParserCapability:
    """解析器能力描述符。"""

    parser_name: str
    supported_types: set[str]
    supports_bbox: bool = False
    supports_table: bool = False
    supports_ocr: bool = False
    supports_layout: bool = False
    confidence: float = 1.0
    cost_level: str = "low"  # low | medium | high
    version: str = "1.0"


@dataclass(frozen=True)
class ParseTaskRecord:
    """解析任务记录，用于追踪解析过程。"""

    task_id: str
    file_name: str
    strategy: str
    parser_name: str
    parser_version: str
    duration_ms: int
    success: bool
    quality_flags: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None


class ParserProvider(Protocol):
    """解析器 Provider 协议。"""

    def parse(
        self,
        file_name: str,
        mime_type: str | None,
        file_bytes: bytes,
        chunk_size: int,
        chunk_overlap: int,
    ) -> ParsedDocument:
        """解析文档并返回结构化结果。"""
        ...


# ── 内置解析器 ──


class BasicParserProvider:
    """基础解析器，使用现有的 document_parsing 模块。"""

    def parse(
        self,
        file_name: str,
        mime_type: str | None,
        file_bytes: bytes,
        chunk_size: int,
        chunk_overlap: int,
    ) -> ParsedDocument:
        return parse_document(file_name, mime_type, file_bytes, chunk_size, chunk_overlap)


# ── 解析器能力注册表 ──


_PARSER_REGISTRY: dict[str, ParserCapability] = {
    "basic": ParserCapability(
        parser_name="basic",
        supported_types={".txt", ".md", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"},
        supports_bbox=False,
        supports_table=False,
        supports_ocr=False,
        supports_layout=False,
        confidence=0.8,
        cost_level="low",
        version="sprint19.2",
    ),
}

_PROVIDER_REGISTRY: dict[str, ParserProvider] = {
    "basic": BasicParserProvider(),
}


def register_parser_provider(
    name: str,
    capability: ParserCapability,
    provider: ParserProvider,
) -> None:
    """注册新的解析器 Provider。"""
    _PARSER_REGISTRY[name] = capability
    _PROVIDER_REGISTRY[name] = provider


def get_parser_capability(name: str) -> ParserCapability | None:
    """获取解析器能力描述符。"""
    return _PARSER_REGISTRY.get(name)


def list_parser_capabilities() -> list[ParserCapability]:
    """列出所有已注册的解析器能力。"""
    return list(_PARSER_REGISTRY.values())


# ── 路由策略 ──


def _select_parser_for_strategy(
    strategy: ParseStrategy,
    file_extension: str,
) -> list[str]:
    """根据策略和文件类型选择解析器优先级列表。"""
    if strategy == ParseStrategy.LOW_COST:
        return ["basic"]
    elif strategy == ParseStrategy.HIGH_QUALITY:
        # 高质量策略：优先使用布局分析，回退到基础
        return ["layout", "basic"]
    elif strategy == ParseStrategy.STRONG_OCR:
        # 强 OCR 策略：优先使用 OCR，回退到基础
        return ["ocr", "basic"]
    elif strategy == ParseStrategy.TABLE_PRIORITY:
        # 表格优先策略：优先使用表格识别，回退到基础
        return ["table", "basic"]
    else:  # DEFAULT
        return ["basic"]


def route_and_parse(
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    strategy: str | ParseStrategy = ParseStrategy.DEFAULT,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> tuple[ParsedDocument, ParseTaskRecord]:
    """路由并解析文档，返回解析结果和任务记录。

    Args:
        file_name: 文件名
        mime_type: MIME 类型
        file_bytes: 文件内容
        strategy: 解析策略
        chunk_size: 分块大小
        chunk_overlap: 分块重叠

    Returns:
        (ParsedDocument, ParseTaskRecord) 元组
    """
    from pathlib import PurePath
    import time as _time

    if isinstance(strategy, str):
        try:
            strategy = ParseStrategy(strategy)
        except ValueError:
            strategy = ParseStrategy.DEFAULT

    normalized_name = PurePath(file_name).name or "uploaded-document"
    extension = PurePath(normalized_name).suffix.lower()
    start_time = _time.monotonic()

    # 获取解析器优先级列表
    parser_candidates = _select_parser_for_strategy(strategy, extension)

    last_error: Exception | None = None
    fallback_used = False
    fallback_reason = None

    for parser_name in parser_candidates:
        provider = _PROVIDER_REGISTRY.get(parser_name)
        if provider is None:
            continue

        capability = _PARSER_REGISTRY.get(parser_name)
        if capability and extension not in capability.supported_types:
            continue

        try:
            result = provider.parse(
                normalized_name,
                mime_type,
                file_bytes,
                chunk_size,
                chunk_overlap,
            )
            duration_ms = int((_time.monotonic() - start_time) * 1000)

            # 构建质量标记
            quality_flags = {
                "parserName": parser_name,
                "strategy": strategy.value,
                "supportsBbox": capability.supports_bbox if capability else False,
                "supportsTable": capability.supports_table if capability else False,
                "supportsOcr": capability.supports_ocr if capability else False,
            }

            task_record = ParseTaskRecord(
                task_id=str(uuid4()),
                file_name=normalized_name,
                strategy=strategy.value,
                parser_name=parser_name,
                parser_version=capability.version if capability else "unknown",
                duration_ms=duration_ms,
                success=True,
                quality_flags=quality_flags,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
            )

            return result, task_record

        except (DocumentParseError, OSError, ValueError) as exc:
            last_error = exc
            fallback_used = True
            fallback_reason = f"Parser {parser_name} failed: {exc}"
            continue

    # 所有解析器都失败
    duration_ms = int((_time.monotonic() - start_time) * 1000)
    error_code = "ALL_PARSERS_FAILED"
    error_message = str(last_error) if last_error else "No suitable parser found"

    task_record = ParseTaskRecord(
        task_id=str(uuid4()),
        file_name=normalized_name,
        strategy=strategy.value,
        parser_name="none",
        parser_version="none",
        duration_ms=duration_ms,
        success=False,
        error_code=error_code,
        error_message=error_message,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )

    raise DocumentParseError(error_code, error_message)


def get_routing_strategy_info() -> dict[str, Any]:
    """获取路由策略信息，供 API 使用。"""
    return {
        "strategies": [
            {
                "name": "default",
                "label": "默认策略",
                "description": "使用基础解析器，平衡性能和质量",
                "costLevel": "low",
            },
            {
                "name": "low-cost",
                "label": "低成本策略",
                "description": "仅使用本地解析器，最小化成本",
                "costLevel": "low",
            },
            {
                "name": "high-quality",
                "label": "高质量策略",
                "description": "优先使用布局分析，提升解析质量",
                "costLevel": "medium",
            },
            {
                "name": "strong-ocr",
                "label": "强 OCR 策略",
                "description": "适用于扫描件和图片，优先使用 OCR",
                "costLevel": "high",
            },
            {
                "name": "table-priority",
                "label": "表格优先策略",
                "description": "优先识别表格结构，适用于表格密集文档",
                "costLevel": "medium",
            },
        ],
        "providers": [
            {
                "name": cap.parser_name,
                "supportedTypes": list(cap.supported_types),
                "supportsBbox": cap.supports_bbox,
                "supportsTable": cap.supports_table,
                "supportsOcr": cap.supports_ocr,
                "supportsLayout": cap.supports_layout,
                "confidence": cap.confidence,
                "costLevel": cap.cost_level,
                "version": cap.version,
            }
            for cap in _PARSER_REGISTRY.values()
        ],
    }
