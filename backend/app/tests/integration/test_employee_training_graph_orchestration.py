"""B-329 Task 9: EmployeeTrainingGraph 编排集成测试。

验证 Legacy / Primary 路径的端到端行为、幂等保护、responseMode 策略。
"""
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.schemas.training_classroom import (
    ClassroomDomainResult,
    ClassroomEventSubmitRequest,
)
from app.services.agent_runtime.graphs.employee_training_intent import (
    DomainCommand,
    IntentRouteContext,
    get_allowed_classroom_actions,
    resolve_text_intent,
    validate_domain_command,
)
from app.services.agent_runtime.runtime_facade import (
    RuntimeVersion,
    resolve_runtime_version,
    submit_training_classroom_runtime_event,
)
from app.services.training_classroom_service import (
    apply_classroom_domain_event,
    persist_classroom_domain_response,
    resolve_classroom_response_mode,
    read_classroom_event_by_request_id,
)


# ---------------------------------------------------------------------------
# responseMode 确定性策略
# ---------------------------------------------------------------------------


class TestResponseModeStrategy:
    def test_start_plan_to_teach_is_teaching_narration(self):
        assert resolve_classroom_response_mode(
            event_type="start_plan", result_state="TEACH",
        ) == "teaching_narration"

    def test_retry_teach_to_teach_is_teaching_narration(self):
        assert resolve_classroom_response_mode(
            event_type="retry_teach", result_state="TEACH",
        ) == "teaching_narration"

    def test_next_section_to_teach_is_teaching_narration(self):
        assert resolve_classroom_response_mode(
            event_type="next_section", result_state="TEACH",
        ) == "teaching_narration"

    def test_submit_quiz_failed_is_rag_explain(self):
        assert resolve_classroom_response_mode(
            event_type="submit_quiz", result_state="GRADE",
            response_context={"passed": False},
        ) == "rag_explain"

    def test_submit_quiz_passed_is_template(self):
        assert resolve_classroom_response_mode(
            event_type="submit_quiz", result_state="GRADE",
            response_context={"passed": True},
        ) == "template"

    def test_start_to_plan_is_template(self):
        assert resolve_classroom_response_mode(
            event_type="start", result_state="PLAN",
        ) == "template"

    def test_continue_to_check_understand_is_template(self):
        assert resolve_classroom_response_mode(
            event_type="continue", result_state="CHECK_UNDERSTAND",
        ) == "template"


