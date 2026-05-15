"""Langfuse 可观测性客户端单例，根据 LANGFUSE_ENABLED 配置决定启用或降级为 no-op。"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langfuse import Langfuse


class _NoOpLangfuse:
    """禁用时的零开销占位，所有方法静默返回 None。"""

    def trace(self, *args, **kwargs):  # noqa: ANN002
        return self

    def generation(self, *args, **kwargs):  # noqa: ANN002
        return self

    def span(self, *args, **kwargs):  # noqa: ANN002
        return self

    def update(self, *args, **kwargs):  # noqa: ANN002
        return self

    def flush(self) -> None:
        return None


_noop = _NoOpLangfuse()


@lru_cache
def get_langfuse() -> Langfuse | _NoOpLangfuse:
    """返回 Langfuse 客户端单例；未启用时返回 no-op 占位。"""
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.langfuse_enabled:
        return _noop
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return _noop
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return client
    except Exception:
        return _noop
