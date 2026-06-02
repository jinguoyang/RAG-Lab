"""Agent Runtime Task 5: 只读 QARun Tool 测试。"""

from unittest.mock import MagicMock, patch

from app.services.agent_runtime.qa_run_tool import create_bound_qa_run_tool, create_qa_run_tool


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
