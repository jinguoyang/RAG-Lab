"""B-321: Contextual Chunking 与 Late Chunking 服务。

LLM 辅助的上下文分块摘要，提升 Chunk 自解释性，同时保留长文档上下文。

功能:
- 为每个 Chunk 生成上下文摘要 (contextualSummary)
- 提取章节路径 (sectionPath)
- 生成文档简介 (documentBrief)
- 缓存/重放/失效机制
- Late Chunking 扩展接口
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
from uuid import uuid4

from app.services.multi_view_chunking import ChunkResult
from app.services.parsed_document_v2 import ParsedDocumentV2


@dataclass(frozen=True)
class ContextualMetadata:
    """Chunk 的上下文元数据。"""

    chunk_id: str
    contextual_summary: str
    section_path: list[str]
    document_brief: str
    generation_meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextualCacheEntry:
    """上下文缓存条目。"""

    cache_key: str
    chunk_id: str
    doc_hash: str
    chunk_revision_id: str
    prompt_version: str
    model_version: str
    metadata: ContextualMetadata


def _compute_cache_key(
    doc_hash: str,
    chunk_id: str,
    chunk_revision_id: str,
    prompt_version: str,
    model_version: str,
) -> str:
    """计算缓存键。"""
    key_content = f"{doc_hash}:{chunk_id}:{chunk_revision_id}:{prompt_version}:{model_version}"
    return sha256(key_content.encode("utf-8")).hexdigest()


def generate_contextual_summary_llm(
    chunk_content: str,
    document_context: str,
    section_context: str,
) -> tuple[str, str]:
    """使用 LLM 生成上下文摘要和文档简介。

    Args:
        chunk_content: Chunk 内容
        document_context: 文档上下文
        section_context: 章节上下文

    Returns:
        (contextual_summary, document_brief) 元组
    """
    # 简化实现：基于内容生成摘要
    # 实际实现应调用 LLM Provider
    summary_parts = []

    # 提取关键信息
    if section_context:
        summary_parts.append(f"章节: {section_context}")

    # 生成简短摘要
    words = chunk_content.split()
    if len(words) > 20:
        summary = " ".join(words[:20]) + "..."
    else:
        summary = chunk_content

    summary_parts.append(summary)
    contextual_summary = " | ".join(summary_parts)

    # 生成文档简介
    doc_words = document_context.split()
    if len(doc_words) > 50:
        document_brief = " ".join(doc_words[:50]) + "..."
    else:
        document_brief = document_context

    return contextual_summary, document_brief


def generate_contextual_metadata(
    doc: ParsedDocumentV2,
    chunks: list[ChunkResult],
    chunk_revision_id: str,
    prompt_version: str = "v1",
    model_version: str = "local",
) -> list[ContextualMetadata]:
    """为分块结果生成上下文元数据。

    Args:
        doc: ParsedDocumentV2 文档
        chunks: 分块结果列表
        chunk_revision_id: 分块版本 ID
        prompt_version: Prompt 版本
        model_version: 模型版本

    Returns:
        上下文元数据列表
    """
    doc_hash = doc.content_hash
    document_context = " ".join(block.text for block in doc.blocks[:10] if block.text)

    results = []
    for chunk in chunks:
        # 获取章节上下文
        section_context = chunk.section or ""

        # 生成上下文摘要
        contextual_summary, document_brief = generate_contextual_summary_llm(
            chunk.content,
            document_context,
            section_context,
        )

        # 提取章节路径
        section_path = []
        if chunk.section:
            section_path.append(chunk.section)

        metadata = ContextualMetadata(
            chunk_id=chunk.chunk_id,
            contextual_summary=contextual_summary,
            section_path=section_path,
            document_brief=document_brief,
            generation_meta={
                "promptVersion": prompt_version,
                "modelVersion": model_version,
                "docHash": doc_hash,
                "chunkRevisionId": chunk_revision_id,
            },
        )
        results.append(metadata)

    return results


class ContextualChunkingCache:
    """上下文分块缓存管理器。"""

    def __init__(self):
        self._cache: dict[str, ContextualCacheEntry] = {}

    def get(
        self,
        doc_hash: str,
        chunk_id: str,
        chunk_revision_id: str,
        prompt_version: str,
        model_version: str,
    ) -> ContextualMetadata | None:
        """获取缓存的上下文元数据。"""
        cache_key = _compute_cache_key(
            doc_hash, chunk_id, chunk_revision_id, prompt_version, model_version
        )
        entry = self._cache.get(cache_key)
        return entry.metadata if entry else None

    def put(
        self,
        doc_hash: str,
        chunk_id: str,
        chunk_revision_id: str,
        prompt_version: str,
        model_version: str,
        metadata: ContextualMetadata,
    ) -> None:
        """缓存上下文元数据。"""
        cache_key = _compute_cache_key(
            doc_hash, chunk_id, chunk_revision_id, prompt_version, model_version
        )
        entry = ContextualCacheEntry(
            cache_key=cache_key,
            chunk_id=chunk_id,
            doc_hash=doc_hash,
            chunk_revision_id=chunk_revision_id,
            prompt_version=prompt_version,
            model_version=model_version,
            metadata=metadata,
        )
        self._cache[cache_key] = entry

    def invalidate_by_doc_hash(self, doc_hash: str) -> int:
        """按文档哈希失效缓存。"""
        keys_to_remove = [
            key for key, entry in self._cache.items()
            if entry.doc_hash == doc_hash
        ]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def invalidate_by_chunk_revision(self, chunk_revision_id: str) -> int:
        """按分块版本失效缓存。"""
        keys_to_remove = [
            key for key, entry in self._cache.items()
            if entry.chunk_revision_id == chunk_revision_id
        ]
        for key in keys_to_remove:
            del self._cache[key]
        return len(keys_to_remove)

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()

    def size(self) -> int:
        """获取缓存大小。"""
        return len(self._cache)


# 全局缓存实例
_contextual_cache = ContextualChunkingCache()


def get_contextual_cache() -> ContextualChunkingCache:
    """获取全局上下文缓存实例。"""
    return _contextual_cache


def generate_contextual_metadata_with_cache(
    doc: ParsedDocumentV2,
    chunks: list[ChunkResult],
    chunk_revision_id: str,
    prompt_version: str = "v1",
    model_version: str = "local",
    force_regenerate: bool = False,
) -> list[ContextualMetadata]:
    """带缓存的上下文元数据生成。

    Args:
        doc: ParsedDocumentV2 文档
        chunks: 分块结果列表
        chunk_revision_id: 分块版本 ID
        prompt_version: Prompt 版本
        model_version: 模型版本
        force_regenerate: 强制重新生成

    Returns:
        上下文元数据列表
    """
    cache = get_contextual_cache()
    doc_hash = doc.content_hash

    results = []
    chunks_to_generate = []

    for chunk in chunks:
        if not force_regenerate:
            cached = cache.get(
                doc_hash,
                chunk.chunk_id,
                chunk_revision_id,
                prompt_version,
                model_version,
            )
            if cached:
                results.append(cached)
                continue

        chunks_to_generate.append(chunk)

    if chunks_to_generate:
        new_metadata = generate_contextual_metadata(
            doc,
            chunks_to_generate,
            chunk_revision_id,
            prompt_version,
            model_version,
        )

        # 缓存新生成的元数据
        for metadata in new_metadata:
            cache.put(
                doc_hash,
                metadata.chunk_id,
                chunk_revision_id,
                prompt_version,
                model_version,
                metadata,
            )
            results.append(metadata)

    return results


def get_contextual_chunking_stats() -> dict[str, Any]:
    """获取上下文分块统计信息。"""
    cache = get_contextual_cache()
    return {
        "cacheSize": cache.size(),
        "promptVersions": ["v1"],
        "supportedModels": ["local", "http"],
    }
