# 员工培训课堂 Graph 完整编排实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 用途：本文是 E35 / B-329 的课堂 Graph 编排细化实施计划。执行前必须完成 `2026-06-01-agent-runtime-platform-foundation.md`，并先完成 `2026-06-01-agent-runtime-training-classroom.md` 中的 Runtime 版本固定和无副作用 Shadow 基础任务。

**Goal:** 在不复制课堂状态机的前提下，为 `EmployeeTrainingGraph` 增加混合意图路由、自然语言领域命令、页面事件后的按需模型回复、幂等保护和可审计降级。

**Architecture:** 页面事件直接标准化为领域事件，自由文本先经安全规则和快捷规则，再按需使用 LangChain 结构化输出分类。自然语言领域命令与页面事件汇入现有课堂 Controller；Controller 返回确定性的 `responseMode`，Graph 再选择模板、QARun 问答、教学讲解或多 Skill Agent。

**Tech Stack:** Python、FastAPI、Pydantic、SQLAlchemy、PostgreSQL、pytest、LangChain、LangGraph、现有培训课堂 Controller、现有 QARun Tool。

**Design Specs:**

- `docs/04-迭代与交付/specs/2026-06-01-langchain-langgraph-agent-runtime-spec.md`
- `docs/04-迭代与交付/specs/2026-06-01-employee-training-graph-orchestration-spec.md`

---

## 1. 执行边界

本计划必须完成：

- 新建课堂意图类型、结构化分类器和自然语言命令校验。
- 页面事件不调用分类模型。
- 自由文本只在规则不足时调用一次结构化分类模型。
- 所有状态变更统一进入现有课堂 Controller。
- 将现有 Controller 的“执行业务更新”和“生成最终回复”拆开，使 Graph 可按 `responseMode` 触发模型回复。
- 新增 `requestId` 幂等保护。
- 分类、澄清、无证据、越权、降级和重复提交均有测试。
- Graph 节点、分类 Skill、QARun Tool 和 Controller 事件可关联审计。

本计划不做：

- 不删除 Legacy 路径。
- 不删除现有课堂消息和事件表。
- 不让 LangChain Agent 直接写课堂状态。
- 不增加用户可自由配置的课堂 DAG。
- 不接入 SOP Graph。

## 2. 文件结构

### 新增文件

```text
backend/app/services/agent_runtime/graphs/employee_training_intent.py
backend/app/tests/unit/test_employee_training_intent.py
backend/app/tests/unit/test_employee_training_graph_routing.py
backend/app/tests/integration/test_employee_training_graph_orchestration.py
backend/migrations/versions/0042_add_training_classroom_event_request_id.py
```

### 修改文件

```text
backend/app/schemas/training_classroom.py
backend/app/services/training_skill_registry_service.py
backend/app/services/training_classroom_service.py
backend/app/services/agent_runtime/graphs/employee_training_graph.py
backend/app/services/agent_runtime/runtime_facade.py
backend/app/api/routes/training_classroom.py
backend/app/tables.py
backend/app/tests/unit/test_training_skill_registry_service.py
backend/app/tests/unit/test_training_classroom_section_boundary.py
backend/app/tests/integration/test_training_e2e_acceptance.py
```

## 3. Task 1：定义课堂路由类型和允许动作

**Files:**

- Create: `backend/app/services/agent_runtime/graphs/employee_training_intent.py`
- Modify: `backend/app/services/training_classroom_service.py`
- Test: `backend/app/tests/unit/test_employee_training_intent.py`

- [ ] **Step 1：写失败测试，验证状态对应的允许动作**

```python
from app.services.training_classroom_service import get_allowed_classroom_actions


def test_quiz_state_only_exposes_quiz_actions():
    assert get_allowed_classroom_actions("QUIZ") == {
        "submit_answer",
        "submit_quiz",
        "query",
    }


def test_completed_state_has_no_mutating_action():
    assert get_allowed_classroom_actions("COMPLETED") == set()
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_intent.py -q
```

Expected: FAIL，提示缺少 `get_allowed_classroom_actions`。

- [ ] **Step 3：在课堂服务中增加只读允许动作映射**

