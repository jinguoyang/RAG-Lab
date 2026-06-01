# 员工培训课堂 LangGraph 接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 用途：本文是 LangChain 与 LangGraph 平台 Runtime 第二阶段实施计划，属于执行依据。执行前必须完成 `2026-06-01-agent-runtime-platform-foundation.md`。

**Goal:** 将员工培训课堂接入 LangGraph Session、Checkpoint 和官方摘要压缩，同时保留现有课堂领域 Controller 作为唯一状态机和业务真值。

**Architecture:** 新建 `EmployeeTrainingGraph`，用 `thread_id = classroom_session_id` 固定绑定课堂会话。Graph 负责编排、Checkpoint、恢复、追问 Tool 和摘要压缩；现有 `training_classroom_service.py` 继续负责状态流转、评分、进度、权限和结构化动作。按 `legacy_v1 -> langgraph_shadow_v1 -> langgraph_primary_v1` 渐进切换。

**Tech Stack:** Python、FastAPI、SQLAlchemy、PostgreSQL、pytest、LangChain、LangGraph、现有 QARun、现有培训领域服务。

**Design Spec:** `docs/04-迭代与交付/specs/2026-06-01-langchain-langgraph-agent-runtime-spec.md`

---

## 1. 范围边界

本阶段必须完成：

- 课堂会话固定记录 `runtimeVersion`。
- 新建课堂 Graph State 和节点。
- Shadow 模式只镜像状态和上下文构建结果。
- Primary 模式使用 LangGraph Checkpoint 和 P1 提供的 LangChain RAG Agent；该 Agent 内部固定挂载 QARun Tool 和官方摘要中间件。
- 长对话使用 LangChain 官方摘要中间件。
- 摘要成功后同步业务摘要镜像。
- 摘要失败时保留旧摘要和最近窗口，不阻断课堂。
- 恢复时返回业务状态、最近消息、业务摘要和待处理动作。
- 完成长对话、恢复、权限、性能和双轨对照测试。

本阶段不做：

- 不复制课堂状态机。
- 不删除现有 `training_classroom_messages`。
- 不删除旧路径。
- 不接入内部客服。
- 不让模型直接推进课堂状态。

## 2. 文件结构

### 新增文件

```text
backend/app/services/agent_runtime/graphs/__init__.py
backend/app/services/agent_runtime/graphs/employee_training_graph.py
backend/app/tests/unit/test_employee_training_langgraph.py
backend/app/tests/integration/test_employee_training_langgraph_resume.py
backend/app/tests/integration/test_employee_training_langgraph_memory.py
backend/app/tests/integration/test_employee_training_runtime_parity.py
```

### 修改文件

```text
backend/app/services/agent_runtime/runtime_facade.py
backend/app/services/agent_runtime/scenario_registry.py
backend/app/services/training_classroom_service.py
backend/app/schemas/training_classroom.py
backend/app/tables.py
backend/migrations/versions/0041_add_training_runtime_version.py
backend/app/tests/unit/test_training_resume_memory.py
backend/app/tests/integration/test_training_e2e_acceptance.py
```

## 3. Task 1：持久化课堂 Runtime 版本

**Files:**

- Modify: `backend/app/tables.py`
- Create: `backend/migrations/versions/0041_add_training_runtime_version.py`
- Modify: `backend/app/services/training_classroom_service.py`
- Test: `backend/app/tests/unit/test_employee_training_langgraph.py`

- [ ] **Step 1：写失败测试，验证会话创建时固定版本**

```python
from unittest.mock import patch

from app.services.training_classroom_service import create_classroom_session


def test_create_classroom_session_persists_runtime_version(db, classroom_request):
    with patch("app.services.training_classroom_service.resolve_training_context") as resolve:
        resolve.return_value.app_row = {"app_id": "app-001"}
        response = create_classroom_session(db, "credential", classroom_request)

    row = db.execute(training_classroom_sessions.select()).mappings().one()
    assert row["runtime_version"] == "legacy_v1"
    assert response.metadata["runtimeVersion"] == "legacy_v1"
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_langgraph.py::test_create_classroom_session_persists_runtime_version -q
```

Expected: FAIL，提示缺少 `runtime_version`。

- [ ] **Step 3：增加字段和迁移**

在 `training_classroom_sessions` 增加：

```python
sa.Column("runtime_version", sa.String(length=32), nullable=False, server_default="legacy_v1"),
```

迁移：

