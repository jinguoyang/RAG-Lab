# Sprint 38: 文档库 Phase 4 增强功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为文档库添加权限适配、批量操作、统计卡片、上传进度、错误重试和测试覆盖。

**Architecture:** 复用现有 RBAC 权限体系，在 `permission_service.py` 新增 `has_library_permission()`；批量操作和统计作为新端点添加到 `library.py` 路由；前端使用 XMLHttpRequest 实现上传进度。

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, Celery, React, TypeScript, Vitest, pytest

---

## File Structure

### Backend Modified
- `backend/app/tables.py` — `library_parse_jobs` 新增 `error_detail` JSONB 列
- `backend/app/services/permission_service.py` — 新增 `has_library_permission()`
- `backend/app/services/library_service.py` — 替换 `_ensure_owner()` 为 `_ensure_permission()`，新增 `batch_action()`, `get_library_stats()`, 重试逻辑
- `backend/app/schemas/library.py` — 新增 `BatchActionRequest`, `BatchActionResponse`, `LibraryStatsResponse`
- `backend/app/api/routes/library.py` — 新增 `/batch-actions`, `/stats` 端点

### Backend Created
- `backend/migrations/versions/0018_library_permissions_and_error_detail.py`
- `backend/app/tests/__init__.py`
- `backend/app/tests/conftest.py`
- `backend/app/tests/unit/__init__.py`
- `backend/app/tests/unit/test_permission_service.py`
- `backend/app/tests/unit/test_library_service.py`
- `backend/app/tests/unit/test_retry_logic.py`
- `backend/app/tests/integration/__init__.py`
- `backend/app/tests/integration/test_library_e2e.py`

### Frontend Modified
- `frontend/src/app/types/library.ts` — 新增类型
- `frontend/src/app/services/libraryService.ts` — 新增函数 + 上传进度
- `frontend/src/app/pages/P15_Library.tsx` — 统计卡片、批量选择、进度条

### Frontend Created
- `frontend/src/app/services/libraryService.test.ts`

---

### Task 1: Database Migration — error_detail + 权限码初始化

**Files:**
- Create: `backend/migrations/versions/0018_library_permissions_and_error_detail.py`
- Modify: `backend/app/tables.py`

- [ ] **Step 1: 修改 tables.py，为 library_parse_jobs 添加 error_detail 列**

在 `backend/app/tables.py` 中找到 `library_parse_jobs` 表定义，在 `error_message` 列后添加：

```python
sa.Column("error_detail", postgresql.JSONB(), nullable=True),
```

- [ ] **Step 2: 创建 migration 文件**

创建 `backend/migrations/versions/0018_library_permissions_and_error_detail.py`：

```python
"""library permissions and error_detail

Revision ID: 0018_library_perms
Revises: 0017_document_library
Create Date: 2026-05-19 00:00:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0018_library_perms"
down_revision: str | None = "0017_document_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. library_parse_jobs 新增 error_detail
    op.add_column(
        "library_parse_jobs",
        sa.Column("error_detail", postgresql.JSONB(), nullable=True),
    )

    # 2. 插入权限码
    op.execute("""
        INSERT INTO permissions (permission_id, permission_code, scope, name, description, status, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'library.document.read', 'library', '文档库-查看', '查看文档库文档列表和详情', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.create', 'library', '文档库-创建', '上传新文档到文档库', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.update', 'library', '文档库-修改', '修改文档库文档元数据', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.delete', 'library', '文档库-删除', '删除文档库文档', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.admin', 'library', '文档库-管理', '管理所有用户的文档库文档', 'active', now(), now())
        ON CONFLICT DO NOTHING
    """)

    # 3. 平台管理员绑定 library.document.admin
    op.execute("""
        INSERT INTO role_permission_bindings (role_permission_id, role_scope, role_code, permission_code, effect, status, created_at, updated_at)
        SELECT gen_random_uuid(), 'platform', 'admin', 'library.document.admin', 'allow', 'active', now(), now()
        WHERE NOT EXISTS (
            SELECT 1 FROM role_permission_bindings
            WHERE role_scope = 'platform' AND role_code = 'admin' AND permission_code = 'library.document.admin'
        )
    """)

    # 4. 普通用户绑定 read + create
    op.execute("""
        INSERT INTO role_permission_bindings (role_permission_id, role_scope, role_code, permission_code, effect, status, created_at, updated_at)
        SELECT gen_random_uuid(), 'platform', role_code, perm_code, 'allow', 'active', now(), now()
        FROM (VALUES ('user'), ('editor')) AS roles(role_code)
        CROSS JOIN (VALUES ('library.document.read'), ('library.document.create')) AS perms(perm_code)
        WHERE NOT EXISTS (
            SELECT 1 FROM role_permission_bindings
            WHERE role_scope = 'platform' AND role_code = roles.role_code AND permission_code = perms.perm_code
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM role_permission_bindings WHERE permission_code LIKE 'library.document.%'
    """)
    op.execute("""
        DELETE FROM permissions WHERE permission_code LIKE 'library.document.%'
    """)
    op.drop_column("library_parse_jobs", "error_detail")
```

- [ ] **Step 3: 验证 migration 语法**

Run: `cd backend && conda run -n rag-lab python -c "from migrations.versions.0018_library_permissions_and_error_detail import upgrade; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/tables.py backend/migrations/versions/0018_library_permissions_and_error_detail.py
git commit -m "feat(library): add migration for permissions and error_detail field"
```

---

