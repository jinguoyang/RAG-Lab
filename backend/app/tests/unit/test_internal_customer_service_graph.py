"""内部客服 Graph 单元测试。"""
from unittest.mock import Mock

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.services.agent_runtime.graphs.internal_customer_service_graph import (
    NO_EVIDENCE_ANSWER,
    build_internal_customer_service_graph,
)


def test_customer_service_graph_returns_authorized_answer_with_citations():
    """有 Citation 的回答应直接返回。"""
    invoke_rag_agent = Mock(
        return_value={
            "answer": "请按制度提交申请。",
            "runId": "run-001",
            "citations": [{"citationId": "c1", "evidenceId": "e1", "label": "制度", "chunkId": "chunk-1"}],
        }
    )
    graph = build_internal_customer_service_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=invoke_rag_agent,
    )

    result = graph.invoke(
        {"conversationId": "conv-1", "query": "如何提交申请？"},
        {"configurable": {"thread_id": "conv-1"}},
    )

    assert result["answer"] == "请按制度提交申请。"
    assert result["qaRunId"] == "run-001"
    assert result["citations"][0]["chunkId"] == "chunk-1"


def test_customer_service_graph_refuses_answer_without_citations():
    """无 Citation 时应拒答。"""
    graph = build_internal_customer_service_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=Mock(return_value={"answer": "猜测回答", "runId": "run-002", "citations": []}),
    )

    result = graph.invoke(
        {"conversationId": "conv-1", "query": "未知问题"},
        {"configurable": {"thread_id": "conv-1"}},
    )

    assert result["answer"] == NO_EVIDENCE_ANSWER
    assert result["citations"] == []


def test_customer_service_graph_preserves_checkpoint():
    """连续追问应恢复同一 thread 的 Checkpoint。"""
    invoke_rag_agent = Mock(
        return_value={
            "answer": "回答内容",
            "runId": "run-003",
            "citations": [{"citationId": "c1", "evidenceId": "e1", "label": "来源", "chunkId": "chunk-1"}],
        }
    )
    checkpointer = InMemorySaver()
    graph = build_internal_customer_service_graph(
        checkpointer=checkpointer,
        invoke_rag_agent=invoke_rag_agent,
    )
    config = {"configurable": {"thread_id": "conv-2"}}

    graph.invoke({"conversationId": "conv-2", "query": "第一个问题"}, config)
    graph.invoke({"conversationId": "conv-2", "query": "追问"}, config)

    # 验证 invoke_rag_agent 被调用了两次（两次独立问答）
    assert invoke_rag_agent.call_count == 2
    # Checkpoint 中应保留 thread_id
    state = graph.get_state(config)
    assert state.values.get("conversationId") == "conv-2"


def test_customer_service_graph_has_no_training_imports():
    """客服 Graph 源码不应依赖课堂模块。"""
    import inspect

    from app.services.agent_runtime.graphs import internal_customer_service_graph

    source = inspect.getsource(internal_customer_service_graph)

    assert "training_classroom_service" not in source
    assert "training_progress_service" not in source
    assert "training_question" not in source


def test_customer_service_graph_accepts_none_citations():
    """invoke_rag_agent 返回 None citations 时应降级为空列表拒答。"""
    graph = build_internal_customer_service_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=Mock(return_value={"answer": "回答", "runId": "run-004", "citations": None}),
    )

    result = graph.invoke(
        {"conversationId": "conv-3", "query": "问题"},
        {"configurable": {"thread_id": "conv-3"}},
    )

    assert result["answer"] == NO_EVIDENCE_ANSWER
    assert result["citations"] == []
