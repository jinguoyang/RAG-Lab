"""内部客服 LangGraph 编排。"""
from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph


NO_EVIDENCE_ANSWER = "当前知识库中没有足够依据回答该问题，请联系人工渠道。"


class InternalCustomerServiceState(TypedDict, total=False):
    """内部客服运行态，不依赖课堂领域对象。"""

    conversationId: str
    query: str
    answer: str
    qaRunId: str
    citations: list[dict[str, Any]]
    usage: dict[str, Any]
    skillCallId: str
    modelCallId: str
    modelStatus: str
    summaryVersion: int
    summaryStatus: str
    toolInvocationMode: str


def build_internal_customer_service_graph(*, checkpointer, invoke_rag_agent):
    """构建内部客服 Graph，回答必须具有授权 Citation。

    Parameters
    ----------
    checkpointer:
        LangGraph Checkpointer 实例（InMemorySaver 或 PostgresSaver）。
    invoke_rag_agent:
        ``(query: str) -> dict`` 回调，返回 ``{"answer", "runId", "citations"}``。
    """
    builder = StateGraph(InternalCustomerServiceState)

    def query_knowledge_base(state: InternalCustomerServiceState) -> InternalCustomerServiceState:
        result = invoke_rag_agent(state["query"])
        citations = result.get("citations") or []
        return {
            "answer": result["answer"] if citations else NO_EVIDENCE_ANSWER,
            "qaRunId": result.get("runId", ""),
            "citations": citations,
            "usage": result.get("usage", {}),
            "skillCallId": result.get("skillCallId", ""),
            "modelCallId": result.get("modelCallId", ""),
            "modelStatus": result.get("modelStatus", "success"),
            "summaryVersion": result.get("summaryVersion", 0),
            "summaryStatus": result.get("summaryStatus", "not_triggered"),
            "toolInvocationMode": result.get("toolInvocationMode", ""),
        }

    builder.add_node("query_knowledge_base", query_knowledge_base)
    builder.add_edge(START, "query_knowledge_base")
    builder.add_edge("query_knowledge_base", END)
    return builder.compile(checkpointer=checkpointer)