```python
_CLASSROOM_ALLOWED_ACTIONS: dict[str, set[str]] = {
    "INIT": {"start"},
    "PLAN": {"continue", "start_plan"},
    "TEACH": {"continue", "query"},
    "CHECK_UNDERSTAND": {"continue", "start_quiz", "query"},
    "QUIZ": {"submit_answer", "submit_quiz", "query"},
    "GRADE": {"continue", "query"},
    "REVIEW": {"continue", "retry_teach", "retry_quiz", "query"},
    "SUMMARY": {"next_section", "complete", "query"},
    "NEXT_SECTION": {"continue", "query"},
    "COMPLETED": set(),
    "OFF_TOPIC": {"continue", "query"},
}


def get_allowed_classroom_actions(current_state: str) -> set[str]:
    """返回当前课堂状态允许的输入动作，供 Graph 路由和 Controller 复核。"""
    return set(_CLASSROOM_ALLOWED_ACTIONS.get(current_state, set()))
```

- [ ] **Step 4：定义结构化类型**

在 `employee_training_intent.py` 新增：

```python
"""员工培训课堂自由文本意图路由。"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DomainCommand(BaseModel):
    """由自然语言解析出的领域事件候选，执行前仍需 Controller 校验。"""

    eventType: str
    payload: dict[str, Any] = Field(default_factory=dict)


class TextIntentResult(BaseModel):
    """自由文本分类结果；不直接授予状态修改权限。"""

    intent: Literal[
        "domain_command",
        "course_qa",
        "teaching_adjustment",
        "multi_tool_task",
        "classroom_meta",
        "content_feedback",
        "off_topic",
    ]
    command: DomainCommand | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str


class IntentRouteContext(BaseModel):
    """分类器所需的最小课堂上下文。"""

    currentState: str
    allowedActions: list[str]
    currentQuestion: dict[str, Any] | None = None
    courseSummary: str = ""
    recentMessages: list[dict[str, str]] = Field(default_factory=list)
    availableSkills: list[str] = Field(default_factory=list)
```

- [ ] **Step 5：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_intent.py -q
python -m py_compile backend/app/services/agent_runtime/graphs/employee_training_intent.py
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/training_classroom_service.py backend/app/services/agent_runtime/graphs/employee_training_intent.py backend/app/tests/unit/test_employee_training_intent.py
git commit -m "feat: define classroom intent routing types"
```

## 4. Task 2：实现规则优先的结构化意图分类

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/employee_training_intent.py`
- Modify: `backend/app/services/training_skill_registry_service.py`
- Modify: `backend/app/tests/unit/test_employee_training_intent.py`
- Modify: `backend/app/tests/unit/test_training_skill_registry_service.py`

- [ ] **Step 1：写失败测试，验证页面事件不会调用分类模型**

```python
from unittest.mock import Mock

from app.services.agent_runtime.graphs.employee_training_intent import resolve_text_intent


def test_explicit_continue_rule_does_not_call_model_when_only_one_safe_action():
    classifier = Mock()

    result = resolve_text_intent(
        query="继续",
        context=IntentRouteContext(
            currentState="PLAN",
            allowedActions=["continue"],
        ),
        classifier=classifier,
    )

    assert result.command.eventType == "continue"
    classifier.assert_not_called()
```

- [ ] **Step 2：写失败测试，验证模糊“继续”要求澄清**

```python
def test_continue_rule_requires_clarification_when_multiple_safe_actions_exist():
    classifier = Mock()

    result = resolve_text_intent(
        query="继续",
        context=IntentRouteContext(
            currentState="SUMMARY",
            allowedActions=["next_section", "complete"],
        ),
        classifier=classifier,
    )

    assert result.intent == "clarification_required"
    classifier.assert_not_called()
```

- [ ] **Step 3：补充路由决策类型和快捷规则**

`TextIntentResult` 只表示模型分类结果。增加 Graph 使用的决策类型：

```python
class TextRouteDecision(BaseModel):
    """Graph 可执行的文本路由决策。"""

    intent: Literal[
        "domain_command",
        "course_qa",
        "teaching_adjustment",
        "multi_tool_task",
        "classroom_meta",
        "content_feedback",
        "off_topic",
        "clarification_required",
        "forbidden",
    ]
    command: DomainCommand | None = None
    confidence: float = Field(ge=0, le=1)
    reason: str
```

实现：

