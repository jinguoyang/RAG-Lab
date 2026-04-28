# 迭代计划 Sprint 10

## 1. Sprint 基本信息

- Sprint 名称：Sprint 10
- Sprint 主题：E9 图检索分析与诊断
- 时间范围：待定
- 目标：完成图快照、图查询诊断、支撑 Chunk 回落和 stale 状态标记，为 P11 图检索分析页提供可联调基础。

## 2. 关键假设

- Sprint 10 基于 E5 的 Neo4j Graph Retrieval Provider 占位能力和 E7 的 Chunk 真值继续推进。
- 本轮不扩展新的图存储模型，`graph_snapshots` 仍作为图快照状态与诊断入口。
- `pipelineDefinition` 仍是后端执行契约，P11 页面画布和展示状态不反向污染后端快照模型。
- 图支撑证据必须回落到授权 Chunk 后再返回，不能直接以图数据库副本替代 PostgreSQL 真值。
- ACL 变更触发 stale 标记先作为规则沉淀，具体联动由后续权限治理任务复用。

## 3. 本 Sprint 目标

- 提供图快照列表、详情、实体搜索、路径搜索和社区摘要接口。
- 提供图对象支撑 Chunk 回落查询，并返回权限裁剪后的 `filteredCount` 诊断。
- 沉淀 P11 图检索分析页所需的 stale 提示规则和 Sprint 文档。
- 将文档 active version 切换、Chunk 重建后的成功图快照统一标记为 stale。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S10-001 | B-043 | 实现图快照列表/详情、实体搜索、关系路径和社区摘要接口 | P1 | 1d | Codex | Done |
| S10-002 | B-044 | 实现图支撑 Chunk 回落查询、权限裁剪和 filteredCount 诊断 | P0 | 1d | Codex | Done |
| S10-003 | B-045 | 实现图检索分析页 P11 的快照、实体路径、支撑证据和 stale 提示 | P1 | 1d | Codex | Done |
| S10-004 | B-046 | 完善 GraphSnapshot stale 标记规则与文档、ACL 变更联动 | P1 | 0.5d | Codex | Done |

## 5. Stale 标记规则

| reason | 触发场景 | 当前处理 |
| --- | --- | --- |
| `active_version_changed` | 文档 active version 切换后，已有成功图快照不再代表当前检索真值 | 已由文档版本激活流程调用统一 stale helper |
| `chunk_changed` | 文档版本重新解析或入库 Worker 删除、替换 Chunk 后，图支撑引用可能失效 | 已由本地入库 Worker 调用统一 stale helper |
| `acl_changed` | 成员、角色、ACL 或 Chunk 访问过滤摘要变化后，图支撑证据权限诊断可能变化 | 预留给后续权限治理任务复用同一 helper |

规则约束：只更新 `status = success` 的图快照为 `stale`，不覆盖已经 stale 的快照原因和时间。

## 6. 验收标准

- 图快照列表、详情、实体搜索、路径搜索、社区摘要和支撑 Chunk 回落接口可通过最小验证脚本。
- `mark_graph_snapshots_stale` 可被验证脚本导入并调用。
- 文档 active version 切换会以 `active_version_changed` 标记当前成功图快照为 stale。
- 文档入库 Worker 删除并替换 Chunk 后，会以 `chunk_changed` 标记当前成功图快照为 stale。
- 已经 stale 的图快照不会被新的 stale 规则覆盖。
- 后端应用代码可通过 Python 编译检查，Epic 9 图验证脚本可通过。

## 7. 范围边界

- B-045 前端页面已作为 Task 4 完成，本 Sprint 不再扩展 P11 之外的新前端页面。
- 不实现 ACL 变更时的实际调用链，只记录 `acl_changed` 复用规则。
- 不新增图数据库重建调度或后台任务。
- 不改变现有 Graph Retrieval Provider 的外部依赖接入方式。
