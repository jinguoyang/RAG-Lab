# 员工培训学习进度与完成判定设计规范

> 用途：本文件是 B-309 / Sprint 61 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

建立员工学习进度、答题记录和课程完成判定，使课堂测验结果能转化为业务真值，而不是只存在于消息文本中。

## 范围

- 新增 `training_progress_records`。
- 新增 `training_answer_records`。
- 新增 `training_progress_service.py`。
- 课堂评分后更新进度和答题记录。
- 不实现报表聚合，报表由 B-314 承接。

## 数据模型

`training_progress_records` 记录当前课程进度、完成小节数、最后得分和状态。

`training_answer_records` 记录每次答题的题目、答案、分数、是否正确和元数据。

## 验收标准

- 通过测验后当前小节计入完成。
- 未通过测验不计入完成。
- 答题记录包含分数和题目 ID。
- 进度按 `appId + sessionId + endUserId` 隔离。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_progress.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
```
