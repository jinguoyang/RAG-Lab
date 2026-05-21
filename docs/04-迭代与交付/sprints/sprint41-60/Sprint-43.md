# 迭代计划 Sprint 43

## 1. Sprint 基本信息

- Sprint 名称：Sprint 43
- Sprint 主题：三层架构回归验收与文档同步
- 涉及 Epic：E30 三层架构模型收口
- 建议版本：架构演进 V2.0
- 时间范围：待排期
- 目标：用端到端验证证明三层模型可运行、可追溯、可治理，并同步接口、数据模型、测试计划和 OpenAPI。

## 2. 关键假设

- Sprint 40 至 Sprint 42 已完成主要后端和前端改造。
- 本轮不再新增大功能，主要做验收、缺陷修复和文档同步。
- 真实 Provider 网络级复测按发布环境条件执行；本地允许使用 mock 或可用 Provider 进行功能验证。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-214 | 建立三层主链路端到端验收：上传、解析、绑定、切换版本、QA、App Runtime 调用 | P0 | 2d | In Progress |
| B-215 | 建立删除和清理回归：active 引用禁止删除、历史 QA 引用强确认、索引副本清理重试 | P0 | 1.5d | In Progress |
| B-216 | 建立权限矩阵和 Runtime 状态回归 | P0 | 1.5d | In Progress |
| B-217 | 同步接口设计、数据模型设计、数据库设计、测试计划和 OpenAPI，回填 E30 验收结论 | P1 | 1.5d | In Progress |

## 4. 验收标准

- 三层主链路端到端脚本通过。
- 删除旧文档版本不会破坏当前知识库检索和 App Runtime。
- 历史 QA 在引用源被清理后仍可打开。
- 权限矩阵覆盖平台角色、资源角色、用户组并集和跨资源校验。
- OpenAPI 能导出并与前端服务层字段一致。
- 系统设计文档不再与 E30 已确认规则冲突。

## 5. 范围边界

- 不在本轮新增未规划功能。
- 不为了同步历史归档而改写旧 Sprint 正文。
- 不把本地 mock 验证表述为真实 Provider 网络级通过。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests
conda run -n rag-lab python scripts/export_openapi.py
```

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

```powershell
git diff --check
```

## 7. 关联文档

- `../../plans/2026-05-21-e30-three-layer-architecture-refactor.md`
- `../../plans/2026-05-21-sprint43-regression-validation.md`
- `../../specs/2026-05-20-permission-role-model-design.md`
- `../../specs/2026-05-21-document-version-parse-revision-deletion-design.md`
- `../../specs/2026-05-21-knowledge-base-chunk-management-design.md`
- `../../specs/2026-05-21-document-kb-app-architecture-briefing.md`
- `../../specs/2026-05-21-sprint43-regression-validation-design.md`
