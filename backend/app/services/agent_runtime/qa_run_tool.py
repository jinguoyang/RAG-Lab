"""将现有 App Runtime/QARun 封装为只读 LangChain Tool。"""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.schemas.app_runtime import AppRuntimeChatRequest
from app.services.app_runtime_service import chat_with_app_runtime


class QARunToolInput(BaseModel):
    """只读知识库问答 Tool 输入。"""

    query: str = Field(min_length=1, max_length=4000)


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

    return StructuredTool.from_function(
        func=query_knowledge_base,
        name="query_knowledge_base",
        description="通过受控 QARun 查询当前应用绑定知识库，返回授权回答和引用。",
        args_schema=QARunToolInput,
    )