```python
def upgrade() -> None:
    op.add_column(
        "training_classroom_sessions",
        sa.Column("runtime_version", sa.String(length=32), nullable=False, server_default="legacy_v1"),
    )


def downgrade() -> None:
    op.drop_column("training_classroom_sessions", "runtime_version")
```

创建课堂会话时显式写入：

```python
runtime_version=get_settings().agent_runtime_default_version,
```

- [ ] **Step 4：运行测试和迁移语法检查**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_langgraph.py::test_create_classroom_session_persists_runtime_version -q
python -m py_compile backend/migrations/versions/0041_add_training_runtime_version.py
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/tables.py backend/migrations/versions/0041_add_training_runtime_version.py backend/app/services/training_classroom_service.py backend/app/tests/unit/test_employee_training_langgraph.py
git commit -m "feat: persist training classroom runtime version"
```

## 4. Task 2：建立课堂 Graph State 和无副作用 Shadow

**Files:**

- Create: `backend/app/services/agent_runtime/graphs/__init__.py`
- Create: `backend/app/services/agent_runtime/graphs/employee_training_graph.py`
- Modify: `backend/app/services/agent_runtime/scenario_registry.py`
- Modify: `backend/app/services/agent_runtime/runtime_facade.py`
- Modify: `backend/app/tests/unit/test_employee_training_langgraph.py`

- [ ] **Step 1：写失败测试，验证 Shadow 不执行模型、QARun 和领域写操作**

```python
from unittest.mock import Mock

from app.services.agent_runtime.graphs.employee_training_graph import build_employee_training_graph


def test_training_shadow_graph_projects_state_without_side_effects():
    invoke_rag_agent = Mock()
    invoke_domain_event = Mock()
    graph = build_employee_training_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=invoke_rag_agent,
        invoke_domain_event=invoke_domain_event,
        shadow=True,
    )

    result = graph.invoke(
        {"sessionId": "s1", "runtimeVersion": "langgraph_shadow_v1", "eventType": "query", "query": "解释一下"},
        {"configurable": {"thread_id": "s1"}},
    )

    assert result["sessionId"] == "s1"
    invoke_rag_agent.assert_not_called()
    invoke_domain_event.assert_not_called()
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_langgraph.py::test_training_shadow_graph_projects_state_without_side_effects -q
```

Expected: FAIL，提示 Graph 模块不存在。

- [ ] **Step 3：实现最小 Graph**

```python
"""员工培训课堂 LangGraph 编排。"""
from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph


class EmployeeTrainingState(TypedDict, total=False):
    """课堂 Graph 运行态；业务真值仍保存在课堂表。"""

    sessionId: str
    runtimeVersion: str
    eventType: str
    query: str
    currentState: str
    visibleContent: str
    citations: list[dict[str, Any]]


def build_employee_training_graph(*, checkpointer, invoke_rag_agent, invoke_domain_event, shadow: bool):
    """构建课堂 Graph；Shadow 只投影输入，Primary 才执行受控节点。"""
    builder = StateGraph(EmployeeTrainingState)

    def project_state(state: EmployeeTrainingState) -> EmployeeTrainingState:
        return dict(state)

    builder.add_node("project_state", project_state)
    builder.add_edge(START, "project_state")
    builder.add_edge("project_state", END)
    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 4：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_langgraph.py -q
```

Expected: PASS。

- [ ] **Step 5：注册课堂 Graph Builder**

在 `scenario_registry.py` 增加员工培训 builder 注册，不在 Facade 内写死分支。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime backend/app/tests/unit/test_employee_training_langgraph.py
git commit -m "feat: add side-effect-free training shadow graph"
```

## 5. Task 3：Primary 模式调用现有领域 Controller 和 LangChain RAG Agent

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/employee_training_graph.py`
- Modify: `backend/app/services/agent_runtime/runtime_facade.py`
- Modify: `backend/app/services/training_classroom_service.py`
- Modify: `backend/app/tests/unit/test_employee_training_langgraph.py`

- [ ] **Step 1：写失败测试，验证按钮事件只调用现有 Controller**

```python
def test_training_primary_graph_routes_button_event_to_existing_controller():
    invoke_domain_event = Mock(return_value={"currentState": "PLAN", "visibleContent": "学习计划"})
    invoke_rag_agent = Mock()
    graph = build_employee_training_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=invoke_rag_agent,
        invoke_domain_event=invoke_domain_event,
        shadow=False,
    )

    result = graph.invoke(
        {"sessionId": "s1", "eventType": "start"},
        {"configurable": {"thread_id": "s1"}},
    )

    assert result["currentState"] == "PLAN"
    invoke_domain_event.assert_called_once()
    invoke_rag_agent.assert_not_called()