### Task 2: 权限服务 — has_library_permission()

**Files:**
- Modify: `backend/app/services/permission_service.py`

- [ ] **Step 1: 编写权限检查函数**

在 `permission_service.py` 末尾添加：

```python
def has_library_permission(
    session: Session,
    current_user: CurrentUserResponse,
    permission_code: str,
    document_owner_id: UUID | None = None,
) -> bool:
    """判断当前用户是否具备文档库权限。

    规则：
    1. 平台管理员自动通过
    2. 拥有 library.document.admin 权限则通过
    3. 拥有对应权限码 且 (无 owner 要求 或 是文档 owner) 则通过
    """
    user_id = _user_id(current_user)

    # 管理员自动通过
    if current_user.user.platformRole == "admin":
        return True

    # 解析平台角色权限
    platform_allowed, platform_denied = _role_permissions(
        session, "platform", {current_user.user.platformRole},
    )

    # admin 权限码可绕过 owner 限制
    if "library.document.admin" in platform_allowed and "library.document.admin" not in platform_denied:
        return True

    # 检查目标权限码
    if permission_code in platform_denied:
        return False
    if permission_code not in platform_allowed:
        return False

    # 对于需要 owner 检查的权限
    if document_owner_id is not None and permission_code in {
        "library.document.read",
        "library.document.update",
        "library.document.delete",
    }:
        return user_id == document_owner_id

    return True
```

- [ ] **Step 2: 验证导入**

Run: `cd backend && conda run -n rag-lab python -c "from app.services.permission_service import has_library_permission; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/permission_service.py
git commit -m "feat(library): add has_library_permission() to permission service"
```

---

### Task 3: Library Service — 替换 _ensure_owner 为 _ensure_permission

**Files:**
- Modify: `backend/app/services/library_service.py`

- [ ] **Step 1: 修改 _ensure_owner 函数**

将 `library_service.py` 中的 `_ensure_owner` 函数（约 107-125 行）替换为：

```python
def _ensure_owner(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    permission_code: str = "library.document.read",
) -> RowMapping:
    """校验文档存在且当前用户有权限访问，否则抛出异常。"""
    from app.services.permission_service import has_library_permission

    row = session.execute(
        select(documents)
        .where(
            documents.c.document_id == document_id,
            documents.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if row is None:
        raise LibraryDocumentNotFoundError

    owner_id = row["owner_id"]
    if owner_id is not None and not has_library_permission(
        session, current_user, permission_code, document_owner_id=UUID(str(owner_id)),
    ):
        raise LibraryPermissionError
    return row
```

- [ ] **Step 2: 确认所有调用点仍然正确**

Run: `cd backend && grep -n "_ensure_owner" app/services/library_service.py`
Expected: 约 6 处调用，均传入 `session, current_user, document_id`，默认使用 `library.document.read`

- [ ] **Step 3: 验证导入**

Run: `cd backend && conda run -n rag-lab python -c "from app.services.library_service import _ensure_owner; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/library_service.py
git commit -m "feat(library): replace owner-check with RBAC permission check"
```

---

### Task 4: 批量操作 — Schema + Service + Route

**Files:**
- Modify: `backend/app/schemas/library.py`
- Modify: `backend/app/services/library_service.py`
- Modify: `backend/app/api/routes/library.py`

- [ ] **Step 1: 添加批量操作 DTO**

在 `backend/app/schemas/library.py` 末尾添加：

```python
class BatchActionRequest(BaseModel):
    """批量操作请求。"""
    documentIds: list[str] = Field(..., min_length=1, max_length=100)
    action: Literal["delete", "reparse", "disable"]


class BatchActionFailedItem(BaseModel):
    """批量操作失败项。"""
    documentId: str
    error: str
    message: str


class BatchActionSummary(BaseModel):
    """批量操作汇总。"""
    total: int
    succeeded: int
    failed: int


class BatchActionResponse(BaseModel):
    """批量操作响应。"""
    succeeded: list[str]
    failed: list[BatchActionFailedItem]
    summary: BatchActionSummary
```

注意：需要在文件顶部的 `from pydantic import BaseModel` 行添加 `Field` 和 `Literal`：

```python
from typing import Literal
from pydantic import BaseModel, Field
```

- [ ] **Step 2: 添加批量操作 service 函数**

在 `library_service.py` 中添加（在 `retry_library_parse` 函数之后）：

```python
def batch_action(
    session: Session,
    current_user: CurrentUserResponse,
    document_ids: list[str],
    action: str,
) -> dict:
    """批量操作文档：delete / reparse / disable。逐个检查权限，部分执行。"""
    succeeded: list[str] = []
    failed: list[dict] = []

    for doc_id_str in document_ids:
        try:
            doc_id = UUID(doc_id_str)
        except ValueError:
            failed.append({"documentId": doc_id_str, "error": "INVALID_ID", "message": "无效的文档 ID"})
            continue

        try:
            if action == "delete":
                delete_library_document(session, current_user, doc_id)
            elif action == "reparse":
                retry_library_parse(session, current_user, doc_id)
            elif action == "disable":
                _ensure_owner(session, current_user, doc_id, "library.document.update")
                row = session.execute(
                    select(documents).where(documents.c.document_id == doc_id)
                ).mappings().first()
                if row and row["status"] != "active":
                    raise LibraryPermissionError
                session.execute(
                    update(documents)
                    .where(documents.c.document_id == doc_id)
                    .values(
                        status="disabled",
                        updated_by=UUID(current_user.user.userId),
                        updated_at=func.now(),
                    )
                )
                session.commit()
            succeeded.append(doc_id_str)
        except LibraryPermissionError:
            failed.append({"documentId": doc_id_str, "error": "PERMISSION_DENIED", "message": "无权限操作该文档"})
        except LibraryDocumentNotFoundError:
            failed.append({"documentId": doc_id_str, "error": "NOT_FOUND", "message": "文档不存在"})
        except Exception:
            failed.append({"documentId": doc_id_str, "error": "UNKNOWN", "message": "操作失败，请稍后重试"})

    return {
        "succeeded": succeeded,
        "failed": failed,
        "summary": {
            "total": len(document_ids),
            "succeeded": len(succeeded),
            "failed": len(failed),
        },
    }
```

