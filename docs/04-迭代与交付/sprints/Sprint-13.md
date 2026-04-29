# 迭代计划 Sprint 13

## 1. Sprint 基本信息

- Sprint 名称：Sprint 13
- Sprint 主题：RAG 质量回归与发布观测
- 时间范围：待定
- 目标：在 Sprint 12 验收硬化和参数生效基础上，补齐评估样本批量回归、结果视图、Provider 连通性诊断和 V1.0 验收报告。

## 2. 关键假设

- Sprint 13 默认承接 Sprint 12 的产物：端到端验收脚本、权限回归用例、验收清单回填和 P08 参数生效链路已经完成或正在收尾。
- 本轮选择 `B-056`、`B-057`、`B-058`、`B-060`，不再扩大到 P02/P05 统计增强或 P08 模板预设。
- EvaluationSample 已有创建和列表能力；本轮新增 EvaluationRun / Result 的最小闭环，先做人工触发和同步/轻量执行，不引入复杂调度平台。
- Provider 诊断只做显式触发的 readiness 级检查，基础 `/health` 仍保持轻量，不被外部组件网络状态拖慢。
- PostgreSQL 继续作为评估运行、结果、报告和发布验收状态的业务真值中心。

## 3. 本 Sprint 目标

- 扩展 Provider 真实连通性诊断，能区分未配置、配置存在但连接失败、连接成功和 local/mock 降级。
- 形成 V1.0 验收执行报告，记录通过项、失败项、环境限制、真实 Provider 风险和后续处理建议。
- 实现 EvaluationRun / EvaluationResult 最小数据模型与接口，支持对评估样本集触发批量回归并保存每条样本结果。
- 在 P10 或评估集入口展示回归批次、通过率、失败原因、关联 ConfigRevision 和可回放 QARun。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S13-001 | B-056 | 扩展 Provider 真实连通性诊断与降级说明 | P1 | 1d | Codex | Done |
| S13-002 | B-057 | 补 V1.0 验收执行报告与遗留风险清单 | P1 | 0.5d | Codex | Done |
| S13-003 | B-058 | 实现 EvaluationRun / Result 最小模型与批量回归执行接口 | P1 | 1.5d | Codex | Done |
| S13-004 | B-060 | P10 增加评估集回归结果视图 | P1 | 1d | Codex | Done |

## 5. 验收标准

- Provider 诊断接口或脚本能输出每类 Provider 的配置状态、连通状态、降级状态和失败原因，且不会影响基础健康检查。
- V1.0 验收执行报告能引用 Sprint 12 验收结果，并明确列出真实 Provider 环境下仍需复测的项目。
- EvaluationRun 可从现有 EvaluationSample 集合创建，保存 run 级状态、目标 ConfigRevision、样本总数、通过数、失败数和错误摘要。
- EvaluationResult 可记录单条样本的 query、expectedAnswer 或 judgingHint、实际 QARun、判定状态、失败原因和核心 metrics。
- P10 能展示回归批次列表和批次详情，至少包含通过率、失败原因、关联 revision、样本级结果和跳转到历史运行的入口。
- 后端应用代码可通过 Python 编译检查，前端可通过 Vite 构建，新增回归验证脚本可在本地环境运行。

## 6. 范围边界

- 不实现复杂异步调度、队列重试、定时回归或多环境基准对比。
- 不引入自动 LLM-as-judge 评分；本轮只保留规则判定、人工判定字段或可解释的最小比较结果。
- 不修改 QARun 的核心执行契约，EvaluationRun 通过现有 QARun 创建与详情链路复用结果。
- 不新增新的图表库；P10 优先使用现有卡片、表格、Badge 和抽屉组件展示回归结果。
- 不要求真实外部 Provider 必须在线才能完成本地验收；真实连通性失败应被诊断和记录，而不是阻塞 local/mock 验收。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 13 验证脚本：`conda run -n rag-lab python scripts/verify_sprint13_regression.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
