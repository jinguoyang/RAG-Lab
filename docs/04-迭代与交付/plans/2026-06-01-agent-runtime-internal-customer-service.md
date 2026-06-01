# 内部客服 LangGraph 最小对照接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 用途：本文是 LangChain 与 LangGraph 平台 Runtime 第三阶段实施计划，属于执行依据。执行前必须完成平台 Runtime 基座和员工培训课堂首个接入。

**Goal:** 使用同一平台 Runtime 建立内部客服最小 Graph，验证 Session、Checkpoint、官方摘要压缩、只读 QARun Tool 和 Citation 能力可跨场景复用，且没有课堂耦合。

**Architecture:** 新建 `InternalCustomerServiceGraph`。内部客服保持轻量：加载 Thread、调用 P1 提供的 LangChain RAG Agent、校验 Citation、无证据时拒答、保存 Checkpoint 和完整消息。RAG Agent 内部固定挂载只读 QARun Tool、官方摘要中间件和调用限额中间件。使用现有 `/app-runtime/chat-messages` 入口，不新增第二套通用会话 API。

**Tech Stack:** Python、FastAPI、SQLAlchemy、PostgreSQL、pytest、LangChain、LangGraph、现有 App Runtime、现有 QARun。

**Design Spec:** `docs/04-迭代与交付/specs/2026-06-01-langchain-langgraph-agent-runtime-spec.md`

---

## 1. 范围边界

本阶段必须完成：

- 新建内部客服 Graph。
- 复用 P1 的 Runtime Facade、Checkpointer、官方摘要中间件和 QARun Tool。
- 使用 `conversation_id` 作为固定 `thread_id`。
- 支持连续追问、断线恢复、Citation 和无证据拒答。
- 证明客服 Graph 不依赖课堂模块。
- 完成框架利用率、性能和 Code Review 验收。

本阶段不做：

- 不开发工单系统。
- 不开发人工客服工作台。
- 不新增写操作 Skill。
- 不新增 SOP 和合规检查。
- 不修改 `QARun` 内部 Pipeline。
- 不复制 App Runtime 完整消息表。

## 2. 文件结构

### 新增文件

```text
backend/app/services/agent_runtime/graphs/internal_customer_service_graph.py
backend/app/tests/unit/test_internal_customer_service_graph.py
backend/app/tests/integration/test_internal_customer_service_runtime.py
backend/app/tests/integration/test_internal_customer_service_memory.py
```

### 修改文件

```text
backend/app/services/agent_runtime/scenario_registry.py
backend/app/services/agent_runtime/runtime_facade.py
backend/app/services/app_runtime_service.py
backend/app/schemas/app_runtime.py
backend/app/tests/unit/test_app_runtime_protection.py
```

## 3. Task 1：建立内部客服 Graph

**Files:**

- Create: `backend/app/services/agent_runtime/graphs/internal_customer_service_graph.py`
- Modify: `backend/app/services/agent_runtime/scenario_registry.py`
- Create: `backend/app/tests/unit/test_internal_customer_service_graph.py`

- [ ] **Step 1：写失败测试，验证带 Citation 回答**

```python
from unittest.mock import Mock

from langgraph.checkpoint.memory import InMemorySaver

from app.services.agent_runtime.graphs.internal_customer_service_graph import build_internal_customer_service_graph


def test_customer_service_graph_returns_authorized_answer_with_citations():
    invoke_rag_agent = Mock(
        return_value={
            "answer": "请按制度提交申请。",
            "runId": "run-001",
            "citations": [{"citationId": "c1", "evidenceId": "e1", "label": "制度", "chunkId": "chunk-1"}],
        }
    )
    graph = build_internal_customer_service_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=invoke_rag_agent,
    )

    result = graph.invoke(
        {"conversationId": "conv-1", "query": "如何提交申请？"},
        {"configurable": {"thread_id": "conv-1"}},
    )

    assert result["answer"] == "请按制度提交申请。"
    assert result["qaRunId"] == "run-001"
    assert result["citations"][0]["chunkId"] == "chunk-1"
```

- [ ] **Step 2：写失败测试，验证无 Citation 拒答**

```python
def test_customer_service_graph_refuses_answer_without_citations():
    graph = build_internal_customer_service_graph(
        checkpointer=InMemorySaver(),
        invoke_rag_agent=Mock(return_value={"answer": "猜测回答", "runId": "run-002", "citations": []}),
    )

    result = graph.invoke(
        {"conversationId": "conv-1", "query": "未知问题"},
        {"configurable": {"thread_id": "conv-1"}},
    )

    assert result["answer"] == "当前知识库中没有足够依据回答该问题，请联系人工渠道。"
    assert result["citations"] == []
```

