# 员工培训主观题 LLM 批改设计规范

> 用途：本文件是 B-308 / Sprint 60 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

让平台按题库中的 rubric 和知识库证据对主观题进行 AI 辅助评分，并返回分数、评分理由和命中的评分项。

## 范围

- 在 `training_classroom_service.py` 中为主观题接入 `gradeSubjectiveAnswer` Skill。
- 评分输入来自服务端题库，不信任客户端 rubric。
- LLM 失败时保留保守规则评分。
- 评分结果写入答题记录由 B-309 承接。

## 输入

- `questionId`
- 员工答案
- 服务端 rubric
- 题目证据

## 输出

- `score`
- `reason`
- `matchedCriteria`
- `needsManualReview`

## 验收标准

- 主观题评分不读取客户端传入的正确答案或 rubric。
- LLM 评分分数必须限制在 `0-100`。
- 返回内容可展示给管理员复核。
- LLM 异常时不阻断课堂流程。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_subjective_grading.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
```
