# 平台 Agent Runtime 基座实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 用途：本文是 LangChain 与 LangGraph 平台 Runtime 第一阶段实施计划，属于执行依据。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

**Goal:** 在不改变现有业务主链路的前提下，引入 LangChain 与 LangGraph 平台适配层，落地官方 PostgreSQL Checkpointer、官方摘要中间件、只读 QARun Tool、Skill Adapter、Runtime 版本路由和框架利用率验收。

**Architecture:** 新增 `backend/app/services/agent_runtime/` 平台目录。现有 `QARun`、App Runtime 和课堂服务保持默认走 `legacy_v1`；新基座先提供 `langgraph_shadow_v1` 无副作用对照能力。生产 Checkpoint 使用 LangGraph 官方 `PostgresSaver`，测试使用依赖注入的 `InMemorySaver`。

**Tech Stack:** Python、FastAPI、SQLAlchemy、PostgreSQL、pytest、LangChain 1.x、LangGraph 1.x、`langchain-openai`、`langgraph-checkpoint-postgres`、现有 Langfuse。

**Design Spec:** `docs/04-迭代与交付/specs/2026-06-01-langchain-langgraph-agent-runtime-spec.md`

---

## 1. 范围边界

本阶段必须完成：

- 引入 LangChain、LangGraph 和 PostgreSQL Checkpointer 依赖。
- 新增平台 Runtime 配置。
- 新增 ChatModel Adapter。
- 新增官方 Checkpointer 工厂和初始化脚本。
- 新增 LangChain 官方 `SummarizationMiddleware` 工厂。
- 新增只读 `QARun` LangChain Tool。
- 新增平台 Skill Adapter。
- 新增 Scenario Registry 与 Runtime Facade 最小骨架。
- 新增 Shadow 无副作用验证。
- 新增框架利用率测试与阶段 Code Review。

本阶段不做：

- 不切换课堂主链路。
- 不新增客服 API。
- 不删除现有 HTTP Provider。
- 不改写 `QARun` 内部 Pipeline。
- 不创建手写 Checkpoint 表。
- 不新增另一套手写摘要逻辑。

## 2. 文件结构

### 新增文件

```text
backend/app/services/agent_runtime/__init__.py
backend/app/services/agent_runtime/types.py
backend/app/services/agent_runtime/model_adapter.py
backend/app/services/agent_runtime/checkpoint_service.py
backend/app/services/agent_runtime/memory_service.py
backend/app/services/agent_runtime/qa_run_tool.py
backend/app/services/agent_runtime/rag_agent_factory.py
backend/app/services/agent_runtime/skill_adapter.py
backend/app/services/agent_runtime/scenario_registry.py
backend/app/services/agent_runtime/runtime_facade.py
backend/scripts/setup_langgraph_checkpoints.py
backend/app/tests/unit/test_agent_runtime_model_adapter.py
backend/app/tests/unit/test_agent_runtime_checkpoint_service.py
backend/app/tests/unit/test_agent_runtime_memory_service.py
backend/app/tests/unit/test_agent_runtime_qa_run_tool.py
backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py
backend/app/tests/unit/test_agent_runtime_skill_adapter.py
backend/app/tests/unit/test_agent_runtime_facade.py
backend/app/tests/integration/test_agent_runtime_checkpoint_postgres.py
```

### 修改文件

```text
backend/requirements.txt
backend/app/core/config.py
```

## 3. 依赖约束

官方依据：

- LangChain 安装：<https://docs.langchain.com/oss/python/langchain/install>
- LangGraph 安装与定位：<https://docs.langchain.com/oss/python/langgraph>
- PostgreSQL Checkpointer：<https://docs.langchain.com/oss/python/langgraph/add-memory>
- 官方摘要中间件：<https://docs.langchain.com/oss/python/langchain/middleware/built-in>

依赖采用主版本上限，不在本阶段锁死补丁版本：

```text
langchain>=1.3,<2.0
langgraph>=1.2,<2.0
langchain-openai>=1.2,<2.0
langgraph-checkpoint-postgres>=3.1,<4.0
psycopg[binary,pool]>=3.2,<4.0
```

执行前必须运行：

```powershell
python -m pip index versions langchain
python -m pip index versions langgraph
python -m pip index versions langchain-openai
python -m pip index versions langgraph-checkpoint-postgres
```

