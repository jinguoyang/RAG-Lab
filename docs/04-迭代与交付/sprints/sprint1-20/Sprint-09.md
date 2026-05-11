# 迭代计划 Sprint 09

## 1. Sprint 基本信息

- Sprint 名称：Sprint 09
- Sprint 主题：E8 QA 历史与评估闭环
- 时间范围：待定
- 目标：围绕 QA 历史详情、人工反馈、失败归因、回放上下文和评估样本，完成 P10 到 P09 的可联调闭环。

## 2. 关键假设

- Sprint 09 基于 E4 的 QARun 最小链路和 E7 的 Chunk 真值继续推进。
- 本轮完成 `B-039` 至 `B-042`。
- 失败归因先写入 `qa_runs.metrics.failureType`，避免为了单个归因字段扩大迁移范围。
- EvaluationSample 本轮只实现样本创建与列表，不实现完整回归执行和评分引擎。
- 回放上下文只负责带入 query、sourceRunId、revision 和 overrideParams，不直接复用旧答案。

## 3. 本 Sprint 目标

- 完善 QA 历史列表与详情 DTO，补充反馈、失败归因和 override 快照。
- 实现人工反馈更新接口、回放上下文接口、从 QARun 生成 Revision 草稿接口。
- 创建 `evaluation_samples` 表，实现从 QARun 加入评估集和评估样本列表。
- 接入 P10 历史详情抽屉、人工标注、回放到 P09、加入评估集和生成 Revision 草稿。
- P09 接收真实回放上下文，并在新运行时带入 sourceRunId、configRevisionId 和 overrideParams。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S9-001 | B-039 | 完善 QA 历史列表/详情、反馈标注和失败归因接口 | P0 | 1d | Codex | Done |
| S9-002 | B-040 | 实现回放上下文与从 QARun 生成 Revision 草稿入口 | P0 | 1d | Codex | Done |
| S9-003 | B-041 | 实现 EvaluationSample 创建、列表和回归样本管理最小接口 | P1 | 1d | Codex | Done |
| S9-004 | B-042 | 接入 QA 历史详情、人工标注、回放和加入评估集 | P0 | 1d | Codex | Done |

## 5. 验收标准

- QA 历史列表可按关键词、运行状态和反馈状态筛选。
- QA 历史详情可展示 Answer、Trace、Evidence、Candidate、反馈和失败归因。
- 人工反馈可保存为 `correct` / `wrong` 等状态，并持久化失败归因。
- 回放动作可把 query、sourceRunId、configRevisionId 和 overrideParams 带入 P09。
- 可从 QARun 生成 ConfigRevision 草稿，不修改原 Revision 和 active revision。
- 可从 QARun 生成 EvaluationSample，并可分页查询样本列表。
- 后端应用代码可通过 Python 编译检查，前端可通过 Vite 构建。

## 6. 范围边界

- 不实现评估样本批量导入、归档和删除。
- 不实现回归执行调度、评分规则和报告页面。
- 不实现复杂同 query 统计报表，P10 只做当前列表内的同 query 对比。
- 不改变 QA Run 的核心执行编排，只增强历史沉淀和回放入口。
