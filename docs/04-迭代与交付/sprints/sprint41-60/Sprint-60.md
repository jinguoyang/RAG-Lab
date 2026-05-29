# 迭代计划 Sprint 60

## 1. Sprint 基本信息

- Sprint 名称：Sprint 60
- Sprint 主题：员工培训 AI 生成与主观题评分
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 目标：将学习计划、题库生成和主观题评分从规则化能力升级为 LLM 辅助能力，并保留证据绑定和规则回退。

## 2. 关键假设

- Sprint 59 已完成 Skill Registry 和 LLM JSON 解析基座。
- AI 输出只作为草稿或辅助评分，必须经平台 schema 和业务校验。
- 客观题评分继续以服务端题库答案为准。
- LLM 失败时，接口必须可用并回退到规则草稿或保守评分。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-306 | 员工培训 AI 学习计划生成完整化 | P0 | 2d | Ready | [Spec](../../specs/2026-05-29-training-ai-plan-generation-spec.md) |
| B-307 | 员工培训 AI 题库生成完整化 | P0 | 2d | Ready | [Spec](../../specs/2026-05-29-training-ai-question-generation-spec.md) |
| B-308 | 员工培训主观题 LLM 批改 | P0 | 1.5d | Ready | [Spec](../../specs/2026-05-29-training-subjective-grading-spec.md) |

## 4. 验收标准

- 学习计划生成优先使用 LLM 结构化输出，失败时规则回退。
- 题库生成支持按单文档生成选择题、判断题和主观题。
- 所有题目保留 evidenceChunkIds。
- 主观题评分使用服务端 rubric 和证据，不能信任客户端 rubric。

## 5. 范围边界

- 不实现审核发布和版本冻结。
- 不实现学习进度和报表。
- 不实现证书或组织级学习画像。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_llm_plan.py backend/app/tests/integration/test_employee_training_question_generation.py backend/app/tests/integration/test_employee_training_subjective_grading.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
git diff --check
```

## 7. 关联文档

- [员工培训智能体完整化实施计划](../../plans/2026-05-29-employee-training-agent-completion-plan.md)
- [AI 学习计划生成设计规范](../../specs/2026-05-29-training-ai-plan-generation-spec.md)
- [AI 题库生成设计规范](../../specs/2026-05-29-training-ai-question-generation-spec.md)
- [主观题 LLM 批改设计规范](../../specs/2026-05-29-training-subjective-grading-spec.md)

## 8. 执行记录

- 待执行。