- [ ] **Step 3：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_internal_customer_service_graph.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 4：实现最小 Graph**

```python
"""内部客服 LangGraph 编排。"""
from __future__ import annotations

from typing import Any
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph


NO_EVIDENCE_ANSWER = "当前知识库中没有足够依据回答该问题，请联系人工渠道。"


class InternalCustomerServiceState(TypedDict, total=False):
    """内部客服运行态，不依赖课堂领域对象。"""

    conversationId: str
    query: str
    answer: str
    qaRunId: str
    citations: list[dict[str, Any]]


def build_internal_customer_service_graph(*, checkpointer, invoke_rag_agent):
    """构建内部客服 Graph，回答必须具有授权 Citation。"""
    builder = StateGraph(InternalCustomerServiceState)

    def query_knowledge_base(state: InternalCustomerServiceState) -> InternalCustomerServiceState:
        result = invoke_rag_agent(state["query"])
        citations = result["citations"]
        return {
            "answer": result["answer"] if citations else NO_EVIDENCE_ANSWER,
            "qaRunId": result["runId"],
            "citations": citations,
        }

    builder.add_node("query_knowledge_base", query_knowledge_base)
    builder.add_edge(START, "query_knowledge_base")
    builder.add_edge("query_knowledge_base", END)
    return builder.compile(checkpointer=checkpointer)
```

- [ ] **Step 5：注册 Graph 并运行测试**

在 `scenario_registry.py` 注册 `knowledge_qa` 场景 builder。

```powershell
python -m pytest backend/app/tests/unit/test_internal_customer_service_graph.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime backend/app/tests/unit/test_internal_customer_service_graph.py
git commit -m "feat: add internal customer service graph"
```

## 4. Task 2：通过现有 App Runtime 入口路由客服 Graph

**Files:**

- Modify: `backend/app/services/app_runtime_service.py`
- Modify: `backend/app/services/agent_runtime/runtime_facade.py`
- Modify: `backend/app/schemas/app_runtime.py`
- Create: `backend/app/tests/integration/test_internal_customer_service_runtime.py`

- [ ] **Step 1：写失败测试，验证 `conversation_id` 固定映射 `thread_id`**

```python
def test_customer_service_runtime_uses_conversation_as_thread_id(db, knowledge_qa_app):
    first = chat_with_app_runtime(
        db,
        knowledge_qa_app.credential,
        AppRuntimeChatRequest(query="如何申请？", endUserId="u1"),
    )
    second = chat_with_app_runtime(
        db,
        knowledge_qa_app.credential,
        AppRuntimeChatRequest(query="需要哪些材料？", conversationId=first.conversationId, endUserId="u1"),
    )

    assert second.conversationId == first.conversationId
    assert second.metadata["threadId"] == first.conversationId
    assert second.metadata["runtimeVersion"] == "langgraph_primary_v1"
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/integration/test_internal_customer_service_runtime.py::test_customer_service_runtime_uses_conversation_as_thread_id -q
```

Expected: FAIL，响应尚未包含 Graph 元数据。

- [ ] **Step 3：在 Facade 中增加客服入口**

新增：

```python
def invoke_internal_customer_service(
    *,
    graph,
    conversation_id: str,
    query: str,
) -> dict:
    """使用 conversation_id 作为固定 thread_id 调用客服 Graph。"""
    return graph.invoke(
        {"conversationId": conversation_id, "query": query},
        {"configurable": {"thread_id": conversation_id}},
    )
```

- [ ] **Step 4：在 App Runtime 中按场景和固定版本路由**

仅当：

```python
scenario_type == "knowledge_qa" and runtime_version == "langgraph_primary_v1"
```

才进入客服 Graph。旧会话继续使用 Legacy。Facade 必须通过 P1 `build_rag_answer_agent()` 创建客服 RAG Agent；该 Agent 内部使用 P1 的只读 QARun Tool，不得再次复制 `create_qa_run()` 调用代码：

```python
rag_agent = build_rag_answer_agent(
    model=create_chat_model(settings),
    qa_run_tool=create_qa_run_tool(
        session=session,
        credential=credential,
        end_user_id=request.endUserId,
    ),
    checkpointer=checkpointer,
    trigger_tokens=settings.agent_runtime_summary_trigger_tokens,
    keep_messages=settings.agent_runtime_summary_keep_messages,
    system_prompt="你是内部客服助手。回答前必须调用 query_knowledge_base；没有授权依据时不要猜测。",
)
```

- [ ] **Step 5：补充响应元数据并运行测试**