- [ ] **Step 3: 添加路由端点**

在 `routes/library.py` 中：
1. 在 import 区域添加 `BatchActionRequest` 到从 `app.schemas.library` 的导入
2. 在 import 区域添加 `batch_action` 到从 `app.services.library_service` 的导入
3. 在路由函数区域添加新端点（放在 `list_documents` 之后，`{document_id}` 路由之前）：

```python
@router.post("/batch-actions", response_model=BatchActionResponse)
def batch_actions(
    body: BatchActionRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> BatchActionResponse:
    """批量操作文档：删除、重新解析、停用。"""
    try:
        result = batch_action(db, current_user, body.documentIds, body.action)
        return BatchActionResponse(**result)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable
```

- [ ] **Step 4: 验证导入**

Run: `cd backend && conda run -n rag-lab python -c "from app.api.routes.library import router; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/library.py backend/app/services/library_service.py backend/app/api/routes/library.py
git commit -m "feat(library): add batch-actions endpoint for delete/reparse/disable"
```

---

### Task 5: 统计 API — Schema + Service + Route

**Files:**
- Modify: `backend/app/schemas/library.py`
- Modify: `backend/app/services/library_service.py`
- Modify: `backend/app/api/routes/library.py`

- [ ] **Step 1: 添加统计 DTO**

在 `backend/app/schemas/library.py` 末尾添加：

```python
class LibraryStatsResponse(BaseModel):
    """文档库统计响应。"""
    totalDocuments: int
    todayUploads: int
    pendingParse: int
```

- [ ] **Step 2: 添加统计 service 函数**

在 `library_service.py` 中添加（在 `batch_action` 函数之后）：

```python
def get_library_stats(
    session: Session,
    current_user: CurrentUserResponse,
) -> dict:
    """获取当前用户的文档库统计数据。"""
    owner_id = UUID(current_user.user.userId)
    today_start = sa.text("date_trunc('day', now())")

    total_documents = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.owner_id == owner_id,
            documents.c.source_type == "upload",
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    today_uploads = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.owner_id == owner_id,
            documents.c.source_type == "upload",
            documents.c.deleted_at.is_(None),
            documents.c.created_at >= today_start,
        )
    ).scalar_one()

    pending_parse = session.execute(
        select(func.count())
        .select_from(library_parse_jobs)
        .join(documents, library_parse_jobs.c.document_id == documents.c.document_id)
        .where(
            library_parse_jobs.c.status.in_(["pending", "running", "queued"]),
            documents.c.owner_id == owner_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    return {
        "totalDocuments": total_documents,
        "todayUploads": today_uploads,
        "pendingParse": pending_parse,
    }
```

- [ ] **Step 3: 添加路由端点**

在 `routes/library.py` 中：
1. 在 import 区域添加 `LibraryStatsResponse` 到从 `app.schemas.library` 的导入
2. 在 import 区域添加 `get_library_stats` 到从 `app.services.library_service` 的导入
3. 在路由函数区域添加新端点（放在 `batch_actions` 之后）：

```python
@router.get("/stats", response_model=LibraryStatsResponse)
def get_stats(
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryStatsResponse:
    """获取当前用户的文档库统计。"""
    try:
        return LibraryStatsResponse(**get_library_stats(db, current_user))
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable
```

- [ ] **Step 4: 验证导入**

Run: `cd backend && conda run -n rag-lab python -c "from app.api.routes.library import router; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/library.py backend/app/services/library_service.py backend/app/api/routes/library.py
git commit -m "feat(library): add stats endpoint for library dashboard"
```

---

### Task 6: 错误重试机制 — 解析失败自动重试

**Files:**
- Modify: `backend/app/services/library_service.py`

- [ ] **Step 1: 修改 _mark_job_failed 支持 error_detail**

将 `library_service.py` 中的 `_mark_job_failed` 函数（约 721-746 行）替换为：

```python
def _mark_job_failed(
    session: Session,
    job_id: UUID,
    error_code: str,
    error_message: str,
    error_detail: dict | None = None,
) -> None:
    values = {
        "status": "failed",
        "error_code": error_code,
        "error_message": error_message,
        "finished_at": sa.func.now(),
    }
    if error_detail is not None:
        values["error_detail"] = error_detail

    session.execute(
        update(library_parse_jobs)
        .where(library_parse_jobs.c.job_id == job_id)
        .values(**values)
    )
    # 同步更新 version 状态
    job = session.execute(
        select(library_parse_jobs).where(library_parse_jobs.c.job_id == job_id)
    ).mappings().first()
    if job:
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == job["version_id"])
            .values(
                parse_status="failed",
                error_code=error_code,
                error_message=error_message,
            )
        )
    session.commit()
```

