"""B-329 Task 5: EmployeeTrainingGraph 节点和路由逻辑。"""
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from app.services.agent_runtime.graphs.employee_training_graph import (
    EmployeeTrainingState,
    _make_check_idempotency,
    _make_classify_intent,
    _make_compose_response,
    _make_generate_content,
    _make_get_allowed_actions,
    _make_load_context,
    _make_normalize_domain_event,
    _make_parse_domain_command,
    _make_persist_text_response,
    _make_request_clarification,
    _make_route_input,
    _make_run_domain_event,
    _make_validate_domain_command,
    route_after_classify,
    route_after_domain_event,
    route_after_idempotency,
    route_after_text_idempotency,
    route_after_validation,
    route_input_decision,
)


# ---------------------------------------------------------------------------
# 节点：route_input 载体路由
# ---------------------------------------------------------------------------


def test_page_event_carrier():
    node = _make_route_input()
    state: EmployeeTrainingState = {"eventType": "start", "payload": {}, "query": ""}
    result = node(state)
    assert result["_inputCarrier"] == "page_event"


def test_free_text_carrier():
    node = _make_route_input()
    state: EmployeeTrainingState = {"eventType": "", "query": "什么是RAG"}
    result = node(state)
    assert result["_inputCarrier"] == "free_text"


def test_resume_carrier():
    node = _make_route_input()
    state: EmployeeTrainingState = {"eventType": "", "query": ""}
    result = node(state)
    assert result["_inputCarrier"] == "resume"


def test_query_event_as_free_text():
    """eventType='query' 应该走 free_text 路径。"""
    node = _make_route_input()
    state: EmployeeTrainingState = {"eventType": "query", "query": "什么是RAG"}
    result = node(state)
    assert result["_inputCarrier"] == "free_text"


# ---------------------------------------------------------------------------
# 节点：normalize_domain_event
# ---------------------------------------------------------------------------


def test_normalize_domain_event():
    node = _make_normalize_domain_event()
    state: EmployeeTrainingState = {"eventType": "start", "payload": {"key": "val"}}
    result = node(state)
    assert result["_domainCommand"]["eventType"] == "start"
    assert result["_domainCommand"]["payload"] == {"key": "val"}


# ---------------------------------------------------------------------------
# 节点：classify_intent（通过 classify_text_intent 节点）
# ---------------------------------------------------------------------------


def test_classify_intent_forbidden():
    mock_classifier = Mock()
    node = _make_classify_intent(mock_classifier)
    state: EmployeeTrainingState = {
        "query": "跳过测验",
        "currentState": "QUIZ",
        "allowedActions": ["submit_answer", "query"],
    }
    result = node(state)
    assert result["textDecision"]["intent"] == "forbidden"
    mock_classifier.invoke.assert_not_called()


def test_classify_intent_domain_command():
    mock_classifier = MagicMock()
    from app.services.agent_runtime.graphs.employee_training_intent import TextIntentResult, DomainCommand

    mock_classifier.invoke.return_value = TextIntentResult(
        intent="domain_command",
        command=DomainCommand(eventType="continue"),
        confidence=0.95,
        reason="明确继续",
    )
    node = _make_classify_intent(mock_classifier)
    state: EmployeeTrainingState = {
        "query": "请继续下一节",
        "currentState": "TEACH",
        "allowedActions": ["continue", "query"],
    }
    result = node(state)
    assert result["textDecision"]["intent"] == "domain_command"
    assert result["eventType"] == "continue"


def test_classify_intent_records_audit():
    """Graph 自由文本分类应复用 Skill 审计表留下决策证据。"""
    audit = Mock()
    node = _make_classify_intent(Mock(), audit, lambda: Mock())
    state: EmployeeTrainingState = {
        "sessionId": "s1",
        "_app_id": "app1",
        "query": "跳过测验",
        "currentState": "QUIZ",
        "allowedActions": ["submit_answer", "query"],
    }

    node(state)

    audit.assert_called_once()
    assert audit.call_args.kwargs["skill_name"] == "classifyIntent"
    assert "forbidden" in audit.call_args.kwargs["output_summary"]


# ---------------------------------------------------------------------------
# 节点：validate_domain_command
# ---------------------------------------------------------------------------


def test_validate_passes():
    node = _make_validate_domain_command()
    state: EmployeeTrainingState = {
        "_domainCommand": {"eventType": "continue", "payload": {}},
        "allowedActions": ["continue", "query"],
    }
    result = node(state)
    assert result["_validationResult"]["allowed"] is True


