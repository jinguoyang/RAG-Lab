# 文档库版本管理设计文档

**日期**: 2026-05-20
**状态**: 待审批
**范围**: 文档库（Library）文档版本升级、查看、切换、删除，以及对知识库绑定的影响处理

---

## 1. 背景与目标

### 1.1 现状

- 文档库文档上传后只创建 version_no=1，无法上传新版本
- `document_versions` 表缺少 `deleted_at`/`deleted_by` 列（`document_service.py:654` 已引用，是潜在 bug）
- KB 文档子系统已有完整的版本管理（列表、切换、重解析），但文档库侧没有
- 文档库详情页（P16_LibraryDetail）是平铺布局，无版本管理 UI
- 绑定到 KB 的文档在 ingest 时总是取最新库版本的 `parsed_chunks`（`document_service.py:650-658`）

### 1.2 目标

1. 允许用户为已有库文档上传新文件，创建新版本
2. 查看文档的所有历史版本，包括文件信息和解析状态
3. 手动切换文档的活跃版本
4. 删除不需要的历史版本（有安全约束）
5. KB 绑定保持旧版本，用户可在库侧手动切换 KB 绑定的版本
6. 重解析仅影响当前活跃版本

---

## 2. 设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 版本来源 | 上传新文件 | 每个版本对应不同的源文件 |
| KB 绑定同步 | 保持旧版本，手动切换 | 避免自动更新影响下游 KB |
| 重解析范围 | 仅影响活跃版本 | 历史版本解析结果保持不变 |
| 删除约束 | 禁止删除已绑定版本 | 保护 KB 数据完整性 |

---

## 3. 数据模型变更

### 3.1 迁移: `0022_library_version_management.py`

**变更内容:**

1. `document_versions` 表新增列:
   - `deleted_at` — DateTime, nullable
   - `deleted_by` — UUID, nullable

2. 新增部分索引:
   - `idx_document_versions_document_not_deleted` ON `(document_id, deleted_at)` WHERE `deleted_at IS NULL`

3. 扩展 `library_parse_jobs.job_type` CHECK 约束:
   - 新增 `'upload_version'` 值

### 3.2 表定义更新 (`backend/app/tables.py`)

在 `document_versions` 表定义（line 332 之前）新增:
```python
sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
```

### 3.3 无需变更的表

- `document_kb_bindings` — 已有 `version_id` 列，KB 侧版本切换通过 UPDATE 实现
- `stored_files` — 复用现有结构
- `documents` — `active_version_id` 列已存在

---

## 4. 后端 API 设计

### 4.1 新增端点 — 文档库版本管理 (`backend/app/api/routes/library.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/{document_id}/versions` | 上传新版本文件 |
| `GET` | `/{document_id}/versions` | 列出所有版本 |
| `POST` | `/{document_id}/versions/{version_id}/activate` | 切换活跃版本 |
| `DELETE` | `/{document_id}/versions/{version_id}` | 删除指定版本 |

### 4.2 新增端点 — KB 绑定版本切换 (`backend/app/api/routes/bindings.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/{binding_id}/switch-version` | 切换 KB 绑定到不同的库版本 |

请求体: `{ "libraryVersionId": "uuid" }`

---

## 5. 后端服务层

### 5.1 新增函数 — `library_service.py`

#### `upload_library_version(session, current_user, document_id, file_name, mime_type, file_bytes)`

流程:
1. `_ensure_owner` 权限校验
2. 查询当前最大 version_no（`deleted_at IS NULL`）
3. `next_version_no = max + 1`
4. 存储文件到 MinIO: `users/{actor_id}/library/{document_id}/{file_name}`
5. 创建 `stored_files` 行
6. 创建 `document_versions` 行: `version_no=next_version_no`, `status='processing'`, `parse_status='pending'`
7. **不更新** `documents.active_version_id`（新版本默认非活跃）
8. 创建 `library_parse_jobs` 行: `job_type='upload_version'`
9. 提交事务，派发 Celery `library_parse.run` 任务
10. 返回 `LibraryVersionUploadResponse`

