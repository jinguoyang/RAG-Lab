"""PDF 预览磁盘缓存，带 LRU 淘汰和容量上限兜底。"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _cache_dir() -> Path:
    d = Path(get_settings().pdf_preview_cache_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _max_bytes() -> int:
    return get_settings().pdf_preview_cache_max_bytes


def _cache_key(document_id: UUID, version_id: UUID) -> str:
    return f"{document_id}_{version_id}.pdf"


# ------------------------------------------------------------------


def get(document_id: UUID, version_id: UUID) -> bytes | None:
    """命中缓存返回 PDF bytes，未命中返回 None。"""
    path = _cache_dir() / _cache_key(document_id, version_id)
    if not path.exists():
        return None
    try:
        data = path.read_bytes()
        # 更新 atime（touch），供 LRU 淘汰排序
        path.touch(exist_ok=True)
        logger.debug("pdf_preview_cache hit: %s", path.name)
        return data
    except OSError:
        return None


def put(document_id: UUID, version_id: UUID, pdf_bytes: bytes) -> None:
    """写入缓存并触发淘汰。"""
    path = _cache_dir() / _cache_key(document_id, version_id)
    with _lock:
        try:
            path.write_bytes(pdf_bytes)
        except OSError:
            logger.warning("pdf_preview_cache write failed: %s", path, exc_info=True)
            return
        _evict()


# ------------------------------------------------------------------


def _evict() -> None:
    """按 atime 升序删除最旧文件，直到总大小 ≤ 上限。"""
    cache_dir = _cache_dir()
    max_bytes = _max_bytes()

    files = sorted(cache_dir.iterdir(), key=lambda f: f.stat().st_atime)
    total = sum(f.stat().st_size for f in files if f.is_file())

    while total > max_bytes and files:
        oldest = files.pop(0)
        if oldest.is_file():
            size = oldest.stat().st_size
            try:
                oldest.unlink()
                total -= size
                logger.info("pdf_preview_cache evicted: %s (%d bytes)", oldest.name, size)
            except OSError:
                pass
