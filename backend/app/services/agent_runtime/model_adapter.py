"""LangChain ChatModel 适配器。"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from langchain_openai import ChatOpenAI
from pydantic import BaseModel


def _openai_base_url(endpoint: str) -> str:
    """将现有 Chat Completions endpoint 收敛为 OpenAI-compatible base_url。"""
    parts = urlsplit(endpoint.rstrip("/"))
    path = parts.path
    suffix = "/chat/completions"
    if path.endswith(suffix):
        path = path[: -len(suffix)]
    return urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"), "", ""))


def create_chat_model(settings):
    """使用现有 LLM 配置创建 LangChain ChatModel。"""
    if not settings.llm_endpoint:
        raise ValueError("LLM endpoint 未配置。")
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key or "not-set",
        base_url=_openai_base_url(settings.llm_endpoint),
        timeout=60,
        max_retries=2,
    )


class ProviderCapabilityReport(BaseModel):
    """真实 Provider 能力探测结果。"""

    chat: bool
    toolCalling: bool
    structuredOutput: bool
    summarization: bool
