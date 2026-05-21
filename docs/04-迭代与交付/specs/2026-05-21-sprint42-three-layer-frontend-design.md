# Sprint 42 三层架构前端体验改造设计

本文档是 Sprint 42 的设计规范，覆盖文档库、知识库、智能应用三层前端体验改造。Sprint 41 已完成后端生命周期改造，Sprint 42 聚焦前端页面对三层架构的支撑。

## 1. 设计目标

- 让用户在页面上清楚理解文档库、知识库、智能应用三层边界。
- 支持版本入库、版本切换、删除影响确认、权限来源查看和 Runtime 状态解释。
- 复用现有组件（ConfirmDialog、StatusBadge、Drawer），不引入新设计系统。
- 后端补充 deletion-impact-analysis 独立 API 端点。

## 2. 范围

| Backlog | 标题 | 优先级 | 修改页面 |
| --- | --- | --- | --- |
| B-209 | 文档库详情和版本管理交互改造 | P0 | P16_LibraryDetail.tsx |
| B-210 | 知识库文档中心绑定改造 | P0 | P06_DocumentCenter.tsx |
| B-211 | QA历史和Chunk详情展示改造 | P0 | P10_QAHistory.tsx |
| B-212 | 成员与权限页面改造 | P1 | P12_MembersAndPermissions.tsx |
| B-213 | 智能应用管理页面改造 | P1 | P13_RagAppManagement.tsx |

后端补充：`GET /library/documents/{doc_id}/versions/{version_id}/deletion-impact`

## 3. 后端 API 补充

### 3.1 删除影响分析端点

当前 `analyze_document_version_deletion_impact` 仅在 `document_service` 内部调用，前端无法独立获取影响数据。需新增独立端点：

```text
GET /library/documents/{doc_id}/versions/{version_id}/deletion-impact
```

响应复用已有的 `DeletionImpactAnalysis` schema：

```text
{
  canDelete: boolean
  blockingReasons: string[]
  isActiveVersion: boolean
  activeBindingCount: number
  pendingJobsCount: number
  qaEvidenceCount: number
  qaCitationCount: number
  requiresStrongConfirmation: boolean
}
```

权限：`library.version.delete`（查看影响分析与删除操作使用相同权限）。

### 3.2 QA Evidence 元数据扩展

B-211 需要 QA Evidence 返回文档和版本元数据。后端 `qa_runs.py` 的详情端点返回的 evidence 需要扩展：

```text
evidence 扩展字段：
  document_name: string
  version_no: int
  page_no: int
  section_path: string
  chunk_status: string  // active / retired / deleted
```

通过 join `chunks` → `document_versions` → `documents` 查询填充。

### 3.3 绑定版本切换响应扩展

B-210 需要切换版本后获取 BindingRevision 状态。`bindings.py` 的 `switch-version` 端点响应需要包含：

```text
{
  bindingRevisionId: string
  status: string  // building / active / failed
  createdAt: string
}
```

### 3.4 App 详情知识库状态

B-213 需要 App 详情返回所属知识库状态。`rag_apps.py` 的 App 详情端点响应扩展：

```text
knowledgeBaseStatus: string  // active / disabled / deleted
knowledgeBaseName: string
```

### 3.5 权限摘要端点扩展

B-212 需要权限来源信息。`knowledge_bases.py` 的权限摘要端点扩展：

```text
permissions 扩展：
  每个 permissionCode 附加 source: "direct" | "group"
  如果 source=group，附加 groupName: string
```

## 4. B-209 文档库详情和版本管理交互改造

### 4.1 修改文件

- `frontend/src/app/pages/P16_LibraryDetail.tsx`
- `frontend/src/app/services/libraryService.ts`（新增 getDeletionImpact）
- `frontend/src/app/types/library.ts`（扩展类型）

### 4.2 重复文件提醒

上传新版本时，如果文件 hash 与已有版本相同，在上传确认区域显示警告 Badge：

```text
该文件与版本 X 内容相同
```

实现方式：上传前调用后端 hash 检查接口（Sprint 41 B-202 已实现），返回 `isDuplicate` 和 `duplicateVersionNo`。前端在上传区域展示 Alert 组件，不阻止上传。

