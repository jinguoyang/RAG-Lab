# 迭代计划 Sprint 57

## 1. Sprint 基本信息

- Sprint 名称：Sprint 57
- Sprint 主题：外部培训应用课堂交互
- 涉及 Epic：E33 员工培训 Agent 与外部培训应用深化
- 建议版本：V2.2
- 时间范围：待排期
- 目标：在无 LLM 能力的外部培训应用中补齐题库审核、课堂页面和结构化答题组件，验证平台 `uiActions` 协议可被外部应用渲染。

## 2. 关键假设

- Sprint 53 已完成外部培训应用基线、数据库迁移和学习计划审核页面。
- Sprint 56 已完成平台侧题库草稿和审核门禁。
- 外部培训应用只调用平台 API 和渲染结构化数据。
- 外部培训应用不直接调用 LLM、Embedding 或 RAG Provider。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-293 | 外部培训应用题库审核页面 | P0 | 2d | Todo |
| B-294 | 外部培训应用课堂页面 | P0 | 2d | Todo |
| B-295 | 外部培训应用结构化答题组件 | P0 | 2d | Todo |

## 4. 验收标准

- 外部培训应用能展示并提交题库审核结果。
- 外部培训应用课堂页面能展示平台返回的课堂状态和可见内容。
- 外部培训应用能渲染单选题 A/B/C/D 结构化组件。
- 答题操作通过课堂事件提交给平台。
- 代码和配置中不存在 LLM Provider、Embedding Provider 或模型调用配置。

## 5. 范围边界

- 不实现完整 LMS、班级、证书或组织学习档案。
- 不实现 SSE 和 Markdown 高级体验。
- 不复制平台文档正文、Chunk 正文或 RAG Trace。

## 6. 验证命令

```powershell
cd external-training-app
npm run build
```

```powershell
git diff --check
```

## 7. 关联文档

- [外部培训应用设计规范](../../specs/2026-05-26-external-training-app-design.md)
- [员工培训 Agent 与外部培训应用实施计划](../../plans/2026-05-26-employee-training-agent-and-external-app.md)

## 8. 执行记录

- 待执行。
