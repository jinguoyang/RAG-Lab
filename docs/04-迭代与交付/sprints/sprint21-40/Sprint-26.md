# 迭代计划 Sprint 26

## 1. Sprint 基本信息

- Sprint 名称：Sprint 26
- Sprint 主题：RAG 配置评估与优化闭环
- 涉及 Epic：E21 RAG 模块化调优
- 建议版本：V1.7
- 时间范围：待定
- 目标：基于 Sprint 25 的模块化配置，固化 QARun Pipeline Snapshot，并通过评估对比支撑真实 RAG 参数优化。

## 2. 关键假设

- Sprint 25 已经让核心 RAG 节点和参数可配置。
- EvaluationRun 已具备最小批量回归能力，可复用为配置对比入口。
- 优化建议只作为可复核草稿，不直接修改 active pipeline。

## 3. 本 Sprint 目标

- QARun 保存实际执行的 Pipeline Snapshot 和节点级参数快照。
- 评估脚本能对比两个 Pipeline 配置的效果和耗时。
- P10/P08 能展示配置差异、样本差异和优化建议。
- 建立 V1.7 RAG 调优参数字典。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S26-001 | B-115 | 固化 QARun Pipeline Snapshot 和节点级参数快照 | P0 | 1.5d | Codex | Done |
| S26-002 | B-116 | 建立不同 Pipeline 配置的评估对比脚本 | P1 | 2d | Codex | Done |
| S26-003 | B-117 | P10/P08 展示配置效果对比和优化建议 | P1 | 2d | Codex | Done |
| S26-004 | B-118 | 建立 V1.7 RAG 调优指南和参数字典 | P2 | 1d | Codex | Done |

## 5. 验收标准

- 每个 QARun 可追溯到当次执行的 Pipeline Snapshot。
- 评估对比能展示命中、引用、答案质量、耗时和失败原因差异。
- 优化建议能说明关联样本、建议参数、预期影响和风险。
- 调优指南记录参数含义、推荐范围和常见诊断方向。

## 6. 范围边界

- 不自动上线优化建议。
- 不建设复杂实验平台或 AB 流量系统。
- 不引入新的指标体系，优先复用现有 EvaluationRun 和 Trace。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- 配置评估验证：`conda run -n rag-lab python scripts/verify_v17_pipeline_evaluation.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`

## 8. 执行记录

- B-115：新增 QARun `pipeline_snapshot` 与 `node_param_snapshot` 持久化字段，详情和配置对比优先读取运行快照。
- B-116：新增 V1.7 评估闭环验证脚本，评估结果补充 `hitCount`、`citationCount`、`latencyMs`、`failureReason` 和节点参数快照。
- B-117：P10 展示参数快照、配置效果对比、失败样本指标和优化建议；P08 发布复核提示关联评估对比。
- B-118：曾新增 V1.7 RAG 调优指南；后续文档瘦身时已合并到 [V1.7 RAG 模块化优化规划](../../releases/V1.7-RAG模块化优化规划.md) 的调优和复测口径中。