将实际安装版本记录在阶段 Code Review 说明中。

## 4. Task 1：引入依赖和 Runtime 配置

**Files:**

- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Test: `backend/app/tests/unit/test_agent_runtime_model_adapter.py`

- [ ] **Step 1：写失败测试，验证 Runtime 默认关闭且默认路径为旧链路**

```python
from app.core.config import Settings


def test_agent_runtime_defaults_to_legacy_and_disabled():
    settings = Settings(_env_file=None)

    assert settings.agent_runtime_enabled is False
    assert settings.agent_runtime_default_version == "legacy_v1"
    assert settings.agent_runtime_checkpoint_backend == "postgres"
    assert settings.agent_runtime_summary_trigger_tokens == 4000
    assert settings.agent_runtime_summary_keep_messages == 20
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_model_adapter.py::test_agent_runtime_defaults_to_legacy_and_disabled -q
```

Expected: FAIL，提示 `Settings` 缺少 `agent_runtime_enabled`。

- [ ] **Step 3：增加依赖和配置**

在 `backend/requirements.txt` 增加 Lang 系列依赖，并将已有 `psycopg[binary]` 行替换为：

```text
langchain>=1.3,<2.0
langgraph>=1.2,<2.0
langchain-openai>=1.2,<2.0
langgraph-checkpoint-postgres>=3.1,<4.0
psycopg[binary,pool]>=3.2,<4.0
```

在 `Settings` 增加：

```python
    agent_runtime_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("RAG_LAB_AGENT_RUNTIME_ENABLED", "AGENT_RUNTIME_ENABLED"),
    )
    agent_runtime_default_version: str = Field(
        default="legacy_v1",
        pattern="^(legacy_v1|langgraph_shadow_v1|langgraph_primary_v1)$",
        validation_alias=AliasChoices("RAG_LAB_AGENT_RUNTIME_DEFAULT_VERSION", "AGENT_RUNTIME_DEFAULT_VERSION"),
    )
    agent_runtime_checkpoint_backend: str = Field(
        default="postgres",
        pattern="^(postgres|memory)$",
        validation_alias=AliasChoices("RAG_LAB_AGENT_RUNTIME_CHECKPOINT_BACKEND", "AGENT_RUNTIME_CHECKPOINT_BACKEND"),
    )
    agent_runtime_checkpoint_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "RAG_LAB_AGENT_RUNTIME_CHECKPOINT_DATABASE_URL",
            "AGENT_RUNTIME_CHECKPOINT_DATABASE_URL",
        ),
    )
    agent_runtime_summary_trigger_tokens: int = Field(
        default=4000,
        ge=512,
        validation_alias=AliasChoices("RAG_LAB_AGENT_RUNTIME_SUMMARY_TRIGGER_TOKENS"),
    )
    agent_runtime_summary_keep_messages: int = Field(
        default=20,
        ge=2,
        validation_alias=AliasChoices("RAG_LAB_AGENT_RUNTIME_SUMMARY_KEEP_MESSAGES"),
    )
```

- [ ] **Step 4：安装依赖并运行测试**

```powershell
python -m pip install -r backend/requirements.txt
python -m pytest backend/app/tests/unit/test_agent_runtime_model_adapter.py::test_agent_runtime_defaults_to_legacy_and_disabled -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/requirements.txt backend/app/core/config.py backend/app/tests/unit/test_agent_runtime_model_adapter.py
git commit -m "feat: add agent runtime dependencies and settings"
```

## 5. Task 2：新增 ChatModel Adapter

**Files:**

- Create: `backend/app/services/agent_runtime/__init__.py`
- Create: `backend/app/services/agent_runtime/model_adapter.py`
- Modify: `backend/app/tests/unit/test_agent_runtime_model_adapter.py`

- [ ] **Step 1：写失败测试，验证 OpenAI-compatible 配置进入 LangChain Adapter**

