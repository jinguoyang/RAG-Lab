# 迭代计划 Sprint 62

## 1. Sprint 基本信息

- Sprint 名称：Sprint 62
- Sprint 主题：员工培训安全、报表与端到端验收
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 目标：补齐权限隔离、培训报表和平台/应用端端到端验收，使员工培训智能体达到完整产品级闭环。

## 2. 关键假设

- Sprint 59 至 Sprint 61 已完成核心能力。
- 外部培训应用仍不具备 LLM、Embedding、RAG Provider 或模型调用能力。
- 平台负责所有权威业务数据、评分、安全和报表聚合。
- 本 Sprint 结束后，E33 完整员工培训智能体可进入验收复核。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-313 | 员工培训权限隔离与安全边界 | P0 | 1.5d | Ready | [Spec](../../specs/2026-05-29-training-security-boundary-spec.md) |
| B-314 | 员工培训报表与薄弱点统计 | P1 | 2d | Ready | [Spec](../../specs/2026-05-29-training-reporting-spec.md) |
| B-315 | 员工培训完整链路端到端验收 | P0 | 2d | Ready | [Spec](../../specs/2026-05-29-training-e2e-acceptance-spec.md) |

## 4. 验收标准

- 跨 App、跨员工、跨计划访问被阻止。
- 管理端可查询完成率、平均分、错题分布和薄弱点。
- 平台 E2E 覆盖计划、题库、课堂、评分、进度和报表。
- 应用端 E2E 验证只调用平台 API 并保存本地镜像。

## 5. 范围边界

- 不实现证书系统。
- 不实现复杂组织树、长期学习档案和多模态题目。
- 不推进 SOP、文件合规性检查和内部客服场景。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_security.py backend/app/tests/integration/test_employee_training_reports.py backend/app/tests/integration/test_employee_training_e2e.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
cd external-training-app/backend
python -m pytest app/tests/integration/test_training_e2e_contract.py app/tests/integration/test_classroom_api.py -q
python -m compileall app
cd ../frontend
npm run build
cd ../../
git diff --check
```

## 7. 关联文档

- [员工培训智能体完整化实施计划](../../plans/2026-05-29-employee-training-agent-completion-plan.md)
- [权限隔离与安全边界设计规范](../../specs/2026-05-29-training-security-boundary-spec.md)
- [报表与薄弱点统计设计规范](../../specs/2026-05-29-training-reporting-spec.md)
- [端到端验收设计规范](../../specs/2026-05-29-training-e2e-acceptance-spec.md)

## 8. 执行记录

- 待执行。