- [ ] **Step 2: 修改 run_library_parse_job_by_id 添加重试逻辑**

将 `run_library_parse_job_by_id` 函数（约 464-578 行）中的解析部分替换为带重试的版本。找到以下代码块：

```python
        try:
            parsed = parse_document(
                file_name=file_row["file_name"],
                mime_type=file_row["mime_type"],
                file_bytes=file_bytes,
            )
        except DocumentParseError as exc:
            _mark_job_failed(session, job_id, exc.error_code, str(exc))
            return {"error": exc.error_code}
```

替换为：

```python
        # 带重试的解析逻辑
        import time
        from app.services.document_parsing import DocumentParseError

        max_retries = 3
        retry_delays = [5, 15, 45]  # 指数退避
        parsed = None
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                parsed = parse_document(
                    file_name=file_row["file_name"],
                    mime_type=file_row["mime_type"],
                    file_bytes=file_bytes,
                )
                break  # 成功，退出重试循环
            except DocumentParseError as exc:
                last_error = exc
                if attempt < max_retries:
                    # 更新 job 进度，记录重试信息
                    session.execute(
                        update(library_parse_jobs)
                        .where(library_parse_jobs.c.job_id == job_id)
                        .values(
                            progress=int((attempt + 1) / (max_retries + 1) * 50),
                            error_message=f"重试 {attempt + 1}/{max_retries}: {exc}",
                        )
                    )
                    session.commit()
                    time.sleep(retry_delays[attempt])
                else:
                    # 最终失败
                    error_detail = {
                        "type": "parse_error",
                        "file": file_row["file_name"],
                        "fileSize": file_row["file_size"],
                        "retryCount": max_retries,
                        "errorCode": exc.error_code,
                        "suggestion": _get_error_suggestion(exc.error_code),
                    }
                    _mark_job_failed(session, job_id, exc.error_code, str(exc), error_detail)
                    return {"error": exc.error_code}

        if parsed is None:
            _mark_job_failed(session, job_id, "UNKNOWN", "解析失败", {
                "type": "unknown",
                "file": file_row["file_name"],
                "retryCount": max_retries,
                "suggestion": "请联系管理员",
            })
            return {"error": "UNKNOWN"}
```

- [ ] **Step 3: 添加错误建议函数**

在 `library_service.py` 中 `_mark_job_failed` 函数之前添加：

```python
def _get_error_suggestion(error_code: str) -> str:
    """根据错误码返回用户友好的建议。"""
    suggestions = {
        "PARSE_TIMEOUT": "请尝试拆分文件或联系管理员",
        "UNSUPPORTED_FORMAT": "请检查文件格式是否受支持",
        "FILE_CORRUPTED": "请重新上传文件",
        "STORAGE_ERROR": "存储服务异常，请稍后重试",
    }
    return suggestions.get(error_code, "请联系管理员")
```

- [ ] **Step 4: 验证导入**

Run: `cd backend && conda run -n rag-lab python -c "from app.services.library_service import run_library_parse_job_by_id; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/library_service.py
git commit -m "feat(library): add auto-retry with exponential backoff for parse failures"
```

---

### Task 7: 前端类型 + API 函数

**Files:**
- Modify: `frontend/src/app/types/library.ts`
- Modify: `frontend/src/app/services/libraryService.ts`

- [ ] **Step 1: 添加前端类型定义**

在 `frontend/src/app/types/library.ts` 末尾添加：

```typescript
export interface LibraryStatsResponse {
  totalDocuments: number;
  todayUploads: number;
  pendingParse: number;
}

export interface BatchActionFailedItem {
  documentId: string;
  error: string;
  message: string;
}

export interface BatchActionSummary {
  total: number;
  succeeded: number;
  failed: number;
}

export interface BatchActionResponse {
  succeeded: string[];
  failed: BatchActionFailedItem[];
  summary: BatchActionSummary;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

export interface UploadWithProgressResult {
  promise: Promise<LibraryDocumentUploadResponse>;
  cancel: () => void;
  onProgress: (callback: (progress: UploadProgress) => void) => void;
}
```

- [ ] **Step 2: 添加 API 函数**

在 `frontend/src/app/services/libraryService.ts` 中添加：

```typescript
export async function fetchLibraryStats(): Promise<LibraryStatsResponse> {
  return apiGet<LibraryStatsResponse>("/library/documents/stats");
}

export async function batchAction(
  documentIds: string[],
  action: "delete" | "reparse" | "disable",
): Promise<BatchActionResponse> {
  return apiPostJson<BatchActionResponse>("/library/documents/batch-actions", {
    documentIds,
    action,
  });
}
```

同时在文件顶部的 import 中添加新类型：

```typescript
import type {
  // ... existing types ...
  LibraryStatsResponse,
  BatchActionResponse,
  UploadProgress,
  UploadWithProgressResult,
} from "../types/library";
```

- [ ] **Step 3: 修改 uploadLibraryDocument 支持进度**

将 `libraryService.ts` 中的 `uploadLibraryDocument` 函数替换为：

