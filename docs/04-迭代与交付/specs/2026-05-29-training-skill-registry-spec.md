# 员工培训 Skill Registry 与调用审计设计规范

> 用途：本文件是 B-304 / Sprint 59 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

为员工培训智能体建立最小 Skill Registry，使平台能显式管理允许调用的培训 Skill，并为后续 LLM 生成、意图识别、主观题评分和安全检查记录调用审计。

## 范围

- 新增员工培训内置 Skill 描述 DTO。
- 新增 Skill 注册表，首批包含 `buildLearningPlanDraft`、`generateQuestionDrafts`、`gradeSubjectiveAnswer`、`classifyIntent`。
- 新增 `training_skill_calls` 表，记录 Skill 调用摘要、状态、错误和耗时。
- 不实现通用插件系统，不允许模型自由构造任意工具名。

## 数据模型

`training_skill_calls` 字段：

- `skill_call_id`
- `session_id`
- `app_id`
- `skill_name`
- `input_summary`
- `output_summary`
- `status`
- `error_code`
- `latency_ms`
- `created_at`

## 服务接口

- `list_training_skills() -> list[TrainingSkillDTO]`
- `get_training_skill(skill_name: str) -> TrainingSkillDTO | None`
- 后续可扩展 `record_training_skill_call(...)`

## 验收标准

- 未注册 Skill 返回 `None`，不能被调用。
- 已注册 Skill 返回稳定描述、输入 schema 和输出 schema。
- Skill 调用审计表能随测试数据库创建。
- 不影响现有员工培训课堂 API。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_training_skill_registry.py -q
python -m py_compile backend/migrations/versions/0040_training_completion_tables.py
python -m compileall backend/app
```
