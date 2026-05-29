# 员工培训报表与薄弱点统计设计规范

> 用途：本文件是 B-314 / Sprint 62 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

为管理员提供员工培训完成率、平均分、错题分布和薄弱能力统计，支撑培训运营和复训安排。

## 范围

- 新增平台报表服务和 API。
- 聚合 `training_progress_records` 和 `training_answer_records`。
- 外部培训应用管理员页面展示摘要。
- 不实现证书、复杂组织树和长期学习画像。

## API

- `GET /api/v1/training/reports/summary?appId=...`

## 输出

- `completionRate`
- `averageScore`
- `passedCount`
- `failedQuestionCount`
- `weaknesses`

## 验收标准

- 完成率和平均分按当前 App 聚合。
- 错题和薄弱点可追溯到题目或能力组。
- 无数据时返回空报表，不抛 500。
- 应用端不直接访问平台数据库。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_reports.py -q
cd external-training-app/frontend
npm run build
```
