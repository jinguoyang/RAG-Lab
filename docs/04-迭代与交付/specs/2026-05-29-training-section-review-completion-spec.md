# 员工培训章节边界、错题复习与课程完成设计规范

> 用途：本文件是 B-310 / Sprint 61 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

完善课堂状态机中的章节边界、未通过复习、下一节和课程完成逻辑，避免课堂无限推进或提前完成。

## 范围

- `GRADE` 阶段根据通过分决定进入 `REVIEW` 或 `SUMMARY`。
- `SUMMARY -> NEXT_SECTION -> TEACH` 前检查是否存在下一节。
- 最后一节通过后允许进入 `COMPLETED`。
- 复习阶段展示错题和证据摘要。

## 状态规则

- `score >= passingScore`：通过本节，可进入小结。
- `score < passingScore`：进入复习，复习后回到教学或重新测验。
- 有下一节：`SUMMARY -> NEXT_SECTION -> TEACH`。
- 无下一节：`SUMMARY -> COMPLETED`。

## 验收标准

- 未通过不会计入完成。
- 最后一节完成后课程状态可变为 `COMPLETED`。
- 越界进入下一节会被控制器拦截。
- 复习内容包含错题解释和 Citation。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_progress.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
```
