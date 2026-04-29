# 迭代计划 Sprint 22

## 1. Sprint 基本信息

- Sprint 名称：Sprint 22
- Sprint 主题：真实回放、复跑与对比
- 涉及 Epic：E19 真实检索与回放闭环
- 建议版本：V1.5
- 时间范围：待定
- 目标：完善 P10 历史回放，让历史 QARun 能带完整上下文回到 P09，支持复跑并比较原结果、新结果和配置差异。

## 2. 关键假设

- Sprint 21 已经让 P09 真实 QA 主链路可运行。
- 回放不是复用旧答案，而是基于历史上下文创建新的 QARun。
- 历史 Evidence 读取仍按当前用户权限二次校验。
- 对比只覆盖研发调试所需字段，不建设 BI 报表中心。

## 3. 本 Sprint 目标

- QARun 回放上下文补齐 retrieval channels、topK、temperature、maxContextTokens、graphSnapshotId、provider diagnostics。
- P10 支持一键回放到 P09 并保留来源 runId。
- 复跑后展示原运行与新运行的状态、答案、证据、引用、Trace 指标和配置差异。
- 补齐真实检索链路下的权限裁剪和跨 KB 回归。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S22-001 | B-097 | 完善 QARun 回放上下文快照 | P0 | 1.5d | Codex | Todo |
| S22-002 | B-098 | 支持回放复跑、结果对比和配置差异对比 | P0 | 2d | Codex | Todo |
| S22-003 | B-099 | 补齐真实检索链路下的权限裁剪回归 | P0 | 1.5d | Codex | Todo |
| S22-004 | B-100 | 建立 V1.5 真实 QA 与回放验收脚本 | P0 | 1d | Codex | Todo |

## 5. 验收标准

- P10 点击回放后，P09 自动带入原 query、sourceRunId、configRevisionId 和 overrideParams。
- 用户复跑后，系统创建新的 QARun，并与 sourceRunId 建立可追溯关系。
- 对比视图能展示原结果和新结果的答案差异、证据差异、引用差异、Trace 耗时差异和配置差异。
- 无权限用户无法通过回放读取或复跑不可见 run。

## 6. 范围边界

- 不做复杂评审流或工单派发。
- 不做跨知识库批量回放。
- 不以历史快照绕过当前权限。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 22 验证脚本：`conda run -n rag-lab python scripts/verify_sprint22_replay.py`
- V1.5 真实链路验收：`conda run -n rag-lab python scripts/verify_v15_real_qa_replay.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