```python
from types import SimpleNamespace
from unittest.mock import patch

from app.services.agent_runtime.model_adapter import create_chat_model


def test_create_chat_model_uses_existing_openai_compatible_settings():
    settings = SimpleNamespace(
        llm_model="private-model",
        llm_endpoint="http://llm.local/v1/chat/completions",
        llm_api_key="secret",
    )
    with patch("app.services.agent_runtime.model_adapter.ChatOpenAI") as chat_model:
        create_chat_model(settings)

    chat_model.assert_called_once_with(
        model="private-model",
        api_key="secret",
        base_url="http://llm.local/v1",
        timeout=60,
        max_retries=2,
    )
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_model_adapter.py::test_create_chat_model_uses_existing_openai_compatible_settings -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3：实现最小 Adapter**

```python
"""LangChain ChatModel 适配器。"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from langchain_openai import ChatOpenAI


def _openai_base_url(endpoint: str) -> str:
    """将现有 Chat Completions endpoint 收敛为 OpenAI-compatible base_url。"""
    parts = urlsplit(endpoint.rstrip("/"))
    path = parts.path
    suffix = "/chat/completions"
    if path.endswith(suffix):
        path = path[: -len(suffix)]
    return urlunsplit((parts.scheme, parts.netloc, path.rstrip("/"), "", ""))


def create_chat_model(settings):
    """使用现有 LLM 配置创建 LangChain ChatModel。"""
    if not settings.llm_endpoint:
        raise ValueError("LLM endpoint 未配置。")
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key or "not-set",
        base_url=_openai_base_url(settings.llm_endpoint),
        timeout=60,
        max_retries=2,
    )
```

- [ ] **Step 4：补充 base URL 单元测试并运行**

```python
from app.services.agent_runtime.model_adapter import _openai_base_url


def test_openai_base_url_removes_chat_completions_suffix():
    assert _openai_base_url("http://llm.local/v1/chat/completions") == "http://llm.local/v1"
```

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_model_adapter.py -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime backend/app/tests/unit/test_agent_runtime_model_adapter.py
git commit -m "feat: add langchain chat model adapter"
```

## 6. Task 3：接入官方 Checkpointer

**Files:**

- Create: `backend/app/services/agent_runtime/checkpoint_service.py`
- Create: `backend/scripts/setup_langgraph_checkpoints.py`
- Create: `backend/app/tests/unit/test_agent_runtime_checkpoint_service.py`
- Create: `backend/app/tests/integration/test_agent_runtime_checkpoint_postgres.py`

- [ ] **Step 1：写失败测试，验证测试环境可以注入官方 InMemorySaver**

```python
from langgraph.checkpoint.memory import InMemorySaver

from app.services.agent_runtime.checkpoint_service import create_checkpointer


def test_create_checkpointer_supports_official_memory_backend():
    checkpointer = create_checkpointer(backend="memory", database_url=None)

    assert isinstance(checkpointer, InMemorySaver)
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_checkpoint_service.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3：实现官方 Checkpointer 工厂**

```python
"""LangGraph 官方 Checkpointer 工厂。"""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver


def create_checkpointer(*, backend: str, database_url: str | None):
    """创建官方 Checkpointer；生产使用 PostgreSQL，测试允许使用内存实现。"""
    if backend == "memory":
        return InMemorySaver()
    if backend == "postgres" and database_url:
        return PostgresSaver.from_conn_string(database_url)
    raise ValueError("PostgreSQL Checkpointer 需要 database_url。")
```

- [ ] **Step 4：实现独立初始化脚本**

```python
"""初始化 LangGraph PostgreSQL Checkpoint 表。"""
from app.core.config import get_settings
from app.services.agent_runtime.checkpoint_service import create_checkpointer


def main() -> None:
    """运行官方 setup()，不手写框架内部迁移表。"""
    settings = get_settings()
    database_url = settings.agent_runtime_checkpoint_database_url or settings.database_url
    with create_checkpointer(backend="postgres", database_url=database_url) as checkpointer:
        checkpointer.setup()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5：增加 PostgreSQL 集成测试**

测试仅在配置 `RAG_LAB_TEST_POSTGRES_URL` 时执行：

```python
import os

import pytest
from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict

from app.services.agent_runtime.checkpoint_service import create_checkpointer


class State(TypedDict):
    value: str


@pytest.mark.skipif(not os.getenv("RAG_LAB_TEST_POSTGRES_URL"), reason="需要 PostgreSQL 测试库")
def test_postgres_checkpointer_persists_thread_state():
    with create_checkpointer(
        backend="postgres",
        database_url=os.environ["RAG_LAB_TEST_POSTGRES_URL"],
    ) as checkpointer:
        checkpointer.setup()
        builder = StateGraph(State)
        builder.add_node("copy", lambda state: {"value": state["value"]})
        builder.add_edge(START, "copy")
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "foundation-test-thread"}}

        graph.invoke({"value": "saved"}, config)

        assert graph.get_state(config).values["value"] == "saved"
```

- [ ] **Step 6：运行单元测试和可选 PostgreSQL 集成测试**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_checkpoint_service.py -q
$env:RAG_LAB_TEST_POSTGRES_URL="postgresql://postgres:postgres@127.0.0.1:5432/rag_lab_test"
python -m pytest backend/app/tests/integration/test_agent_runtime_checkpoint_postgres.py -q
```

Expected: PASS。若本地没有 PostgreSQL 测试库，第二条命令记录为未执行，并在共享测试环境补跑。

- [ ] **Step 7：提交**

```powershell
git add backend/app/services/agent_runtime/checkpoint_service.py backend/scripts/setup_langgraph_checkpoints.py backend/app/tests/unit/test_agent_runtime_checkpoint_service.py backend/app/tests/integration/test_agent_runtime_checkpoint_postgres.py
git commit -m "feat: add official langgraph checkpointer"
```

## 7. Task 4：接入官方摘要中间件

**Files:**

- Create: `backend/app/services/agent_runtime/memory_service.py`
- Create: `backend/app/tests/unit/test_agent_runtime_memory_service.py`

- [ ] **Step 1：写失败测试，验证配置使用官方 `SummarizationMiddleware`**

```python
from unittest.mock import patch

from app.services.agent_runtime.memory_service import create_summary_middleware


def test_create_summary_middleware_uses_langchain_builtin():
    with patch("app.services.agent_runtime.memory_service.SummarizationMiddleware") as middleware:
        create_summary_middleware(model="summary-model", trigger_tokens=4000, keep_messages=20)

    middleware.assert_called_once_with(
        model="summary-model",
        trigger=("tokens", 4000),
        keep=("messages", 20),
    )
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_memory_service.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3：实现中间件工厂**

```python
"""Agent 上下文摘要中间件工厂。"""
from langchain.agents.middleware import SummarizationMiddleware


def create_summary_middleware(*, model, trigger_tokens: int, keep_messages: int):
    """创建 LangChain 官方摘要中间件，不新增平行手写压缩实现。"""
    return SummarizationMiddleware(
        model=model,
        trigger=("tokens", trigger_tokens),
        keep=("messages", keep_messages),
    )
```

- [ ] **Step 4：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_memory_service.py -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime/memory_service.py backend/app/tests/unit/test_agent_runtime_memory_service.py
git commit -m "feat: add langchain summarization middleware factory"
```

## 8. Task 5：封装只读 QARun Tool

**Files:**

- Create: `backend/app/services/agent_runtime/types.py`
- Create: `backend/app/services/agent_runtime/qa_run_tool.py`
- Create: `backend/app/tests/unit/test_agent_runtime_qa_run_tool.py`

- [ ] **Step 1：写失败测试，验证 Tool 返回安全结果**

```python
from unittest.mock import MagicMock, patch

from app.services.agent_runtime.qa_run_tool import create_qa_run_tool


def test_qa_run_tool_returns_authorized_answer_and_citations_only():
    response = MagicMock(
        answer="授权回答",
        runId="run-001",
        citations=[MagicMock(citationId="c1", evidenceId="e1", label="依据", locationSnapshot={"chunkId": "chunk-1"})],
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
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_qa_run_tool.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3：实现 Tool**

```python
"""将现有 App Runtime/QARun 封装为只读 LangChain Tool。"""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.schemas.app_runtime import AppRuntimeChatRequest
from app.services.app_runtime_service import chat_with_app_runtime


class QARunToolInput(BaseModel):
    """只读知识库问答 Tool 输入。"""

    query: str = Field(min_length=1, max_length=4000)


def create_qa_run_tool(*, session, credential: str, end_user_id: str | None):
    """创建仅返回授权结果的 QARun Tool。"""
    def query_knowledge_base(query: str) -> dict:
        response = chat_with_app_runtime(
            session,
            credential,
            AppRuntimeChatRequest(query=query, endUserId=end_user_id),
        )
        return {
            "runId": response.runId,
            "answer": response.answer,
            "citations": [
                {
                    "citationId": item.citationId,
                    "evidenceId": item.evidenceId,
                    "label": item.label,
                    "chunkId": item.locationSnapshot.get("chunkId"),
                }
                for item in response.citations
            ],
            "usage": response.usage,
        }

    return StructuredTool.from_function(
        func=query_knowledge_base,
        name="query_knowledge_base",
        description="通过受控 QARun 查询当前应用绑定知识库，返回授权回答和引用。",
        args_schema=QARunToolInput,
    )
```

- [ ] **Step 4：补充只读边界测试并运行**

```python
def test_qa_run_tool_schema_exposes_query_only():
    tool = create_qa_run_tool(session=MagicMock(), credential="cred", end_user_id="u1")

    assert set(tool.args_schema.model_fields) == {"query"}
```

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_qa_run_tool.py -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime/types.py backend/app/services/agent_runtime/qa_run_tool.py backend/app/tests/unit/test_agent_runtime_qa_run_tool.py
git commit -m "feat: expose qarun as readonly langchain tool"
```

## 9. Task 6：建立可复用 LangChain RAG Agent

**Files:**

- Create: `backend/app/services/agent_runtime/rag_agent_factory.py`
- Create: `backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py`

- [ ] **Step 1：写失败测试，验证 Agent 真实挂载官方摘要、模型限额、Tool 限额和 QARun Tool**

```python
from unittest.mock import Mock, patch

from app.services.agent_runtime.rag_agent_factory import build_rag_answer_agent


def test_build_rag_answer_agent_uses_langchain_create_agent_and_builtin_middleware():
    model = Mock()
    checkpointer = Mock()
    qa_run_tool = Mock(name="query_knowledge_base")
    qa_run_tool.name = "query_knowledge_base"
    summary = Mock(name="summary")

    with (
        patch("app.services.agent_runtime.rag_agent_factory.create_summary_middleware", return_value=summary),
        patch("app.services.agent_runtime.rag_agent_factory.create_agent") as create_agent,
    ):
        build_rag_answer_agent(
            model=model,
            qa_run_tool=qa_run_tool,
            checkpointer=checkpointer,
            trigger_tokens=4000,
            keep_messages=20,
            system_prompt="请基于知识库回答。",
        )

    middleware = create_agent.call_args.kwargs["middleware"]
    assert middleware[0] is summary
    assert middleware[1].run_limit == 3
    assert middleware[2].tool_name == "query_knowledge_base"
    assert middleware[2].run_limit == 1
    assert create_agent.call_args.kwargs["tools"] == [qa_run_tool]
    assert create_agent.call_args.kwargs["checkpointer"] is checkpointer
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3：实现 Agent 工厂**

```python
"""可复用的 LangChain RAG Agent 工厂。"""
from __future__ import annotations

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware

from app.services.agent_runtime.memory_service import create_summary_middleware


def build_rag_answer_agent(
    *,
    model,
    qa_run_tool,
    checkpointer,
    trigger_tokens: int,
    keep_messages: int,
    system_prompt: str,
):
    """构建受控 RAG Agent，统一复用官方中间件和只读 QARun Tool。"""
    return create_agent(
        model=model,
        tools=[qa_run_tool],
        system_prompt=system_prompt,
        middleware=[
            create_summary_middleware(
                model=model,
                trigger_tokens=trigger_tokens,
                keep_messages=keep_messages,
            ),
            ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
            ToolCallLimitMiddleware(
                tool_name=qa_run_tool.name,
                run_limit=1,
                exit_behavior="error",
            ),
        ],
        checkpointer=checkpointer,
    )
```

- [ ] **Step 4：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime/rag_agent_factory.py backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py
git commit -m "feat: add reusable langchain rag agent factory"
```

## 10. Task 7：新增平台 Skill Adapter

**Files:**

- Create: `backend/app/services/agent_runtime/skill_adapter.py`
- Create: `backend/app/tests/unit/test_agent_runtime_skill_adapter.py`

- [ ] **Step 1：写失败测试，验证场景白名单**

```python
import pytest

from app.services.agent_runtime.skill_adapter import PlatformSkill, select_allowed_skills


def test_select_allowed_skills_filters_by_scenario():
    skills = [
        PlatformSkill(name="retrieveDocuments", scenarios={"knowledge_qa", "employee_training"}, readonly=True),
        PlatformSkill(name="gradeSubjectiveAnswer", scenarios={"employee_training"}, readonly=False),
    ]

    selected = select_allowed_skills(skills, scenario_type="knowledge_qa")

    assert [item.name for item in selected] == ["retrieveDocuments"]
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_skill_adapter.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3：实现最小平台 Skill 描述和筛选**

```python
"""平台 Skill 白名单适配器。"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlatformSkill:
    """平台级 Skill 描述，首版只保留当前执行需要的字段。"""

    name: str
    scenarios: set[str] = field(default_factory=set)
    readonly: bool = True