### 4.3 ParseRevision 状态展示

在版本列表中，每个 DocumentVersion 行下方展示 ParseRevision 状态：

- 使用 StatusBadge 组件
- `success`：绿色
- `failed`：红色，hover 展示错误信息
- `running`：蓝色加载态
- `pending`：灰色

数据来源：后端 `LibraryDocumentVersionDTO` 需扩展 `parse_revisions` 数组，每项包含 `parse_revision_id`、`status`、`parser_name`、`created_at`。

### 4.4 删除影响分析弹窗

点击删除版本按钮时的流程：

1. 调用 `GET /library/documents/{docId}/versions/{versionId}/deletion-impact`
2. 展示 ConfirmDialog，内容包括：
   - 影响摘要表：active BindingRevision 数、运行中任务数、历史 QA 引用数
   - 如果 `canDelete=false`：展示 blockingReasons，禁用删除按钮
   - 如果 `requiresStrongConfirmation=true`：展示强确认 checkbox
3. 用户确认后调用 `deleteLibraryVersion`

### 4.5 强确认删除

当 `requiresStrongConfirmation=true` 时，ConfirmDialog 中增加：

```text
[ ] 我确认清理该文档版本，并接受相关 QA 历史证据不可回放
```

checkbox 未勾选时，删除按钮禁用。ConfirmDialog 组件需要扩展支持 checkbox 类型的确认条件。

## 5. B-210 知识库文档中心绑定改造

### 5.1 修改文件

- `frontend/src/app/pages/P06_DocumentCenter.tsx`
- `frontend/src/app/services/libraryService.ts`（新增 fetchLibraryDocumentVersions）
- `frontend/src/app/types/library.ts`（扩展类型）

### 5.2 选择文档版本入库

绑定文档到知识库时，当前流程直接绑定。改造后增加版本选择步骤：

1. 用户选择要绑定的文档
2. 弹出版本选择 Drawer
3. 展示该文档的所有 DocumentVersion 列表：
   - 版本号、上传时间、文件大小
   - 解析状态（只有 `parse_status=success` 的版本可选）
   - ParseRevision 状态
4. 选择版本后调用 `bindDocumentsToKB(docId, versionId)`

### 5.3 绑定版本切换

对已绑定的文档，增加"切换版本"操作：

1. 在文档操作列增加"切换版本"按钮
2. 点击后展示 Drawer：
   - 当前绑定信息：DocumentVersion、BindingRevision 状态
   - 可切换版本列表（同文档其他已解析成功的版本）
3. 选择新版本后调用 `switchBindingVersion(bindingId, newVersionId)`
4. 切换后展示 BindingRevision 状态变化：building → active

### 5.4 BindingRevision 状态展示

在文档列表的绑定状态列中，展示 BindingRevision 状态：

- `building`：蓝色加载 Badge + "构建中"
- `active`：绿色 Badge + "已激活"
- `retired`：灰色 Badge + "已退役"
- `failed`：红色 Badge + "构建失败"，hover 展示失败原因

## 6. B-211 QA历史和Chunk详情展示改造

### 6.1 修改文件

- `frontend/src/app/pages/P10_QAHistory.tsx`
- `frontend/src/app/adapters/qaRunAdapter.ts`（扩展证据映射）
- `frontend/src/app/types/qaRun.ts`（扩展证据类型）

### 6.2 证据回溯链路展示

在 QA 历史详情的证据区域，每条 Evidence 展示完整回溯链路：

```text
source_status=available 时：
  文档名 → 版本号 → 页码/章节 → 命中片段

source_status=source_deleted 时：
  "引用文件已被清理"
  保留证据顺序、得分等运行信息
```

使用 Timeline 组件展示链路层级。数据来源：后端 evidence 扩展字段（见 3.2）。

### 6.3 Chunk 详情 Drawer

点击证据可展开 Drawer 查看 Chunk 元数据：

- 所属文档、版本、解析版本
- 页码、章节路径、token 数
- Chunk 状态（active/retired/deleted）
- 如果 Chunk 已 retired 或 deleted，显示对应状态 Badge

