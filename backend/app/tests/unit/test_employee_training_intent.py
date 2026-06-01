"""B-329 Task 1-3: 员工培训课堂意图分类与路由类型。"""
from unittest.mock import Mock, MagicMock

from app.services.agent_runtime.graphs.employee_training_intent import (
    DomainCommand,
    DomainCommandValidation,
    IntentRouteContext,
    TextIntentResult,
    TextRouteDecision,
    _CLASSROOM_ALLOWED_ACTIONS,
    _DOMAIN_COMMANDS,
    _FORBIDDEN_TERMS,
    _REPEAT_TERMS,
    create_text_intent_classifier,
    get_allowed_classroom_actions,
    resolve_text_intent,
    validate_domain_command,
)


# ---------------------------------------------------------------------------
# Task 1: 允许动作映射
# ---------------------------------------------------------------------------


def test_quiz_state_allows_only_submit_and_query():
    actions = get_allowed_classroom_actions("QUIZ")
    assert actions == {"submit_answer", "submit_quiz", "query"}


def test_completed_state_has_no_mutating_actions():
    actions = get_allowed_classroom_actions("COMPLETED")
    assert actions == set()


def test_init_state_allows_only_start():
    actions = get_allowed_classroom_actions("INIT")
    assert actions == {"start"}


def test_unknown_state_returns_empty():
    actions = get_allowed_classroom_actions("NONEXISTENT")
    assert actions == set()


def test_all_classroom_states_covered():
    expected = {"INIT", "PLAN", "TEACH", "CHECK_UNDERSTAND", "QUIZ", "GRADE",
                "REVIEW", "SUMMARY", "NEXT_SECTION", "COMPLETED", "OFF_TOPIC"}
    assert set(_CLASSROOM_ALLOWED_ACTIONS.keys()) == expected


# ---------------------------------------------------------------------------
# Task 3: 领域命令校验
# ---------------------------------------------------------------------------


def test_validate_submit_quiz_with_valid_payload():
    cmd = DomainCommand(eventType="submit_quiz", payload={"questionId": "q1", "answer": "B"})
    result = validate_domain_command(cmd, {"submit_quiz"})
    assert result.allowed is True
    assert result.command is cmd


def test_validate_submit_quiz_missing_question_id():
    cmd = DomainCommand(eventType="submit_quiz", payload={"answer": "B"})
    result = validate_domain_command(cmd, {"submit_quiz"})
    assert result.allowed is False
    assert "questionId" in result.reason


def test_validate_submit_quiz_missing_answer():
    cmd = DomainCommand(eventType="submit_quiz", payload={"questionId": "q1"})
    result = validate_domain_command(cmd, {"submit_quiz"})
    assert result.allowed is False
    assert "answer" in result.reason


def test_validate_next_section_outside_summary():
    cmd = DomainCommand(eventType="next_section")
    result = validate_domain_command(cmd, {"continue", "query"})
    assert result.allowed is False
    assert "不允许" in result.reason


def test_validate_unknown_event_type():
    cmd = DomainCommand(eventType="hack_system")
    result = validate_domain_command(cmd, {"hack_system"})
    assert result.allowed is False
    assert "未知" in result.reason


def test_validate_continue_in_valid_state():
    cmd = DomainCommand(eventType="continue")
    result = validate_domain_command(cmd, {"continue", "query"})
    assert result.allowed is True


def test_domain_commands_whitelist():
    """确保白名单包含所有已知命令。"""
    expected = {"start", "continue", "start_plan", "start_quiz",
                "submit_answer", "submit_quiz", "retry_teach",
                "retry_quiz", "next_section", "complete"}
    assert _DOMAIN_COMMANDS == expected


# ---------------------------------------------------------------------------
# Task 2: 规则优先分类
# ---------------------------------------------------------------------------


def test_forbidden_term_returns_forbidden():
    ctx = IntentRouteContext(currentState="QUIZ", allowedActions=["submit_answer", "query"])
    classifier = Mock()
    decision = resolve_text_intent(query="跳过测验", ctx=ctx, classifier=classifier)
    assert decision.intent == "forbidden"
    assert decision.confidence == 1.0
    classifier.invoke.assert_not_called()


