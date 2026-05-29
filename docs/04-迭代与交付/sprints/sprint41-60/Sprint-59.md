# 迭代计划 Sprint 59

## 1. Sprint 基本信息

- Sprint 名称：Sprint 59
- Sprint 主题：员工培训 Skill 与 LLM 结构化基座
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 目标：为完整员工培训智能体补齐 Skill Registry、Skill 调用审计和 LLM 结构化 JSON 解析基座。

## 2. 关键假设

- 当前员工培训平台侧主链路已经具备计划、题库和课堂 API。
- 本 Sprint 只建立训练 Agent 内部能力边界，不改变外部应用 UI。
- Skill 是平台内置白名单能力，不是外部插件市场。
- LLM JSON 解析只负责结构化输出校验，具体业务生成在 Sprint 60 接入。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-304 | 员工培训 Skill Registry 与调用审计 | P0 | 1.5d | Ready | [Spec](../../specs/2026-05-29-training-skill-registry-spec.md) |
| B-305 | 员工培训 LLM 结构化 JSON 服务 | P0 | 1d | Ready | [Spec](../../specs/2026-05-29-training-llm-json-service-spec.md) |

## 4. 验收标准

- 平台能列出员工培训模板允许使用的 Skill。
- 未注册 Skill 不能被调用。
- Skill 调用审计表随测试数据库创建。
- LLM JSON 解析能处理 fenced JSON，并能拒绝缺字段输出。

## 5. 范围边界

- 不实现学习计划或题库的 LLM 生成。
- 不实现主观题评分。
- 不改外部培训应用页面。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/unit/test_training_skill_registry.py backend/app/tests/unit/test_training_llm_service.py -q
python -m py_compile backend/migrations/versions/0040_training_completion_tables.py
python -m compileall backend/app
git diff --check
```

## 7. 关联文档

- [员工培训智能体完整化实施计划](../../plans/2026-05-29-employee-training-agent-completion-plan.md)
- [员工培训 Skill Registry 与调用审计设计规范](../../specs/2026-05-29-training-skill-registry-spec.md)
- [员工培训 LLM 结构化 JSON 服务设计规范](../../specs/2026-05-29-training-llm-json-service-spec.md)

## 8. 执行记录

- 待执行。