```python
_FORBIDDEN_TERMS = ("跳过测验", "直接完成课程", "修改评分", "查看其他学员成绩")
_REPEAT_TERMS = {"重复一下", "再讲一遍", "讲简单一点", "举个例子"}


def _resolve_rule_decision(query: str, context: IntentRouteContext) -> TextRouteDecision | None:
    """优先处理语义稳定的文本，避免不必要的模型调用。"""
    normalized = query.strip().replace(" ", "")
    if any(term in normalized for term in _FORBIDDEN_TERMS):
        return TextRouteDecision(intent="forbidden", confidence=1, reason="命中越权或绕流程规则")
    if normalized in _REPEAT_TERMS:
        return TextRouteDecision(intent="teaching_adjustment", confidence=1, reason="命中讲解调节快捷规则")
    if normalized in {"继续", "下一步", "听懂了", "明白了"}:
        candidates = [action for action in context.allowedActions if action in {"continue", "next_section", "complete"}]
        if candidates == ["continue"]:
            return TextRouteDecision(
                intent="domain_command",
                command=DomainCommand(eventType="continue"),
                confidence=1,
                reason="当前只有一个安全继续动作",
            )
        return TextRouteDecision(intent="clarification_required", confidence=1, reason="继续动作存在多个解释")
    return None
```

- [ ] **Step 4：实现 LangChain 结构化分类**

```python
def create_text_intent_classifier(model):
    """绑定结构化输出，确保分类模型只能返回约定 Schema。"""
    return model.with_structured_output(TextIntentResult)


def resolve_text_intent(*, query: str, context: IntentRouteContext, classifier) -> TextRouteDecision:
    """规则不足时调用一次结构化分类模型，再转换为 Graph 决策。"""
    rule_decision = _resolve_rule_decision(query, context)
    if rule_decision:
        return rule_decision
    result = classifier.invoke(
        {
            "query": query,
            "currentState": context.currentState,
            "allowedActions": context.allowedActions,
            "currentQuestion": context.currentQuestion,
            "courseSummary": context.courseSummary,
            "recentMessages": context.recentMessages,
            "availableSkills": context.availableSkills,
        }
    )
    if result.intent == "domain_command" and (result.command is None or result.confidence < 0.85):
        return TextRouteDecision(intent="clarification_required", confidence=result.confidence, reason=result.reason)
    if result.confidence < 0.60:
        return TextRouteDecision(intent="clarification_required", confidence=result.confidence, reason=result.reason)
    return TextRouteDecision(**result.model_dump())
```

- [ ] **Step 5：收紧 `classifyIntent` Skill Schema**

将 `training_skill_registry_service.py` 中 `classifyIntent` 的输出 Schema 更新为七类枚举，并增加 `command`、`confidence` 和 `reason`。该 Skill 只由 Graph 的分类节点调用，不暴露给多工具 Agent 自行决定是否调用。

- [ ] **Step 6：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_intent.py backend/app/tests/unit/test_training_skill_registry_service.py -q
```

Expected: PASS。

- [ ] **Step 7：提交**

```powershell
git add backend/app/services/agent_runtime/graphs/employee_training_intent.py backend/app/services/training_skill_registry_service.py backend/app/tests/unit/test_employee_training_intent.py backend/app/tests/unit/test_training_skill_registry_service.py
git commit -m "feat: classify classroom text intents with structured output"
```

## 5. Task 3：校验自然语言领域命令并复用 Controller

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/employee_training_intent.py`
- Modify: `backend/app/tests/unit/test_employee_training_intent.py`

- [ ] **Step 1：写失败测试，验证合法答题命令可转换**

```python
from app.services.agent_runtime.graphs.employee_training_intent import validate_domain_command


def test_submit_answer_command_is_allowed_in_quiz():
    command = DomainCommand(
        eventType="submit_quiz",
        payload={"questionId": "Q-1", "answer": "B"},
    )

    result = validate_domain_command(command, allowed_actions={"submit_quiz", "query"})

    assert result.allowed is True
    assert result.command == command
```

- [ ] **Step 2：写失败测试，验证非法推进被拒绝**

```python
def test_next_section_command_is_rejected_outside_summary():
    result = validate_domain_command(
        DomainCommand(eventType="next_section"),
        allowed_actions={"continue", "query"},
    )

    assert result.allowed is False
    assert result.reason == "当前阶段不允许执行 next_section"
```