def test_repeat_term_returns_teaching_adjustment():
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    classifier = Mock()
    decision = resolve_text_intent(query="再讲一遍", ctx=ctx, classifier=classifier)
    assert decision.intent == "teaching_adjustment"
    assert decision.confidence == 1.0
    classifier.invoke.assert_not_called()


def test_single_continue_skips_model():
    # TEACH 状态下 safe_actions 只有 "continue" 命中，可直接转换
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    classifier = Mock()
    decision = resolve_text_intent(query="继续", ctx=ctx, classifier=classifier)
    assert decision.intent == "domain_command"
    assert decision.command is not None
    assert decision.command.eventType == "continue"
    classifier.invoke.assert_not_called()


def test_ambiguous_continue_requests_clarification():
    # PLAN 状态下 safe_actions 有 continue + start_plan，需要澄清
    ctx = IntentRouteContext(currentState="PLAN", allowedActions=["continue", "start_plan"])
    classifier = Mock()
    decision = resolve_text_intent(query="继续", ctx=ctx, classifier=classifier)
    assert decision.intent == "clarification_required"
    classifier.invoke.assert_not_called()


def test_llm_low_confidence_requests_clarification():
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    mock_classifier = MagicMock()
    mock_classifier.invoke.return_value = TextIntentResult(
        intent="course_qa",
        confidence=0.4,
        reason="模糊的问题",
    )
    decision = resolve_text_intent(query="这是什么", ctx=ctx, classifier=mock_classifier)
    assert decision.intent == "clarification_required"
    assert decision.confidence == 0.4


def test_llm_domain_command_low_confidence_requests_clarification():
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    mock_classifier = MagicMock()
    mock_classifier.invoke.return_value = TextIntentResult(
        intent="domain_command",
        command=DomainCommand(eventType="continue"),
        confidence=0.7,
        reason="可能是继续",
    )
    decision = resolve_text_intent(query="go on", ctx=ctx, classifier=mock_classifier)
    assert decision.intent == "clarification_required"


def test_llm_domain_command_high_confidence_accepted():
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    mock_classifier = MagicMock()
    mock_classifier.invoke.return_value = TextIntentResult(
        intent="domain_command",
        command=DomainCommand(eventType="continue"),
        confidence=0.9,
        reason="明确的继续意图",
    )
    decision = resolve_text_intent(query="请继续下一节", ctx=ctx, classifier=mock_classifier)
    assert decision.intent == "domain_command"
    assert decision.command is not None
    assert decision.command.eventType == "continue"


def test_llm_domain_command_not_in_allowed_actions():
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    mock_classifier = MagicMock()
    mock_classifier.invoke.return_value = TextIntentResult(
        intent="domain_command",
        command=DomainCommand(eventType="submit_quiz"),
        confidence=0.95,
        reason="提交答案",
    )
    decision = resolve_text_intent(query="我选B", ctx=ctx, classifier=mock_classifier)
    assert decision.intent == "clarification_required"
    assert "不允许" in decision.reason


def test_llm_course_qa_high_confidence_accepted():
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    mock_classifier = MagicMock()
    mock_classifier.invoke.return_value = TextIntentResult(
        intent="course_qa",
        confidence=0.85,
        reason="关于课程内容的问题",
    )
    decision = resolve_text_intent(query="什么是RAG", ctx=ctx, classifier=mock_classifier)
    assert decision.intent == "course_qa"


def test_classifier_exception_returns_clarification():
    ctx = IntentRouteContext(currentState="TEACH", allowedActions=["continue", "query"])
    mock_classifier = MagicMock()
    mock_classifier.invoke.side_effect = RuntimeError("model timeout")
    decision = resolve_text_intent(query="什么是RAG", ctx=ctx, classifier=mock_classifier)
    assert decision.intent == "clarification_required"
    assert "失败" in decision.reason


def test_create_text_intent_classifier():
    mock_model = Mock()
    create_text_intent_classifier(mock_model)
    mock_model.with_structured_output.assert_called_once_with(TextIntentResult)
