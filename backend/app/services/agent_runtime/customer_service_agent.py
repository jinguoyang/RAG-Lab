"""内部客服 LangChain Agent 调用适配器。"""
from __future__ import annotations

from uuid import uuid4

from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langchain_core.messages import AIMessage


def _read_final_answer(messages: list) -> str:
    """读取最后一条不包含 Tool 调用的模型回答。"""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return message.text
    return ""


def _count_summary_versions(messages: list) -> int:
    """统计当前上下文中的官方摘要消息数量。"""
    return sum(
        1
        for message in messages
        if getattr(message, "additional_kwargs", {}).get("lc_source") == "summarization"
    )


def _read_summary_status(messages: list) -> str:
    """区分未触发、成功摘要和官方中间件降级错误。"""
    summaries = [
        message
        for message in messages
        if getattr(message, "additional_kwargs", {}).get("lc_source") == "summarization"
    ]
    if not summaries:
        return "not_triggered"
    if any("Error generating summary:" in str(message.content) for message in summaries):
        return "failed"
    return "success"


def ensure_customer_service_tool_result(*, qa_run_tool, query: str, agent_answer: str, tool_result: dict) -> str:
    """模型跳过 Tool 时，使用同一个只读 Tool 补做授权检索。"""
    if tool_result:
        return "agent"
    validation_query = f"{query}\n回答草稿：{agent_answer}" if agent_answer else query
    tool_result.update(dict(qa_run_tool.invoke({"query": validation_query})))
    return "guard"


def invoke_customer_service_agent(*, rag_agent, conversation_id: str, query: str) -> dict:
    """调用客服 RAG Agent，并返回模型调用与官方摘要关联信息。"""
    config = {"configurable": {"thread_id": f"{conversation_id}:rag-agent"}}
    model_status = "success"
    try:
        result = rag_agent.invoke(
            {"messages": [{"role": "user", "content": query}]},
            config=config,
        )
    except ToolCallLimitExceededError:
        # Provider 重复调用 Tool 时保留硬限额，外层使用最后一次授权 QARun 结果收敛。
        result = rag_agent.get_state(config).values
        model_status = "tool_limit_reached"
    messages = list(result.get("messages") or [])
    return {
        "answer": _read_final_answer(messages) if model_status == "success" else "",
        "modelCallId": str(uuid4()),
        "modelStatus": model_status,
        "summaryVersion": _count_summary_versions(messages),
        "summaryStatus": _read_summary_status(messages),
    }