def select_allowed_skills(skills: list[PlatformSkill], *, scenario_type: str) -> list[PlatformSkill]:
    """只返回当前场景允许暴露的 Skill。"""
    return [skill for skill in skills if scenario_type in skill.scenarios]
```

- [ ] **Step 4：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_skill_adapter.py -q
```

Expected: PASS。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime/skill_adapter.py backend/app/tests/unit/test_agent_runtime_skill_adapter.py
git commit -m "feat: add platform skill allowlist adapter"
```

## 11. Task 8：新增 Scenario Registry 与 Runtime Facade

**Files:**

- Create: `backend/app/services/agent_runtime/scenario_registry.py`
- Create: `backend/app/services/agent_runtime/runtime_facade.py`
- Create: `backend/app/tests/unit/test_agent_runtime_facade.py`

- [ ] **Step 1：写失败测试，验证 Legacy 与 Shadow 路由**

```python
from app.services.agent_runtime.runtime_facade import RuntimeVersion, resolve_runtime_version


def test_runtime_version_defaults_to_legacy():
    assert resolve_runtime_version(None) == RuntimeVersion.LEGACY


def test_runtime_version_accepts_shadow():
    assert resolve_runtime_version("langgraph_shadow_v1") == RuntimeVersion.LANGGRAPH_SHADOW