```typescript
export function uploadLibraryDocumentWithProgress(
  file: File,
  name: string,
  securityLevel: string,
): UploadWithProgressResult {
  const body = new FormData();
  body.set("file", file);
  if (name.trim()) {
    body.set("name", name.trim());
  }
  body.set("securityLevel", securityLevel);

  const xhr = new XMLHttpRequest();
  let progressCallback: ((progress: UploadProgress) => void) | null = null;

  const promise = new Promise<LibraryDocumentUploadResponse>((resolve, reject) => {
    xhr.open("POST", `${API_BASE_URL}/library/documents`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && progressCallback) {
        progressCallback({
          loaded: event.loaded,
          total: event.total,
          percent: Math.round((event.loaded / event.total) * 100),
        });
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as LibraryDocumentUploadResponse);
      } else {
        let message = `上传失败: ${xhr.status}`;
        try {
          const body = JSON.parse(xhr.responseText);
          message = body.detail || body.message || message;
        } catch {}
        reject(new Error(message));
      }
    };

    xhr.onerror = () => reject(new Error("网络错误，请检查连接"));
    xhr.onabort = () => reject(new Error("上传已取消"));

    xhr.send(body);
  });

  return {
    promise,
    cancel: () => xhr.abort(),
    onProgress: (callback) => { progressCallback = callback; },
  };
}

// 保留原有函数作为向后兼容
export async function uploadLibraryDocument(
  file: File,
  name: string,
  securityLevel: string,
): Promise<LibraryDocumentUploadResponse> {
  return uploadLibraryDocumentWithProgress(file, name, securityLevel).promise;
}
```

注意：需要在文件顶部确认 `API_BASE_URL` 已从 `apiClient` 导入：

```typescript
import { apiDelete, apiDownload, apiGet, apiPatchJson, apiPostForm, apiPostJson } from "./apiClient";
import { API_BASE_URL } from "./apiClient";
```

- [ ] **Step 4: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/types/library.ts frontend/src/app/services/libraryService.ts
git commit -m "feat(frontend): add stats API, batch action, and upload progress support"
```

---

### Task 8: 前端 P15 — 统计卡片 + 批量选择 + 上传进度

**Files:**
- Modify: `frontend/src/app/pages/P15_Library.tsx`

- [ ] **Step 1: 添加统计卡片到 P15**

在 `P15_Library.tsx` 中：
1. 添加新的 import：

```typescript
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Search, Upload, Download, FileText, ChevronLeft, ChevronRight, Trash2, RefreshCw, Power, SquareCheck } from "lucide-react";
import { Card, CardContent } from "../components/rag/Card";
import {
  fetchLibraryDocuments,
  uploadLibraryDocumentWithProgress,
  downloadLibraryDocument,
  fetchLibraryStats,
  batchAction,
} from "../services/libraryService";
import type { LibraryDocumentDTO, LibraryParseJobStatus, LibraryStatsResponse, UploadProgress } from "../types/library";
```

2. 在 `Library` 组件的 state 中添加：

```typescript
const [stats, setStats] = useState<LibraryStatsResponse | null>(null);
const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
const [batchLoading, setBatchLoading] = useState(false);
const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
```

3. 添加 stats 加载函数：

```typescript
const loadStats = useCallback(async () => {
  try {
    const data = await fetchLibraryStats();
    setStats(data);
  } catch {}
}, []);

useEffect(() => {
  void loadStats();
}, [loadStats]);
```

4. 在 `loadData` 函数末尾添加 `void loadStats();`

5. 在搜索和筛选区域之前添加统计卡片：

```tsx
{/* 统计卡片 */}
{stats && (
  <div className="grid grid-cols-3 gap-4">
    <Card className="cursor-pointer hover:border-terracotta transition-colors" onClick={() => { setStatusFilter(""); void loadData("", 1); }}>
      <CardContent className="py-4">
        <div className="text-2xl font-semibold text-near-black">{stats.totalDocuments}</div>
        <div className="text-sm text-stone-gray">总文档数</div>
      </CardContent>
    </Card>
    <Card>
      <CardContent className="py-4">
        <div className="text-2xl font-semibold text-near-black">{stats.todayUploads}</div>
        <div className="text-sm text-stone-gray">今日上传</div>
      </CardContent>
    </Card>
    <Card className="cursor-pointer hover:border-terracotta transition-colors" onClick={() => { setStatusFilter("active"); void loadData("", 1); }}>
      <CardContent className="py-4">
        <div className="text-2xl font-semibold text-amber-600">{stats.pendingParse}</div>
        <div className="text-sm text-stone-gray">待解析</div>
      </CardContent>
    </Card>
  </div>
)}
```

- [ ] **Step 2: 添加批量选择功能**

1. 在表格 header 中添加 checkbox 列：

```tsx
<TableHead className="w-10">
  <input
    type="checkbox"
    checked={selectedIds.size === documents.length && documents.length > 0}
    onChange={(e) => {
      if (e.target.checked) {
        setSelectedIds(new Set(documents.map((d) => d.documentId)));
      } else {
        setSelectedIds(new Set());
      }
    }}
    className="h-4 w-4 accent-terracotta"
  />
</TableHead>
```

2. 在表格 body 的每行开头添加 checkbox：

```tsx
<TableCell>
  <input
    type="checkbox"
    checked={selectedIds.has(doc.documentId)}
    onChange={(e) => {
      const next = new Set(selectedIds);
      if (e.target.checked) next.add(doc.documentId);
      else next.delete(doc.documentId);
      setSelectedIds(next);
    }}
    onClick={(e) => e.stopPropagation()}
    className="h-4 w-4 accent-terracotta"
  />