## 7. B-212 成员与权限页面改造

### 7.1 修改文件

- `frontend/src/app/pages/P12_MembersAndPermissions.tsx`

### 7.2 三层角色展示

成员列表中每个用户/用户组的角色按资源层级分组展示：

- 文档库角色：`library_owner` / `library_manager` / `library_editor` / `library_binder` / `library_viewer`
- 知识库角色：`kb_owner` / `kb_manager` / `kb_editor` / `kb_viewer` / `kb_qa_runner`
- 应用角色：`app_owner` / `app_operator` / `app_viewer`

使用 Badge 分色区分不同层级。平台角色（`platform_admin` / `platform_user`）使用独立颜色。

### 7.3 有效权限展示

展开用户详情时，展示合并后的有效权限码列表：

- 区分来源："直接授权" vs "用户组继承"
- 用户组继承的权限标注来源用户组名称
- 数据来源：后端权限摘要端点（见 3.5）

### 7.4 用户组来源标注

对于通过用户组获得的权限，在角色 Badge 旁显示用户组图标，hover 展示用户组名称。

## 8. B-213 智能应用管理页面改造

### 8.1 修改文件

- `frontend/src/app/pages/P13_RagAppManagement.tsx`
- `frontend/src/app/types/ragApp.ts`（扩展类型）

### 8.2 所属知识库状态展示

在 App 详情的概览区域，展示所属知识库状态：

- `active`：正常 Badge
- `disabled`：警告 Badge + 提示"知识库已停用，Runtime 调用将被拒绝"
- 知识库名称可点击跳转

### 8.3 Key 可用性展示

在 API Key 列表中，增加"可用性"列：

| 条件 | 展示 |
| --- | --- |
| Key 未过期 且 App active 且 KB active | "可用" 绿色 Badge |
| Key 已过期 | "已过期" 灰色 Badge |
| App disabled | "应用已停用" 黄色 Badge |
| KB disabled | "知识库已停用" 红色 Badge |

### 8.4 Runtime 拒绝原因

在试运行区域，调用失败时展示具体拒绝原因：

- `KB_DISABLED`：知识库已停用，请先恢复知识库
- `KB_NOT_FOUND`：知识库不存在或已删除
- `APP_DISABLED`：应用已停用
- `KEY_EXPIRED`：API Key 已过期

使用 Alert 组件展示，error variant。

### 8.5 调用统计影响

在统计面板中，如果知识库处于 disabled 状态，显示提示：

```text
知识库已停用，自停用以来无新调用记录
```

## 9. 实现顺序

按以下顺序实现，每项完成后可独立验收：

1. 后端 API 补充（deletion-impact 端点、evidence 扩展、绑定切换响应扩展）
2. B-209 文档库详情和版本管理
3. B-210 知识库文档中心绑定
4. B-211 QA历史证据展示
5. B-212 成员与权限
6. B-213 智能应用管理

## 10. 不做范围

- 不重写页面整体布局。
- 不新增设计系统组件。
- 不实现复杂可视化图谱。
- 不暴露普通用户独立删除 ParseRevision 的入口。
- 不做自动清理策略。

## 11. 验收标准

- 文档库上传重复文件时有清晰提醒，但不强制阻止。
- 文档版本删除前展示 active 引用、运行中任务、历史 QA 引用等影响分析。
- 知识库绑定文档时可以选择具体文档版本。
- 知识库文档中心能展示 BindingRevision 的 building、active、retired、failed 状态。
- QA 历史中 source_deleted 证据展示"引用文件已被清理"。
- 权限页面能解释用户直接角色和用户组角色来源。
- P13 能展示知识库 disabled 对 App Runtime 的影响。

## 12. 验证命令

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

```powershell
git diff --check
```

## 13. 关联文档

- `2026-05-21-document-kb-app-architecture-briefing.md`
- `2026-05-20-permission-role-model-design.md`
- `2026-05-21-document-version-parse-revision-deletion-design.md`
- `2026-05-21-knowledge-base-chunk-management-design.md`
- `2026-05-21-sprint41-backend-lifecycle-refactor-design.md`
