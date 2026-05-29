# 员工培训 AI 题库生成设计规范

> 用途：本文件是 B-307 / Sprint 60 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

将当前模板化题库草稿升级为 AI 辅助出题：平台针对单个文档或指定文档集合生成判断题、选择题和主观题草稿，并保留答案、解析、rubric 和证据。

## 范围

- `training_question_service.py` 优先调用 LLM 生成题目。
- 支持 `documentIds` 限定单文档出题。
- 题型覆盖 `single_choice`、`true_false`、`subjective`。
- 所有题目必须绑定 `evidenceChunkIds`。
- LLM 失败时保留规则回退。

## 输入

- `planId`
- `appId`
- `jobTitle`
- `documentIds`
- `count`
- 检索证据

## 输出

- `questionType`
- `content`
- `options`
- `correctAnswer`
- `explanation`
- `rubric`
- `evidenceChunkIds`

## 验收标准

- 可基于指定单文档生成题目。
- 三类题型结构稳定。
- 主观题必须带 rubric。
- 认证题发布前不得进入课堂正式题库。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_question_generation.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
```
