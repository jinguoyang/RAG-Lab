"""将现有 App Runtime/QARun 封装为 LangChain Tool。

副作用边界（spec 9.1）：

只读语义：
- 本 Tool 对知识库内容只读，不直接写入 Milvus、OpenSearch、Neo4j 或未裁剪 Chunk。
- 检索、权限裁剪、Evidence 和 Citation 生成均由现有 QARun Pipeline 完成。

允许的副作用（业务写入）：
- 通过 App Runtime 写入 Conversation、Message、Invocation 和 QARun 记录。
- 这些写入是受控审计记录，用于会话历史、调用审计和反馈回流。
- Tool 返回的 runId 可关联到 QARun 详情页。

重放幂等约束：
- 同一 agentInvocationId 重复调用时，直接返回缓存结果，不重复创建 QARun。
- 幂等键由调用方（Graph / Facade）生成并传入。
"""
from __future__ import annotations

import hashlib
import json
import logging
from time import perf_counter
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.schemas.app_runtime import AppRuntimeChatRequest
from app.services.app_runtime_service import chat_with_app_runtime

logger = logging.getLogger(__name__)


class QARunToolInput(BaseModel):
    """知识库问答 Tool 输入。"""

    query: str = Field(min_length=1, max_length=4000, description="用户查询文本")


def create_bound_qa_run_tool(
    *,
    invoke_qa_run,
    record_skill_call=None,
    idempotency_store: dict[str, dict] | None = None,
):
    """将已授权 QARun 回调封装为 LangChain Tool。

    Parameters
    ----------
    invoke_qa_run:
        ``(query: str) -> dict`` 回调，返回 ``{"runId", "answer", "citations", ...}``。
    record_skill_call:
        可选审计回调。
    idempotency_store:
        可选幂等缓存 ``{idempotency_key: result_dict}``。
        由调用方（Graph / Facade）管理生命周期，同一 agentInvocationId 复用。
    """

    def query_knowledge_base(query: str) -> dict:
        # 幂等检查
        if idempotency_store is not None:
            cache_key = _build_idempotency_key(query)
            cached = idempotency_store.get(cache_key)
            if cached is not None:
                logger.debug("QARun Tool 幂等命中: %s", cache_key[:16])
                return cached

        started_counter = perf_counter()
        try:
            result = dict(invoke_qa_run(query))
        except Exception as exc:
            if record_skill_call is not None:
                record_skill_call(
                    status="failed",
                    input_summary=json.dumps({"query": query}, ensure_ascii=False),
                    output_summary=None,
                    error_code=type(exc).__name__,
                    latency_ms=round((perf_counter() - started_counter) * 1000),
                )
            raise

        if record_skill_call is not None:
            skill_call_id = record_skill_call(
                status="success",
                input_summary=json.dumps({"query": query}, ensure_ascii=False),
                output_summary=json.dumps(
                    {
                        "runId": result.get("runId"),
                        "citationCount": len(result.get("citations") or []),
                    },
                    ensure_ascii=False,
                ),
                error_code=None,
                latency_ms=round((perf_counter() - started_counter) * 1000),
            )
            result["skillCallId"] = str(skill_call_id)

        # 写入幂等缓存
        if idempotency_store is not None:
            cache_key = _build_idempotency_key(query)
            idempotency_store[cache_key] = result

        return result

    return StructuredTool.from_function(
        func=query_knowledge_base,
        name="query_knowledge_base",
        description=(
            "查询当前应用绑定知识库，返回授权回答和引用。"
            "对知识库内容只读；允许的副作用仅为写入会话和调用审计记录。"
        ),
        args_schema=QARunToolInput,
    )


def create_qa_run_tool(
    *,
    session,
    credential: str,
    end_user_id: str | None,
    idempotency_store: dict[str, dict] | None = None,
):
    """创建 QARun Tool，封装 chat_with_app_runtime 调用。"""

    def query_knowledge_base(query: str) -> dict:
        response = chat_with_app_runtime(
            session,
            credential,
            AppRuntimeChatRequest(query=query, endUserId=end_user_id),
        )
        return {
            "runId": response.runId,
            "answer": response.answer,
            "citations": [
                {
                    "citationId": item.citationId,
                    "evidenceId": item.evidenceId,
                    "label": item.label,
                    "chunkId": item.locationSnapshot.get("chunkId"),
                }
                for item in response.citations
            ],
            "usage": response.usage,
        }

    return create_bound_qa_run_tool(
        invoke_qa_run=query_knowledge_base,
        idempotency_store=idempotency_store,
    )


def _build_idempotency_key(query: str) -> str:
    """基于查询文本构建幂等键。"""
    return hashlib.sha256(query.encode()).hexdigest()[:32]
