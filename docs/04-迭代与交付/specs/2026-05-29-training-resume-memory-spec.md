# 员工培训断线续接与上下文摘要记忆设计规范

> 用途：本文件是 B-312 / Sprint 61 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

让员工中断课堂后能恢复当前状态、最近消息、摘要记忆和待处理动作，减少重复学习和状态丢失。

## 范围

- 会话详情返回 `pendingActions`。
- 会话持久化 `contextSummary`。
- 追问时使用最近消息和摘要记忆。
- 应用端恢复课堂页面时渲染待处理动作。

## 响应约定

`GET /training/classroom/sessions/{sessionId}` 的 `metadata` 增加：

- `pendingActions`
- `contextSummary`
- `currentDocument`
- `currentSectionIndex`

## 验收标准

- `CHECK_UNDERSTAND` 恢复后仍展示“听懂了继续/继续追问”。
- `SUMMARY` 恢复后仍展示“下一节/完成课程”。
- 最近消息和摘要记忆不会跨 App 或跨员工复用。
- 应用端刷新后可继续提交事件。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_resume.py -q
cd external-training-app/frontend
npm run build
```
