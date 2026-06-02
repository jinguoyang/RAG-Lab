# LangGraph Primary 真实 E2E 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> 用途：本文是内部客服 `knowledge_qa` 场景真实 Primary E2E 的执行计划。当前状态以 Backlog、Sprint 和 Release 状态源为准。

**Goal:** 新增一条使用独立测试库、真实 Graph、真实 Checkpoint 和真实 Provider 的 `langgraph_primary_v1` 发布级 E2E，并按失败证据完成最小修复。

**Architecture:** 复用现有真实 Provider 文档入库脚本的夹具，新建窄范围 Primary 验收脚本。生产修复只围绕内部客服 Graph 接入统一 RAG Agent、只读 QARun Tool、官方摘要中间件和现有审计表展开，不新增数据库迁移。

**Tech Stack:** Python、FastAPI TestClient、SQLAlchemy、PostgreSQL、pytest、LangChain、LangGraph、现有 QARun。

**Design Spec:** `docs/04-迭代与交付/specs/2026-06-02-langgraph-primary-real-e2e-spec.md`

---

## Task 1：增加脚本保护规则

**Files:**

- Create: `backend/scripts/verify_agent_runtime_primary_e2e.py`
- Create: `backend/app/tests/unit/test_agent_runtime_primary_e2e_script.py`

- [ ] 先写失败测试，验证缺少独立测试库、业务库 DSN 和 Checkpoint DSN 不一致时拒绝运行。
- [ ] 运行 `python -m pytest backend/app/tests/unit/test_agent_runtime_primary_e2e_script.py -q`，确认因脚本模块不存在而失败。
- [ ] 实现 DSN 解析和独立测试库保护函数。
- [ ] 重跑测试，确认保护规则通过。

## Task 2：增加真实 Primary E2E

**Files:**

- Modify: `backend/scripts/verify_agent_runtime_primary_e2e.py`
- Modify: `backend/app/tests/unit/test_agent_runtime_primary_e2e_script.py`

- [ ] 先写失败测试，验证 Trace 串联断言会拒绝缺失 `threadId`、`checkpointId`、`qaRunId`、`skillCallId` 和 `summaryVersion` 的调用摘要。
- [ ] 实现真实文档入库、连续追问、Checkpointer 重建、长对话摘要和数据库审计查询。
- [ ] 使用独立测试库运行真实 E2E，记录实际失败项。

## Task 3：按证据做最小生产修复

**Files:**

- Modify: `backend/app/services/agent_runtime/graphs/internal_customer_service_graph.py`
- Modify: `backend/app/services/agent_runtime/qa_run_tool.py`
- Modify: `backend/app/services/app_runtime_service.py`
- Modify: `backend/app/tests/integration/test_internal_customer_service_runtime.py`
- Modify: `backend/app/tests/integration/test_internal_customer_service_memory.py`

- [ ] 为每个真实失败项先增加专项失败测试。
- [ ] 将内部客服 Graph 接入统一 RAG Agent 和只读 QARun Tool。
- [ ] 将 Tool 审计和 Runtime Trace 摘要写入现有表。
- [ ] 保留现有授权 Citation、完整消息和 QARun 真值链路。
- [ ] 重跑真实 E2E，直至通过。

## Task 4：验证与评审

- [ ] 运行内部客服与 Agent Runtime 专项测试。
- [ ] 运行 `python -m compileall backend/app backend/scripts`。
- [ ] 运行统一 Agent Runtime 验收。
- [ ] 运行 `git diff --check`。
- [ ] 复核没有新增迁移、课堂状态机改动或直接检索旁路。