#### `list_library_versions(session, current_user, document_id)`

流程:
1. `_ensure_owner` 权限校验
2. 查询 `document_versions` WHERE `document_id` AND `deleted_at IS NULL` ORDER BY `version_no DESC`
3. JOIN `stored_files` 获取文件名和文件大小
4. 返回 `list[LibraryDocumentVersionDTO]`

#### `activate_library_version(session, current_user, document_id, version_id, confirm_impact)`

流程:
1. `_ensure_owner` 权限校验
2. 要求 `confirm_impact=True`
3. 校验版本存在、属于该文档、未删除、`parse_status='success'`
4. 将该文档所有其他版本设为 `status='inactive'`
5. 目标版本设为 `status='active'`
6. 更新 `documents.active_version_id = version_id`
7. 提交事务，返回 `LibraryVersionActivateResponse`

#### `delete_library_version(session, current_user, document_id, version_id)`

流程:
1. `_ensure_owner` 权限校验
2. 校验版本存在、属于该文档、未删除
3. 检查: 是否为 `documents.active_version_id`？→ 是则拒绝（`VERSION_IS_ACTIVE`）
4. 检查: `document_kb_bindings` 中是否有引用该版本的活跃绑定？→ 是则返回 KB 名称列表（`VERSION_IN_USE`）
5. 软删除: `deleted_at=now()`, `deleted_by=actor_id`, `status='archived'`
6. 同步软删除关联的 `stored_files` 行
7. 提交事务

### 5.2 新增函数 — `binding_service.py`

#### `switch_binding_version(session, current_user, kb_id, binding_id, target_library_version_id)`

流程:
1. `_ensure_kb_permission` 权限校验
2. 加载绑定行，校验存在且属于该 KB
3. 加载库文档，校验用户拥有该文档
4. 校验目标库版本: 存在、属于该库文档、`parse_status='success'`、未删除
5. 获取 KB 侧文档（通过 `binding.version_id` → `document_versions.document_id`）
6. 在 KB 侧创建新的 `document_versions` 行:
   - `version_no` = KB 文档当前最大 version_no + 1
   - `source_file_id` = 目标库版本的 `source_file_id`
   - `metadata.library_version_id` = 目标库版本 ID（用于 ingest 管线定位 parsed_chunks）
7. 更新 `document_kb_bindings.version_id` = 新 KB 版本 ID
8. 更新 `document_kb_bindings.status` = `'processing'`
9. 创建 `ingest_jobs` 行
10. 提交事务，派发 Celery `document_ingest.run` 任务
11. 返回更新后的绑定 DTO

### 5.3 Bug 修复

#### 修复 ingest 管线库版本定位 (`document_service.py:645-662`)

**当前问题**: 总是取最新库版本 (`ORDER BY version_no DESC LIMIT 1`)，且引用不存在的 `deleted_at` 列。

**修复方案**:
1. 优先从 KB 版本 `metadata.library_version_id` 读取指定库版本
2. 回退到取最新版本（兼容旧数据）
3. 加入 `deleted_at IS NULL` 过滤

#### 修复 `retry_library_parse` (`library_service.py`)

**当前问题**: 取最新版本，应取活跃版本。

**修复**: 查询改为使用 `documents.active_version_id`。

#### 修复 `get_document_text` (`library_service.py`)

**当前问题**: 取最新版本，应取活跃版本。

**修复**: 查询改为使用 `documents.active_version_id`，或接受可选 `version_id` 参数。

---

## 6. Pydantic Schema 变更

### 6.1 更新 `backend/app/schemas/library.py`

