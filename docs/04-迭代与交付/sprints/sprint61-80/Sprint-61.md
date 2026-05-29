# 迭代计划 Sprint 61

## 1. Sprint 基本信息

- Sprint 名称：Sprint 61
- Sprint 主题：员工培训进度、审核发布与断线续接
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 目标：补齐学习进度、答题记录、章节边界、管理员审核发布和课堂断线续接，形成可恢复的培训业务闭环。

## 2. 关键假设

- Sprint 60 已完成 AI 计划、AI 题库和主观题评分。
- 计划和题目发布后才作为课堂正式业务数据。
- 进度和答题记录是业务真值，不能只保存在消息文本中。
- 断线续接由平台返回当前状态和待处理动作，应用端只负责渲染。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-309 | 员工培训学习进度、答题记录和完成判定 | P0 | 2d | Ready | [Spec](../../specs/2026-05-29-training-progress-completion-spec.md) |
| B-310 | 员工培训章节边界、错题复习与课程完成 | P0 | 1.5d | Ready | [Spec](../../specs/2026-05-29-training-section-review-completion-spec.md) |
| B-311 | 员工培训管理员审核、发布与版本冻结 | P0 | 2d | Ready | [Spec](../../specs/2026-05-29-training-review-publish-spec.md) |
| B-312 | 员工培训断线续接与上下文摘要记忆 | P0 | 1.5d | Ready | [Spec](../../specs/2026-05-29-training-resume-memory-spec.md) |

## 4. 验收标准

- 课堂评分后写入答题记录和进度记录。
- 未通过进入复习，最后一节通过后可完成课程。
- 计划和题目发布后形成稳定版本，课堂只使用发布数据。
- 刷新或重新进入课堂能恢复状态、待处理动作和上下文摘要。

## 5. 范围边界

- 不实现报表聚合。
- 不实现跨 App 安全专项测试，该项由 Sprint 62 承接。
- 不实现复杂组织学习档案。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_progress.py backend/app/tests/integration/test_employee_training_review_publish.py backend/app/tests/integration/test_employee_training_resume.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
cd external-training-app/frontend
npm run build
cd ../../
git diff --check
```

## 7. 关联文档

- [员工培训智能体完整化实施计划](../../plans/2026-05-29-employee-training-agent-completion-plan.md)
- [学习进度与完成判定设计规范](../../specs/2026-05-29-training-progress-completion-spec.md)
- [章节边界与课程完成设计规范](../../specs/2026-05-29-training-section-review-completion-spec.md)
- [审核发布设计规范](../../specs/2026-05-29-training-review-publish-spec.md)
- [断线续接与摘要记忆设计规范](../../specs/2026-05-29-training-resume-memory-spec.md)

## 8. 执行记录

- 待执行。
