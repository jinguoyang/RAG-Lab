# 迭代计划 Sprint 10

## 1. Sprint 基本信息

- Sprint 名称：Sprint 10
- Sprint 主题：图检索分析与诊断
- 涉及 Epic：E9 图检索分析与诊断
- 时间范围：已完成
- 目标：完成图快照、实体路径、社区摘要、支撑 Chunk 回落和 stale 诊断的本地可验证闭环。

## 2. 关键假设

- 图结构不替代 PostgreSQL 业务真值，支撑 Chunk 必须回表并经过权限裁剪。
- Sprint 10 优先完成本地可验证的图诊断能力，不强依赖真实 Neo4j 在线。
- P11 以诊断和解释为主，不扩展为自由图编辑器。

## 3. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- |
| S10-001 | B-043 | 实现图快照列表/详情、实体搜索、关系路径和社区摘要接口 | P1 | Codex | Done |
| S10-002 | B-044 | 实现图支撑 Chunk 回落查询、权限裁剪和 filteredCount 诊断 | P0 | Codex | Done |
| S10-003 | B-045 | 实现图检索分析页 P11 的快照、实体路径、支撑证据和 stale 提示 | P1 | Codex | Done |
| S10-004 | B-046 | 完善 GraphSnapshot stale 标记规则与文档、ACL 变更联动 | P1 | Codex | Done |

## 4. 验收标准

- 可查询图快照、实体、关系路径和社区摘要。
- 图支撑 Chunk 查询必须经过 PostgreSQL 回表和权限裁剪，并输出 `filteredCount` 诊断。
- 文档、版本或 ACL 变更后，相关图快照能被标记为 stale。
- P11 页面能展示快照、实体路径、支撑证据和 stale 提示。

## 5. 验证命令

- 后端图检索验证：`conda run -n rag-lab python scripts/verify_epic9_graph.py`
- 后端编译：`conda run -n rag-lab python -m compileall app`
- 前端构建：`npm run build`