- [ ] **Step 3：实现白名单和参数校验**

```python
class DomainCommandValidation(BaseModel):
    """自然语言领域命令校验结果。"""

    allowed: bool
    command: DomainCommand | None = None
    reason: str


_DOMAIN_COMMANDS = {
    "start",
    "continue",
    "start_plan",
    "start_quiz",
    "submit_answer",
    "submit_quiz",
    "retry_teach",
    "retry_quiz",
    "next_section",
    "complete",
}


def validate_domain_command(command: DomainCommand, *, allowed_actions: set[str]) -> DomainCommandValidation:
    """校验模型生成的领域事件候选，禁止绕过 Controller。"""
    if command.eventType not in _DOMAIN_COMMANDS:
        return DomainCommandValidation(allowed=False, reason=f"未知课堂动作 {command.eventType}")
    if command.eventType not in allowed_actions:
        return DomainCommandValidation(allowed=False, reason=f"当前阶段不允许执行 {command.eventType}")
    if command.eventType in {"submit_answer", "submit_quiz"}:
        if not command.payload.get("questionId") or not str(command.payload.get("answer", "")).strip():
            return DomainCommandValidation(allowed=False, reason="提交答案缺少 questionId 或 answer")
    return DomainCommandValidation(allowed=True, command=command, reason="校验通过")
```

- [ ] **Step 4：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_intent.py -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime/graphs/employee_training_intent.py backend/app/tests/unit/test_employee_training_intent.py
git commit -m "feat: validate natural language classroom commands"
```

## 6. Task 4：拆分领域执行结果和最终回复生成

**Files:**

- Modify: `backend/app/schemas/training_classroom.py`
- Modify: `backend/app/services/training_classroom_service.py`
- Modify: `backend/app/tests/unit/test_training_classroom_section_boundary.py`

- [ ] **Step 1：写失败测试，验证页面事件返回确定性响应策略**

```python
from app.services.training_classroom_service import resolve_classroom_response_mode


def test_wrong_quiz_answer_requests_rag_explanation():
    assert resolve_classroom_response_mode(
        event_type="submit_quiz",
        result_state="GRADE",
        response_context={"passed": False},
    ) == "rag_explain"


def test_next_section_requests_teaching_narration():
    assert resolve_classroom_response_mode(
        event_type="next_section",
        result_state="TEACH",
        response_context={},
    ) == "teaching_narration"
```

- [ ] **Step 2：增加内部领域结果 DTO**

在 `training_classroom.py` 增加：

```python
from typing import Any, Literal


class ClassroomDomainResult(BaseModel):
    """课堂领域事件结果；Graph 根据响应策略生成最终回复。"""

    eventType: str
    resultState: str
    responseMode: Literal["template", "teaching_narration", "rag_explain", "agent_task"]
    responseContext: dict[str, Any] = Field(default_factory=dict)
    visibleContent: str
    uiActions: list[ClassroomUiActionDTO] = Field(default_factory=list)
    citations: list[ClassroomCitationDTO] = Field(default_factory=list)
    progressUpdate: ClassroomProgressUpdateDTO | None = None
```

- [ ] **Step 3：增加确定性响应策略**

```python
def resolve_classroom_response_mode(*, event_type: str, result_state: str, response_context: dict[str, Any]) -> str:
    """根据领域结果选择回复策略，不把课堂流程控制交给模型。"""
    if event_type in {"start_plan", "retry_teach", "next_section"} and result_state == "TEACH":
        return "teaching_narration"
    if event_type in {"submit_answer", "submit_quiz"} and result_state == "GRADE" and not response_context.get("passed", False):
        return "rag_explain"
    return "template"
```

- [ ] **Step 4：抽取领域执行函数，保留 Legacy 兼容行为**

将 `submit_classroom_event()` 当前各业务分支中的状态校验、进度更新、评分和事件结果组装抽取到：

```python
def apply_classroom_domain_event(
    session: Session,
    credential: str,
    session_id: str,
    request: Any,
) -> ClassroomDomainResult:
    """执行标准课堂领域事件；只允许 Controller 修改权威业务状态。"""
```

保留现有公开入口：

```python
def submit_classroom_event(session: Session, credential: str, session_id: str, request: Any) -> ClassroomEventResponse:
    """执行 Legacy 课堂事件，并保持现有 API 行为兼容。"""
    result = apply_classroom_domain_event(session, credential, session_id, request)
    return persist_classroom_domain_response(session, session_id=session_id, result=result)
