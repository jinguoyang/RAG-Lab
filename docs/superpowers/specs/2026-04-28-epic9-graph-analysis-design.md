# Epic 9 图检索分析与诊断设计

## 背景

Epic 9 覆盖产品待办 `B-043` 到 `B-046`，目标是在不伪造复杂图数据的前提下，完成图检索分析与诊断的本地可验证闭环：

- `B-043`：图快照列表/详情、实体搜索、关系路径和社区摘要接口。
- `B-044`：图支撑 Chunk 回落查询、权限裁剪和 `filteredCount` 诊断。
- `B-045`：P11 图检索分析页接入快照、实体路径、支撑证据和 stale 提示。
- `B-046`：完善 `GraphSnapshot` stale 标记规则与文档、ACL 变更联动。

本轮采用“本地可验证闭环优先”口径：接口和前端完整；Neo4j Provider 有数据时读取真实图摘要，没有配置或调用失败时返回空结果和明确降级诊断，不在后端伪造复杂图谱。

## 关键假设

- PostgreSQL 仍是业务真值中心，`graph_snapshots` 和 `graph_chunk_refs` 保存图快照元数据与支撑 Chunk 回溯关系。
- Neo4j 只保存图结构本体；实体、关系和社区摘要不能直接作为最终 Evidence 或 Citation。
- P11 页面只展示后端授权后的 Chunk，不在前端自行推断权限。
- 无 Neo4j 数据时，P11 仍应能展示快照状态、空结果/降级态和 supporting chunks 诊断。
- 本轮不新增生产级异步图构建 Worker，不重构现有 QA Run Provider 编排。

## 范围

本轮会修改：

- 后端 Graph DTO、Service 和 Route，补齐路径、社区、支撑 Chunk 回表裁剪和降级诊断。
- 后端 Graph Provider 抽象，新增路径查询与社区摘要查询能力，Neo4j 不可用时保持安全空结果。
- 文档生命周期或权限相关服务中的 stale 标记入口，保证 active version、Chunk 重写/删除、权限过滤摘要变化有一致规则。
- 前端 P11 页面、Graph 类型、Service 和 Adapter，使页面接入真实接口。
- Epic 9 Sprint 文档和产品待办状态。

本轮不会修改：

- 不搭建真实 Neo4j 测试环境。
- 不新增复杂图可视化库。
- 不把 Neo4j 图结构复制进 PostgreSQL。
- 不改变现有认证模型、角色权限矩阵或 QA Run 主流程。

## 后端设计

### Graph API

保留现有接口：

- `GET /api/v1/knowledge-bases/{kbId}/graph-snapshots`
- `GET /api/v1/knowledge-bases/{kbId}/graph-snapshots/{graphSnapshotId}`
- `GET /api/v1/knowledge-bases/{kbId}/graph/entities`
- `GET /api/v1/knowledge-bases/{kbId}/graph/supporting-chunks`

新增接口：

- `GET /api/v1/knowledge-bases/{kbId}/graph/paths`
- `GET /api/v1/knowledge-bases/{kbId}/graph/communities`

所有图摘要接口要求 `kb.view`；supporting chunks 要求 `kb.chunk.read` 语义，但实现上仍需要返回 `filteredCount` 诊断。为避免无权限用户通过接口枚举资源，服务层先判断知识库可见性，再执行 Chunk 回表裁剪；无 Chunk 正文权限时返回空 `items` 和被裁剪数量。

### DTO

新增或扩展 DTO：

- `GraphPathDTO`：包含 `pathKey`、`sourceEntity`、`targetEntity`、`relationType`、`hopCount`、`supportKeys`、`metadata`。
- `GraphCommunityDTO`：包含 `communityKey`、`title`、`summary`、`entityCount`、`supportKeys`、`metadata`。
- `GraphQueryDiagnosticsDTO`：包含 `degraded`、`degradedReason`、`provider`。
- `GraphPathSearchResponse` 和 `GraphCommunitySearchResponse`：包含 `items`、`graphSnapshotId`、`diagnostics`。
- `GraphSupportingChunkDTO` 扩展为包含 `documentId`、`documentName`、`chunkIndex`、`contentPreview`、`securityLevel`、`metadata`。