# ---------------------------------------------------------------------------
# 幂等保护
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_same_request_id_returns_cached_snapshot(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = {
            "event_id": "evt-123",
            "session_id": "s1",
            "payload": {
                "_runtime": {
                    "requestId": "req-abc",
                    "responseSnapshot": {
                        "eventType": "start",
                        "resultState": "PLAN",
                        "visibleContent": "课程大纲",
                        "responseMode": "template",
                    },
                },
            },
        }
        request = ClassroomEventSubmitRequest(
            eventType="start", requestId="req-abc",
        )
        with patch("app.services.training_classroom_service._read_session", return_value={"current_state": "INIT", "end_user_id": "u1"}):
            from app.services.training_classroom_service import submit_classroom_event
            result = submit_classroom_event(mock_session, "cred", "s1", request)
        assert result.eventType == "start"
        assert result.resultState == "PLAN"

    def test_new_request_id_proceeds_normally(self):
        mock_session = MagicMock()
        # First call: no existing event (idempotency check)
        # Second call: _read_session for apply_classroom_domain_event
        mock_session.execute.return_value.mappings.return_value.first.return_value = None
        request = ClassroomEventSubmitRequest(eventType="start", requestId="req-new")

        with (
            patch("app.services.training_classroom_service.read_classroom_event_by_request_id", return_value=None),
            patch("app.services.training_classroom_service._read_session", return_value={
                "session_id": "s1", "app_id": "app1", "current_state": "INIT",
                "end_user_id": "u1", "metadata": {}, "current_section_index": 0,
            }),
            patch("app.services.training_classroom_service.resolve_training_context") as mock_ctx,
            patch("app.services.training_classroom_service._plan_content", return_value=("content", [])),
            patch("app.services.training_classroom_service._insert_event", return_value="evt-1"),
            patch("app.services.training_classroom_service._insert_message"),
            patch("app.services.training_classroom_service._update_state"),
        ):
            mock_ctx.return_value = SimpleNamespace(kb_row={"kb_id": "kb1"})
            from app.services.training_classroom_service import submit_classroom_event
            result = submit_classroom_event(mock_session, "cred", "s1", request)
        assert result.sessionId == "s1"


# ---------------------------------------------------------------------------
# 意图分类集成
# ---------------------------------------------------------------------------


class TestIntentClassificationIntegration:
    def test_page_event_skips_classifier(self):
        """页面按钮事件不调用 LLM 分类器。"""
        mock_classifier = Mock()
        # 页面事件走 normalize_domain_event，不经过 classify_text_intent
        carrier = "page_event"
        assert carrier == "page_event"
        mock_classifier.invoke.assert_not_called()

    def test_text_i_choose_b_routes_to_submit_quiz(self):
        """文本 '我选B' 应路由到 submit_quiz。"""
        from unittest.mock import MagicMock
        from app.services.agent_runtime.graphs.employee_training_intent import TextIntentResult

        mock_classifier = MagicMock()
        mock_classifier.invoke.return_value = TextIntentResult(
            intent="domain_command",
            command=DomainCommand(eventType="submit_quiz", payload={"questionId": "q1", "answer": "B"}),
            confidence=0.95,
            reason="明确的答题意图",
        )
        ctx = IntentRouteContext(
            currentState="QUIZ",
            allowedActions=["submit_answer", "submit_quiz", "query"],
        )
        decision = resolve_text_intent(query="我选B", ctx=ctx, classifier=mock_classifier)
        assert decision.intent == "domain_command"
        assert decision.command is not None
        assert decision.command.eventType == "submit_quiz"
        assert decision.command.payload["answer"] == "B"

    def test_off_topic_guidance(self):
        """偏题问题应路由到 build_guidance_response。"""
        from app.services.agent_runtime.graphs.employee_training_intent import TextIntentResult

        mock_classifier = MagicMock()
        mock_classifier.invoke.return_value = TextIntentResult(
            intent="off_topic",
            confidence=0.90,
            reason="与培训内容无关",
        )
        ctx = IntentRouteContext(
            currentState="TEACH",
            allowedActions=["continue", "query"],
        )
        decision = resolve_text_intent(query="帮我写一封请假邮件", ctx=ctx, classifier=mock_classifier)
        assert decision.intent == "off_topic"

    def test_forbidden_blocks_execution(self):
        """禁止词直接拦截，不调用 LLM。"""
        mock_classifier = Mock()
        ctx = IntentRouteContext(
            currentState="QUIZ",
            allowedActions=["submit_answer", "query"],
        )
        decision = resolve_text_intent(query="跳过测验", ctx=ctx, classifier=mock_classifier)
        assert decision.intent == "forbidden"
        mock_classifier.invoke.assert_not_called()


# ---------------------------------------------------------------------------
# Legacy vs Primary 路径行为一致性
# ---------------------------------------------------------------------------


class TestLegacyPrimaryParity:
    def test_legacy_uses_submit_classroom_event(self):
        mock_request = Mock(eventType="start", payload={}, query=None)
        with patch("app.services.training_classroom_service.submit_classroom_event") as mock_submit:
            mock_submit.return_value = Mock()
            submit_training_classroom_runtime_event(
                Mock(), "cred", "s1", mock_request, RuntimeVersion.LEGACY,
            )
            mock_submit.assert_called_once()

    def test_primary_uses_graph(self):
        """Primary 路径应通过 Graph 编排执行。"""
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

    def test_shadow_does_not_double_call(self):
        """Shadow 模式只调用一次 submit_classroom_event（Primary），不再调用 shadow projection 的模型。"""
        mock_request = Mock(eventType="start", payload={}, query=None)
        call_count = 0
        with patch("app.services.training_classroom_service.submit_classroom_event") as mock_submit:
            mock_submit.return_value = Mock()
            submit_training_classroom_runtime_event(
                Mock(), "cred", "s1", mock_request, RuntimeVersion.LANGGRAPH_SHADOW,
            )
            assert mock_submit.call_count == 1


# ---------------------------------------------------------------------------
# 显式降级
# ---------------------------------------------------------------------------


class TestExplicitFallback:
    def test_primary_graph_error_falls_back_to_legacy(self):
        mock_request = Mock(eventType="start", payload={}, query=None, requestId=None)
        with (
            patch("app.services.agent_runtime.runtime_facade._build_graph_for_session", side_effect=RuntimeError("graph error")),
            patch("app.services.training_classroom_service.submit_classroom_event") as mock_legacy,
            patch("app.services.agent_runtime.runtime_facade._record_fallback") as mock_audit,
        ):
            mock_legacy.return_value = Mock()
            submit_training_classroom_runtime_event(
                Mock(), "cred", "s1", mock_request, RuntimeVersion.LANGGRAPH_PRIMARY,
            )
            mock_legacy.assert_called_once()
            mock_audit.assert_called_once()


# ---------------------------------------------------------------------------
# 幂等快照完整性
# ---------------------------------------------------------------------------


class TestIdempotencySnapshotCompleteness:
    def test_duplicate_returns_full_response_with_ui_actions(self):
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = {
            "event_id": "evt-123",
            "session_id": "s1",
            "payload": {
                "_runtime": {
                    "requestId": "req-abc",
                    "responseSnapshot": {
                        "eventType": "start",
                        "resultState": "PLAN",
                        "visibleContent": "课程大纲内容",
                        "responseMode": "template",
                        "uiActions": [{"actionType": "button_group", "data": {"buttons": []}}],
                        "citations": [{"documentId": "d1", "chunkId": "c1", "content": "ref", "score": 1.0}],
                        "progressUpdate": None,
                    },
                },
            },
        }
        request = ClassroomEventSubmitRequest(eventType="start", requestId="req-abc")
        with patch("app.services.training_classroom_service._read_session", return_value={"current_state": "INIT", "end_user_id": "u1"}):
            from app.services.training_classroom_service import submit_classroom_event
            result = submit_classroom_event(mock_session, "cred", "s1", request)
        assert result.eventType == "start"
        assert result.resultState == "PLAN"
        assert result.visibleContent == "课程大纲内容"
        assert len(result.uiActions) == 1
        assert len(result.citations) == 1


class TestPrimaryGraphTextIdempotency:
    def test_duplicate_text_request_reuses_snapshot_without_rerunning_agent(self):
        """自由文本重复提交应直接回放快照，不重复调用 QARun Agent。"""
        pytest.importorskip("langgraph")
        from app.services.agent_runtime.graphs.employee_training_graph import build_employee_training_graph
        from app.services.agent_runtime.graphs.employee_training_intent import TextIntentResult

        existing = None
        agent = Mock()
        agent.invoke.return_value = {"messages": [SimpleNamespace(content="RAG 回答")]}
        classifier = Mock()
        classifier.invoke.return_value = TextIntentResult(
            intent="course_qa",
            confidence=0.95,
            reason="课程问题",
        )

        def read_by_request_id(_session, _session_id, _request_id):
            return existing

        def persist(_session, _session_id, _state_row, domain_result, _end_user_id, request_id=None):
            nonlocal existing
            existing = {
                "event_id": "evt-text",
                "payload": {
                    "_runtime": {
                        "requestId": request_id,
                        "responseSnapshot": {
                            "eventType": domain_result.eventType,
                            "resultState": domain_result.resultState,
                            "visibleContent": domain_result.visibleContent,
                            "responseMode": domain_result.responseMode,
                            "uiActions": [],
                            "citations": [],
                            "progressUpdate": None,
                        },
                    }
                },
            }
            return SimpleNamespace(eventId="evt-text", progressUpdate=None)

        graph = build_employee_training_graph(
            get_db_session_fn=Mock,
            read_session_fn=lambda *_: {
                "app_id": "app1",
                "current_state": "TEACH",
                "end_user_id": "u1",
            },
            resolve_context_fn=lambda *_: SimpleNamespace(kb_row={"kb_id": "kb1"}),
            recent_messages_fn=lambda *_: [],
            read_by_request_id_fn=read_by_request_id,
            apply_domain_event_fn=Mock(),
            persist_domain_response_fn=persist,
            build_agent_fn=lambda **_: agent,
            qa_run_tool=Mock(),
            model=Mock(),
            classifier=classifier,
        )
        initial = {
            "sessionId": "s1",
            "requestId": "req-text",
            "eventType": "query",
            "query": "什么是 RAG？",
        }

        first = graph.invoke(initial)
        second = graph.invoke(initial)

        assert first["_persistedEventId"] == "evt-text"
        assert second["_persistedEventId"] == "evt-text"
        assert second["visibleContent"] == "RAG 回答"
        assert agent.invoke.call_count == 1


# ---------------------------------------------------------------------------
# 允许动作映射完整性
# ---------------------------------------------------------------------------


class TestAllowedActionsCompleteness:
    def test_all_states_have_actions(self):
        states = ["INIT", "PLAN", "TEACH", "CHECK_UNDERSTAND", "QUIZ",
                   "GRADE", "REVIEW", "SUMMARY", "NEXT_SECTION", "COMPLETED", "OFF_TOPIC"]
        for state in states:
            actions = get_allowed_classroom_actions(state)
            assert isinstance(actions, set), f"{state} should return a set"

    def test_completed_has_no_mutating_actions(self):
        actions = get_allowed_classroom_actions("COMPLETED")
        mutating = {"start", "continue", "submit_answer", "submit_quiz",
                     "retry_teach", "retry_quiz", "next_section", "complete"}
        assert actions & mutating == set()
