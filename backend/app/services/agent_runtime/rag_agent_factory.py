"""可复用的 LangChain RAG Agent 工厂。"""
from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

from app.services.agent_runtime.memory_service import create_summary_middleware


def build_rag_answer_agent(
    *,
    model,
    qa_run_tool,
    checkpointer,
    trigger_tokens: int,
    keep_messages: int,
    system_prompt: str,
):
    """构建受控 RAG Agent，统一复用官方中间件和只读 QARun Tool。"""
    return create_agent(
        model=model,
        tools=[qa_run_tool],
        system_prompt=system_prompt,
        middleware=[
            create_summary_middleware(
                model=model,
                trigger_tokens=trigger_tokens,
                keep_messages=keep_messages,
            ),
            ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
            ToolCallLimitMiddleware(
                tool_name=qa_run_tool.name,
                run_limit=2,
                exit_behavior="error",
            ),
        ],
        checkpointer=checkpointer,
    )