```python
metadata = dict(response.metadata)
metadata.update(
    {
        "threadId": str(conversation_row["conversation_id"]),
        "runtimeVersion": runtime_version,
        "checkpointId": checkpoint_id,
    }
)
```

```powershell
python -m pytest backend/app/tests/integration/test_internal_customer_service_runtime.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/app_runtime_service.py backend/app/services/agent_runtime/runtime_facade.py backend/app/schemas/app_runtime.py backend/app/tests/integration/test_internal_customer_service_runtime.py
git commit -m "feat: route knowledge qa app through customer service graph"
```

## 5. Task 3：接入连续追问、摘要压缩和恢复

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/internal_customer_service_graph.py`
- Modify: `backend/app/services/agent_runtime/memory_service.py`
- Create: `backend/app/tests/integration/test_internal_customer_service_memory.py`

- [ ] **Step 1：写失败测试，验证连续追问恢复同一 Checkpoint**

```python
def test_customer_service_resume_uses_latest_checkpoint(db, customer_service_runtime):
    first = customer_service_runtime.ask("如何提交申请？")
    checkpoint_before = customer_service_runtime.latest_checkpoint(first.conversationId)

    second = customer_service_runtime.ask("需要哪些材料？", conversation_id=first.conversationId)

    assert second.metadata["threadId"] == first.conversationId
    assert second.metadata["checkpointId"] != checkpoint_before
```

- [ ] **Step 2：写失败测试，验证长对话使用官方摘要中间件**

```python
def test_customer_service_long_thread_uses_builtin_summary_middleware(customer_service_runtime):
    with patch("app.services.agent_runtime.memory_service.SummarizationMiddleware.before_model") as before_model:
        customer_service_runtime.send_long_conversation(message_count=30, chars_per_message=500)

    assert before_model.called
```

- [ ] **Step 3：写失败测试，验证完整消息保留**

```python
def test_customer_service_summary_does_not_delete_app_messages(db, customer_service_runtime):
    conversation_id = customer_service_runtime.send_long_conversation(message_count=30, chars_per_message=500)

    count = db.execute(
        select(func.count()).select_from(app_messages).where(app_messages.c.conversation_id == conversation_id)
    ).scalar_one()

    assert count >= 30
```

- [ ] **Step 4：将 P1 摘要中间件接入客服 Agent 节点**

使用 P1 `build_rag_answer_agent()` 中挂载的同一 `create_summary_middleware()`，不得在客服模块新增字符串截断摘要函数。摘要失败时保留旧摘要和最近窗口，记录审计但不阻断回答。

- [ ] **Step 5：运行测试**

```powershell
python -m pytest backend/app/tests/integration/test_internal_customer_service_memory.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime backend/app/tests/integration/test_internal_customer_service_memory.py
git commit -m "feat: add customer service checkpoint and summary memory"
```

## 6. Task 4：证明 Runtime 通用解耦

**Files:**

- Modify: `backend/app/tests/unit/test_internal_customer_service_graph.py`
- Modify: `backend/app/tests/unit/test_app_runtime_protection.py`

- [ ] **Step 1：增加禁止课堂依赖测试**

```python
def test_customer_service_graph_has_no_training_imports():
    source = inspect.getsource(internal_customer_service_graph)

    assert "training_classroom_service" not in source
    assert "training_progress_service" not in source
    assert "training_question" not in source
```

- [ ] **Step 2：增加跨 App 会话隔离测试**

```python
def test_customer_service_conversation_cannot_cross_app(db, app_a, app_b):
    first = chat_with_app_runtime(db, app_a.credential, AppRuntimeChatRequest(query="问题", endUserId="u1"))

    with pytest.raises(AppRuntimeNotFoundError):
        chat_with_app_runtime(
            db,
            app_b.credential,
            AppRuntimeChatRequest(query="继续", conversationId=first.conversationId, endUserId="u1"),
        )
```

- [ ] **Step 3：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_internal_customer_service_graph.py backend/app/tests/unit/test_app_runtime_protection.py -q
```

Expected: PASS。

- [ ] **Step 4：提交**

```powershell
git add backend/app/tests/unit
git commit -m "test: verify customer service runtime isolation"
```

## 7. Task 5：性能、框架利用率和 Code Review

- [ ] **Step 1：运行 P3 专项测试**

```powershell
python -m pytest backend/app/tests/unit/test_internal_customer_service_graph.py backend/app/tests/integration/test_internal_customer_service_runtime.py backend/app/tests/integration/test_internal_customer_service_memory.py -q
```

Expected: PASS。

- [ ] **Step 2：运行平台和课堂回归**