```

约束：

- `apply_classroom_domain_event()` 继续复用现有状态判断和领域服务。
- `persist_classroom_domain_response()` 继续写入 `training_classroom_events`、助手消息和课堂状态。
- Legacy 测试必须保持通过。
- Graph Primary 只能调用 `apply_classroom_domain_event()`，不能重新实现状态转移。

- [ ] **Step 5：运行现有课堂回归**

```powershell
python -m pytest backend/app/tests/unit/test_training_classroom_section_boundary.py backend/app/tests/unit/test_training_security_boundary.py backend/app/tests/integration/test_training_e2e_acceptance.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/schemas/training_classroom.py backend/app/services/training_classroom_service.py backend/app/tests/unit/test_training_classroom_section_boundary.py
git commit -m "refactor: separate classroom domain events from responses"
```

## 7. Task 5：增加课堂 Graph 路由节点

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/employee_training_graph.py`
- Create: `backend/app/tests/unit/test_employee_training_graph_routing.py`

- [ ] **Step 1：写失败测试，验证页面事件直达 Controller**

```python
def test_button_event_skips_classifier_and_calls_domain_controller(graph_factory):
    classifier = Mock()
    run_domain_event = Mock(return_value={"resultState": "PLAN", "responseMode": "template"})
    graph = graph_factory(classifier=classifier, run_domain_event=run_domain_event)

    graph.invoke(
        {"sessionId": "s1", "eventType": "start", "payload": {}, "requestId": "r1"},
        {"configurable": {"thread_id": "s1"}},
    )

    classifier.assert_not_called()
    run_domain_event.assert_called_once()
```

- [ ] **Step 2：写失败测试，验证自然语言答题汇入 Controller**

```python
def test_text_answer_command_reuses_domain_controller(graph_factory):
    classifier = Mock(
        return_value=TextRouteDecision(
            intent="domain_command",
            command=DomainCommand(eventType="submit_quiz", payload={"questionId": "Q-1", "answer": "B"}),
            confidence=0.99,
            reason="明确选择答案",
        )
    )
    run_domain_event = Mock(return_value={"resultState": "GRADE", "responseMode": "rag_explain"})
    graph = graph_factory(classifier=classifier, run_domain_event=run_domain_event, current_state="QUIZ")

    graph.invoke(
        {"sessionId": "s1", "eventType": "query", "query": "我选 B", "requestId": "r2"},
        {"configurable": {"thread_id": "s1"}},
    )

    assert run_domain_event.call_args.kwargs["request"].eventType == "submit_quiz"
```

- [ ] **Step 3：扩充 Graph State**

```python
class EmployeeTrainingState(TypedDict, total=False):
    """课堂 Graph 运行态；领域业务真值仍保存在 PostgreSQL。"""

    sessionId: str
    requestId: str
    eventType: str
    payload: dict[str, Any]
    query: str
    currentState: str
    allowedActions: list[str]
    textDecision: dict[str, Any]
    domainResult: dict[str, Any]
    responseMode: str
    visibleContent: str
    citations: list[dict[str, Any]]
    pendingActions: list[dict[str, Any]]
```

- [ ] **Step 4：建立节点和条件边**

Graph 至少包含：

```text
load_context
get_allowed_actions
route_input
classify_text_intent
parse_domain_command
validate_domain_command
check_idempotency
run_domain_event
answer_course_question
regenerate_teaching_response
run_skill_agent
query_classroom_status
record_content_feedback
build_guidance_response
request_clarification
compose_response
persist_and_checkpoint
```

关键约束：

- `route_input` 只判断载体，不做自然语言语义判断。
- `run_domain_event` 只调用 `apply_classroom_domain_event()`。
- `answer_course_question` 使用 P1 的 `build_rag_answer_agent()`，其内部必须调用 `QARun Tool`。
- `run_skill_agent` 只取得 `skill_adapter.select_allowed_skills()` 返回的白名单。
- `persist_and_checkpoint` 统一保存完整消息、运行审计和 Checkpoint。

