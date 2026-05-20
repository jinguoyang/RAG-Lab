# Sprint 38 设计文档: 文档库 Phase 4 增强功能与优化

## 概述

Sprint 38 是文档库功能的第四阶段，聚焦于权限适配、批量操作、统计展示、大文件优化、错误处理和测试覆盖。

**涉及 Epic:** E28 文档库功能
**前置依赖:** Sprint 36/37 核心功能已完成

---

## 1. 权限体系适配 (S38-001)

### 权限码定义

| 权限码 | 说明 | 默认持有者 |
|--------|------|-----------|
| `library.document.read` | 查看文档列表和详情 | 所有用户（自己的文档） |
| `library.document.create` | 上传新文档 | 所有用户 |
| `library.document.update` | 修改文档元数据 | 文档 owner |
| `library.document.delete` | 删除文档 | 文档 owner |
| `library.document.admin` | 管理所有用户的文档 | 平台管理员 |

### 设计方案

复用现有 RBAC 体系（`permissions` + `role_permission_bindings` 表），在现有 `_ensure_owner()` 旁增加 RBAC 权限检查。

**后端改动：**

1. **`permission_service.py`** — 新增 `has_library_permission(session, user, permission_code)` 函数
   - 检查用户是否为平台管理员 → 自动通过
   - 检查 `role_permission_bindings` 表中是否有对应权限码
   - 对于 `read/update/delete`，额外检查 `documents.owner_id == user.userId`

2. **`library_service.py`** — 替换 `_ensure_owner()` 为 `_ensure_permission(permission_code)`
   - 调用 `has_library_permission()` 进行权限检查
   - `admin` 权限码可绕过 owner 限制

3. **Migration** — 预置权限码到 `permissions` 表
   - 平台管理员角色自动绑定 `library.document.admin`
   - 普通用户角色绑定 `library.document.read` 和 `library.document.create`

### 权限检查流程

```
请求 → get_current_user → has_library_permission(session, user, "library.document.delete")
  ├── 用户是管理员? → 通过
  ├── 用户有 library.document.admin 权限? → 通过
  ├── 用户有 library.document.delete 权限 AND 是文档 owner? → 通过
  └── 否则 → 403 Forbidden
```

---

## 2. 批量操作支持 (S38-002)

### API 设计

```
POST /api/v1/library/documents/batch-actions
Content-Type: application/json

Request Body:
{
  "documentIds": ["doc-1", "doc-2", "doc-3"],
  "action": "delete" | "reparse" | "disable"
}

Response (200):
{
  "succeeded": ["doc-1", "doc-3"],
  "failed": [
    { "documentId": "doc-2", "error": "PERMISSION_DENIED", "message": "无权限操作该文档" }
  ],
  "summary": { "total": 3, "succeeded": 2, "failed": 1 }
}
```

### 行为定义

| Action | 行为 | 前置条件 |
|--------|------|---------|
| `delete` | 软删除 + 级联解绑 | 文档存在 + 有 delete 权限 |
| `reparse` | 重置解析状态 + 重新触发 Celery 任务 | 文档存在 + 有 update 权限 + 当前状态为 failed |
| `disable` | 设置 `documents.status = 'disabled'` | 文档存在 + 有 update 权限 + 当前状态为 active |

### 权限检查策略

部分执行 + 返回明细：逐个检查权限，只操作有权限的文档，返回成功/失败明细。

### 限制

- 单次批量操作最大文档数：100
- 超过限制返回 400 错误

### 实现方案

**后端改动：**

1. **`schemas/library.py`** — 新增 `BatchActionRequest` 和 `BatchActionResponse` DTO
2. **`library_service.py`** — 新增 `batch_action(session, user, document_ids, action)` 函数
   - 遍历 document_ids，逐个检查权限并执行
   - 收集成功/失败结果
   - 对于 `delete`，复用现有 `delete_document()` 逻辑（含级联解绑）
   - 对于 `reparse`，复用现有 `retry_parse()` 逻辑
3. **`routes/library.py`** — 新增 `POST /batch-actions` 端点

**前端改动：**

1. **`P15_Library.tsx`** — 添加批量选择 checkbox + 操作按钮栏
2. **`libraryService.ts`** — 新增 `batchAction(documentIds, action)` API 函数

---

## 3. 文档库统计卡片 (S38-003)

### API 设计

