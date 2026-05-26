# 迭代计划 Sprint 53

> 归档说明：原“Sprint 53 嵌入页体验 + 运营视图”计划已按 E33 新口径取代。SSE、Markdown 渲染和 P13 运营分析降级为低优先级后续；本 Sprint 聚焦无 LLM 能力的外部培训应用基线。

## 1. Sprint 基本信息

- Sprint 名称：Sprint 53
- Sprint 主题：外部培训应用基线
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 目标：建立一个独立、轻量、无 LLM 能力的外部培训应用，用于接入平台员工培训 Agent，完成平台绑定、数据库迁移和学习计划审核最小链路。

## 2. 关键假设

- 外部培训应用是 demo 级外部接入应用，不是平台核心前端。
- 外部培训应用有自己的数据库，只保存最小业务状态和平台对象映射。
- 外部培训应用不直接调用 LLM、Embedding、向量库、图数据库或 RAG Provider。
- 平台侧仍是学习计划、题库、课堂状态和 Agent 输出的权威方。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-283 | 外部培训应用项目骨架 | P0 | 1.5d | Done |
| B-284 | 外部培训应用数据库设计与迁移 | P0 | 1.5d | Done |
| B-285 | 外部培训应用平台绑定与 API 接入 | P0 | 1.5d | Done |
| B-286 | 外部培训应用学习计划审核页面 | P0 | 2d | Done |

## 4. 验收标准

- 外部培训应用可以独立启动。
- 外部培训应用数据库包含外部用户、平台绑定、审核任务、课堂会话、课堂消息和答题记录的最小表。
- 外部培训应用后端可配置平台地址和 App 绑定信息。
- 学习计划审核页面能展示平台结构化草稿，并提交审核结果。
- 代码和配置中不存在 LLM Provider、Embedding Provider 或直接模型调用配置。

## 5. 范围边界

- 不实现课堂页面和结构化答题组件，它们在后续 Sprint 承接。
- 不实现题库审核页面，它在后续 Sprint 承接。
- 不实现完整 LMS、班级、证书或组织学习档案。
- 不实现 SSE、Markdown 渲染或运营分析。

## 6. 验证命令

```powershell
cd external-training-app
npm run build
```

```powershell
git diff --check
```

## 7. 关联文档

- [外部培训应用设计规范](../../specs/2026-05-26-external-training-app-design.md)
- [员工培训 Agent 与外部培训应用实施计划](../../plans/2026-05-26-employee-training-agent-and-external-app.md)

## 8. 执行记录

- B-283: 外部培训应用项目骨架 — Done（Vite+React+TypeScript 前端 + FastAPI+SQLite 后端）
- B-284: 外部培训应用数据库设计与迁移 — Done（6 张表：external_users, platform_app_bindings, training_review_tasks, training_class_sessions, training_class_messages, training_answer_records）
- B-285: 外部培训应用平台绑定与 API 接入 — Done（PlatformClient 通过 httpx 调用平台 API）
- B-286: 外部培训应用学习计划审核页面 — Done（BindingPage + ReviewPage，支持生成草稿和审核操作）