- [ ] **Step 5：运行路由测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_graph_routing.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime/graphs/employee_training_graph.py backend/app/tests/unit/test_employee_training_graph_routing.py
git commit -m "feat: route classroom events through employee training graph"
```

## 8. Task 6：接入 Runtime Facade，保留双轨切换

**Files:**

- Modify: `backend/app/services/agent_runtime/runtime_facade.py`
- Modify: `backend/app/api/routes/training_classroom.py`
- Create: `backend/app/tests/integration/test_employee_training_graph_orchestration.py`

- [ ] **Step 1：写失败测试，验证 Legacy 仍走旧入口**

```python
def test_legacy_runtime_keeps_existing_classroom_service():
    submit_legacy = Mock(return_value={"classroomState": "PLAN"})
    submit_training_classroom_runtime_event(
        runtime_version="legacy_v1",
        submit_legacy=submit_legacy,
        invoke_graph=Mock(),
        run_shadow=Mock(),
    )
    submit_legacy.assert_called_once()
```

- [ ] **Step 2：写失败测试，验证 Primary 只走 Graph**

```python
def test_primary_runtime_does_not_execute_legacy_path():
    submit_legacy = Mock()
    invoke_graph = Mock(return_value={"classroomState": "PLAN"})
    submit_training_classroom_runtime_event(
        runtime_version="langgraph_primary_v1",
        submit_legacy=submit_legacy,
        invoke_graph=invoke_graph,
        run_shadow=Mock(),
    )
    invoke_graph.assert_called_once()
    submit_legacy.assert_not_called()
```

- [ ] **Step 3：在 Facade 增加课堂入口**

```python
def submit_training_classroom_runtime_event(
    *,
    runtime_version: str,
    submit_legacy,
    invoke_graph,
    run_shadow,
):
    """按会话固定版本提交课堂事件，避免单次请求混跑两套主链路。"""
    resolved = resolve_runtime_version(runtime_version)
    if resolved is RuntimeVersion.LEGACY:
        return submit_legacy()
    if resolved is RuntimeVersion.LANGGRAPH_SHADOW:
        response = submit_legacy()
        run_shadow()
        return response
    return invoke_graph()
```

- [ ] **Step 4：路由层改用 Facade**

`training_classroom.py` 的事件 API 仍保持原有 URL 和 DTO，但内部调用改为 `submit_training_classroom_runtime_event()`。会话创建后必须使用持久化的 `runtimeVersion`，不得允许请求覆盖。

- [ ] **Step 5：运行测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_graph_orchestration.py backend/app/tests/integration/test_training_e2e_acceptance.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime/runtime_facade.py backend/app/api/routes/training_classroom.py backend/app/tests/integration/test_employee_training_graph_orchestration.py
git commit -m "feat: submit classroom events through runtime facade"
```

## 9. Task 7：增加 `requestId` 幂等保护

**Files:**

- Modify: `backend/app/schemas/training_classroom.py`
- Modify: `backend/app/tables.py`
- Create: `backend/migrations/versions/0042_add_training_classroom_event_request_id.py`
- Modify: `backend/app/services/training_classroom_service.py`
- Modify: `backend/app/tests/integration/test_employee_training_graph_orchestration.py`

- [ ] **Step 1：写失败测试，验证重复提交只推进一次**

```python
def test_duplicate_request_id_returns_previous_result_without_second_state_change(classroom_runtime):
    first = classroom_runtime.submit(event_type="continue", request_id="REQ-001")
    second = classroom_runtime.submit(event_type="continue", request_id="REQ-001")

    assert second.eventId == first.eventId
    assert classroom_runtime.count_events(request_id="REQ-001") == 1
```

- [ ] **Step 2：增加 DTO 和数据库字段**

`ClassroomEventSubmitRequest` 增加：

```python
requestId: str | None = Field(default=None, min_length=1, max_length=64)
```

`training_classroom_events` 增加：

```python
sa.Column("request_id", sa.String(length=64), nullable=True),
sa.UniqueConstraint("session_id", "request_id", name="uq_training_classroom_events_session_request"),
```

- [ ] **Step 3：保存首次响应快照并增加幂等查询**

`persist_classroom_domain_response()` 写入事件时，在原业务 `payload` 的 `_runtime` 子对象中保存最小响应快照：

```python
event_payload = {
    **result.responseContext,
    "_runtime": {
        "requestId": request_id,
        "responseSnapshot": response.model_dump(mode="json"),
    },
}
```

