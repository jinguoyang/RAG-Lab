"""Agent Runtime Task 8: Scenario Registry 与 Runtime Facade 测试。"""

from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, Mock, patch

import pytest

import app.services.agent_runtime.runtime_facade as runtime_facade
from app.services.agent_runtime.runtime_facade import (
    RuntimeVersion,
    resolve_runtime_version,
    run_shadow_projection,
    submit_training_classroom_runtime_event,
)
from app.services.agent_runtime.scenario_registry import ScenarioGraphRegistry


# ---------------------------------------------------------------------------
# RuntimeVersion
# ---------------------------------------------------------------------------


def test_runtime_version_defaults_to_legacy():
    assert resolve_runtime_version(None) == RuntimeVersion.LEGACY


def test_runtime_version_accepts_shadow():
    assert resolve_runtime_version("langgraph_shadow_v1") == RuntimeVersion.LANGGRAPH_SHADOW


def test_runtime_version_accepts_primary():
    assert resolve_runtime_version("langgraph_primary_v1") == RuntimeVersion.LANGGRAPH_PRIMARY


# ---------------------------------------------------------------------------
# Shadow Projection
# ---------------------------------------------------------------------------


def test_shadow_projection_does_not_call_model_or_qarun():
    call_model = Mock()
    call_qa_run = Mock()

    result = run_shadow_projection(
        state={"sessionId": "s1", "currentState": "TEACH"},
        call_model=call_model,
        call_qa_run=call_qa_run,
    )

    assert result["sessionId"] == "s1"
    call_model.assert_not_called()
    call_qa_run.assert_not_called()


# ---------------------------------------------------------------------------
# ScenarioGraphRegistry
# ---------------------------------------------------------------------------


def test_scenario_registry_register_and_get():
    registry = ScenarioGraphRegistry()
    builder = Mock()

    registry.register("knowledge_qa", builder)

    assert registry.get("knowledge_qa") is builder
    assert registry.get("unknown") is None


# ---------------------------------------------------------------------------
# submit_training_classroom_runtime_event
# ---------------------------------------------------------------------------


def test_legacy_calls_submit_classroom_event():
    mock_request = Mock(eventType="start", payload={}, query=None)
    with patch("app.services.training_classroom_service.submit_classroom_event") as mock_submit:
        mock_submit.return_value = Mock()
        submit_training_classroom_runtime_event(
            Mock(), "cred", "s1", mock_request, RuntimeVersion.LEGACY,
        )
        mock_submit.assert_called_once()


def test_shadow_calls_submit_classroom_event():
    mock_request = Mock(eventType="start", payload={}, query=None)
    with patch("app.services.training_classroom_service.submit_classroom_event") as mock_submit:
        mock_submit.return_value = Mock()
        submit_training_classroom_runtime_event(
            Mock(), "cred", "s1", mock_request, RuntimeVersion.LANGGRAPH_SHADOW,
        )
        mock_submit.assert_called_once()


def test_primary_calls_graph():
    """Primary 路径应调用 Graph 编排，而非直接 apply + persist。"""
    mock_request = Mock(eventType="start", payload={}, query=None, requestId=None)
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "sessionId": "s1",
        "eventType": "start",
        "currentState": "INIT",
        "visibleContent": "课程大纲",
        "domainResult": {"resultState": "PLAN", "eventType": "start"},
        "citations": [],
        "pendingActions": [],
    }
    with patch("app.services.agent_runtime.runtime_facade._build_graph_for_session", return_value=mock_graph):
        result = submit_training_classroom_runtime_event(
            Mock(), "cred", "s1", mock_request, RuntimeVersion.LANGGRAPH_PRIMARY,
        )
        mock_graph.invoke.assert_called_once()
        assert result.visibleContent == "课程大纲"


def test_primary_falls_back_to_legacy_on_error():
    """Primary Graph 构建失败时应降级到 Legacy。"""
    mock_request = Mock(eventType="start", payload={}, query=None, requestId=None)
    with (
        patch("app.services.agent_runtime.runtime_facade._build_graph_for_session", side_effect=RuntimeError("graph build failed")),
        patch("app.services.training_classroom_service.submit_classroom_event") as mock_legacy,
        patch("app.services.agent_runtime.runtime_facade._record_fallback"),
    ):
        mock_legacy.return_value = Mock()
        submit_training_classroom_runtime_event(
            Mock(), "cred", "s1", mock_request, RuntimeVersion.LANGGRAPH_PRIMARY,
        )
        mock_legacy.assert_called_once()


def test_primary_does_not_fall_back_after_graph_started():
    """Graph 已开始执行后失败时不得重放 Legacy，避免重复业务副作用。"""
    mock_request = Mock(eventType="start", payload={}, query=None, requestId="req-1")
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("persist may already have happened")
    with (
        patch("app.services.agent_runtime.runtime_facade._build_graph_for_session", return_value=mock_graph),
        patch("app.services.training_classroom_service.submit_classroom_event") as mock_legacy,
        patch("app.services.agent_runtime.runtime_facade._record_fallback") as mock_audit,
    ):
        with pytest.raises(RuntimeError, match="persist may already have happened"):
            submit_training_classroom_runtime_event(
                Mock(), "cred", "s1", mock_request, RuntimeVersion.LANGGRAPH_PRIMARY,
            )
        mock_legacy.assert_not_called()
        mock_audit.assert_not_called()


def test_get_shared_checkpointer_enters_configured_postgres_context():
    """Facade 应读取 Agent Runtime 专用配置，并持有 Postgres saver 上下文。"""
    saver = Mock()
    context = MagicMock()
    context.__enter__.return_value = saver
    settings = SimpleNamespace(
        agent_runtime_checkpoint_backend="postgres",
        agent_runtime_checkpoint_database_url="postgresql://checkpoint-db",
    )
    runtime_facade._shared_checkpointer = None
    runtime_facade._shared_checkpointer_context = None
    checkpoint_module = SimpleNamespace(create_checkpointer=Mock(return_value=context))
    try:
        with (
            patch("app.core.config.get_settings", return_value=settings),
            patch.dict("sys.modules", {"app.services.agent_runtime.checkpoint_service": checkpoint_module}),
        ):
            assert runtime_facade._get_shared_checkpointer() is saver
            assert runtime_facade._get_shared_checkpointer() is saver

        checkpoint_module.create_checkpointer.assert_called_once_with(
            backend="postgres",
            database_url="postgresql://checkpoint-db",
        )
        context.__enter__.assert_called_once()
    finally:
        runtime_facade._close_shared_checkpointer()


def test_build_graph_passes_classroom_end_user_to_qa_run_tool():
    """QARun Tool 应继承当前课堂学员身份，不能匿名创建会话。"""
    qa_tool = Mock()
    qa_module = SimpleNamespace(create_qa_run_tool=Mock(return_value=qa_tool))
    graph_builder = Mock(return_value=Mock())
    with (
        patch("app.services.training_classroom_service._read_session", return_value={"end_user_id": "user-1"}),
        patch("app.services.agent_runtime.runtime_facade._get_shared_checkpointer", return_value=Mock()),
        patch("app.services.agent_runtime.graphs.employee_training_graph.build_employee_training_graph", graph_builder),
        patch.dict("sys.modules", {"app.services.agent_runtime.qa_run_tool": qa_module}),
    ):
        runtime_facade._build_graph_for_session(Mock(), "cred", "s1")

    qa_module.create_qa_run_tool.assert_called_once_with(
        session=ANY,
        credential="cred",
        end_user_id="user-1",
    )
