# 迭代计划 Sprint 56

## 1. Sprint 基本信息

- Sprint 名称：Sprint 56
- Sprint 主题：题库生成与审核
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 目标：平台侧基于已审核学习计划生成结构化题库草稿，并建立练习题、认证题、rubric 和认证题审核门禁。

## 2. 关键假设

- Sprint 55 已完成结构化学习计划生成、校验和版本快照。
- 题库属于平台侧权威数据，外部培训应用只负责审核界面和审核结果提交。
- 认证题必须人工审核后才能使用。
- 外部培训应用没有 LLM 能力，不能自行生成题目或评分模型。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-290 | 题库结构化草稿生成 | P0 | 2d | Done |
| B-291 | 认证题人工审核门禁 | P0 | 1.5d | Done |
| B-292 | 主观题 rubric 存储与 AI 辅助评分结构 | P1 | 2d | Done |

## 4. 验收标准

- 平台能基于已审核学习计划生成结构化题目草稿。
- 题目草稿包含题型、题干、选项、答案、解析、rubric 和来源证据。
- 练习题和认证题有明确分类。
- 未审核认证题不能进入课堂或认证流程。
- 主观题保存 rubric，AI 辅助评分必须基于 rubric 输出。

## 5. 范围边界

- 不实现证书和认证分数线业务闭环。
- 不实现错题复习。
- 不实现题目多模态。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

```powershell
git diff --check
```

## 7. 关联文档

- [员工培训 Agent 平台侧设计规范](../../specs/2026-05-26-employee-training-agent-platform-design.md)
- [员工培训 Agent 与外部培训应用实施计划](../../plans/2026-05-26-employee-training-agent-and-external-app.md)

## 8. 执行记录

- B-290: 题库结构化草稿生成 — Done（首版模板：单选、判断、主观题）
- B-291: 认证题人工审核门禁 — Done（draft → approved/rejected 状态门禁）
- B-292: 主观题 rubric 存储与 AI 辅助评分结构 — Done（rubric JSON 字段存储）
