# 迭代计划 Sprint 29

## 1. Sprint 基本信息

- Sprint 名称：Sprint 29
- Sprint 主题：治理后验证闭环
- 涉及 Epic：E22 知识库治理工作流强化
- 建议版本：内部增强
- 时间范围：待定
- 目标：治理动作完成后复用已有 QA / EvaluationRun 链路，形成最近治理动作、验证入口和验证结果摘要。

## 2. 关键假设

- Sprint 27 和 Sprint 28 已完成治理操作与诊断入口。
- 治理后验证优先复用已有 EvaluationRun，不新建实验平台。
- Chunk 排除只影响后续检索和 QA，不删除正文真值。

## 3. 本 Sprint 目标

- 治理动作完成后提供“验证治理效果”入口。
- P05 增加最近治理动作和验证结果摘要。
- QA evidence 和图支撑 Chunk 过滤被治理排除的 Chunk。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S29-001 | B-124 | 治理动作完成后提供验证治理效果入口，复用 EvaluationRun 链路 | P1 | 1.5d | Codex | Done |
| S29-002 | B-125 | P05 增加最近治理动作和验证结果摘要 | P2 | 1d | Codex | Done |

## 5. 验收标准

- P05 能触发已有 EvaluationRun 作为治理后验证入口。
- P05 能展示最近治理动作和验证结果摘要。
- 被治理排除的 Chunk 不进入 QA evidence。
- 图支撑 Chunk 查询会过滤治理排除标记。

## 6. 范围边界

- 不建设新的实验平台。
- 不新增新的发布版本或上线部署事项。
- 不把治理动作直接等同于验证通过；验证结果仍来自 EvaluationRun。
- 不删除被排除 Chunk 的正文真值。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- 既有治理验证：`conda run -n rag-lab python scripts/verify_sprint16_kb_governance.py`
- Sprint 29 验证：`conda run -n rag-lab python scripts/verify_sprint29_governance_validation.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`

## 8. 执行记录

- B-124：P05 增加“验证治理效果”入口，复用 EvaluationRun 创建与查询能力。
- B-125：P05 增加最近治理动作和治理验证摘要，辅助判断治理动作是否改善检索与引用。
- QA 和图支撑链路继续过滤治理排除 Chunk，保持 PostgreSQL 正文真值不被删除。
- 新增 `verify_sprint29_governance_validation.py`，检查 EvaluationRun 契约、治理排除过滤和 P05 验证闭环入口。