```
GET /api/v1/library/documents/stats

Response (200):
{
  "totalDocuments": 42,
  "todayUploads": 3,
  "pendingParse": 5
}
```

### 实现方案

**后端改动：**

1. **`library_service.py`** — 新增 `get_library_stats(session, user)` 函数
   - `totalDocuments`: `SELECT COUNT(*) FROM documents WHERE owner_id = :userId AND source_type = 'library'`（仅统计当前用户的文档库文档）
   - `todayUploads`: 同上 + `created_at >= today`
   - `pendingParse`: `SELECT COUNT(*) FROM library_parse_jobs jp JOIN documents d ON jp.document_id = d.document_id WHERE jp.status IN ('pending', 'running') AND d.owner_id = :userId`
2. **`schemas/library.py`** — 新增 `LibraryStatsResponse` DTO
3. **`routes/library.py`** — 新增 `GET /stats` 端点

**前端改动：**

1. **`P15_Library.tsx`** — 在文档列表上方添加统计卡片区域
   - 三张卡片：总文档数、今日上传、待解析
   - 待解析卡片可点击，自动筛选 `status=pending` 的文档
   - 使用现有 `Card` 组件，保持视觉风格一致

2. **`libraryService.ts`** — 新增 `fetchLibraryStats()` API 函数

### P15 页面布局

```
┌─────────────────────────────────────────────────────┐
│  我的文档库                                  [上传文档] │
├─────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ 总文档 42 │  │ 今日上传 3│  │ 待解析 5  │          │
│  └──────────┘  └──────────┘  └──────────┘          │
├─────────────────────────────────────────────────────┤
│  [搜索框] [状态筛选]                    共 X 个文档    │
│  ┌─────────────────────────────────────────────┐    │
│  │ 文档列表表格                                  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 4. 大文件处理优化 (S38-004)

### 前端方案

**进度条实现：**

1. **`libraryService.ts`** — 修改 `uploadLibraryDocument()` 函数
   - 使用 `XMLHttpRequest` 替代 `fetch`（fetch 不支持 upload progress）
   - 监听 `xhr.upload.onprogress` 事件
   - 返回 `{ promise, progress$ }` 结构，progress$ 为可观察的进度流

2. **`P15_Library.tsx`** — 上传组件增强
   - 上传时显示进度条（百分比 + 文件大小）
   - 上传完成后自动刷新列表和统计数据
   - 上传失败显示错误信息，支持重试

### 后端方案

后端无需改动 — FastAPI 的 `UploadFile` 已支持流式接收，不需要分片逻辑。

### 进度条 UI

```
┌─────────────────────────────────────┐
│  上传中: report.pdf                  │
│  ████████████░░░░░░░░  65% (65MB/100MB) │
│                              [取消]  │
└─────────────────────────────────────┘
```

---

## 5. 错误处理与重试机制 (S38-005)

### 重试机制

**解析失败自动重试：**

- 最多重试 3 次
- 间隔递增：5s → 15s → 45s（指数退避）
- 重试在 Celery 任务内部执行，同步等待
- 3 次全部失败后，标记任务为 `failed`，记录最终错误

**实现改动：**

1. **Celery 任务** (`library_service.py` 中的 `run_library_parse_task`)
   - 在现有逻辑外包裹重试循环
   - 每次重试前等待递增间隔
   - 记录每次重试的错误信息到 `library_parse_jobs.error_message`

2. **`error_detail` 字段** — 新增到 `library_parse_jobs` 表（JSONB 类型）
   - 存储结构化诊断信息（错误类型、文件名、重试次数、建议）
   - 需要新增 database migration

3. **手动重试** — 保留现有的 `retry_parse` 端点，用户可手动触发

### 错误诊断信息

**结构化错误字段扩展：**

```json
{
  "status": "failed",
  "errorCode": "PARSE_TIMEOUT",
  "errorMessage": "解析超时，文件可能过大或格式异常",
  "errorDetail": {
    "type": "timeout",
    "file": "large_report.pdf",
    "fileSize": 157286400,
    "retryCount": 3,
    "lastRetryAt": "2026-05-19T10:30:00Z",
    "suggestion": "请尝试拆分文件或联系管理员"
  }
}
```

**错误类型枚举：**

| errorCode | 说明 | 建议 |
|-----------|------|------|
| `PARSE_TIMEOUT` | 解析超时 | 拆分文件或联系管理员 |
| `UNSUPPORTED_FORMAT` | 不支持的文件格式 | 检查文件格式 |
| `FILE_CORRUPTED` | 文件损坏 | 重新上传 |
| `STORAGE_ERROR` | 存储服务异常 | 稍后重试 |
| `UNKNOWN` | 未知错误 | 联系管理员 |

---

## 6. 单元测试与集成测试 (S38-006)

### 后端测试结构

```
backend/app/tests/
├── conftest.py              # 测试配置：测试数据库、fixtures
├── unit/
│   ├── test_permission_service.py   # 权限检查逻辑
│   ├── test_library_service.py      # CRUD、批量操作、统计
│   └── test_retry_logic.py          # 重试机制
└── integration/
    └── test_library_e2e.py          # 上传→解析→预览→绑定→使用