```

- [ ] **Step 2：写失败测试，验证文本追问通过可复用 LangChain RAG Agent**

```python
def test_training_primary_graph_routes_query_to_qarun_tool():
    invoke_rag_agent = Mock(return_value={"answer": "授权回答", "runId": "run-1", "citations": []})
    graph = build_employee_training_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=invoke_rag_agent,
        invoke_domain_event=Mock(),
        shadow=False,
    )

    result = graph.invoke(
        {"sessionId": "s1", "eventType": "query", "query": "解释一下"},
        {"configurable": {"thread_id": "s1"}},
    )

    assert result["visibleContent"] == "授权回答"
    assert result["qaRunId"] == "run-1"
    invoke_rag_agent.assert_called_once_with("解释一下")
```

- [ ] **Step 3：实现条件路由**

```python
def route_event(state: EmployeeTrainingState) -> str:
    """文本追问进入受控 LangChain RAG Agent，其余事件交给现有课堂 Controller。"""
    return "answer_query" if state.get("eventType") == "query" else "domain_event"


def answer_query(state: EmployeeTrainingState) -> EmployeeTrainingState:
    result = invoke_rag_agent(state["query"])
    return {
        "visibleContent": result["answer"],
        "qaRunId": result["runId"],
        "citations": result["citations"],
    }


def domain_event(state: EmployeeTrainingState) -> EmployeeTrainingState:
    return invoke_domain_event(state)
```

Graph 必须包含：

```python
builder.add_conditional_edges("project_state", route_event, {
    "answer_query": "answer_query",
    "domain_event": "domain_event",
})
builder.add_edge("answer_query", END)
builder.add_edge("domain_event", END)
```

- [ ] **Step 4：在 Runtime Facade 中创建 P1 LangChain RAG Agent**

课堂 Graph 的 `invoke_rag_agent` 必须由 P1 `build_rag_answer_agent()` 构建，不得直接复制模型调用或 `create_qa_run()`：

```python
rag_agent = build_rag_answer_agent(
    model=create_chat_model(settings),
    qa_run_tool=create_qa_run_tool(
        session=session,
        credential=credential,
        end_user_id=end_user_id,
    ),
    checkpointer=checkpointer,
    trigger_tokens=settings.agent_runtime_summary_trigger_tokens,
    keep_messages=settings.agent_runtime_summary_keep_messages,
    system_prompt="你是员工培训课堂答疑助手。回答课程追问前必须调用 query_knowledge_base。",
)
```

- [ ] **Step 5：在课堂服务中增加单一 Facade 入口**

保留现有 `submit_classroom_event()` 作为领域 Controller。新增薄入口时只能在入口处根据固定 `runtime_version` 决定调用 Graph 或旧路径，不得在业务分支中混合两套流程。

- [ ] **Step 6：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_langgraph.py -q
python -m pytest backend/app/tests/integration/test_employee_training_agent_runtime.py -q
```

Expected: PASS。

- [ ] **Step 7：提交**

```powershell
git add backend/app/services/agent_runtime backend/app/services/training_classroom_service.py backend/app/tests/unit/test_employee_training_langgraph.py
git commit -m "feat: route training classroom through langgraph primary"
```

## 6. Task 4：接入官方摘要压缩和业务摘要镜像

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/employee_training_graph.py`
- Modify: `backend/app/services/agent_runtime/memory_service.py`
- Modify: `backend/app/services/training_classroom_service.py`
- Modify: `backend/app/tests/integration/test_employee_training_langgraph_memory.py`
- Modify: `backend/app/tests/unit/test_training_resume_memory.py`

- [ ] **Step 1：写失败测试，验证超过 token 阈值触发官方摘要中间件**

```python
from unittest.mock import patch


def test_long_classroom_thread_uses_langchain_summary_middleware(db, langgraph_classroom):
    with patch("app.services.agent_runtime.memory_service.SummarizationMiddleware.before_model") as before_model:
        langgraph_classroom.send_long_conversation(message_count=30, chars_per_message=500)

    assert before_model.called
```

- [ ] **Step 2：写失败测试，验证完整消息不会因压缩减少**

```python
def test_summary_compaction_keeps_full_classroom_message_log(db, langgraph_classroom):
    before = langgraph_classroom.count_messages()

    langgraph_classroom.trigger_summary()

    assert langgraph_classroom.count_messages() == before
    assert langgraph_classroom.read_context_summary()
