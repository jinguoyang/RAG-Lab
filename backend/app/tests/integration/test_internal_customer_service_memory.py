"""内部客服 Checkpoint 和摘要记忆集成测试。"""
from unittest.mock import Mock, patch

from langgraph.checkpoint.memory import InMemorySaver

from app.services.agent_runtime.graphs.internal_customer_service_graph import (
    NO_EVIDENCE_ANSWER,
    build_internal_customer_service_graph,
)


def _make_graph(invoke_rag_agent=None, checkpointer=None):
    """创建可复用的测试 Graph。"""
    if invoke_rag_agent is None:
        invoke_rag_agent = Mock(
            return_value={
                "answer": "标准回答",
                "runId": "run-mem-001",
                "citations": [{"citationId": "c1", "evidenceId": "e1", "label": "来源", "chunkId": "chunk-1"}],
            }
        )
    if checkpointer is None:
        checkpointer = InMemorySaver()
    return build_internal_customer_service_graph(
        checkpointer=checkpointer,
        invoke_rag_agent=invoke_rag_agent,
    )


def test_customer_service_resume_uses_same_thread():
    """连续追问应恢复同一 thread 的 Checkpoint。"""
    call_count = 0

    def mock_invoke(query):
        nonlocal call_count
        call_count += 1
        return {
            "answer": f"回答{call_count}",
            "runId": f"run-{call_count}",
            "citations": [{"citationId": "c1", "evidenceId": "e1", "label": "来源", "chunkId": "chunk-1"}],
        }

    checkpointer = InMemorySaver()
    graph = _make_graph(invoke_rag_agent=mock_invoke, checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "conv-mem-1"}}

    first = graph.invoke({"conversationId": "conv-mem-1", "query": "第一个问题"}, config)
    second = graph.invoke({"conversationId": "conv-mem-1", "query": "追问"}, config)

    # 两次都应成功回答
    assert first["answer"] == "回答1"
    assert second["answer"] == "回答2"
    # 两次独立调用 RAG Agent
    assert call_count == 2
    # thread_id 保持一致
    state = graph.get_state(config)
    assert state.values["conversationId"] == "conv-mem-1"


def test_customer_service_checkpoint_preserves_citations():
    """Checkpoint 应保留 citations 信息。"""
    graph = _make_graph()
    config = {"configurable": {"thread_id": "conv-mem-2"}}

    graph.invoke({"conversationId": "conv-mem-2", "query": "问题"}, config)
    state = graph.get_state(config)

    assert len(state.values["citations"]) == 1
    assert state.values["citations"][0]["chunkId"] == "chunk-1"


def test_customer_service_different_threads_isolated():
    """不同 thread 的 Checkpoint 应互相隔离。"""
    invoke_rag_agent = Mock(
        return_value={
            "answer": "回答",
            "runId": "run-iso",
            "citations": [{"citationId": "c1", "evidenceId": "e1", "label": "来源", "chunkId": "chunk-1"}],
        }
    )
    checkpointer = InMemorySaver()
    graph = _make_graph(invoke_rag_agent=invoke_rag_agent, checkpointer=checkpointer)

    graph.invoke({"conversationId": "conv-a", "query": "A的问题"}, {"configurable": {"thread_id": "conv-a"}})
    graph.invoke({"conversationId": "conv-b", "query": "B的问题"}, {"configurable": {"thread_id": "conv-b"}})

    state_a = graph.get_state({"configurable": {"thread_id": "conv-a"}})
    state_b = graph.get_state({"configurable": {"thread_id": "conv-b"}})

    assert state_a.values["query"] == "A的问题"
    assert state_b.values["query"] == "B的问题"
