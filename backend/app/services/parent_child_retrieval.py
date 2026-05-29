"""B-323: 大小 Chunk / Parent-child 检索与上下文打包服务。

"小块精准检索 + 大块连贯上下文" 的父子检索模式，解决命中碎片化、
上下文不足和引用不连续的问题。

功能:
- 小块检索和重排序
- 父块查找：通过 parent_id、section_id 或 block 范围
- chunkWindow 相邻块扩展
- packingStrategy: relevance_first, document_order, section_grouped
- Token 预算强制执行和截断日志
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services.multi_view_chunking import ChunkResult
from app.services.token_utils import estimate_tokens


class PackingStrategy(str, Enum):
    """上下文打包策略枚举。"""
    RELEVANCE_FIRST = "relevance_first"
    DOCUMENT_ORDER = "document_order"
    SECTION_GROUPED = "section_grouped"


@dataclass(frozen=True)
class PackedContext:
    """打包后的上下文。"""

    chunks: list[ChunkResult]
    total_tokens: int
    packing_strategy: str
    truncation_log: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# 向后兼容的别名
_estimate_tokens = estimate_tokens


def find_parent_chunk(
    child: ChunkResult,
    all_chunks: list[ChunkResult],
) -> ChunkResult | None:
    """查找子块对应的父块。

    Args:
        child: 子块
        all_chunks: 所有块列表

    Returns:
        父块或 None
    """
    # 通过 parent_chunk_id 查找
    if child.parent_chunk_id:
        for chunk in all_chunks:
            if chunk.chunk_id == child.parent_chunk_id:
                return chunk

    # 通过 section 查找
    if child.section:
        for chunk in all_chunks:
            if (chunk.section == child.section and
                chunk.chunk_id != child.chunk_id and
                not chunk.parent_chunk_id):
                return chunk

    return None


def expand_adjacent_chunks(
    target: ChunkResult,
    all_chunks: list[ChunkResult],
    window: int = 1,
) -> list[ChunkResult]:
    """扩展相邻块。

    Args:
        target: 目标块
        all_chunks: 所有块列表
        window: 扩展窗口大小

    Returns:
        扩展后的块列表
    """
    if window <= 0:
        return [target]

    # 按 chunk_index 排序
    sorted_chunks = sorted(all_chunks, key=lambda c: c.chunk_index)

    # 找到目标块的位置
    target_idx = None
    for i, chunk in enumerate(sorted_chunks):
        if chunk.chunk_id == target.chunk_id:
            target_idx = i
            break

    if target_idx is None:
        return [target]

    # 扩展窗口
    start = max(0, target_idx - window)
    end = min(len(sorted_chunks), target_idx + window + 1)

    return sorted_chunks[start:end]


def pack_context_relevance_first(
    chunks: list[ChunkResult],
    max_tokens: int,
) -> PackedContext:
    """按相关性优先打包上下文。

    Args:
        chunks: 候选块列表（已按相关性排序）
        max_tokens: 最大 token 数

    Returns:
        打包后的上下文
    """
    selected: list[ChunkResult] = []
    used_tokens = 0
    truncation_log: list[dict[str, Any]] = []

    for chunk in chunks:
        chunk_tokens = _estimate_tokens(chunk.content)
        if used_tokens + chunk_tokens > max_tokens:
            truncation_log.append({
                "chunkId": chunk.chunk_id,
                "reason": "tokenBudgetExceeded",
                "chunkTokens": chunk_tokens,
                "usedTokens": used_tokens,
                "maxTokens": max_tokens,
            })
            continue
        selected.append(chunk)
        used_tokens += chunk_tokens

    return PackedContext(
        chunks=selected,
        total_tokens=used_tokens,
        packing_strategy=PackingStrategy.RELEVANCE_FIRST.value,
        truncation_log=truncation_log,
    )


def pack_context_document_order(
    chunks: list[ChunkResult],
    max_tokens: int,
) -> PackedContext:
    """按文档顺序打包上下文。

    Args:
        chunks: 候选块列表
        max_tokens: 最大 token 数

    Returns:
        打包后的上下文
    """
    # 按 chunk_index 排序
    sorted_chunks = sorted(chunks, key=lambda c: c.chunk_index)

    selected: list[ChunkResult] = []
    used_tokens = 0
    truncation_log: list[dict[str, Any]] = []

    for chunk in sorted_chunks:
        chunk_tokens = _estimate_tokens(chunk.content)
        if used_tokens + chunk_tokens > max_tokens:
            truncation_log.append({
                "chunkId": chunk.chunk_id,
                "reason": "tokenBudgetExceeded",
                "chunkTokens": chunk_tokens,
                "usedTokens": used_tokens,
                "maxTokens": max_tokens,
            })
            continue
        selected.append(chunk)
        used_tokens += chunk_tokens

    return PackedContext(
        chunks=selected,
        total_tokens=used_tokens,
        packing_strategy=PackingStrategy.DOCUMENT_ORDER.value,
        truncation_log=truncation_log,
    )


def pack_context_section_grouped(
    chunks: list[ChunkResult],
    max_tokens: int,
) -> PackedContext:
    """按章节分组打包上下文。

    Args:
        chunks: 候选块列表
        max_tokens: 最大 token 数

    Returns:
        打包后的上下文
    """
    # 按章节分组
    sections: dict[str, list[ChunkResult]] = {}
    for chunk in chunks:
        section = chunk.section or "default"
        if section not in sections:
            sections[section] = []
        sections[section].append(chunk)

    selected: list[ChunkResult] = []
    used_tokens = 0
    truncation_log: list[dict[str, Any]] = []

    # 按章节顺序打包
    for section, section_chunks in sections.items():
        # 章节内按 chunk_index 排序
        section_chunks.sort(key=lambda c: c.chunk_index)

        for chunk in section_chunks:
            chunk_tokens = _estimate_tokens(chunk.content)
            if used_tokens + chunk_tokens > max_tokens:
                truncation_log.append({
                    "chunkId": chunk.chunk_id,
                    "reason": "tokenBudgetExceeded",
                    "section": section,
                    "chunkTokens": chunk_tokens,
                    "usedTokens": used_tokens,
                    "maxTokens": max_tokens,
                })
                continue
            selected.append(chunk)
            used_tokens += chunk_tokens

    return PackedContext(
        chunks=selected,
        total_tokens=used_tokens,
        packing_strategy=PackingStrategy.SECTION_GROUPED.value,
        truncation_log=truncation_log,
    )


def pack_context_with_parent_child(
    child_chunks: list[ChunkResult],
    all_chunks: list[ChunkResult],
    max_tokens: int,
    packing_strategy: str = PackingStrategy.RELEVANCE_FIRST.value,
    chunk_window: int = 0,
) -> PackedContext:
    """使用父子检索模式打包上下文。

    Args:
        child_chunks: 命中的子块列表
        all_chunks: 所有块列表
        max_tokens: 最大 token 数
        packing_strategy: 打包策略
        chunk_window: 相邻块扩展窗口

    Returns:
        打包后的上下文
    """
    # 1. 为每个子块找到父块和相邻块
    expanded_chunks: list[ChunkResult] = []
    seen_ids: set[str] = set()

    for child in child_chunks:
        # 添加子块
        if child.chunk_id not in seen_ids:
            expanded_chunks.append(child)
            seen_ids.add(child.chunk_id)

        # 查找父块
        parent = find_parent_chunk(child, all_chunks)
        if parent and parent.chunk_id not in seen_ids:
            expanded_chunks.append(parent)
            seen_ids.add(parent.chunk_id)

        # 扩展相邻块
        if chunk_window > 0:
            adjacent = expand_adjacent_chunks(child, all_chunks, chunk_window)
            for chunk in adjacent:
                if chunk.chunk_id not in seen_ids:
                    expanded_chunks.append(chunk)
                    seen_ids.add(chunk.chunk_id)

    # 2. 根据策略打包
    try:
        strategy = PackingStrategy(packing_strategy)
    except ValueError:
        strategy = PackingStrategy.RELEVANCE_FIRST

    if strategy == PackingStrategy.DOCUMENT_ORDER:
        return pack_context_document_order(expanded_chunks, max_tokens)
    elif strategy == PackingStrategy.SECTION_GROUPED:
        return pack_context_section_grouped(expanded_chunks, max_tokens)
    else:
        return pack_context_relevance_first(expanded_chunks, max_tokens)


def get_packing_strategies() -> list[dict[str, Any]]:
    """获取可用的打包策略。"""
    return [
        {
            "name": "relevance_first",
            "label": "相关性优先",
            "description": "按相关性分数排序，优先保留高相关性块",
        },
        {
            "name": "document_order",
            "label": "文档顺序",
            "description": "按文档原始顺序打包，保留上下文连贯性",
        },
        {
            "name": "section_grouped",
            "label": "章节分组",
            "description": "按章节分组打包，保留章节结构",
        },
    ]
