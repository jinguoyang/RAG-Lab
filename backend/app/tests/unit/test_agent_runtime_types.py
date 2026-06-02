"""Agent Runtime 共享类型测试。"""

from app.services.agent_runtime.types import RuntimeTraceContext


def test_runtime_trace_context_creation():
    trace = RuntimeTraceContext(
        agent_invocation_id="inv-001",
        thread_id="thread-001",
        scenario_type="employee_training",
        runtime_version="langgraph_primary_v1",
    )
    assert trace.agent_invocation_id == "inv-001"
    assert trace.thread_id == "thread-001"
    assert trace.scenario_type == "employee_training"


def test_runtime_trace_context_defaults():
    trace = RuntimeTraceContext(agent_invocation_id="inv-001", thread_id="t1")
    assert trace.scenario_type == ""
    assert trace.runtime_version == ""
    assert trace.checkpoint_id == ""
    assert trace.qa_run_id == ""
    assert trace.skill_call_id == ""
    assert trace.model_call_id == ""
    assert trace.summary_version == 0


def test_runtime_trace_context_to_dict():
    trace = RuntimeTraceContext(
        agent_invocation_id="inv-001",
        thread_id="t1",
        scenario_type="qa",
        qa_run_id="run-42",
    )
    d = trace.to_dict()
    assert d["agentInvocationId"] == "inv-001"
    assert d["threadId"] == "t1"
    assert d["scenarioType"] == "qa"
    assert d["qaRunId"] == "run-42"
    assert d["skillCallId"] == ""


def test_runtime_trace_context_mutable_fields():
    """Trace 上下文字段在 Graph 执行后可被更新。"""
    trace = RuntimeTraceContext(agent_invocation_id="inv-001", thread_id="t1")
    trace.qa_run_id = "run-99"
    trace.skill_call_id = "skill-99"
    assert trace.to_dict()["qaRunId"] == "run-99"
    assert trace.to_dict()["skillCallId"] == "skill-99"
