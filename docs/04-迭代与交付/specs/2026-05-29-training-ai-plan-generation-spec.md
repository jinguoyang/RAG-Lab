# 员工培训 AI 学习计划生成设计规范

> 用途：本文件是 B-306 / Sprint 60 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

将当前规则化学习计划草稿升级为 AI 辅助生成：平台基于岗位名称、岗位描述和知识库证据，生成可编辑、可审核、可追溯的结构化学习计划草稿。

## 范围

- `training_plan_service.py` 优先调用 LLM 生成结构化计划。
- LLM 输出必须经 JSON 解析和字段校验。
- 输出文档必须绑定当前 App 知识库授权证据。
- LLM 失败时保留现有规则回退。
- 不实现管理员发布版本，该能力由 B-311 承接。

## 输入

- `appId`
- `jobTitle`
- `jobDescription`
- 当前 App 知识库检索证据

## 输出

- `abilityGroups`
- `documents`
- `readingOrder`
- `recommendReason`
- `evidenceChunkIds`

## 验收标准

- LLM 输出可覆盖规则默认结果。
- 文档 ID 必须来自检索证据或平台授权资源。
- 返回结构保持应用端可二次编辑。
- LLM 失败不影响接口可用性，自动回退规则草稿。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_llm_plan.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
```
