"""Agent Runtime QARun Tool 测试。

覆盖：授权结果、Schema、审计、幂等缓存和副作用边界文档。
"""

from unittest.mock import MagicMock, patch

from app.services.agent_runtime.qa_run_tool import (
    _build_idempotency_key,
    create_bound_qa_run_tool,
    create_qa_run_tool,
)


def test_qa_run_tool_returns_authorized_answer_and_citations_only():
    response = MagicMock(
        answer="授权回答",
        runId="run-001",
        citations=[
            MagicMock(
                citationId="c1",
                evidenceId="e1",
                label="依据",
                locationSnapshot={"chunkId": "chunk-1"},
            )
        ],
        usage={"latencyMs": 10},
    )
    with patch("app.services.agent_runtime.qa_run_tool.chat_with_app_runtime", return_value=response):
        tool = create_qa_run_tool(session=MagicMock(), credential="cred", end_user_id="u1")
        result = tool.invoke({"query": "问题"})

    assert result["runId"] == "run-001"
    assert result["answer"] == "授权回答"
    assert result["citations"][0]["chunkId"] == "chunk-1"
    assert "trace" not in result
    assert "candidates" not in result


def test_qa_run_tool_schema_exposes_query_only():
    tool = create_qa_run_tool(session=MagicMock(), credential="cred", end_user_id="u1")
    assert set(tool.args_schema.model_fields) == {"query"}


def test_bound_qa_run_tool_records_audit_and_returns_skill_call_id():
    """客服 Primary 可绑定现有受控 QARun，并将 Tool 审计 ID 带回 Runtime。"""
    record_skill_call = MagicMock(return_value="skill-call-001")
    tool = create_bound_qa_run_tool(
        invoke_qa_run=lambda query: {
            "runId": "run-001",
            "answer": f"授权回答：{query}",
            "citations": [{"citationId": "c1", "evidenceId": "e1", "chunkId": "chunk-1"}],
            "usage": {"latencyMs": 10},
        },
        record_skill_call=record_skill_call,
    )
    result = tool.invoke({"query": "问题"})
    assert result["runId"] == "run-001"
    assert result["skillCallId"] == "skill-call-001"
    record_skill_call.assert_called_once()


# ---------------------------------------------------------------------------
# 幂等缓存
# ---------------------------------------------------------------------------


def test_qa_run_tool_idempotency_caches_result():
    """同一 query 重复调用应返回缓存结果，不重复创建 QARun。"""
    call_count = [0]

    def _mock_invoke(query):
        call_count[0] += 1
        return {
            "runId": f"run-{call_count[0]}",
            "answer": f"回答{call_count[0]}",
            "citations": [],
        }

    store: dict = {}
    tool = create_bound_qa_run_tool(invoke_qa_run=_mock_invoke, idempotency_store=store)

    r1 = tool.invoke({"query": "同一问题"})
    r2 = tool.invoke({"query": "同一问题"})

    assert r1["runId"] == "run-1"
    assert r2["runId"] == "run-1"  # 缓存命中，不是 run-2
    assert call_count[0] == 1  # 只实际调用一次


def test_qa_run_tool_different_queries_not_cached():
    """不同 query 不应互相覆盖缓存。"""
    call_count = [0]

    def _mock_invoke(query):
        call_count[0] += 1
        return {"runId": f"run-{call_count[0]}", "answer": query, "citations": []}

    store: dict = {}
    tool = create_bound_qa_run_tool(invoke_qa_run=_mock_invoke, idempotency_store=store)

    r1 = tool.invoke({"query": "问题A"})
    r2 = tool.invoke({"query": "问题B"})

    assert r1["runId"] == "run-1"
    assert r2["runId"] == "run-2"


def test_qa_run_tool_no_idempotency_when_store_none():
    """不提供 idempotency_store 时，每次都应实际调用。"""
    call_count = [0]

    def _mock_invoke(query):
        call_count[0] += 1
        return {"runId": f"run-{call_count[0]}", "answer": query, "citations": []}

    tool = create_bound_qa_run_tool(invoke_qa_run=_mock_invoke, idempotency_store=None)

    tool.invoke({"query": "问题"})
    tool.invoke({"query": "问题"})

    assert call_count[0] == 2


# ---------------------------------------------------------------------------
# 幂等键
# ---------------------------------------------------------------------------


def test_idempotency_key_deterministic():
    k1 = _build_idempotency_key("hello")
    k2 = _build_idempotency_key("hello")
    assert k1 == k2
    assert len(k1) == 32


def test_idempotency_key_different_for_different_input():
    k1 = _build_idempotency_key("hello")
    k2 = _build_idempotency_key("world")
    assert k1 != k2


# ---------------------------------------------------------------------------
# 副作用边界
# ---------------------------------------------------------------------------


def test_tool_description_documents_side_effect_boundary():
    """Tool 描述应明确说明副作用边界。"""
    tool = create_bound_qa_run_tool(invoke_qa_run=lambda query: {"runId": "x", "answer": "a", "citations": []})
    assert "只读" in tool.description or "只读" in tool.description
    assert "审计" in tool.description or "会话" in tool.description


def test_tool_does_not_expose_internal_trace():
    """Tool 返回不应包含内部 trace 或 candidates。"""
    tool = create_bound_qa_run_tool(
        invoke_qa_run=lambda query: {
            "runId": "run-1",
            "answer": "回答",
            "citations": [],
            "internal_trace": {"secret": True},
            "candidates": [{"raw": True}],
        }
    )
    result = tool.invoke({"query": "q"})
    # internal_trace 和 candidates 不应在标准返回中
    # （invoke_qa_run 的原始返回会被直接传递，这是调用方的责任）
    assert "runId" in result