</TableCell>
```

3. 在搜索栏下方添加批量操作按钮：

```tsx
{/* 批量操作栏 */}
{selectedIds.size > 0 && (
  <div className="flex items-center gap-3 p-3 bg-parchment rounded-lg border border-border-cream">
    <span className="text-sm text-near-black">已选 {selectedIds.size} 个文档</span>
    <Button variant="ghost" size="sm" disabled={batchLoading} onClick={() => void handleBatchAction("reparse")}>
      <RefreshCw className="w-4 h-4 mr-1" /> 重新解析
    </Button>
    <Button variant="ghost" size="sm" disabled={batchLoading} onClick={() => void handleBatchAction("disable")}>
      <Power className="w-4 h-4 mr-1" /> 停用
    </Button>
    <Button variant="ghost" size="sm" disabled={batchLoading} onClick={() => void handleBatchAction("delete")} className="text-red-600 hover:text-red-700">
      <Trash2 className="w-4 h-4 mr-1" /> 删除
    </Button>
  </div>
)}
```

4. 添加批量操作处理函数：

```typescript
async function handleBatchAction(action: "delete" | "reparse" | "disable") {
  if (selectedIds.size === 0) return;
  const actionLabel = { delete: "删除", reparse: "重新解析", disable: "停用" }[action];
  if (!confirm(`确定要${actionLabel}选中的 ${selectedIds.size} 个文档吗？`)) return;

  setBatchLoading(true);
  try {
    const result = await batchAction(Array.from(selectedIds), action);
    setFeedback({
      variant: result.failed.length > 0 ? "warning" : "success",
      title: `批量${actionLabel}完成`,
      message: `成功 ${result.summary.succeeded} 个，失败 ${result.summary.failed} 个`,
    });
    setSelectedIds(new Set());
    await loadData(searchTerm, pageNo);
    await loadStats();
  } catch (error) {
    setFeedback({
      variant: "error",
      title: `批量${actionLabel}失败`,
      message: error instanceof Error ? error.message : "请稍后重试。",
    });
  } finally {
    setBatchLoading(false);
  }
}
```

- [ ] **Step 3: 添加上传进度条**

1. 修改 `handleUploadSubmit` 使用带进度的上传：

```typescript
async function handleUploadSubmit() {
  if (!selectedFile) {
    setFeedback({ variant: "warning", title: "请选择文件", message: "请先选择要上传的文档。" });
    return;
  }
  setUploading(true);
  setUploadProgress(null);
  try {
    const upload = uploadLibraryDocumentWithProgress(selectedFile, uploadName, uploadLevel);
    upload.onProgress((progress) => setUploadProgress(progress));
    await upload.promise;
    setFeedback({ variant: "success", title: "上传成功", message: "文档已上传，文本提取任务已创建。" });
    setSelectedFile(null);
    setUploadName("");
    setIsUploadOpen(false);
    setUploadProgress(null);
    await loadData(searchTerm, 1);
    await loadStats();
  } catch (error) {
    setFeedback({
      variant: "error",
      title: "上传失败",
      message: error instanceof Error ? error.message : "请稍后重试。",
    });
  } finally {
    setUploading(false);
    setUploadProgress(null);
  }
}
```

2. 在上传对话框中添加进度条显示（在上传按钮附近）：

```tsx
{uploading && uploadProgress && (
  <div className="space-y-2">
    <div className="flex justify-between text-sm text-stone-gray">
      <span>上传中: {selectedFile?.name}</span>
      <span>{uploadProgress.percent}% ({formatFileSize(uploadProgress.loaded)}/{formatFileSize(uploadProgress.total)})</span>
    </div>
    <div className="w-full bg-border-cream rounded-full h-2">
      <div
        className="bg-terracotta h-2 rounded-full transition-all duration-300"
        style={{ width: `${uploadProgress.percent}%` }}
      />
    </div>
  </div>
)}
```

- [ ] **Step 4: 验证 TypeScript 编译**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/P15_Library.tsx
git commit -m "feat(frontend): add stats cards, batch selection, and upload progress to P15"
```

---

### Task 9: 后端测试基础设施 + 单元测试

**Files:**
- Create: `backend/app/tests/__init__.py`
- Create: `backend/app/tests/conftest.py`
- Create: `backend/app/tests/unit/__init__.py`
- Create: `backend/app/tests/unit/test_permission_service.py`
- Create: `backend/app/tests/unit/test_library_service.py`

- [ ] **Step 1: 创建测试目录结构**

```bash
mkdir -p backend/app/tests/unit backend/app/tests/integration
touch backend/app/tests/__init__.py backend/app/tests/unit/__init__.py backend/app/tests/integration/__init__.py
```

- [ ] **Step 2: 创建 conftest.py**

创建 `backend/app/tests/conftest.py`：

```python
"""测试配置：fixtures 和测试数据库。"""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# 使用 SQLite in-memory 作为测试数据库
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(engine):
    """每个测试一个独立的数据库 session，测试后回滚。"""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def test_user():
    """模拟当前用户。"""
    from app.schemas.auth import CurrentUserResponse, UserDTO

    user_id = str(uuid4())
    return CurrentUserResponse(
        user=UserDTO(
            userId=user_id,
            username="testuser",
            displayName="Test User",
            email="test@example.com",
            platformRole="user",
            securityLevel="internal",
            status="active",
        )
    )


@pytest.fixture()
def admin_user():
    """模拟管理员用户。"""
    from app.schemas.auth import CurrentUserResponse, UserDTO

    user_id = str(uuid4())
    return CurrentUserResponse(
        user=UserDTO(
            userId=user_id,
            username="admin",
            displayName="Admin User",
            email="admin@example.com",
            platformRole="admin",
            securityLevel="internal",
            status="active",
        )
    )
```