```

- [ ] **Step 2：运行测试确认失败**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_facade.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 3：实现版本类型与场景注册表**

```python
"""平台 Agent Runtime 场景注册表。"""
from collections.abc import Callable


class ScenarioGraphRegistry:
    """按场景注册 Graph 构建函数，避免 Runtime 写死课堂语义。"""

    def __init__(self) -> None:
        self._builders: dict[str, Callable] = {}

    def register(self, scenario_type: str, builder: Callable) -> None:
        self._builders[scenario_type] = builder

    def get(self, scenario_type: str) -> Callable | None:
        return self._builders.get(scenario_type)
```

```python
"""平台 Agent Runtime Facade。"""
from enum import StrEnum


class RuntimeVersion(StrEnum):
    """会话创建后固定使用的 Runtime 版本。"""

    LEGACY = "legacy_v1"
    LANGGRAPH_SHADOW = "langgraph_shadow_v1"
    LANGGRAPH_PRIMARY = "langgraph_primary_v1"


def resolve_runtime_version(value: str | None) -> RuntimeVersion:
    """解析 Runtime 版本，缺省保持旧链路。"""
    return RuntimeVersion(value or RuntimeVersion.LEGACY)
```

- [ ] **Step 4：补充 Shadow 无副作用测试**

```python
from unittest.mock import Mock

