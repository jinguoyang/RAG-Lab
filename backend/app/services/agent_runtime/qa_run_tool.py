"""将现有 App Runtime/QARun 封装为只读 LangChain Tool。"""
from __future__ import annotations

import json
from time import perf_counter

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.schemas.app_runtime import AppRuntimeChatRequest
from app.services.app_runtime_service import chat_with_app_runtime


class QARunToolInput(BaseModel):
    """只读知识库问答 Tool 输入。"""

    query: str = Field(min_length=1, max_length=4000)


def create_bound_qa_run_tool(*, invoke_qa_run, record_skill_call=None):
    """将已授权 QARun 回调封装为只读 Tool，并可选记录 Skill 审计。"""

    def query_knowledge_base(query: str) -> dict:
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
        return result

    return StructuredTool.from_function(
        func=query_knowledge_base,
        name="query_knowledge_base",
        description="通过受控 QARun 查询当前应用绑定知识库，返回授权回答和引用。",
        args_schema=QARunToolInput,
    )


def create_qa_run_tool(*, session, credential: str, end_user_id: str | None):
    """创建仅返回授权结果的 QARun Tool。"""

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

    return create_bound_qa_run_tool(invoke_qa_run=query_knowledge_base)