- [ ] **Step 3: 创建权限服务单元测试**

创建 `backend/app/tests/unit/test_permission_service.py`：

```python
"""权限服务单元测试。"""

from uuid import uuid4

import pytest

from app.services.permission_service import has_library_permission


class TestHasLibraryPermission:
    """测试 has_library_permission 函数。"""

    def test_admin_user_always_has_permission(self, db, admin_user):
        """管理员用户应拥有所有权限。"""
        result = has_library_permission(db, admin_user, "library.document.delete")
        assert result is True

    def test_admin_bypasses_owner_check(self, db, admin_user):
        """管理员不需要是文档 owner。"""
        random_owner_id = uuid4()
        result = has_library_permission(
            db, admin_user, "library.document.delete",
            document_owner_id=random_owner_id,
        )
        assert result is True

    def test_regular_user_read_own_document(self, db, test_user):
        """普通用户可以读取自己的文档。"""
        owner_id = uuid4()
        test_user.user.userId = str(owner_id)
        result = has_library_permission(
            db, test_user, "library.document.read",
            document_owner_id=owner_id,
        )
        assert result is True

    def test_regular_user_cannot_read_others_document(self, db, test_user):
        """普通用户不能读取他人的文档（无 admin 权限时）。"""
        result = has_library_permission(
            db, test_user, "library.document.read",
            document_owner_id=uuid4(),
        )
        # 在没有权限码数据的情况下应返回 False
        assert result is False

    def test_permission_denied_takes_precedence(self, db, test_user):
        """deny 应覆盖 allow。"""
        result = has_library_permission(db, test_user, "library.document.delete")
        assert result is False
```

- [ ] **Step 4: 创建 library 服务单元测试**

创建 `backend/app/tests/unit/test_library_service.py`：

```python
"""Library 服务单元测试。"""

from uuid import uuid4

import pytest

from app.services.library_service import (
    LibraryDocumentNotFoundError,
    LibraryPermissionError,
    _get_error_suggestion,
    batch_action,
)


class TestGetErrorSuggestion:
    """测试错误建议函数。"""

    def test_known_error_codes(self):
        assert "拆分" in _get_error_suggestion("PARSE_TIMEOUT")
        assert "格式" in _get_error_suggestion("UNSUPPORTED_FORMAT")
        assert "重新上传" in _get_error_suggestion("FILE_CORRUPTED")
        assert "稍后" in _get_error_suggestion("STORAGE_ERROR")

    def test_unknown_error_code(self):
        assert "管理员" in _get_error_suggestion("UNKNOWN")
        assert "管理员" in _get_error_suggestion("SOME_NEW_ERROR")


class TestBatchAction:
    """测试批量操作。"""

    def test_batch_action_with_invalid_ids(self, db, test_user):
        """无效 ID 应返回失败。"""
        result = batch_action(db, test_user, ["not-a-uuid"], "delete")
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "INVALID_ID"
        assert result["summary"]["total"] == 1
        assert result["summary"]["failed"] == 1

    def test_batch_action_with_nonexistent_docs(self, db, test_user):
        """不存在的文档应返回 NOT_FOUND。"""
        fake_id = str(uuid4())
        result = batch_action(db, test_user, [fake_id], "delete")
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "NOT_FOUND"
```

- [ ] **Step 5: 安装 pytest 依赖**

Run: `cd backend && conda run -n rag-lab pip install pytest --quiet`
Expected: 安装成功

- [ ] **Step 6: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit -v`
Expected: 所有测试 PASSED

- [ ] **Step 7: Commit**

```bash
git add backend/app/tests/
git commit -m "test(library): add unit tests for permission and library services"
```

---

### Task 10: 前端测试

**Files:**
- Create: `frontend/src/app/services/libraryService.test.ts`

- [ ] **Step 1: 创建 libraryService 测试**

创建 `frontend/src/app/services/libraryService.test.ts`：

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock apiClient
vi.mock("./apiClient", () => ({
  API_BASE_URL: "/api/v1",
  apiGet: vi.fn(),
  apiPostJson: vi.fn(),
  apiPostForm: vi.fn(),
  apiDelete: vi.fn(),
  apiPatchJson: vi.fn(),
  apiDownload: vi.fn(),
}));

import { apiGet, apiPostJson } from "./apiClient";
import { fetchLibraryStats, batchAction, fetchLibraryDocuments } from "./libraryService";

describe("libraryService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("fetchLibraryStats", () => {
    it("should call GET /library/documents/stats", async () => {
      const mockStats = { totalDocuments: 10, todayUploads: 2, pendingParse: 3 };
      vi.mocked(apiGet).mockResolvedValue(mockStats);

      const result = await fetchLibraryStats();

      expect(apiGet).toHaveBeenCalledWith("/library/documents/stats");
      expect(result).toEqual(mockStats);
    });
  });

  describe("batchAction", () => {
    it("should call POST /library/documents/batch-actions with correct body", async () => {
      const mockResponse = {
        succeeded: ["doc-1"],
        failed: [],
        summary: { total: 1, succeeded: 1, failed: 0 },
      };
      vi.mocked(apiPostJson).mockResolvedValue(mockResponse);

      const result = await batchAction(["doc-1"], "delete");

      expect(apiPostJson).toHaveBeenCalledWith("/library/documents/batch-actions", {
        documentIds: ["doc-1"],
        action: "delete",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("fetchLibraryDocuments", () => {
    it("should pass query parameters correctly", async () => {
      const mockPage = { items: [], pageNo: 1, pageSize: 20, total: 0 };
      vi.mocked(apiGet).mockResolvedValue(mockPage);

      await fetchLibraryDocuments({ keyword: "test", pageNo: 2, status: "active" });

      expect(apiGet).toHaveBeenCalledWith(
        expect.stringContaining("keyword=test"),
      );
      expect(apiGet).toHaveBeenCalledWith(
        expect.stringContaining("pageNo=2"),
      );
      expect(apiGet).toHaveBeenCalledWith(
        expect.stringContaining("status=active"),
      );
    });
  });
});
```