扩展现有 `LibraryDocumentVersionDTO`:
```python
class LibraryDocumentVersionDTO(BaseModel):
    versionId: str
    documentId: str
    versionNo: int
    sourceFileId: str
    fileName: str | None = None      # 新增
    fileSize: int | None = None      # 新增
    status: str
    parseStatus: str
    chunkCount: int
    tokenCount: int | None
    createdAt: str
    updatedAt: str
```

新增:
```python
class LibraryVersionUploadResponse(BaseModel):
    version: LibraryDocumentVersionDTO
    parseJob: LibraryParseJobDTO
    storedFile: LibraryStoredFileDTO

class LibraryVersionActivateRequest(BaseModel):
    confirmImpact: bool = False

class LibraryVersionActivateResponse(BaseModel):
    documentId: str
    activeVersionId: str
    previousActiveVersionId: str | None
```

### 6.2 更新 `backend/app/schemas/binding.py`

```python
class SwitchBindingVersionRequest(BaseModel):
    libraryVersionId: str
```

---

## 7. 前端变更

### 7.1 TypeScript 类型 (`frontend/src/app/types/library.ts`)

扩展现有类型:
```typescript
// LibraryDocumentVersionDTO 新增字段
fileName?: string;
fileSize?: number;
```

新增类型:
```typescript
export interface LibraryVersionUploadResponse {
  version: LibraryDocumentVersionDTO;
  parseJob: LibraryParseJobDTO;
  storedFile: LibraryStoredFileDTO;
}

export interface LibraryVersionActivateResponse {
  documentId: string;
  activeVersionId: string;
  previousActiveVersionId: string | null;
}
```

### 7.2 新增 Service 函数 (`frontend/src/app/services/libraryService.ts`)

```typescript
export async function uploadLibraryVersion(
  documentId: string, file: File
): Promise<LibraryVersionUploadResponse>

export async function fetchLibraryVersions(
  documentId: string
): Promise<LibraryDocumentVersionDTO[]>

export async function activateLibraryVersion(
  documentId: string, versionId: string, confirmImpact: boolean
): Promise<LibraryVersionActivateResponse>

export async function deleteLibraryVersion(
  documentId: string, versionId: string
): Promise<void>
```

绑定版本切换:
```typescript
export async function switchBindingVersion(
  kbId: string, bindingId: string, libraryVersionId: string
): Promise<LibraryBindingDTO>
```

### 7.3 P16_LibraryDetail 页面重构

将当前平铺布局重构为 **Tabs 结构**（对齐 P07_DocumentDetail 模式）:

#### Tab 1: 概览
- 文档信息卡片（安全等级、状态、来源类型、创建时间）
- 文件预览（PdfPreview / DocxPreview / TextPreview）
- 保持现有逻辑不变

#### Tab 2: 版本列表（新）
- 表格列: 版本号、文件名、文件大小、解析状态、分块数、Token 数、状态、创建时间、操作
- 活跃版本行: 显示"当前生效" Badge
- 非活跃版本行（parse_status='success'）: 显示"切换"按钮
- 所有版本行: 显示"删除"按钮（活跃版本或被绑定版本禁用，tooltip 说明原因）
- Tab 头部: "上传新版本"按钮 → 文件选择器 → 上传 → 自动刷新版本列表
- 切换操作: ConfirmDialog 二次确认 → 调用 `activateLibraryVersion`
- 删除操作: 检查绑定 → ConfirmDialog → 调用 `deleteLibraryVersion`

#### Tab 3: 解析任务
- 从现有内联区域移出，独立展示
- 表格列: 任务 ID、状态、进度、创建时间、错误信息
- 保持现有逻辑

#### Tab 4: KB 绑定
- 从现有"使用情况"区域移出
- 表格列: KB 名称、绑定状态、当前绑定版本号、分块数、创建时间、操作
- 每行显示该绑定当前指向的库版本号
- "切换版本"操作 → Drawer 打开:
  - 加载 `fetchLibraryVersions` 获取可选版本列表
  - 版本列表显示版本号、文件名、解析状态
  - 用户选择版本 → 确认 → 调用 `switchBindingVersion`
  - 绑定状态变为 "processing"，刷新列表