快照只保存已授权的 API 响应，不保存未裁剪 Evidence、Provider 密钥或内部 Trace。

```python
def read_classroom_event_by_request_id(session: Session, *, session_id: str, request_id: str | None):
    """读取同一课堂请求的首次事件结果；未提供 requestId 时保持旧行为。"""
    if not request_id:
        return None
    return session.execute(
        select(training_classroom_events)
        .where(training_classroom_events.c.session_id == session_id)
        .where(training_classroom_events.c.request_id == request_id)
        .limit(1)
    ).mappings().first()
```

Graph 的 `check_idempotency` 在任何有副作用节点前调用。Legacy 路径也调用相同函数，避免双轨行为不一致。

- [ ] **Step 4：运行测试和迁移语法检查**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_graph_orchestration.py -q
python -m py_compile backend/migrations/versions/0042_add_training_classroom_event_request_id.py
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/schemas/training_classroom.py backend/app/tables.py backend/migrations/versions/0042_add_training_classroom_event_request_id.py backend/app/services/training_classroom_service.py backend/app/tests/integration/test_employee_training_graph_orchestration.py
git commit -m "feat: make classroom event submission idempotent"
```

## 10. Task 8：补齐场景分支和降级

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/employee_training_graph.py`
- Modify: `backend/app/tests/unit/test_employee_training_graph_routing.py`
- Modify: `backend/app/tests/integration/test_employee_training_graph_orchestration.py`

- [ ] **Step 1：增加参数化分支测试**

```python
@pytest.mark.parametrize(
    ("intent", "expected_node"),
    [
        ("course_qa", "answer_course_question"),
        ("teaching_adjustment", "regenerate_teaching_response"),
        ("multi_tool_task", "run_skill_agent"),
        ("classroom_meta", "query_classroom_status"),
        ("content_feedback", "record_content_feedback"),
        ("off_topic", "build_guidance_response"),
        ("clarification_required", "request_clarification"),
        ("forbidden", "build_guidance_response"),
    ],
)
def test_text_intent_routes_to_expected_node(graph_factory, intent, expected_node):
    graph = graph_factory(text_decision=intent)
    result = graph.invoke(
        {"sessionId": "s1", "eventType": "query", "query": "测试输入"},
        {"configurable": {"thread_id": "s1"}},
    )
    assert result["handledBy"] == expected_node
```

- [ ] **Step 2：写分类失败降级测试**

```python
def test_classifier_failure_keeps_state_and_requests_clarification(graph_factory):
    graph = graph_factory(classifier=Mock(side_effect=RuntimeError("provider timeout")))

    result = graph.invoke(
        {"sessionId": "s1", "eventType": "query", "query": "继续处理"},
        {"configurable": {"thread_id": "s1"}},
    )

    assert result["classroomState"] == "TEACH"
    assert result["handledBy"] == "request_clarification"
```

- [ ] **Step 3：写无 Evidence 拒答测试**

```python
def test_course_question_without_authorized_evidence_returns_grounded_refusal(graph_factory):
    graph = graph_factory(rag_answer={"answer": "", "citations": [], "runId": "run-1"})

    result = graph.invoke(
        {"sessionId": "s1", "eventType": "query", "query": "材料里是否提到了某品牌？"},
        {"configurable": {"thread_id": "s1"}},
    )

    assert "未找到可靠依据" in result["visibleContent"]
```

- [ ] **Step 4：实现分支节点**

要求：

- `course_qa` 调用 P1 `build_rag_answer_agent()` 和 `QARun Tool`。
- `teaching_adjustment` 读取当前章节和最近讲解，不推进领域状态。
- `classroom_meta` 只读取当前学员进度。
- `content_feedback` 写入课堂事件审计，不修改评分和完成状态。
- `off_topic` 需要进入现有 `OFF_TOPIC` 状态时调用 Controller，不能由 Graph 直接更新状态。
- `off_topic` 和 `forbidden` 返回不同审计类型。
- 分类、QARun 或 Skill 失败时保留当前领域状态。

