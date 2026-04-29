# 迭代计划 Sprint 24

## 1. Sprint 基本信息

- Sprint 名称：Sprint 24
- Sprint 主题：真实 RAG 监控回放与验收硬化
- 涉及 Epic：E20 真实 RAG 有效闭环
- 建议版本：V1.6
- 时间范围：待定
- 目标：在 Sprint 23 真实 QA 主链路基础上，补齐监控展示、回放复跑、差异对比、端到端验收脚本和真实依赖复测记录。

## 2. 关键假设

- Sprint 23 已经能产生至少一个真实文档 QA Run。
- 回放复跑只复用上下文和配置，不复用旧授权结果。
- V1.6 验收脚本需要同时支持本地源码护栏和真实环境复测结果记录。

## 3. 本 Sprint 目标

- P10 能对真实文档 QA Run 回放复跑并展示差异。
- P06/P07/P09/P10 展示真实链路关键阶段状态和失败原因。
- 建立 `verify_v16_real_rag_e2e.py` 作为 V1.6 单一验收入口。
- 补齐发布环境真实依赖复测记录和环境限制说明。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S24-001 | B-105 | 完善真实文档 QA 的历史回放、复跑和差异对比 | P0 | 1.5d | Codex | Todo |
| S24-002 | B-106 | P06/P07/P09/P10 展示真实链路状态和失败原因 | P1 | 1.5d | Codex | Todo |
| S24-003 | B-107 | 建立 V1.6 真实文档 RAG 端到端验收脚本 | P0 | 1.5d | Codex | Todo |
| S24-004 | B-108 | 补齐真实依赖复测记录和环境限制说明 | P1 | 1d | Codex | Todo |

## 5. 验收标准

- P10 能从真实 QA Run 回放到 P09，并复跑生成新的 QARun。
- 对比视图能展示答案、Evidence、Citation、Trace 耗时和配置差异。
- `verify_v16_real_rag_e2e.py` 能输出通过、代码缺口或环境限制三类结果。
- 发布与运维文档记录真实 Provider 的复测命令、失败分类和后续处理方式。

## 6. 范围边界

- 不建设批量回放中心或 BI 报表。
- 不把 Provider 环境不可用视为代码通过；必须在验收输出中单独标记。
- 不新增复杂审批、通知或工单流。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- V1.6 验收脚本：`conda run -n rag-lab python scripts/verify_v16_real_rag_e2e.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
