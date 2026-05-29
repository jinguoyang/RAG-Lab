"""培训模块统一 LLM 调用客户端。

集中管理 OpenAI-compatible 接口的 HTTP 调用逻辑，避免各服务重复实现。
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMCallError(Exception):
    """LLM 调用失败。"""


def call_llm(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    timeout: float = 60,
) -> str:
    """调用 OpenAI-compatible LLM 接口，返回 assistant 消息文本。

    Args:
        messages: chat messages 列表。
        temperature: 生成温度。
        max_tokens: 最大生成 token 数，None 时不限制。
        timeout: HTTP 超时秒数。

    Returns:
        assistant 消息文本。

    Raises:
        LLMCallError: LLM endpoint 未配置、HTTP 请求失败或响应格式无效。
    """
    settings = get_settings()
    if not settings.llm_endpoint:
        raise LLMCallError("LLM endpoint 未配置。")

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    request_json: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        request_json["max_tokens"] = max_tokens

    try:
        response = httpx.post(
            settings.llm_endpoint,
            headers=headers,
            json=request_json,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"])
    except httpx.HTTPStatusError as exc:
        raise LLMCallError(f"LLM HTTP 错误: {exc.response.status_code}") from exc
    except (httpx.RequestError, KeyError, IndexError, TypeError) as exc:
        raise LLMCallError(f"LLM 调用失败: {exc}") from exc
