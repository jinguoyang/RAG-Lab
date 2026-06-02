# LangGraph Primary 真实 E2E 验收规范

> 用途：本文是内部客服 `knowledge_qa` 场景 `langgraph_primary_v1` 真实 E2E 的验收规范，属于执行依据。当前 Backlog、Sprint 和 Release 状态仍以对应状态源为准。

## 1. 目标

新增一条发布级真实 E2E，使用独立测试库、真实 LangGraph、真实 PostgreSQL Checkpoint 和真实 Provider，验证内部客服 `knowledge_qa` 场景的连续追问、恢复、摘要、Tool、Trace 与 QARun 串联。

## 2. 关键假设

- 本轮主场景为内部客服 `knowledge_qa`，不混入课堂状态机。
- 不新增数据库表，复用 `app_invocations.response_summary` 保存 Runtime Trace 摘要，复用 `training_skill_calls` 保存 `query_knowledge_base` Tool 审计。
- `QARun` 继续是受控 RAG 真值链路，Agent 不直接访问检索 Provider。
- 真实 E2E 为发布级脚本，不进入默认 `pytest` 回归。

## 3. 范围

本轮包含：

- 新增独立真实 Primary E2E 脚本。
- 强制独立测试库和独立 Checkpoint DSN，拒绝隐式回退到业务库。
- 复用已有真实 Provider 文档入库链路。
- 验证同一 `conversationId` 连续追问。
- 关闭并重建共享 Checkpointer 后继续追问，验证恢复。
- 通过低阈值长对话触发官方摘要中间件。
- 验证 `app_invocations.response_summary`、`training_skill_calls` 和 `qa_runs` 可串联。
- 仅根据真实 E2E 暴露的失败项做最小生产修复。

本轮不包含：

- 不新增数据库迁移。
- 不修改课堂状态机。
- 不新增写操作 Skill。
- 不开发 Shadow 差异记录以外的新运行时功能。
- 不将真实网络脚本并入默认测试套件。

## 4. 验收证据

脚本成功时必须输出脱敏 JSON，至少包含：

- `status`
- `appId`
- `conversationId`
- `threadId`
- `checkpointId`
- `qaRunIds`
- `skillCallIds`
- `summaryVersion`
- `invocationCount`
- `citationCount`

失败时必须非零退出，并明确指出未满足的断言。

## 5. 数据保护

- 必须显式提供 `RAG_LAB_TEST_POSTGRES_URL`。
- 必须显式提供 `RAG_LAB_AGENT_RUNTIME_CHECKPOINT_DATABASE_URL`。
- 两个 DSN 必须指向同一个独立测试数据库，数据库名必须以 `_test` 结尾。
- Checkpoint 表只能在独立测试数据库中初始化。

## 6. 完成定义

- 真实 E2E 在独立测试库中通过。
- 真实 Provider 完成文档入库、问答和摘要模型调用。
- Checkpointer 重建后同一会话可恢复。
- Tool、Trace 与 QARun 审计可以通过标识串联。
- 相关专项回归、编译检查和 `git diff --check` 通过。