```powershell
python -m pytest backend/app/tests/unit/test_app_runtime_protection.py backend/app/tests/unit/test_app_runtime_embed_token.py backend/app/tests/integration/test_employee_training_agent_runtime.py backend/app/tests/integration/test_training_e2e_acceptance.py backend/app/tests/integration/test_employee_training_runtime_parity.py -q
python -m compileall backend/app
git diff --check
```

Expected: PASS。

- [ ] **Step 3：记录客服性能基线**

固定样本记录：

```text
首次问答 P50、P95
连续追问 P50、P95
Checkpoint get/put P50、P95
QARun Tool 耗时
摘要压缩额外耗时
每轮模型调用次数
每轮 QARun 调用次数
无证据拒答比例
```

- [ ] **Step 4：执行框架利用率验收**

必须提供测试或 Trace 证据：

- 客服 Graph 使用 P1 的 `ScenarioGraphRegistry`。
- 客服 Graph 使用 P1 的 Checkpointer。
- 客服 Graph 使用 P1 的 `QARun Tool`。
- 客服长对话使用 P1 的官方摘要中间件。
- `conversation_id` 固定映射 `thread_id`。
- 完整消息继续写入 `app_messages`。
- Citation 仍来自授权 `QARun`。
- 无 Evidence 时拒答。

- [ ] **Step 5：执行 Code Review 门禁**

评审必须确认：

- 客服模块没有课堂依赖。
- 没有新增第二套通用消息表。
- 没有复制 `create_qa_run()` 链路。
- 没有新增手写摘要函数。
- 没有绕过 `QARun` 的直接检索。
- Trace 能串联 `threadId`、`checkpointId`、`qaRunId` 和模型调用。
- SOP 和合规检查未来可以通过注册新 Graph 接入，不需要修改客服或课堂 Graph。

- [ ] **Step 6：提交评审修复**

```powershell
git add backend
git commit -m "test: harden internal customer service graph"
```

## 8. Task 6：总体验收

- [ ] **Step 1：运行完整 Agent Runtime 回归**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_model_adapter.py backend/app/tests/unit/test_agent_runtime_checkpoint_service.py backend/app/tests/unit/test_agent_runtime_memory_service.py backend/app/tests/unit/test_agent_runtime_qa_run_tool.py backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py backend/app/tests/unit/test_agent_runtime_skill_adapter.py backend/app/tests/unit/test_agent_runtime_facade.py backend/app/tests/unit/test_employee_training_langgraph.py backend/app/tests/unit/test_internal_customer_service_graph.py backend/app/tests/integration/test_agent_runtime_checkpoint_postgres.py backend/app/tests/integration/test_employee_training_langgraph_memory.py backend/app/tests/integration/test_employee_training_langgraph_resume.py backend/app/tests/integration/test_employee_training_runtime_parity.py backend/app/tests/integration/test_internal_customer_service_runtime.py backend/app/tests/integration/test_internal_customer_service_memory.py -q
```

Expected: PASS。PostgreSQL 测试必须在共享测试环境实际执行，不以 skip 作为最终验收。

- [ ] **Step 2：运行现有业务回归**

```powershell
python -m pytest backend/app/tests/unit backend/app/tests/integration -q
python -m compileall backend/app backend/scripts
git diff --check
```

Expected: PASS。

- [ ] **Step 3：执行真实 Provider 网络验证**

```powershell
python backend/scripts/setup_langgraph_checkpoints.py
python backend/scripts/verify_agent_runtime_provider.py
```

Expected:

- PostgreSQL Checkpoint 表初始化成功。
- 报告明确列出 `chat`、`toolCalling`、`structuredOutput` 和 `summarization`。
- 不输出 API Key。
- 正式结果回填发布运维复测记录。

- [ ] **Step 4：完成最终收口评审**

最终评审逐项确认：

- LangGraph 真实承担课堂和客服运行态、Checkpoint、恢复和节点编排。
- LangChain 真实承担 ChatModel、Tool 和官方摘要中间件。
- `QARun` 继续承担受控 RAG、权限、Evidence、Citation 和 Trace。
- 审核、评分、进度、权限和报表仍由领域服务负责。
- 没有框架空壳、平行手写上下文管理、第二套课堂状态机或直接检索旁路。
- P1、P2、P3 性能基线均可定位瓶颈。

## 9. P3 完成定义

- 内部客服通过同一 Runtime 基座完成问答、连续追问、恢复、摘要和拒答。
- 客服 Graph 不依赖课堂模块。
- 课堂和客服均可通过 Trace 定位 Checkpoint、Tool、模型和 `QARun`。
- SOP 和合规检查可以通过新增 Graph 和 Skill 注册接入，无需改写现有场景。
- 三阶段 Code Review、测试、性能和真实 Provider 证据完整。