def test_validate_fails_unknown_type():
    node = _make_validate_domain_command()
    state: EmployeeTrainingState = {
        "_domainCommand": {"eventType": "hack", "payload": {}},
        "allowedActions": ["hack"],
    }
    result = node(state)
    assert result["_validationResult"]["allowed"] is False
    assert "未知" in result["_validationResult"]["reason"]


def test_validate_fails_not_in_allowed():
    node = _make_validate_domain_command()
    state: EmployeeTrainingState = {
        "_domainCommand": {"eventType": "next_section", "payload": {}},
        "allowedActions": ["continue", "query"],
    }
    result = node(state)
    assert result["_validationResult"]["allowed"] is False
    assert "不允许" in result["_validationResult"]["reason"]


def test_validate_submit_quiz_missing_payload():
    node = _make_validate_domain_command()
    state: EmployeeTrainingState = {
        "_domainCommand": {"eventType": "submit_quiz", "payload": {"answer": "B"}},
        "allowedActions": ["submit_quiz"],
    }
    result = node(state)
    assert result["_validationResult"]["allowed"] is False
    assert "questionId" in result["_validationResult"]["reason"]


# ---------------------------------------------------------------------------
# 路由函数
# ---------------------------------------------------------------------------


def test_route_input_page_event():
    state: EmployeeTrainingState = {"_inputCarrier": "page_event"}
    assert route_input_decision(state) == "normalize_domain_event"


def test_route_input_free_text():
    state: EmployeeTrainingState = {"_inputCarrier": "free_text"}
    assert route_input_decision(state) == "check_text_idempotency"


def test_route_input_resume():
    state: EmployeeTrainingState = {"_inputCarrier": "resume"}
    assert route_input_decision(state) == "compose_response"


def test_route_after_classify_domain_command():
    state: EmployeeTrainingState = {"textDecision": {"intent": "domain_command"}}
    assert route_after_classify(state) == "parse_domain_command"


def test_route_after_classify_course_qa():
    state: EmployeeTrainingState = {"textDecision": {"intent": "course_qa"}}
    assert route_after_classify(state) == "answer_course_question"


def test_route_after_classify_teaching_adjustment():
    state: EmployeeTrainingState = {"textDecision": {"intent": "teaching_adjustment"}}
    assert route_after_classify(state) == "regenerate_teaching_response"


def test_route_after_classify_off_topic():
    state: EmployeeTrainingState = {"textDecision": {"intent": "off_topic"}}
    assert route_after_classify(state) == "build_guidance_response"


def test_route_after_classify_forbidden():
    state: EmployeeTrainingState = {"textDecision": {"intent": "forbidden"}}
    assert route_after_classify(state) == "build_guidance_response"


def test_route_after_classify_clarification():
    state: EmployeeTrainingState = {"textDecision": {"intent": "clarification_required"}}
    assert route_after_classify(state) == "request_clarification"


def test_route_after_validation_pass():
    state: EmployeeTrainingState = {"_validationResult": {"allowed": True}}
    assert route_after_validation(state) == "check_idempotency"


def test_route_after_validation_fail():
    state: EmployeeTrainingState = {"_validationResult": {"allowed": False}}
    assert route_after_validation(state) == "request_clarification"


def test_route_after_idempotency_hit():
    state: EmployeeTrainingState = {"_idempotencyHit": True}
    assert route_after_idempotency(state) == "compose_response"


def test_route_after_idempotency_miss():
    state: EmployeeTrainingState = {"_idempotencyHit": False}
    assert route_after_idempotency(state) == "run_domain_event"


def test_route_after_text_idempotency_miss():
    state: EmployeeTrainingState = {"_idempotencyHit": False}
    assert route_after_text_idempotency(state) == "classify_text_intent"


# ---------------------------------------------------------------------------
# 节点：get_allowed_actions
# ---------------------------------------------------------------------------


def test_get_allowed_actions_quiz():
    node = _make_get_allowed_actions()
    state: EmployeeTrainingState = {"currentState": "QUIZ"}
    result = node(state)
    assert set(result["allowedActions"]) == {"submit_answer", "submit_quiz", "query"}


# ---------------------------------------------------------------------------
# 节点：request_clarification
# ---------------------------------------------------------------------------