from app.services.agent_runtime.runtime_facade import run_shadow_projection


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
```

实现：

```python
def run_shadow_projection(*, state: dict, call_model, call_qa_run) -> dict:
    """Shadow 只投影状态，不重复调用真实模型、QARun 或领域写操作。"""
    return dict(state)
```

- [ ] **Step 5：运行测试**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_facade.py -q
```

Expected: PASS。

- [ ] **Step 6：提交**

```powershell
git add backend/app/services/agent_runtime/scenario_registry.py backend/app/services/agent_runtime/runtime_facade.py backend/app/tests/unit/test_agent_runtime_facade.py
git commit -m "feat: add agent runtime facade and shadow routing"
```

## 12. Task 9：真实 Provider 能力探测

**Files:**

- Create: `backend/scripts/verify_agent_runtime_provider.py`
- Create: `backend/app/tests/unit/test_agent_runtime_provider_probe.py`

- [ ] **Step 1：写失败测试，验证能力报告结构**

```python
from app.services.agent_runtime.model_adapter import ProviderCapabilityReport


def test_provider_capability_report_has_explicit_fallback_flags():
    report = ProviderCapabilityReport(
        chat=True,
        toolCalling=False,
        structuredOutput=False,
        summarization=True,
    )

    assert report.toolCalling is False
    assert report.structuredOutput is False
```

