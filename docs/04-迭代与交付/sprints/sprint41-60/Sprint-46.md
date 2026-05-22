# 迭代计划 Sprint 46

## 1. Sprint 基本信息

- Sprint 名称：Sprint 46
- Sprint 主题：ChunkRevision 前端改造与文档同步
- 涉及 Epic：E30 三层架构模型收口
- 建议版本：V1.9
- 时间范围：待排期
- 目标：完成前端类型替换、页面文案更新、rechunk 入口和文档同步。

## 2. 关键假设

- Sprint 45 已完成后端全量改造，API 返回的字段名已从 `bindingRevision*` 变为 `chunkRevision*`。
- 前端需要适配新的 API 字段名和 rechunk 端点。
- UI 文案统一使用 "ChunkRevision" 替代 "BindingRevision"，缩写从 "BR" 改为 "CR"。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-232 | 前端 TypeScript 类型和 utils 全量替换 bindingRevision → chunkRevision | P0 | 1d | Ready |
| B-233 | P06/P07/P10 页面文案和展示更新为 ChunkRevision | P0 | 1d | Ready |
| B-234 | P06 增加 rechunk 入口，支持选择分块策略和参数 | P0 | 2d | Ready |
| B-235 | 更新 E2E 测试和前端单元测试适配重命名 | P0 | 1d | Ready |
| B-236 | 同步设计文档、接口文档、数据模型文档和 OpenAPI | P1 | 1.5d | Ready |

## 4. 验收标准

- 前端 TypeScript 类型中不再出现 `bindingRevision` 标识符。
- P06 展示 ChunkRevision 状态、chunk 数量和版本 ID。
- P07 展示 "Active ChunkRevision" 和 "当前 ChunkRevision Chunks"。
- P10 证据缩写从 "BR {id}" 改为 "CR {id}"。
- P06 提供 rechunk 按钮，用户可选择分块策略和参数，触发 rechunk 后状态刷新。
- E2E 测试和前端单元测试全部通过。
- OpenAPI 文档反映新的字段名和 rechunk 端点。

## 5. 范围边界

- 不修改后端逻辑（Sprint 45 已完成）。
- 不实现 rechunk 进度轮询的实时 UI（复用现有 ingest job 状态轮询）。
- 不在 P07 Chunk 详情中展示 strategy/params（仅在 P06 rechunk 入口中选择）。

## 6. 验证命令

```powershell
cd frontend
npm run lint
npm run test
npm run build
npx playwright test
```

```powershell
git diff --check
```

## 7. 关联文档

- [BindingRevision→ChunkRevision 重命名设计](../specs/2026-05-22-binding-to-chunk-revision-rename-design.md)