### 7.4 无需变更的页面

- **P07_DocumentDetail** — KB 侧已有完整版本管理 UI，库侧切换版本会创建新 KB 版本和 ingest 任务，P07 已能正确处理
- **P15_Library** — 列表页无需变更，版本管理在详情页进行
- **P06_DocumentCenter** — KB 文档中心无需变更

---

## 8. 数据流与边界情况

### 8.1 版本上传数据流

```
用户上传文件 → upload_library_version
  → stored_files (MinIO + DB)
  → document_versions (status=processing, parse_status=pending)
  → library_parse_jobs (type=upload_version)
  → Celery: library_parse.run
    → 解析文件 → 存储 parsed_chunks 到 version metadata
    → 更新 version: parse_status=success
```

### 8.2 KB 绑定版本切换数据流

```
用户在 P16 Tab4 点击"切换版本" → 选择目标版本 → 确认
  → switch_binding_version
    → 创建 KB 侧新 document_versions (metadata.library_version_id = 目标版本)
    → 更新 document_kb_bindings.version_id
    → 创建 ingest_jobs
    → Celery: document_ingest.run
      → 从 library_version_id 定位 parsed_chunks
      → 复用 parsed_chunks → 生成 embeddings → 写入 chunks → 同步索引
```

### 8.3 边界情况

| 场景 | 处理方式 |
|------|----------|
| 删除活跃版本 | 拒绝，返回 VERSION_IS_ACTIVE 错误 |
| 删除被 KB 绑定引用的版本 | 拒绝，返回 VERSION_IN_USE + KB 名称列表 |
| 上传新版本后 KB 继续用旧版本 | 自然行为，binding.version_id 不变 |
| 重解析影响历史版本 | 不会，只处理 active_version_id |
| 旧数据无 library_version_id | ingest 管线回退到取最新版本 |
| 新版本未解析完成就尝试切换 | 校验 parse_status='success'，不满足则拒绝 |

---

## 9. 实现顺序

1. **迁移** — `0022_library_version_management.py` + `tables.py` 更新
2. **Schema** — `schemas/library.py`, `schemas/binding.py` 新增 DTO
3. **库服务** — `library_service.py`: 4 个新函数 + 2 个 bug 修复
4. **绑定服务** — `binding_service.py`: `switch_binding_version`
5. **Ingest 修复** — `document_service.py:645-662` 库版本定位修复
6. **API 路由** — `routes/library.py`, `routes/bindings.py` 新增端点
7. **前端类型** — `types/library.ts` 扩展
8. **前端服务** — `libraryService.ts` 新增函数
9. **前端页面** — `P16_LibraryDetail.tsx` Tabs 重构

---

## 10. 关键文件索引

| 文件 | 变更类型 |
|------|----------|
| `backend/migrations/versions/0022_library_version_management.py` | 新建 |
| `backend/app/tables.py` | 修改（document_versions 新增列） |
| `backend/app/schemas/library.py` | 修改（新增 DTO） |
| `backend/app/schemas/binding.py` | 修改（新增请求 Schema） |
| `backend/app/services/library_service.py` | 修改（4 个新函数 + 2 个修复） |
| `backend/app/services/binding_service.py` | 修改（1 个新函数） |
| `backend/app/services/document_service.py` | 修改（ingest 管线修复） |
| `backend/app/api/routes/library.py` | 修改（4 个新端点） |
| `backend/app/api/routes/bindings.py` | 修改（1 个新端点） |
| `frontend/src/app/types/library.ts` | 修改（新增类型） |
| `frontend/src/app/services/libraryService.ts` | 修改（新增函数） |
| `frontend/src/app/pages/P16_LibraryDetail.tsx` | 重构（Tabs 布局） |