- [ ] **Step 2：实现 DTO 和验证脚本**

在 `model_adapter.py` 增加：

```python
from pydantic import BaseModel


class ProviderCapabilityReport(BaseModel):
    """真实 Provider 能力探测结果。"""

    chat: bool
    toolCalling: bool
    structuredOutput: bool
    summarization: bool
```

新增脚本，使用 `create_chat_model()` 执行四项独立探测，输出 JSON 报告；失败项写 `false` 和错误摘要，不输出 API Key。

- [ ] **Step 3：运行单元测试**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_provider_probe.py -q
```

Expected: PASS。

- [ ] **Step 4：在真实 Provider 环境执行**

```powershell
python backend/scripts/verify_agent_runtime_provider.py
```

Expected: 输出包含 `chat`、`toolCalling`、`structuredOutput`、`summarization` 的 JSON。正式结果回填到发布运维复测记录，不把 mock 结果标记为真实兼容。

- [ ] **Step 5：提交**

```powershell
git add backend/app/services/agent_runtime/model_adapter.py backend/scripts/verify_agent_runtime_provider.py backend/app/tests/unit/test_agent_runtime_provider_probe.py
git commit -m "test: add agent runtime provider capability probe"
```

## 13. Task 10：P1 回归、性能基线与 Code Review

- [ ] **Step 1：运行 P1 单元测试**

```powershell
python -m pytest backend/app/tests/unit/test_agent_runtime_model_adapter.py backend/app/tests/unit/test_agent_runtime_checkpoint_service.py backend/app/tests/unit/test_agent_runtime_memory_service.py backend/app/tests/unit/test_agent_runtime_qa_run_tool.py backend/app/tests/unit/test_agent_runtime_rag_agent_factory.py backend/app/tests/unit/test_agent_runtime_skill_adapter.py backend/app/tests/unit/test_agent_runtime_facade.py backend/app/tests/unit/test_agent_runtime_provider_probe.py -q
```

Expected: PASS。

- [ ] **Step 2：运行现有关键回归**

```powershell
python -m pytest backend/app/tests/unit/test_qa_providers.py backend/app/tests/unit/test_app_runtime_protection.py backend/app/tests/unit/test_app_runtime_embed_token.py backend/app/tests/integration/test_employee_training_agent_runtime.py backend/app/tests/integration/test_training_e2e_acceptance.py -q
python -m compileall backend/app backend/scripts
git diff --check
```

Expected: PASS。

- [ ] **Step 3：执行 Code Review 门禁**

评审必须确认：

- `QARun` 内部实现没有被修改。
- Checkpoint 使用官方 `PostgresSaver`，没有手写平行表。
- 摘要使用官方 `SummarizationMiddleware`。
- 新增代码没有零散 `httpx.post()`。
- Shadow 不调用真实 LLM、真实 `QARun` 或领域写操作。
- Tool 只暴露授权后的安全摘要。
- 实际安装依赖版本已记录。

- [ ] **Step 4：记录 P1 性能基线**

记录：

```text
checkpoint.setup 耗时
checkpoint put/get P50、P95
Shadow projection P50、P95
QARun Tool 额外包装耗时
```

- [ ] **Step 5：提交评审修复**

```powershell
git add backend
git commit -m "test: harden agent runtime foundation"
```

## 13. P1 完成定义

- 默认主链路仍为 `legacy_v1`。
- LangChain ChatModel Adapter 可使用现有 OpenAI-compatible 配置。
- LangGraph 官方 PostgreSQL Checkpointer 可初始化、写入和恢复。
- LangChain 官方摘要中间件工厂可用。
- `QARun` 已以只读 LangChain Tool 暴露。
- Shadow 模式不会产生第二次真实调用和业务副作用。
- Provider 能力报告可明确记录 Tool Calling、Structured Output 和摘要能力。
- 现有 App Runtime、QARun 和培训回归通过。
- 独立 Code Review 通过。