```

- [ ] **Step 3：写失败测试，验证摘要失败降级**

```python
def test_summary_failure_keeps_old_summary_and_does_not_block_classroom(db, langgraph_classroom):
    langgraph_classroom.set_context_summary("旧摘要")

    with patch("app.services.agent_runtime.memory_service.SummarizationMiddleware.before_model", side_effect=RuntimeError("summary failed")):
        response = langgraph_classroom.ask("请继续解释")

    assert response.visibleContent
    assert langgraph_classroom.read_context_summary() == "旧摘要"
```

- [ ] **Step 4：实现摘要镜像同步**

在 `memory_service.py` 增加同步函数：

```python
def persist_summary_snapshot(session, *, session_id: str, summary: str, covered_message_ids: list[str]) -> None:
    """将官方摘要结果镜像到业务表；失败时调用方保留旧摘要。"""
    row = session.execute(
        select(training_classroom_sessions.c.metadata)
        .where(training_classroom_sessions.c.session_id == session_id)
        .limit(1)
    ).mappings().one()
    metadata = dict(row["metadata"] or {})
    metadata["contextSummarySnapshot"] = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "coveredMessageIds": covered_message_ids,
        "summaryVersion": 1,
    }
    session.execute(
        update(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .values(context_summary=summary, metadata=metadata)
    )
```

注意：摘要文本必须来自官方 `SummarizationMiddleware` 的结果，不得复用原 `_get_context_summary()` 截断预览作为目标实现。

- [ ] **Step 5：运行测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_langgraph_memory.py backend/app/tests/unit/test_training_resume_memory.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime backend/app/services/training_classroom_service.py backend/app/tests/integration/test_employee_training_langgraph_memory.py backend/app/tests/unit/test_training_resume_memory.py
git commit -m "feat: use langchain summarization for classroom memory"
```

## 7. Task 5：实现 Checkpoint 恢复和待处理动作恢复

**Files:**

- Modify: `backend/app/services/agent_runtime/runtime_facade.py`
- Modify: `backend/app/services/training_classroom_service.py`
- Modify: `backend/app/schemas/training_classroom.py`
- Create: `backend/app/tests/integration/test_employee_training_langgraph_resume.py`

- [ ] **Step 1：写失败测试，验证同一 `thread_id` 恢复**

```python
def test_classroom_resume_uses_same_thread_and_checkpoint(db, langgraph_classroom):
    created = langgraph_classroom.create(runtime_version="langgraph_primary_v1")
    langgraph_classroom.start(created.sessionId)
    checkpoint_before = langgraph_classroom.latest_checkpoint(created.sessionId)

    detail = langgraph_classroom.resume(created.sessionId)

    assert detail.metadata["runtimeVersion"] == "langgraph_primary_v1"
    assert detail.metadata["checkpointId"] == checkpoint_before
    assert detail.metadata["pendingActions"]
```

- [ ] **Step 2：写失败测试，验证跨 App 无法复用 thread**

```python
def test_classroom_resume_rejects_cross_app_thread(db, langgraph_classroom):
    session_id = langgraph_classroom.create_for_app("app-a").sessionId

    with pytest.raises(TrainingAgentConflictError):
        langgraph_classroom.resume(session_id, credential="app-b-key")
```

- [ ] **Step 3：实现恢复元数据**

`get_classroom_session()` 返回：

```python
metadata["runtimeVersion"] = row["runtime_version"]
metadata["checkpointId"] = checkpoint_service.latest_checkpoint_id(thread_id=session_id)
metadata["contextSummary"] = row["context_summary"]
metadata["pendingActions"] = _get_pending_actions(current_state, row, is_last)
```

- [ ] **Step 4：运行测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_langgraph_resume.py backend/app/tests/unit/test_training_security_boundary.py -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime backend/app/services/training_classroom_service.py backend/app/schemas/training_classroom.py backend/app/tests/integration/test_employee_training_langgraph_resume.py
git commit -m "feat: resume classroom from langgraph checkpoints"
```

## 8. Task 6：双轨对照、回退和性能测试

**Files:**

- Create: `backend/app/tests/integration/test_employee_training_runtime_parity.py`
- Modify: `backend/app/tests/integration/test_training_e2e_acceptance.py`

- [ ] **Step 1：写 Legacy 与 Primary 对照测试**

```python
@pytest.mark.parametrize("runtime_version", ["legacy_v1", "langgraph_primary_v1"])
def test_training_runtime_versions_keep_authoritative_state_machine(db, runtime_version):
    result = run_training_happy_path(db, runtime_version=runtime_version)

    assert result.states == [
        "PLAN",
        "TEACH",
        "CHECK_UNDERSTAND",
        "QUIZ",
        "GRADE",
        "REVIEW",
        "SUMMARY",
        "COMPLETED",
    ]
    assert result.cross_app_access_rejected is True
```

- [ ] **Step 2：写 Shadow 不重复调用测试**

```python
def test_training_shadow_does_not_duplicate_real_calls(db, classroom_fixture):
    with patch("app.services.app_runtime_service.chat_with_app_runtime") as chat:
        classroom_fixture.ask(runtime_version="langgraph_shadow_v1", query="解释一下")

    assert chat.call_count == 1
```

- [ ] **Step 3：写显式回退审计测试**

```python
def test_training_primary_failure_records_explicit_legacy_fallback(db, classroom_fixture):
    with patch("app.services.agent_runtime.runtime_facade.invoke_training_graph", side_effect=RuntimeError("checkpoint unavailable")):
        response = classroom_fixture.ask(runtime_version="langgraph_primary_v1", query="解释一下")

    assert response.metadata["runtimeFallback"]["from"] == "langgraph_primary_v1"
    assert response.metadata["runtimeFallback"]["to"] == "legacy_v1"
```

- [ ] **Step 4：运行测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_runtime_parity.py backend/app/tests/integration/test_training_e2e_acceptance.py -q
```

Expected: PASS。

- [ ] **Step 5：记录性能对照**

同一固定样本分别运行 `legacy_v1` 和 `langgraph_primary_v1`，记录：

```text
总耗时 P50、P95
Checkpoint get/put P50、P95
QARun Tool 调用耗时
摘要触发次数、成功率和额外耗时
模型调用次数
QARun 调用次数
回退次数和原因
```

- [ ] **Step 6：提交**

```powershell
git add backend/app/tests/integration
git commit -m "test: verify training langgraph parity and fallback"
```

## 9. Task 7：P2 回归与 Code Review

- [ ] **Step 1：运行课堂专项测试**

```powershell
python -m pytest backend/app/tests/unit/test_employee_training_langgraph.py backend/app/tests/unit/test_training_classroom_section_boundary.py backend/app/tests/unit/test_training_resume_memory.py backend/app/tests/unit/test_training_security_boundary.py backend/app/tests/integration/test_employee_training_langgraph_memory.py backend/app/tests/integration/test_employee_training_langgraph_resume.py backend/app/tests/integration/test_employee_training_runtime_parity.py backend/app/tests/integration/test_employee_training_agent_runtime.py backend/app/tests/integration/test_training_e2e_acceptance.py -q
```

Expected: PASS。

- [ ] **Step 2：运行平台关键回归**

```powershell
python -m pytest backend/app/tests/unit/test_app_runtime_protection.py backend/app/tests/unit/test_qa_providers.py -q
python -m compileall backend/app
git diff --check
```

Expected: PASS。

- [ ] **Step 3：执行 Code Review 门禁**

评审必须确认：

- `thread_id` 与课堂 `session_id` 固定绑定。
- Graph 调用现有领域 Controller，没有复制第二套状态机。
- Primary 模式不先执行旧路径再执行 Graph。
- Shadow 没有第二次真实 LLM 或 `QARun`。
- 长对话由官方 `SummarizationMiddleware` 处理。
- 摘要失败保留旧摘要，不阻断课堂。
- 完整消息数量不会因摘要减少。
- Trace 可定位 Checkpoint、Graph 节点、Tool、摘要和 `QARun`。
- 权限和越权状态推进回归通过。

- [ ] **Step 4：提交评审修复**

```powershell
git add backend
git commit -m "test: harden training langgraph integration"
```

## 10. P2 完成定义

- 课堂 Primary 模式真实使用 LangGraph Checkpoint 和条件路由。
- 文本追问真实通过 LangChain QARun Tool。
- 长对话真实使用 LangChain 官方摘要中间件。
- 课堂状态机仍只有现有领域 Controller 一套实现。
- 完整消息、进度、评分、审核和权限继续以业务表为真值。
- Shadow、Primary、显式回退和性能对照均有证据。
- 独立 Code Review 通过。