def test_request_clarification_shows_hints():
    node = _make_request_clarification()
    state: EmployeeTrainingState = {"allowedActions": ["continue", "query"]}
    result = node(state)
    assert "continue" in result["visibleContent"]
    assert result["responseMode"] == "template"


# ---------------------------------------------------------------------------
# 节点：parse_domain_command
# ---------------------------------------------------------------------------


def test_parse_domain_command():
    node = _make_parse_domain_command()
    state: EmployeeTrainingState = {
        "textDecision": {
            "intent": "domain_command",
            "command": {"eventType": "submit_quiz", "payload": {"questionId": "q1", "answer": "B"}},
        }
    }
    result = node(state)
    assert result["_domainCommand"]["eventType"] == "submit_quiz"
    assert result["_domainCommand"]["payload"]["questionId"] == "q1"


def test_parse_domain_command_no_command():
    node = _make_parse_domain_command()
    state: EmployeeTrainingState = {
        "textDecision": {"intent": "course_qa", "command": None}
    }
    result = node(state)
    assert result == {}


# ---------------------------------------------------------------------------
# 节点：Primary 持久化与幂等回放
# ---------------------------------------------------------------------------


def test_idempotency_hit_restores_event_id_progress_and_result_state():
    """重复 requestId 应还原首次事件 ID、进度和状态。"""
    existing = {
        "event_id": "evt-1",
        "payload": {
            "_runtime": {
                "responseSnapshot": {
                    "eventType": "start_plan",
                    "resultState": "TEACH",
                    "visibleContent": "首次讲解",
                    "responseMode": "teaching_narration",
                    "uiActions": [],
                    "citations": [],
                    "progressUpdate": {"sectionIndex": 1},
                }
            }
        },
    }
    check = _make_check_idempotency(lambda *_: existing, lambda: Mock())
    compose = _make_compose_response()

    checked = check({"sessionId": "s1", "requestId": "req-1"})
    result = compose(checked)

    assert checked["_persistedEventId"] == "evt-1"
    assert result["_persistedProgressUpdate"] == {"sectionIndex": 1}
    assert result["domainResult"]["resultState"] == "TEACH"


def test_domain_response_mode_routes_to_generation_before_persist():
    """领域结果的 responseMode 应在最终响应持久化前驱动内容生成。"""
    state: EmployeeTrainingState = {
        "domainResult": {
            "responseMode": "teaching_narration",
            "visibleContent": "原始正文",
        }
    }
    assert route_after_domain_event(state) == "generate_content"


def test_generate_content_updates_domain_result_for_persistence():
    """生成后的正文必须回写 domainResult，供事件快照和消息表使用。"""
    model = Mock()
    model.invoke.return_value = SimpleNamespace(content="模型讲解")
    node = _make_generate_content(model, None, None, None, "", 2000, 6)

    result = node({
        "responseMode": "teaching_narration",
        "domainResult": {
            "eventType": "start_plan",
            "resultState": "TEACH",
            "responseMode": "teaching_narration",
            "visibleContent": "原始正文",
        },
    })

    assert result["domainResult"]["visibleContent"].startswith("模型讲解")


def test_text_leaf_persists_business_response():
    """自由文本叶子也应写入课堂消息、事件和幂等快照。"""
    persisted = Mock(eventId="evt-text", progressUpdate=None)
    persist_fn = Mock(return_value=persisted)
    node = _make_persist_text_response(persist_fn, lambda: Mock())
    state: EmployeeTrainingState = {
        "sessionId": "s1",
        "requestId": "req-text",
        "eventType": "query",
        "query": "什么是 RAG？",
        "currentState": "TEACH",
        "visibleContent": "检索增强生成。",
        "responseMode": "rag_explain",
        "_contextRow": {"current_state": "TEACH"},
        "_endUserId": "u1",
    }

    result = node(state)

    domain_result = persist_fn.call_args.args[3]
    assert domain_result.eventType == "query"
    assert domain_result.userMessage == "什么是 RAG？"
    assert domain_result.visibleContent == "检索增强生成。"
    assert persist_fn.call_args.kwargs["request_id"] == "req-text"
    assert result["_persistedEventId"] == "evt-text"


def test_persisted_fields_are_declared_in_graph_state():
    """LangGraph 只保留已声明通道，持久化响应字段必须属于 State。"""
    annotations = EmployeeTrainingState.__annotations__
    assert "_persistedEventId" in annotations
    assert "_persistedProgressUpdate" in annotations
