# 迭代计划 Sprint 40

## 1. Sprint 基本信息

- Sprint 名称：Sprint 40
- Sprint 主题：三层架构模型基线与权限收口
- 涉及 Epic：E30 三层架构模型收口
- 建议版本：架构演进 V2.0
- 时间范围：待排期
- 目标：先稳定文档库、知识库、智能应用三层模型的迁移边界、核心数据结构和权限判定，为后续后端生命周期改造提供可验证基线。

## 2. 关键假设

- 不另起新项目，在当前仓库内演进。
- PostgreSQL 仍是业务真值中心。
- 迁移必须兼容已有文档库、知识库、Chunk 和 QA 历史数据。
- 本轮优先完成模型、迁移、权限和测试基线，不改造主要前端流程。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-197 | 同步三层架构实施范围，明确迁移边界和兼容策略 | P0 | 0.5d | Done |
| B-198 | 创建核心数据模型迁移，补齐 ParseRevision、BindingRevision、Chunk 状态和 QARunEvidence source_status | P0 | 2d | Done |
| B-199 | 建立历史数据回填脚本，将现有 parsed_chunks 映射到目标 ParseRevision 和 Chunk 元数据 | P0 | 1.5d | Done |
| B-200 | 重构权限服务角色映射，固化三层角色和跨资源校验 | P0 | 2d | Done |
| B-201 | 建立数据迁移和权限矩阵回归测试 | P0 | 1.5d | Done |

## 4. 验收标准

- 数据模型可以表达 DocumentVersion、ParseRevision、DocumentKbBinding、BindingRevision、Chunk 和 QARunEvidence 的目标关系。
- 历史数据回填脚本可在本地样例数据上重复执行，并能输出迁移统计。
- 权限服务支持平台角色、文档库角色、知识库角色、应用角色到权限码的映射。
- 同一资源内用户直接角色和用户组角色按 allow 并集生效。
- 绑定文档到知识库时同时校验 `library.document.bind` 和 `kb.document.bind`。
- 迁移和权限矩阵测试通过。

## 5. 范围边界

- 不改造知识库绑定入库主流程。
- 不实现删除影响分析服务。
- 不改造前端页面。
- 不做显式 deny、字段级权限或 ABAC。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit/test_permission_service.py
conda run -n rag-lab pytest app/tests
```

```powershell
git diff --check
```

## 7. 关联文档

- `../../plans/2026-05-21-e30-three-layer-architecture-refactor.md`
- `../../plans/2026-05-21-sprint40-three-layer-architecture-migration.md`
- `../../specs/2026-05-20-permission-role-model-design.md`
- `../../specs/2026-05-21-knowledge-base-chunk-management-design.md`
- `../../specs/2026-05-21-sprint40-three-layer-architecture-migration-design.md`
- `../../specs/2026-05-21-document-version-parse-revision-deletion-design.md`
- `../../specs/2026-05-21-document-kb-app-architecture-briefing.md`
