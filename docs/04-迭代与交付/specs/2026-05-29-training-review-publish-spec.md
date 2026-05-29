# 员工培训管理员审核、发布与版本冻结设计规范

> 用途：本文件是 B-311 / Sprint 61 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

建立学习计划和题库的管理员审核发布闭环，使 AI 草稿经过人工确认后形成稳定版本，课堂只使用已发布版本。

## 范围

- 学习计划 `draft -> published/rejected`。
- 题目 `draft -> approved/rejected` 或 `published/rejected`。
- 发布后的版本不可被草稿更新直接覆盖。
- 外部培训应用接入平台发布接口。

## API

- `POST /api/v1/training/plans/{planId}/publish`
- `POST /api/v1/training/questions/{questionId}/publish`

## 验收标准

- 只有 `draft` 状态可发布。
- 发布动作记录审核人和时间。
- 课堂只选择已发布或已审核题目。
- 应用端只调用平台发布接口，不自行改平台权威状态。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_review_publish.py -q
cd external-training-app/backend
python -m pytest app/tests/integration/test_classroom_api.py -q
```
