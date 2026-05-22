# Sprint 42 三层架构现有页面补齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 Sprint 42 前端体验，在现有文档库、知识库文档和应用中心页面中呈现三层架构能力。

**Architecture:** 不新增独立菜单；复用现有 service 和 rag 组件；新增纯展示工具集中处理 BindingRevision 状态和权限来源文案；后端只补绑定 DTO 的最小展示字段。

**Tech Stack:** React 18、TypeScript、Vite、FastAPI、Pydantic、SQLAlchemy Core。

---

## File Structure

- Create: `frontend/src/app/utils/threeLayerPresentation.ts`
- Test: `frontend/src/app/utils/threeLayerPresentation.test.ts`
- Modify: `frontend/src/app/pages/P17_LibraryManagement.tsx`
- Modify: `frontend/src/app/pages/P18_LibraryDocuments.tsx`
- Modify: `frontend/src/app/pages/P19_LibraryMembers.tsx`
- Modify: `frontend/src/app/pages/P06_DocumentCenter.tsx`
- Modify: `frontend/src/app/pages/P12_MembersAndPermissions.tsx`
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx`
- Modify: `frontend/src/app/services/libraryService.ts`
- Modify: `frontend/src/app/types/library.ts`
- Modify: `backend/app/schemas/binding.py`
- Modify: `backend/app/services/binding_service.py`

## Task 1: 展示工具 TDD

- [x] 新增 `threeLayerPresentation.test.ts`，覆盖 BindingRevision 状态、三层标签、权限来源标签。
- [x] 运行 `cd frontend; npm run test -- src/app/utils/threeLayerPresentation.test.ts`，确认因模块不存在失败。
- [x] 新增 `threeLayerPresentation.ts`，实现测试要求的纯函数。
- [x] 重新运行同一测试，确认通过。

## Task 2: 后端绑定 DTO 最小扩展

- [x] 扩展 `LibraryBindingDTO`，增加 active BindingRevision 展示字段。
- [x] 在 `_to_binding_dto` 中映射 `active_binding_revision_id`。
- [x] 在 `list_kb_bindings` 中查询 active revision 或 building revision，填充状态、Chunk 数和目标版本。
- [x] 在 `switch_binding_version` 返回值中带回新建 building revision 状态。
- [x] 运行 `cd backend; conda run -n rag-lab python -m compileall app`。

## Task 3: 前端类型与服务

- [x] 扩展 `LibraryBindingDTO` 类型。
- [x] 让 `listKBBindings` 和 `switchBindingVersion` 返回完整绑定 DTO。
- [x] 运行 `cd frontend; npm run test -- src/app/utils/threeLayerPresentation.test.ts`。

## Task 4: 重构文档库页面

- [x] P17 文档库列表增加三层边界说明和权限/版本摘要。
- [x] P18 文档库详情增加版本、ParseRevision、成员权限和知识库绑定的操作导向。
- [x] P19 成员管理增加文档库权限来源说明。

## Task 5: 补齐 P06 与 P12

- [x] P06 读取 `listKBBindings`，在右侧或主区展示绑定与 BindingRevision 状态。
- [x] P06 每个绑定提供“切换版本”，复用现有 Drawer 逻辑。
- [x] P06 增加知识库权限摘要和成员权限管理入口。
- [x] P12 使用 `permissionSourceLabel` 展示平台角色、直接授权、用户组继承和 deny 来源。
- [x] 保持现有增删成员流程不变。

## Task 6: 补齐应用中心权限管理

- [x] P13 增加权限管理区，展示应用运行权限继承自所属知识库。
- [x] P13 在应用详情中提供跳转所属知识库成员与权限页面的入口。
- [x] P13 展示可用 Key 数，并保留 Key 表格中的可用性判断。

## Task 7: 验证

- [x] 运行 `cd frontend; npm run lint`。
- [x] 运行 `cd frontend; npm run test -- src/app/utils/threeLayerPresentation.test.ts`。
- [x] 运行 `cd frontend; npm run build`。
- [x] 运行 `cd backend; conda run -n rag-lab python -m compileall app`。
- [x] 运行 `git diff --check`。
- [ ] 运行 `cd backend; conda run -n rag-lab pytest app/tests/unit/test_binding_lifecycle.py -q`：当前环境缺少 `email-validator`，测试在收集阶段阻塞。
