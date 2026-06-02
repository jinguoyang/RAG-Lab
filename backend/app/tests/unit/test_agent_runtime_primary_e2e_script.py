"""LangGraph Primary 真实 E2E 脚本单元测试。"""
import pytest

from scripts.verify_agent_runtime_primary_e2e import (
    _assert_trace_summary,
    _validate_test_database_urls,
)


TEST_DATABASE_URL = "postgresql+psycopg://tester:secret@127.0.0.1:5432/rag_lab_agent_runtime_test"


def test_validate_test_database_urls_requires_explicit_test_database():
    """真实 E2E 不允许隐式使用业务数据库。"""
    with pytest.raises(AssertionError, match="RAG_LAB_TEST_POSTGRES_URL"):
        _validate_test_database_urls(None, TEST_DATABASE_URL)


def test_validate_test_database_urls_requires_matching_checkpoint_database():
    """业务数据和 Checkpoint 必须落在同一个独立测试库。"""
    with pytest.raises(AssertionError, match="同一个独立测试数据库"):
        _validate_test_database_urls(
            TEST_DATABASE_URL,
            "postgresql+psycopg://tester:secret@127.0.0.1:5432/another_test",
        )


def test_validate_test_database_urls_rejects_non_test_database():
    """数据库名不带 _test 后缀时拒绝执行。"""
    with pytest.raises(AssertionError, match="_test"):
        _validate_test_database_urls(
            "postgresql+psycopg://tester:secret@127.0.0.1:5432/rag_lab",
            "postgresql+psycopg://tester:secret@127.0.0.1:5432/rag_lab",
        )


def test_assert_trace_summary_requires_full_runtime_chain():
    """Trace 摘要必须能串联 Runtime、Checkpoint、Tool 和 QARun。"""
    with pytest.raises(AssertionError, match="skillCallId"):
        _assert_trace_summary(
            {
                "agentInvocationId": "invocation-1",
                "threadId": "conv-1",
                "checkpointId": "checkpoint-1",
                "scenarioType": "knowledge_qa",
                "runtimeVersion": "langgraph_primary_v1",
                "qaRunId": "run-1",
                "modelCallId": "model-1",
                "summaryVersion": 1,
            }
        )


def test_assert_trace_summary_accepts_full_runtime_chain():
    """完整 Trace 摘要可通过发布脚本断言。"""
    _assert_trace_summary(
        {
            "agentInvocationId": "invocation-1",
            "threadId": "conv-1",
            "checkpointId": "checkpoint-1",
            "scenarioType": "knowledge_qa",
            "runtimeVersion": "langgraph_primary_v1",
            "qaRunId": "run-1",
            "skillCallId": "skill-1",
            "modelCallId": "model-1",
            "summaryVersion": 1,
        }
    )


def test_assert_trace_summary_accepts_zero_before_summary_threshold():
    """长对话达到阈值前，Trace 字段应存在但摘要版本允许为零。"""
    _assert_trace_summary(
        {
            "agentInvocationId": "invocation-1",
            "threadId": "conv-1",
            "checkpointId": "checkpoint-1",
            "scenarioType": "knowledge_qa",
            "runtimeVersion": "langgraph_primary_v1",
            "qaRunId": "run-1",
            "skillCallId": "skill-1",
            "modelCallId": "model-1",
            "summaryVersion": 0,
        }
    )