### Provider

`GraphRetrievalProvider` 扩展：

- `search_entities(...)`
- `search_paths(...)`
- `search_communities(...)`

`Neo4jGraphRetrievalProvider` 用 Cypher 查询真实摘要；`LocalGraphRetrievalProvider` 返回空列表。Provider 异常不向前端暴露内部错误细节，Service 统一转为 `diagnostics.degraded=true` 和可读原因。

### Supporting Chunks 回表裁剪

`list_supporting_chunks` 从 `graph_chunk_refs` 找到候选 Chunk 后，回表 `chunks`：

- 只返回 `chunks.kb_id` 匹配、`chunks.status='active'` 的记录。
- 用户具备 `kb.chunk.read` 时返回 Chunk 摘要和正文预览。
- 用户无 `kb.chunk.read` 时不返回正文，`filteredCount` 等于候选数量。
- 如果部分 Chunk 因状态、知识库不匹配或权限不可见被过滤，计入 `filteredCount`。

### Stale 标记

新增集中函数，例如 `mark_graph_snapshots_stale(session, kb_id, reason, current_user)`，统一处理：

- 将当前知识库下 `status='success'` 的快照更新为 `stale`。
- 写入 `stale_reason`、`stale_at`、`updated_at`、`updated_by`。
- 避免重复 stale 的快照被反复覆盖原因。

调用点：

- 文档 active version 切换：原因 `active_version_changed`。
- Chunk 重写/删除：原因 `chunk_changed`。
- ACL 或 Chunk 访问过滤摘要变化：原因 `acl_changed`。

## 前端设计

### 接入层

新增：

- `frontend/src/app/types/graph.ts`
- `frontend/src/app/services/graphService.ts`
- `frontend/src/app/adapters/graphAdapter.ts`

`graphService` 只负责 API 调用；`graphAdapter` 将 DTO 转为 P11 ViewModel，避免页面直接理解后端字段细节。

### P11 页面结构

P11 改为真实接口页：

- 页面加载时读取图快照列表，默认选最近一条。
- 快照状态区展示实体数、关系数、社区数、更新时间、状态和 stale 原因。
- 实体搜索区按关键词调用 `/graph/entities`。
- 路径区调用 `/graph/paths`，展示源实体、目标实体、关系类型和跳数。
- 社区区调用 `/graph/communities`，展示社区标题、摘要和实体数量。
- 支撑 Chunk 区在用户点击实体、路径或社区后调用 `/graph/supporting-chunks`。

### 页面状态

- `loading`：首次加载快照、搜索或回落 Chunk 时展示局部加载。
- `empty`：没有快照或没有图结果时展示空态。
- `degraded`：Provider 不可用或 Neo4j 未配置时展示降级提示。
- `stale`：快照过期时展示暖色提示，说明图谱可能落后于文档或权限。
- `permission filtered`：`filteredCount > 0` 时提示部分支撑证据因权限被裁剪，不展示被裁剪对象细节。
- `error`：接口失败时展示可恢复错误，并保留已加载结果。

## 验证设计

后端按 TDD 推进：

- 先写图路径和社区接口测试，确认无 Provider 数据时返回空结果和降级诊断。
- 先写 supporting chunks 权限裁剪测试，确认无 `kb.chunk.read` 时不返回正文并增加 `filteredCount`。
- 先写 stale 标记测试，确认 success 快照被置为 stale 且已有 stale 不被重复覆盖。
- 实现后运行 `conda run -n rag-lab python -m compileall app` 和相关 FastAPI TestClient 测试。

前端验证：

- 运行 `npm run build`。
- 使用浏览器检查 P11：快照加载、实体搜索、路径/社区空态、supporting chunks 回落、stale 和权限裁剪提示。

## 完成标准

- `B-043` 到 `B-046` 对应能力完成并在产品待办中更新为 `Done`。
- 新增或更新 Sprint 10 / Epic 9 迭代计划，记录范围、验收标准和验证命令。
- 每完成一个 backlog 做一次 git commit，并同步更新待办文档。
- 最终代码通过后端编译检查、相关 API 测试和前端构建。
