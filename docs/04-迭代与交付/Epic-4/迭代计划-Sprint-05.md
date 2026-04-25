# 迭代计划 Sprint 05

## 1. Sprint 基本信息

- Sprint 名称：Sprint 05
- Sprint 主题：E4 QA Run 最小链路
- 时间范围：待定
- 目标：完成 QARun 创建、状态轮询、详情、历史和 mock Provider 调试闭环。

## 2. 关键假设

- Sprint 05 基于 Sprint 04 的 ConfigRevision active 指针继续推进。
- MVP 阶段 QARun 采用创建后同步完成的 mock 执行器，但接口契约仍按异步轮询设计返回 `statusUrl` 和 `detailUrl`。
- 当前仍沿用开发期最小权限：平台管理员可访问全部可见知识库，普通用户仅访问自己负责的知识库。
- 真实 LLM、Embedding、Dense、Sparse、Graph Provider 不在本 Sprint 接入。

## 3. 本 Sprint 目标

- 新增 QA Run、Trace、Candidate、Evidence、Citation 基础表与迁移。
- 实现 QARun 创建、状态查询、详情查询和历史分页接口。
- 实现 mock Provider，跑通 Query -> Trace -> Evidence -> Answer 最小链路。
- 前端 P09/P10 接入真实接口，展示运行状态、回答、证据、引用、Trace 和历史列表。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S5-001 | B-017 | 实现 QARun、Trace、Candidate、Evidence、Citation 基础表与迁移 | P0 | 1d | Codex | Done |
| S5-002 | B-018 | 实现 QARun 创建、状态轮询、详情查询接口 | P0 | 2d | Codex | Todo |
| S5-003 | B-019 | 实现 mock Provider，跑通 Query -> Trace -> Evidence -> Answer 最小链路 | P0 | 1d | Codex | Todo |
| S5-004 | B-020 | 接入 QA 调试页和 QA 历史页最小链路 | P0 | 2d | Codex | Todo |

## 5. 建议实现顺序

1. 数据库迁移：先落 QARun 和明细表，保持与接口和数据模型术语一致。
2. 后端 Schema 与服务：新增 QARun DTO、创建请求、状态响应和详情响应。
3. mock 执行器：在服务层生成可追溯 Trace、Candidate、Evidence、Citation 和 Metrics。
4. API 接口：注册创建、状态、详情和历史列表路由。
5. 前端接入：沿用 `types / services / adapters / pages` 分层，P09/P10 不直接拼接 API 路径。
6. 验证与文档：执行后端编译、接口 TestClient 验证、前端构建，并回写 backlog 状态。

## 6. 验收标准

- 后端可以执行 Alembic 迁移到 `0005_qa_run_tables` 或后续 head。
- `POST /api/v1/knowledge-bases/{kbId}/qa-runs` 可以创建 QARun 并锁定 ConfigRevision。
- `GET /api/v1/knowledge-bases/{kbId}/qa-runs/{runId}/status` 可以返回进度和 `detailReady`。
- `GET /api/v1/knowledge-bases/{kbId}/qa-runs/{runId}` 可以返回 Answer、Evidence、Citation、Trace 和 Metrics。
- `GET /api/v1/knowledge-bases/{kbId}/qa-runs` 可以分页返回 QA 历史。
- P09 可发起一次调试并展示结果，P10 可查看历史记录。

## 7. 范围边界

- 不接入真实 LLM、Embedding、Rerank、Milvus、OpenSearch 或 Neo4j。
- 不实现 WebSocket 或 Server-Sent Events，MVP 使用轮询契约。
- 不实现人工反馈、回放上下文和评估样本接口。
- 不重构 P09/P10 的整体视觉结构，只做真实数据接入所需的最小改动。
