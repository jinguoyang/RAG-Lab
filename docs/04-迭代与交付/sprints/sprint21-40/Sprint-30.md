# 迭代计划 Sprint 30

## 1. Sprint 基本信息

- Sprint 名称：Sprint 30
- Sprint 主题：RAG 应用运行时最小链路
- 涉及 Epic：E25 RAG 应用化封装
- 建议版本：V1.8
- 时间范围：待定
- 目标：将治理后的知识库与 Pipeline 以 RAG 应用形式暴露给外部 Web 应用，先跑通 blocking 对话接口、App API Key 鉴权和 QARun 可追溯闭环。
- 开发计划：[RAG App Runtime Implementation Plan](../../../superpowers/plans/2026-05-14-rag-app-runtime.md)

## 2. 关键假设

- 应用运行时复用现有 QARun、Evidence、Citation、Trace、权限裁剪和 Provider 链路，不另建一套黑盒问答执行器。
- 第一轮只支持 `blocking` 响应；SSE streaming、SDK 和 Webhook 后续再排期。
- 外部调用方通过 App API Key 鉴权，不直接复用后台用户登录态，也不开放公网匿名聊天。
- 应用绑定知识库和默认配置版本；若未指定配置版本，则使用知识库当前 active revision。

## 3. 本 Sprint 目标

- 支持创建、查询、更新 RAG 应用，并生成或禁用 App API Key。
- 支持 `POST /api/v1/app-runtime/chat-messages` blocking 调用。
- 每次外部调用创建会话、消息和调用审计记录，并关联到一次 QARun。
- App Runtime 输出只返回安全的 answer、citations、usage、metadata 和 `runId`，完整 Trace 仍在平台内部查看。
- 建立最小接口抽样验证，覆盖成功调用、无效 key、停用应用和无可运行配置。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S30-001 | B-133 | 实现 RAG 应用定义、API Key hash 存储和管理端最小接口 | P0 | 2d | Codex | Ready |
| S30-002 | B-134 | 实现 App Runtime blocking 对话接口，复用现有 QARun 执行链路 | P0 | 2d | Codex | Ready |
| S30-003 | B-135 | 建立外部 Conversation、Message 和 Invocation 记录，并关联 QARun | P0 | 1.5d | Codex | Ready |
| S30-004 | B-136 | 实现 App API Key 鉴权、禁用、轮换审计和最小调用来源记录 | P0 | 1.5d | Codex | Ready |
| S30-005 | B-137 | 建立 RAG 应用运行时最小接口抽样验证 | P0 | 1d | Codex | Ready |
| S30-006 | B-145 | 补齐 App Runtime 权限裁剪、跨知识库隔离和 Citation 安全回归 | P0 | 1d | Codex | Ready |

## 5. 验收标准

- 有效 App API Key 可以调用绑定应用并得到 answer、citations、conversationId、messageId、runId 和 usage。
- 无效、禁用或过期的 App API Key 被拒绝，且不暴露应用或知识库敏感细节。
- 停用应用、停用知识库、缺少可运行 Config Revision 时返回稳定业务错误。
- 外部调用产生的 `app_message` 和 `app_invocation` 能回溯到对应 QARun。
- 未授权或被治理排除的 Chunk 不会进入外部 answer、evidence 或 citations。

## 6. 范围边界

- 不建设 Dify 式自由工作流、插件市场或多租户计费。
- 不新增应用级 Prompt 变量和复杂表单输入；第一轮只保留 `query`、`conversationId`、`endUserId` 和 `inputs` 扩展位。
- 不开放完整 Trace 给外部调用方；外部只获取精简 metadata，内部治理页面仍可查看完整 QARun。
- 不改变现有 P09/P10 QA 调试与历史接口契约。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- OpenAPI 导出：`conda run -n rag-lab python scripts/export_openapi.py`
- App Runtime 接口抽样：通过 FastAPI TestClient 或接口联调覆盖成功调用、无效 key、停用应用和无可运行配置。
- 权限回归：抽样确认被治理排除或无权限 Chunk 不进入外部 answer、evidence 或 citations。
- 前端构建（如本 Sprint 改前端）：`npm run build`
- 空白检查：`git diff --check`

## 8. 执行记录

- 当前仅创建 Sprint 计划，尚未实施代码和接口抽样验证。
- Sprint 执行完成后，应将 B-133 至 B-137、B-145 的状态回写到 [产品待办清单](../../产品待办清单.md)。
