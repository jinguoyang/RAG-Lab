# 迭代计划 Sprint 14

## 1. Sprint 基本信息

- Sprint 名称：Sprint 14
- Sprint 主题：评估结果驱动配置优化
- 涉及 Epic：E12 RAG 质量闭环、E13 配置优化闭环
- 建议版本：V1.1
- 时间范围：待定
- 目标：在 Sprint 13 的 EvaluationRun / Result 最小闭环基础上，补齐评估状态、指标汇总、结果导出、配置差异对比和失败样本生成优化草稿能力。

## 2. 关键假设

- Sprint 13 已完成 `B-058`、`B-060` 或至少完成 EvaluationRun / Result 的最小可用链路。
- 本轮只做轻量异步状态、失败重试和取消，不引入复杂任务调度平台。
- 配置优化草稿必须可复核，不自动激活，不直接覆盖 active revision。
- 评估结果导出只要求 CSV 或 Markdown 报告，不引入 BI 报表中心。

## 3. 本 Sprint 目标

- EvaluationRun 支持 queued / running / success / failed / cancelled 状态和失败重试。
- EvaluationResult 可汇总通过率、失败原因、核心 metrics，并支持导出。
- P08/P10 能看到 Config Revision 差异和评估结果关联关系。
- 失败评估样本可以生成一个待人工确认的配置优化草稿。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S14-001 | B-061 | 补齐 EvaluationRun 异步状态、失败重试和取消接口 | P1 | 1d | Codex | Todo |
| S14-002 | B-062 | 实现评估指标汇总、CSV 导出和回归报告落库 | P1 | 1d | Codex | Todo |
| S14-003 | B-063 | 实现 Config Revision 差异对比和评估结果关联视图 | P1 | 1d | Codex | Todo |
| S14-004 | B-064 | 从失败评估样本生成可复核配置优化草稿 | P2 | 1d | Codex | Todo |

## 5. 验收标准

- 后端可创建、取消、重试 EvaluationRun，并保存 run 级状态和错误摘要。
- 评估结果能按 run 汇总通过率、失败原因和关键 metrics。
- 评估结果可导出为 CSV 或 Markdown 报告。
- 前端能从评估批次跳转到关联 ConfigRevision，并查看关键参数差异。
- 配置优化草稿只进入草稿状态，不自动激活。

## 6. 范围边界

- 不做定时回归、多环境基准对比或复杂调度平台。
- 不接入 LLM-as-judge 自动评分。
- 不重做 P08/P10 页面信息架构，只在现有结构中增加必要入口。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 14 验证脚本：`conda run -n rag-lab python scripts/verify_sprint14_evaluation_loop.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
