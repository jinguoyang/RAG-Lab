# 迭代计划 Sprint 58

## 1. Sprint 基本信息

- Sprint 名称：Sprint 58
- Sprint 主题：员工培训 Agent 端到端验收
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 状态：Done
- 目标：完成平台与外部培训应用的端到端联调验收，并同步接口设计、数据模型、数据库设计和 OpenAPI。

## 2. 关键假设

- Sprint 52 已完成平台课堂 Agent 基线。
- Sprint 53 已完成外部培训应用基线。
- Sprint 55 至 Sprint 57 已完成学习计划、题库和课堂交互主链路。
- 外部培训应用仍保持无 LLM 能力，只作为外部接入应用验收。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-296 | 平台与外部培训应用端到端联调验收 | P0 | 2d | Done |
| B-297 | 同步接口设计、数据模型、数据库设计和 OpenAPI | P1 | 2d | Done |

## 4. 验收标准

- 可完成“岗位描述生成学习计划 -> 外部培训应用审核 -> 平台发布计划”的链路。
- 可完成“平台生成题库草稿 -> 外部培训应用审核认证题”的链路。
- 可完成“员工进入课堂 -> 多轮提问 -> 平台状态机响应 -> 结构化答题 -> 评分回传”的链路。
- 外部培训应用没有 LLM、Embedding、RAG Provider 或模型调用配置。
- 相关接口、数据模型、数据库设计和 OpenAPI 与实现保持一致。

## 5. 范围边界

- 不补做长期规划项。
- 不将演示嵌入页改造成正式培训应用。
- 不实现组织级学习档案、证书和复杂运营分析。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

```powershell
cd external-training-app
npm run build
```

```powershell
git diff --check
```

## 7. 关联文档

- [员工培训 Agent 平台侧设计规范](../../specs/2026-05-26-employee-training-agent-platform-design.md)
- [外部培训应用设计规范](../../specs/2026-05-26-external-training-app-design.md)
- [员工培训 Agent 与外部培训应用实施计划](../../plans/2026-05-26-employee-training-agent-and-external-app.md)

## 8. 执行记录

- B-296: 平台与外部培训应用端到端联调验收 — Done（平台 API + 外部应用课堂页面联调通过）
- B-297: 同步接口设计、数据模型、数据库设计和 OpenAPI — Done（接口与实现保持一致）
