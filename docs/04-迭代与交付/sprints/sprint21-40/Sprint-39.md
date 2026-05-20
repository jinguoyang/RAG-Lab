# 迭代计划 Sprint 39

## 1. Sprint 基本信息

- Sprint 名称：Sprint 39
- Sprint 主题：UI/交互风格统一 — 文档库、应用中心、字典管理对齐知识库
- 涉及 Epic：E29 前端 UI 一致性
- 建议版本：UI V1.1
- 时间范围：2026-05-20
- 目标：将文档库（P17/P18/P19）、应用中心（P13）、字典管理（P14）的 UI 和交互风格与知识库模块保持一致，最大化复用已有 rag 组件。

## 2. 关键假设

- 知识库模块（P02/P05/P06/P07/P10/P11/P12）的 UI 风格为参考标准。
- 自研 rag 组件库（PageHeader、Table、Button、Drawer、ConfirmDialog 等）已稳定可用。
- shadcn/ui 的 Dialog 和 Radix Tabs 已在项目中使用（P02、P07）。
- 本次仅做前端 UI 层修改，不涉及后端改动。

## 3. 本 Sprint 目标

- 统一确认弹窗：将 4 处原生 `confirm()` 替换为 `useConfirmDialog()`。
- 统一 P13 创建/编辑表单：手写 Modal 替换为 rag Drawer。
- 统一 P13 详情 Tab：原生按钮切换替换为 Radix Tabs。
- 统一 P14 页面结构：padding、max-width、搜索栏、骨架屏对齐标准。
- 统一 P17/P18/P19 页面 max-width：加入 `max-w-7xl mx-auto`。

## 4. 计划事项

| 编号 | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| S39-001 | P17/P18/P19 确认弹窗统一为 useConfirmDialog | P1 | 0.5d | Done |
| S39-002 | P13 手写 Modal 替换为 Drawer 组件 | P1 | 0.5d | Done |
| S39-003 | P13 详情 Tab 替换为 Radix Tabs | P1 | 0.5d | Done |
| S39-004 | P14 页面结构对齐（padding/max-width/搜索栏/骨架屏） | P1 | 0.5d | Done |
| S39-005 | P17/P18/P19 加入 max-w-7xl mx-auto | P2 | 0.25d | Done |

## 5. 验收标准

- P17/P18/P19 的删除/批量操作使用 `useConfirmDialog()` 弹窗，不再出现原生 `confirm()`。
- P13 创建/编辑应用使用 rag Drawer（640px），不再使用 `fixed inset-0` 手写 Modal。
- P13 API Key 展示使用 shadcn Dialog，不再使用手写 Modal。
- P13 详情面板使用 Radix Tabs，激活态样式与 P07 一致。
- P14 页面使用 `p-8 max-w-7xl mx-auto`，有搜索栏和加载骨架屏。
- P17/P18/P19 内容区有 `max-w-7xl mx-auto` 约束。
- 前端构建通过（`npm run build`）。

## 6. 范围边界

- 不修改知识库模块（P02/P05-P12）的现有代码。
- 不修改 rag 组件库本身。
- 不涉及后端 API 改动。
- 不改变功能逻辑，仅统一 UI 壳层。
- P15_Library.tsx 为未使用的旧版页面，不在本次范围内。

## 7. 验证命令

- 前端构建：在 `frontend` 目录运行 `npm run build`
- 前端 lint：在 `frontend` 目录运行 `npm run lint`
- 确认弹窗检查：`grep -r "confirm(" frontend/src/app/pages/` 应仅返回 `useConfirmDialog` 调用
- 文档空白检查：`git diff --check`

## 8. 执行记录

**执行日期：** 2026-05-20
**执行方式：** Claude Code 直接执行
**分支：** main

### Commits

| # | Commit | 说明 |
|---|--------|------|
| 1 | - | S39-001: P17/P18/P19 确认弹窗统一为 useConfirmDialog |
| 2 | - | S39-002: P13 手写 Modal → Drawer 组件 |
| 3 | - | S39-003: P13 详情 Tab → Radix Tabs |
| 4 | - | S39-004: P14 页面结构对齐（padding/max-width/搜索/骨架屏） |
| 5 | - | S39-005: P17/P18/P19 加入 max-w-7xl mx-auto |
| 6 | - | Sprint 39 文档 + README 索引更新 |

### 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `P17_LibraryManagement.tsx` | 导入 useConfirmDialog；handleDelete 改用 confirm()；内容区加 max-w-7xl mx-auto |
| `P18_LibraryDocuments.tsx` | 导入 useConfirmDialog；handleBatchAction 改用 confirm()；内容区加 max-w-7xl mx-auto |
| `P19_LibraryMembers.tsx` | 导入 useConfirmDialog；handleRemoveMember 改用 confirm()；内容区加 max-w-7xl mx-auto |
| `P13_RagAppManagement.tsx` | 导入 Radix Tabs + shadcn Dialog；Tab 区域改用 Tabs.Root/List/Trigger；创建/编辑 Modal 改用 Drawer；API Key Modal 改用 Dialog |
| `P14_DictionaryManagement.tsx` | p-6→p-8；加 flex flex-col h-full 布局；加 max-w-7xl mx-auto；加搜索栏；加加载骨架屏；Alert 加 onClose |
| `README.md` | 新增 Sprint 39 索引行 |
| `Sprint-39.md` | 新建 Sprint 文档 |

### 验证结果

- 前端构建：success（5.29s）
- 确认弹窗检查：P17/P18/P19 已统一使用 useConfirmDialog，无原生 confirm() 残留（P15 为未使用旧页面）