- [ ] **Step 2: 运行前端测试**

Run: `cd frontend && npm run test -- --run`
Expected: 所有测试 PASSED

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/services/libraryService.test.ts
git commit -m "test(frontend): add libraryService unit tests"
```

---

### Task 11: 验证脚本 + 最终验证

**Files:**
- Create: `backend/scripts/verify_sprint38.py`

- [ ] **Step 1: 创建综合验证脚本**

创建 `backend/scripts/verify_sprint38.py`：

```python
"""Sprint 38 综合验证脚本。"""

import sys

def check_imports():
    """验证所有新增模块可导入。"""
    from app.services.permission_service import has_library_permission
    from app.services.library_service import batch_action, get_library_stats, _get_error_suggestion
    from app.schemas.library import BatchActionRequest, BatchActionResponse, LibraryStatsResponse
    from app.api.routes.library import router
    print("  [OK] All imports successful")

def check_permission_function():
    """验证权限函数签名。"""
    from app.services.permission_service import has_library_permission
    import inspect
    sig = inspect.signature(has_library_permission)
    params = list(sig.parameters.keys())
    assert "session" in params, "Missing 'session' parameter"
    assert "current_user" in params, "Missing 'current_user' parameter"
    assert "permission_code" in params, "Missing 'permission_code' parameter"
    assert "document_owner_id" in params, "Missing 'document_owner_id' parameter"
    print("  [OK] has_library_permission signature correct")

def check_batch_function():
    """验证批量操作函数签名。"""
    from app.services.library_service import batch_action
    import inspect
    sig = inspect.signature(batch_action)
    params = list(sig.parameters.keys())
    assert "session" in params
    assert "current_user" in params
    assert "document_ids" in params
    assert "action" in params
    print("  [OK] batch_action signature correct")

def check_stats_function():
    """验证统计函数签名。"""
    from app.services.library_service import get_library_stats
    import inspect
    sig = inspect.signature(get_library_stats)
    params = list(sig.parameters.keys())
    assert "session" in params
    assert "current_user" in params
    print("  [OK] get_library_stats signature correct")

def check_schemas():
    """验证 DTO 定义。"""
    from app.schemas.library import BatchActionRequest, BatchActionResponse, LibraryStatsResponse
    # BatchActionRequest
    req = BatchActionRequest(documentIds=["a", "b"], action="delete")
    assert len(req.documentIds) == 2
    assert req.action == "delete"
    # LibraryStatsResponse
    stats = LibraryStatsResponse(totalDocuments=10, todayUploads=2, pendingParse=3)
    assert stats.totalDocuments == 10
    print("  [OK] Schemas validate correctly")

def check_routes():
    """验证路由注册。"""
    from app.api.routes.library import router
    paths = [route.path for route in router.routes]
    assert "/batch-actions" in paths, "Missing /batch-actions route"
    assert "/stats" in paths, "Missing /stats route"
    print("  [OK] Routes registered: /batch-actions, /stats")

def check_tables():
    """验证表定义。"""
    from app.tables import library_parse_jobs
    column_names = [col.name for col in library_parse_jobs.columns]
    assert "error_detail" in column_names, "Missing error_detail column"
    print("  [OK] library_parse_jobs has error_detail column")

def main():
    print("Sprint 38 Verification")
    print("=" * 40)
    checks = [
        ("Imports", check_imports),
        ("Permission function", check_permission_function),
        ("Batch function", check_batch_function),
        ("Stats function", check_stats_function),
        ("Schemas", check_schemas),
        ("Routes", check_routes),
        ("Tables", check_tables),
    ]
    passed = 0
    failed = 0
    for name, check in checks:
        try:
            print(f"\n--- {name} ---")
            check()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

    print("\n" + "=" * 40)
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("All checks passed!")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行验证脚本**

Run: `cd backend && conda run -n rag-lab python scripts/verify_sprint38.py`
Expected: `All checks passed!`

- [ ] **Step 3: 运行后端单元测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit -v`
Expected: 所有测试 PASSED

- [ ] **Step 4: 运行前端测试**

Run: `cd frontend && npm run test -- --run`
Expected: 所有测试 PASSED

- [ ] **Step 5: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 6: 运行前端 lint**

Run: `cd frontend && npm run lint`
Expected: 无错误

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/verify_sprint38.py
git commit -m "feat(library): add Sprint 38 verification script"
```

---

## Verification Commands

```bash
# 后端验证脚本
cd backend && conda run -n rag-lab python scripts/verify_sprint38.py

# 后端单元测试
cd backend && conda run -n rag-lab pytest app/tests/unit -v

# 前端测试
cd frontend && npm run test -- --run

# 前端构建
cd frontend && npm run build

# 前端 lint
cd frontend && npm run lint

# 文档空白检查
git diff --check
```