```

**conftest.py 关键 fixtures：**
- `test_db`: 创建测试数据库 session
- `test_user`: 模拟当前用户
- `test_library_document`: 预置测试文档

**重点测试用例：**

| 测试文件 | 关键用例 |
|---------|---------|
| `test_permission_service.py` | 管理员全权限、普通用户 owner-check、无权限拒绝 |
| `test_library_service.py` | 上传、列表、详情、删除、批量操作、统计 |
| `test_retry_logic.py` | 重试 3 次后失败、间隔递增、中间成功停止重试 |
| `test_library_e2e.py` | 完整流程：上传文档 → 触发解析 → 预览文本 → 绑定 KB → 验证绑定 |

### 前端测试结构

```
frontend/src/
├── app/
│   ├── services/
│   │   └── libraryService.test.ts    # API 调用测试
│   └── components/
│       └── rag/
│           └── UploadProgress.test.tsx  # 进度条组件测试
```

### 测试运行命令

```bash
# 后端单元测试
conda run -n rag-lab pytest app/tests/unit -v

# 后端集成测试
conda run -n rag-lab pytest app/tests/integration -v

# 前端测试
npm run test -- --run
```

---

## 数据库变更

### Migration 0018

1. **`library_parse_jobs` 表新增字段**
   - `error_detail` JSONB — 存储结构化诊断信息

2. **`permissions` 表初始化数据**
   - 插入 5 条权限码：`library.document.read/create/update/delete/admin`

3. **`role_permission_bindings` 表初始化数据**
   - 平台管理员角色绑定 `library.document.admin`
   - 普通用户角色绑定 `library.document.read` + `library.document.create`

---

## 文件变更清单

### 后端新增文件
- `backend/app/tests/conftest.py`
- `backend/app/tests/unit/test_permission_service.py`
- `backend/app/tests/unit/test_library_service.py`
- `backend/app/tests/unit/test_retry_logic.py`
- `backend/app/tests/integration/test_library_e2e.py`
- `backend/scripts/verify_library_permissions.py`
- `backend/scripts/verify_library_batch_operations.py`
- `backend/scripts/verify_large_file_upload.py`
- `backend/scripts/verify_parsing_retry.py`

### 后端修改文件
- `backend/app/services/permission_service.py` — 新增 `has_library_permission()`
- `backend/app/services/library_service.py` — 权限检查替换、批量操作、统计、重试机制
- `backend/app/schemas/library.py` — 新增 DTO
- `backend/app/api/routes/library.py` — 新增端点
- `backend/app/tables.py` — `library_parse_jobs` 表新增 `error_detail` JSONB 字段
- `backend/migrations/versions/0018_*.py` — 新增 migration（error_detail 字段 + 权限码初始化）

### 前端新增文件
- `frontend/src/app/services/libraryService.test.ts`
- `frontend/src/app/components/rag/UploadProgress.test.tsx`

### 前端修改文件
- `frontend/src/app/pages/P15_Library.tsx` — 统计卡片、批量选择、进度条
- `frontend/src/app/services/libraryService.ts` — 上传进度、批量操作、统计 API
- `frontend/src/app/types/library.ts` — 新增类型定义

---

## 范围边界

- 不支持高级文件夹管理、标签分类或自定义元数据字段
- 不涉及文档版本管理、VCS 级别的变更追踪
- 不支持秒传、去重或内容寻址存储
- 不涉及云存储集成（Google Drive、OneDrive）
- 权限细节采用最小化设计，不涉及复杂的基于内容的访问控制