- [ ] **Step 5：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_graph_routing.py backend/app/tests/integration/test_employee_training_graph_orchestration.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime/graphs/employee_training_graph.py backend/app/tests/unit/test_employee_training_graph_routing.py backend/app/tests/integration/test_employee_training_graph_orchestration.py
git commit -m "feat: handle classroom graph intent branches"
```

## 11. Task 9：完成审计、恢复和性能验证

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/employee_training_graph.py`
- Modify: `backend/app/tests/integration/test_employee_training_graph_orchestration.py`
- Modify: `backend/app/tests/integration/test_employee_training_runtime_parity.py`

- [ ] **Step 1：验证审计关联**

集成测试断言一次自然语言答题至少可关联：

```text
threadId
checkpointId
sessionId
requestId
intent
skillCallId
eventId
qaRunId（仅调用 QARun 时存在）
runtimeVersion
```

- [ ] **Step 2：验证 Checkpoint 恢复不重复副作用**

模拟 `run_domain_event` 成功后 Checkpoint 写入失败，再次恢复相同 `requestId`：

```python
def test_resume_does_not_repeat_domain_side_effect_after_checkpoint_failure(classroom_runtime):
    classroom_runtime.fail_checkpoint_after_domain_event_once()

    classroom_runtime.submit(event_type="continue", request_id="REQ-009")
    classroom_runtime.resume(request_id="REQ-009")

    assert classroom_runtime.count_events(request_id="REQ-009") == 1
```

- [ ] **Step 3：验证新老路径一致性**

固定数据集分别运行 `legacy_v1` 和 `langgraph_primary_v1`，比较：

```text
课堂状态
uiActions
错误码
进度记录
评分记录
完整消息数量
越权拒绝结果
重复提交结果
QARun Citation 授权范围
```

- [ ] **Step 4：记录性能指标**

固定样本至少记录：

```text
页面事件总耗时 P50、P95
自由文本规则命中率
分类模型调用次数
分类模型耗时 P50、P95
QARun Tool 调用耗时
Checkpoint get/put 耗时
摘要压缩触发次数
幂等命中次数
分类降级次数和原因
```

- [ ] **Step 5：运行课堂专项回归**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_intent.py backend/app/tests/unit/test_employee_training_graph_routing.py backend/app/tests/unit/test_training_skill_registry_service.py backend/app/tests/unit/test_training_classroom_section_boundary.py backend/app/tests/unit/test_training_resume_memory.py backend/app/tests/unit/test_training_security_boundary.py backend/app/tests/integration/test_employee_training_graph_orchestration.py backend/app/tests/integration/test_employee_training_langgraph_memory.py backend/app/tests/integration/test_employee_training_langgraph_resume.py backend/app/tests/integration/test_employee_training_runtime_parity.py backend/app/tests/integration/test_training_e2e_acceptance.py -q
python -m compileall backend/app
git diff --check
```

Expected: PASS。

- [ ] **Step 6：执行 Code Review 门禁**

评审必须确认：

- 页面按钮不调用意图分类模型。
- 自由文本规则不足时才调用一次结构化分类模型。
- `classifyIntent` 真实调用 LangChain 结构化输出，不是只写审计名称。
- 自然语言领域命令和页面事件汇入同一个 Controller。
- `responseMode` 由确定性策略生成，不由模型自由决定。
- LangChain Agent、Skill 和 Graph 条件边不能绕过 Controller 修改状态。
- 相同 `sessionId + requestId` 不重复推进状态。
- Checkpoint 重放不会重复执行领域副作用。
- 无授权 Evidence 时稳定拒答。
- Trace 可定位 Graph 节点、分类模型、Skill、QARun 和 Controller 事件。

- [ ] **Step 7：提交评审修复**

```powershell
git add backend
git commit -m "test: harden employee training graph orchestration"
```

## 12. 完成定义

- `EmployeeTrainingGraph` 覆盖页面事件、自由文本、恢复和异常路径。
- 页面事件直接进入标准领域事件，不产生额外分类模型调用。
- 自然语言领域命令经过规则、结构化分类、程序校验和 Controller 校验。
- 课堂状态推进、评分、进度和完成判定仍只有现有 Controller 一套实现。
- 页面事件可按确定性 `responseMode` 触发模板、教学讲解或错题解释。
- 多工具任务只暴露经过 Skill Registry 过滤的白名单能力。
- 幂等、Checkpoint 恢复、无 Evidence 拒答、降级和审计均有测试证据。
- Legacy、Shadow 和 Primary 路径职责清晰，没有混跑两套有副作用实现。
