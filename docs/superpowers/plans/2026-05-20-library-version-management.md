# 文档库版本管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add version management to the document library — upload new versions, view/switch/delete versions, and manage KB binding version switching.

**Architecture:** Extend the existing `document_versions` table with soft-delete columns. Add 4 new library service functions (upload/list/activate/delete version), 1 binding service function (switch binding version), fix 3 bugs in existing code, and restructure P16_LibraryDetail into a tabbed layout.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy Core, PostgreSQL, Alembic, Celery, React 18, TypeScript, Tailwind CSS, Radix UI Tabs

**Design Spec:** `docs/superpowers/specs/2026-05-20-library-version-management-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/migrations/versions/0022_library_version_management.py` | Create | Add deleted_at/deleted_by to document_versions, extend job_type CHECK |
| `backend/app/tables.py:311-333` | Modify | Add deleted_at/deleted_by columns to document_versions |
| `backend/app/schemas/library.py` | Modify | Add LibraryVersionUploadResponse, LibraryVersionActivateRequest/Response; enrich LibraryDocumentVersionDTO with fileName/fileSize |
| `backend/app/schemas/binding.py` | Modify | Add SwitchBindingVersionRequest |
| `backend/app/services/library_service.py` | Modify | Add upload_library_version, list_library_versions, activate_library_version, delete_library_version; fix retry_library_parse and get_document_text |
| `backend/app/services/binding_service.py` | Modify | Add switch_binding_version |
| `backend/app/services/document_service.py:645-662` | Modify | Fix ingest pipeline to use library_version_id from metadata |
| `backend/app/api/routes/library.py` | Modify | Add 4 new endpoints for version management |
| `backend/app/api/routes/bindings.py` | Modify | Add switch-version endpoint |
| `frontend/src/app/types/library.ts` | Modify | Add fileName/fileSize to LibraryDocumentVersionDTO; add new response types |
| `frontend/src/app/services/libraryService.ts` | Modify | Add 5 new API functions |
| `frontend/src/app/pages/P16_LibraryDetail.tsx` | Rewrite | Restructure into Tabs layout with Versions, Parse Jobs, KB Bindings tabs |

---

## Task 1: Migration — Add soft-delete to document_versions

**Files:**
- Create: `backend/migrations/versions/0022_library_version_management.py`
- Modify: `backend/app/tables.py:311-333`

- [ ] **Step 1: Create migration file**

```python
# backend/migrations/versions/0022_library_version_management.py
"""library version management

Revision ID: 0022_library_version_mgmt
Revises: 0021_documents_library_id
Create Date: 2026-05-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0022_library_version_mgmt"
down_revision: str | None = "0021_documents_library_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. document_versions 新增软删除列
    op.add_column(
        "document_versions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. 部分索引：加速查询未删除版本
    op.create_index(
        "idx_document_versions_document_not_deleted",
        "document_versions",
        ["document_id", "deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 3. 扩展 library_parse_jobs.job_type CHECK 约束
    op.drop_constraint("ck_library_parse_jobs_job_type", "library_parse_jobs", type_="check")
    op.create_check_constraint(
        "ck_library_parse_jobs_job_type",
        "library_parse_jobs",
        "job_type IN ('extract_text', 'generate_preview', 'reparse_library', 'upload_version')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_library_parse_jobs_job_type", "library_parse_jobs", type_="check")
    op.create_check_constraint(
        "ck_library_parse_jobs_job_type",
        "library_parse_jobs",
        "job_type IN ('extract_text', 'generate_preview', 'reparse_library')",
    )
    op.drop_index("idx_document_versions_document_not_deleted", table_name="document_versions")
    op.drop_column("document_versions", "deleted_by")
    op.drop_column("document_versions", "deleted_at")
```

- [ ] **Step 2: Update table definition**

In `backend/app/tables.py`, add two columns to the `document_versions` table definition after line 332 (before the closing parenthesis):

```python
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
```

- [ ] **Step 3: Run migration**

```bash
cd backend && python -m alembic upgrade head
```

Expected: Migration applies successfully, `document_versions` table now has `deleted_at` and `deleted_by` columns.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0022_library_version_management.py backend/app/tables.py
git commit -m "feat(migration): add soft-delete columns to document_versions for version management"
```

---

## Task 2: Pydantic Schemas — New DTOs and enriched types

**Files:**
- Modify: `backend/app/schemas/library.py`
- Modify: `backend/app/schemas/binding.py`

- [ ] **Step 1: Enrich LibraryDocumentVersionDTO**

In `backend/app/schemas/library.py`, update `LibraryDocumentVersionDTO` to add `fileName` and `fileSize`:

```python
class LibraryDocumentVersionDTO(BaseModel):
    """文档库版本 DTO，精简为文本提取状态。"""

    versionId: str
    documentId: str
    versionNo: int
    sourceFileId: str
    fileName: str | None = None
    fileSize: int | None = None
    status: str
    parseStatus: str
    chunkCount: int
    tokenCount: int | None
    createdAt: str
    updatedAt: str
```

- [ ] **Step 2: Add new request/response schemas**

Add these new classes at the end of `backend/app/schemas/library.py`:

```python
class LibraryVersionUploadResponse(BaseModel):
    """上传新版本成功响应。"""
    version: LibraryDocumentVersionDTO
    parseJob: LibraryParseJobDTO
    storedFile: LibraryStoredFileDTO


class LibraryVersionActivateRequest(BaseModel):
    """切换活跃版本请求。"""
    confirmImpact: bool = False


class LibraryVersionActivateResponse(BaseModel):
    """切换活跃版本响应。"""
    documentId: str
    activeVersionId: str
    previousActiveVersionId: str | None
```

- [ ] **Step 3: Add SwitchBindingVersionRequest**

In `backend/app/schemas/binding.py`, add:

```python
class SwitchBindingVersionRequest(BaseModel):
    """切换绑定版本请求。"""
    libraryVersionId: str
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/library.py backend/app/schemas/binding.py
git commit -m "feat(schema): add version management DTOs for library and binding"
```

---

## Task 3: Library Service — Version management functions

**Files:**
- Modify: `backend/app/services/library_service.py`

- [ ] **Step 1: Add VersionNotFoundError and VersionInUseError**

Add after the existing exception classes (around line 45):

```python
class LibraryVersionNotFoundError(Exception):
    """版本不存在或不属于当前文档。"""


class LibraryVersionInUseError(Exception):
    """版本正在被知识库绑定引用，无法删除。"""

    def __init__(self, kb_names: list[str]) -> None:
        self.kb_names = kb_names
        super().__init__(f"Version is in use by KBs: {', '.join(kb_names)}")
```

- [ ] **Step 2: Update _to_version_dto to include fileName/fileSize**

Replace the existing `_to_version_dto` function (line 66-78) with:

```python
def _to_version_dto(row: RowMapping, file_name: str | None = None, file_size: int | None = None) -> LibraryDocumentVersionDTO:
    return LibraryDocumentVersionDTO(
        versionId=str(row["version_id"]),
        documentId=str(row["document_id"]),
        versionNo=row["version_no"],
        sourceFileId=str(row["source_file_id"]),
        fileName=file_name,
        fileSize=file_size,
        status=row["status"],
        parseStatus=row["parse_status"],
        chunkCount=row["chunk_count"],
        tokenCount=row["token_count"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )
```

- [ ] **Step 3: Add list_library_versions function**

Add after the `get_document_usage` function:

```python
def list_library_versions(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> list[LibraryDocumentVersionDTO]:
    """列出文档的所有版本（不含已删除）。"""
    _ensure_owner(session, current_user, document_id)

    rows = session.execute(
        select(
            document_versions,
            stored_files.c.file_name,
            stored_files.c.file_size,
        )
        .join(stored_files, stored_files.c.file_id == document_versions.c.source_file_id)
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
        .order_by(document_versions.c.version_no.desc())
    ).mappings().all()

    return [_to_version_dto(row, file_name=row["file_name"], file_size=row["file_size"]) for row in rows]
```

- [ ] **Step 4: Add upload_library_version function**

Add after `list_library_versions`:

```python
def upload_library_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    storage_provider: ObjectStorageProvider | None = None,
) -> LibraryVersionUploadResponse:
    """上传新版本文件到已有文档。"""
    doc_row = _ensure_owner(session, current_user, document_id, "library.document.update")
    actor_id = UUID(current_user.user.userId)
    normalized_file_name = _safe_file_name(file_name)
    checksum = sha256(file_bytes).hexdigest()

    # 查询当前最大 version_no
    max_version_no = session.execute(
        select(func.max(document_versions.c.version_no))
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
    ).scalar() or 0

    next_version_no = max_version_no + 1
    version_id = uuid4()
    file_id = uuid4()
    job_id = uuid4()

    # 存储文件
    storage = storage_provider or get_object_storage_provider()
    owner_id = str(doc_row["owner_id"]) if doc_row.get("owner_id") else str(actor_id)
    object_key = f"users/{owner_id}/library/{document_id}/{normalized_file_name}"
    storage.put_object(object_key, file_bytes, mime_type or "application/octet-stream")

    # 创建 stored_files 行
    session.execute(
        insert(stored_files).values(
            file_id=file_id,
            bucket=get_settings().storage_bucket,
            object_key=object_key,
            file_name=normalized_file_name,
            mime_type=mime_type,
            file_size=len(file_bytes),
            checksum=checksum,
            file_role="source",
            status="active",
            created_by=actor_id,
            updated_by=actor_id,
        )
    )

    # 创建 document_versions 行（不自动激活）
    session.execute(
        insert(document_versions).values(
            version_id=version_id,
            document_id=document_id,
            version_no=next_version_no,
            source_file_id=file_id,
            status="processing",
            parse_status="pending",
            dense_index_status="not_required",
            sparse_index_status="not_required",
            graph_index_status="not_required",
            retrieval_ready=False,
            chunk_count=0,
            metadata={},
            created_by=actor_id,
            updated_by=actor_id,
        )
    )

    # 创建解析任务
    session.execute(
        insert(library_parse_jobs).values(
            job_id=job_id,
            document_id=document_id,
            version_id=version_id,
            job_type="upload_version",
            status="queued",
            progress=0,
            created_by=actor_id,
        )
    )

    session.commit()

    # 触发 Celery
    from app.worker import run_library_parse_task
    run_library_parse_task.delay(str(job_id))

    # 构造响应
    ver_dto = LibraryDocumentVersionDTO(
        versionId=str(version_id),
        documentId=str(document_id),
        versionNo=next_version_no,
        sourceFileId=str(file_id),
        fileName=normalized_file_name,
        fileSize=len(file_bytes),
        status="processing",
        parseStatus="pending",
        chunkCount=0,
        tokenCount=None,
        createdAt=session.execute(select(func.now())).scalar().isoformat(),
        updatedAt=session.execute(select(func.now())).scalar().isoformat(),
    )
    parse_job_dto = LibraryParseJobDTO(
        jobId=str(job_id),
        documentId=str(document_id),
        versionId=str(version_id),
        jobType="upload_version",
        status="queued",
        progress=0,
        errorCode=None,
        errorMessage=None,
        createdAt=session.execute(select(func.now())).scalar().isoformat(),
    )
    stored_file_dto = LibraryStoredFileDTO(
        fileId=str(file_id),
        fileName=normalized_file_name,
        mimeType=mime_type,
        fileSize=len(file_bytes),
        checksum=checksum,
        objectKey=object_key,
    )

    return LibraryVersionUploadResponse(
        version=ver_dto,
        parseJob=parse_job_dto,
        storedFile=stored_file_dto,
    )
```

- [ ] **Step 5: Add activate_library_version function**

```python
def activate_library_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    version_id: UUID,
    confirm_impact: bool = False,
) -> LibraryVersionActivateResponse:
    """切换文档的活跃版本。"""
    _ensure_owner(session, current_user, document_id, "library.document.update")

    if not confirm_impact:
        raise LibraryPermissionError("CONFIRM_REQUIRED: Set confirmImpact=true to proceed.")

    # 校验目标版本
    ver_row = session.execute(
        select(document_versions).where(
            document_versions.c.version_id == version_id,
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    if ver_row is None:
        raise LibraryVersionNotFoundError
    if ver_row["parse_status"] != "success":
        raise LibraryPermissionError("VERSION_NOT_READY: Version must be successfully parsed before activation.")

    # 获取当前活跃版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    previous_active_id = str(doc_row["active_version_id"]) if doc_row and doc_row["active_version_id"] else None

    # 将所有版本设为 inactive
    session.execute(
        update(document_versions)
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
        .values(status="inactive", updated_at=func.now())
    )

    # 目标版本设为 active
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_id)
        .values(status="active", updated_at=func.now())
    )

    # 更新 documents.active_version_id
    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(active_version_id=version_id, updated_at=func.now())
    )

    session.commit()

    return LibraryVersionActivateResponse(
        documentId=str(document_id),
        activeVersionId=str(version_id),
        previousActiveVersionId=previous_active_id,
    )
```

- [ ] **Step 6: Add delete_library_version function**

```python
def delete_library_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    version_id: UUID,
) -> dict:
    """删除指定版本（软删除）。不能删除活跃版本或被 KB 绑定引用的版本。"""
    _ensure_owner(session, current_user, document_id, "library.document.update")
    actor_id = UUID(current_user.user.userId)

    # 校验版本存在
    ver_row = session.execute(
        select(document_versions).where(
            document_versions.c.version_id == version_id,
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    if ver_row is None:
        raise LibraryVersionNotFoundError

    # 不能删除活跃版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    if doc_row and str(doc_row["active_version_id"]) == str(version_id):
        raise LibraryPermissionError("VERSION_IS_ACTIVE: Cannot delete the active version. Switch to another version first.")

    # 检查是否有 KB 绑定引用此版本
    binding_rows = session.execute(
        select(
            document_kb_bindings.c.binding_id,
            knowledge_bases.c.name.label("kb_name"),
        )
        .join(knowledge_bases, knowledge_bases.c.kb_id == document_kb_bindings.c.kb_id)
        .where(
            document_kb_bindings.c.document_id == document_id,
            document_kb_bindings.c.version_id == version_id,
            document_kb_bindings.c.status.in_(["active", "processing", "pending"]),
        )
    ).mappings().all()

    if binding_rows:
        kb_names = [row["kb_name"] for row in binding_rows]
        raise LibraryVersionInUseError(kb_names)

    # 软删除版本
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_id)
        .values(
            status="archived",
            deleted_at=func.now(),
            deleted_by=actor_id,
            updated_at=func.now(),
            updated_by=actor_id,
        )
    )

    # 软删除关联的 stored_files
    session.execute(
        update(stored_files)
        .where(stored_files.c.file_id == ver_row["source_file_id"])
        .values(
            status="deleted",
            updated_at=func.now(),
            updated_by=actor_id,
        )
    )

    session.commit()

    return {"versionId": str(version_id), "status": "deleted"}
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/library_service.py
git commit -m "feat(library): add version upload, list, activate, and delete functions"
```

---

## Task 4: Library Service — Bug fixes for retry_library_parse and get_document_text

**Files:**
- Modify: `backend/app/services/library_service.py`

- [ ] **Step 1: Fix retry_library_parse to use active version**

Replace the version query in `retry_library_parse` (line 708-713). Change:

```python
    version_row = session.execute(
        select(document_versions)
        .where(document_versions.c.document_id == document_id)
        .order_by(document_versions.c.version_no.desc())
        .limit(1)
    ).mappings().first()
```

To:

```python
    # 使用活跃版本而非最新版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    if not doc_row or not doc_row["active_version_id"]:
        raise LibraryDocumentNotFoundError

    version_row = session.execute(
        select(document_versions)
        .where(
            document_versions.c.version_id == doc_row["active_version_id"],
            document_versions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
```

- [ ] **Step 2: Fix get_document_text to use active version**

Replace the version query in `get_document_text` (line 861-866). Change:

```python
    ver_row = session.execute(
        select(document_versions)
        .where(document_versions.c.document_id == document_id)
        .order_by(document_versions.c.version_no.desc())
        .limit(1)
    ).mappings().first()
```

To:

```python
    # 使用活跃版本而非最新版本
    doc_row = session.execute(
        select(documents.c.active_version_id).where(documents.c.document_id == document_id)
    ).mappings().first()
    if not doc_row or not doc_row["active_version_id"]:
        raise LibraryDocumentNotFoundError

    ver_row = session.execute(
        select(document_versions)
        .where(
            document_versions.c.version_id == doc_row["active_version_id"],
            document_versions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/library_service.py
git commit -m "fix(library): use active version instead of latest for retry and text preview"
```

---

## Task 5: Binding Service — switch_binding_version

**Files:**
- Modify: `backend/app/services/binding_service.py`

- [ ] **Step 1: Add VersionNotReadyError exception**

Add after the existing exception classes:

```python
class BindingVersionNotReadyError(Exception):
    """目标版本尚未解析完成。"""
```

- [ ] **Step 2: Add switch_binding_version function**

Add at the end of `binding_service.py`:

```python
def switch_binding_version(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
    target_library_version_id: UUID,
) -> LibraryBindingDTO:
    """切换 KB 绑定到不同的库文档版本。"""
    _ensure_kb_permission(session, current_user, kb_id)

    # 加载绑定行
    binding_row = session.execute(
        select(document_kb_bindings).where(
            document_kb_bindings.c.binding_id == binding_id,
            document_kb_bindings.c.kb_id == kb_id,
        ).limit(1)
    ).mappings().first()
    if binding_row is None:
        raise BindingNotFoundError

    # 验证用户拥有库文档
    lib_doc_id = binding_row["document_id"]
    lib_doc_row = _ensure_library_owner(session, current_user, lib_doc_id)
    doc_name = lib_doc_row["name"]

    # 验证目标库版本
    target_ver = session.execute(
        select(document_versions).where(
            document_versions.c.version_id == target_library_version_id,
            document_versions.c.document_id == lib_doc_id,
            document_versions.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    if target_ver is None:
        raise BindingDocumentNotFoundError(f"Library version {target_library_version_id} not found")
    if target_ver["parse_status"] != "success":
        raise BindingVersionNotReadyError

    # 获取 KB 侧文档 ID（通过当前绑定的 version_id 找到 KB 侧 document_id）
    current_kb_version = session.execute(
        select(document_versions.c.document_id).where(
            document_versions.c.version_id == binding_row["version_id"],
        )
    ).scalar()
    if current_kb_version is None:
        raise BindingNotFoundError

    kb_doc_id = current_kb_version
    actor_id = UUID(current_user.user.userId)

    # 查询 KB 侧文档当前最大 version_no
    max_kb_version_no = session.execute(
        select(func.max(document_versions.c.version_no))
        .where(document_versions.c.document_id == kb_doc_id)
    ).scalar() or 0

    # 创建 KB 侧新 document_versions 行
    new_kb_version_id = uuid4()
    session.execute(
        insert(document_versions).values(
            version_id=new_kb_version_id,
            document_id=kb_doc_id,
            version_no=max_kb_version_no + 1,
            source_file_id=target_ver["source_file_id"],
            status="processing",
            parse_status="pending",
            dense_index_status="pending",
            sparse_index_status="pending",
            graph_index_status="pending",
            retrieval_ready=False,
            chunk_count=0,
            metadata={
                "library_document_id": str(lib_doc_id),
                "library_version_id": str(target_library_version_id),
            },
            created_by=actor_id,
            updated_by=actor_id,
        )
    )

    # 更新绑定指向新 KB 版本
    session.execute(
        update(document_kb_bindings)
        .where(document_kb_bindings.c.binding_id == binding_id)
        .values(
            version_id=new_kb_version_id,
            status="processing",
            updated_at=func.now(),
            updated_by=actor_id,
        )
    )

    # 创建 ingest 任务
    job_id = uuid4()
    session.execute(
        insert(ingest_jobs).values(
            job_id=job_id,
            kb_id=kb_id,
            document_id=kb_doc_id,
            version_id=new_kb_version_id,
            job_type="reparse",
            status="queued",
            stage="queued",
            progress=0,
            result_summary={},
            created_by=actor_id,
        )
    )

    session.commit()

    # 触发 Celery
    try:
        from app.worker import run_document_ingest_task
        run_document_ingest_task.delay(str(job_id))
    except Exception:
        pass

    # 返回更新后的绑定 DTO
    updated_binding = session.execute(
        select(document_kb_bindings).where(document_kb_bindings.c.binding_id == binding_id)
    ).mappings().one()

    return _to_binding_dto(dict(updated_binding), doc_name=doc_name)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/binding_service.py
git commit -m "feat(binding): add switch_binding_version for KB version switching"
```

---

## Task 6: Fix ingest pipeline — library version定位

**Files:**
- Modify: `backend/app/services/document_service.py:645-662`

- [ ] **Step 1: Fix the library parsed_chunks reuse logic**

Replace lines 645-662 in `document_service.py`:

```python
        # Check if we can reuse parsed chunks from library
        parsed_chunks_from_library = None
        if document_row.get("source_type") == "library_bind":
            library_doc_id_str = (document_row.get("metadata") or {}).get("library_document_id")
            if library_doc_id_str:
                library_doc_id = UUID(library_doc_id_str)
                lib_version = session.execute(
                    select(document_versions)
                    .where(
                        document_versions.c.document_id == library_doc_id,
                        document_versions.c.deleted_at.is_(None),
                    )
                    .order_by(document_versions.c.version_no.desc())
                    .limit(1)
                ).mappings().first()
                if lib_version:
                    lib_meta = lib_version.get("metadata") or {}
                    if lib_meta.get("parsed_chunks"):
                        parsed_chunks_from_library = lib_meta["parsed_chunks"]
```

With:

```python
        # Check if we can reuse parsed chunks from library
        parsed_chunks_from_library = None
        if document_row.get("source_type") == "library_bind":
            version_meta = version_row.get("metadata") or {}
            library_version_id_str = version_meta.get("library_version_id")
            library_doc_id_str = version_meta.get("library_document_id") or (document_row.get("metadata") or {}).get("library_document_id")

            lib_version = None
            if library_version_id_str:
                # 优先使用指定的库版本（版本切换场景）
                lib_version = session.execute(
                    select(document_versions)
                    .where(
                        document_versions.c.version_id == UUID(library_version_id_str),
                        document_versions.c.deleted_at.is_(None),
                    )
                    .limit(1)
                ).mappings().first()
            elif library_doc_id_str:
                # 回退到取最新版本（兼容旧数据）
                library_doc_id = UUID(library_doc_id_str)
                lib_version = session.execute(
                    select(document_versions)
                    .where(
                        document_versions.c.document_id == library_doc_id,
                        document_versions.c.deleted_at.is_(None),
                    )
                    .order_by(document_versions.c.version_no.desc())
                    .limit(1)
                ).mappings().first()

            if lib_version:
                lib_meta = lib_version.get("metadata") or {}
                if lib_meta.get("parsed_chunks"):
                    parsed_chunks_from_library = lib_meta["parsed_chunks"]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/document_service.py
git commit -m "fix(ingest): use specific library_version_id for parsed_chunks reuse instead of always latest"
```

---

## Task 7: API Routes — New endpoints

**Files:**
- Modify: `backend/app/api/routes/library.py`
- Modify: `backend/app/api/routes/bindings.py`

- [ ] **Step 1: Add imports to library routes**

Update imports in `backend/app/api/routes/library.py` to include new schemas and service functions:

```python
from app.schemas.library import (
    BatchActionRequest,
    BatchActionResponse,
    LibraryDocumentDTO,
    LibraryDocumentDetailDTO,
    LibraryDocumentUpdateRequest,
    LibraryDocumentUploadResponse,
    LibraryFullTextResponse,
    LibraryParseJobDTO,
    LibraryParsedChunksResponse,
    LibraryStatsResponse,
    LibraryTextPreviewResponse,
    LibraryVersionActivateRequest,
    LibraryVersionActivateResponse,
    LibraryVersionUploadResponse,
)
from app.services.library_service import (
    LibraryDocumentNotFoundError,
    LibraryPermissionError,
    LibraryVersionInUseError,
    LibraryVersionNotFoundError,
    activate_library_version,
    batch_action,
    create_library_upload,
    delete_library_document,
    delete_library_version,
    get_document_text,
    get_document_usage,
    get_library_document_detail,
    get_library_document_source_download,
    get_library_parse_jobs,
    get_library_stats,
    list_library_documents,
    list_library_versions,
    retry_library_parse,
    update_library_document,
    upload_library_version,
)
```

- [ ] **Step 2: Add version error handling to _raise_library_error**

Update `_raise_library_error` in `library.py`:

```python
def _raise_library_error(exc: Exception) -> None:
    if isinstance(exc, LibraryPermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc) or "PERMISSION_DENIED") from exc
    if isinstance(exc, LibraryDocumentNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DOCUMENT_NOT_FOUND") from exc
    if isinstance(exc, LibraryVersionNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VERSION_NOT_FOUND") from exc
    if isinstance(exc, LibraryVersionInUseError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "VERSION_IN_USE", "kbNames": exc.kb_names},
        ) from exc
    if isinstance(exc, ObjectStorageError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STORAGE_ERROR: object storage operation failed.",
        ) from exc
    raise exc
```

- [ ] **Step 3: Add version endpoints to library routes**

Add these endpoints after the existing `get_document_text_route` endpoint:

```python
@router.get("/{document_id}/versions", response_model=list[LibraryDocumentVersionDTO])
def list_versions(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[LibraryDocumentVersionDTO]:
    """列出文档的所有版本。"""
    try:
        return list_library_versions(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("/{document_id}/versions", response_model=LibraryVersionUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_version(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    file: UploadFile = File(...),
) -> LibraryVersionUploadResponse:
    """上传新版本文件。"""
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="EMPTY_FILE")
    try:
        return upload_library_version(
            session=db,
            current_user=current_user,
            document_id=document_id,
            file_name=file.filename or "uploaded-document",
            mime_type=file.content_type,
            file_bytes=file_bytes,
        )
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.post("/{document_id}/versions/{version_id}/activate", response_model=LibraryVersionActivateResponse)
def activate_version(
    document_id: UUID,
    version_id: UUID,
    body: LibraryVersionActivateRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryVersionActivateResponse:
    """切换文档的活跃版本。"""
    try:
        return activate_library_version(db, current_user, document_id, version_id, body.confirmImpact)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable


@router.delete("/{document_id}/versions/{version_id}")
def delete_version(
    document_id: UUID,
    version_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """删除指定版本。"""
    try:
        return delete_library_version(db, current_user, document_id, version_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable
```

- [ ] **Step 4: Add switch-version endpoint to bindings routes**

Update imports in `backend/app/api/routes/bindings.py`:

```python
from app.schemas.binding import (
    LibraryBindRequest,
    LibraryBindResponse,
    LibraryBindingDTO,
    LibraryUnbindResponse,
    SwitchBindingVersionRequest,
)
from app.services.binding_service import (
    BindingAlreadyExistsError,
    BindingDocumentNotFoundError,
    BindingKBNotFoundError,
    BindingNotFoundError,
    BindingPermissionError,
    BindingVersionNotReadyError,
    bind_documents_to_kb,
    list_kb_bindings,
    retry_binding,
    switch_binding_version,
    unbind_document_from_kb,
)
```

Add error handling for the new exception in `_raise_binding_error`:

```python
    if isinstance(exc, BindingVersionNotReadyError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VERSION_NOT_READY",
        ) from exc
```

Add the new endpoint:

```python
@router.post("/{binding_id}/switch-version", response_model=LibraryBindingDTO)
def switch_version(
    kb_id: UUID,
    binding_id: UUID,
    body: SwitchBindingVersionRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryBindingDTO:
    """切换绑定到不同的库文档版本。"""
    try:
        return switch_binding_version(db, current_user, kb_id, binding_id, UUID(body.libraryVersionId))
    except Exception as exc:
        _raise_binding_error(exc)
        raise  # unreachable
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/library.py backend/app/api/routes/bindings.py
git commit -m "feat(api): add version management endpoints for library and binding"
```

---

## Task 8: Frontend Types and Service

**Files:**
- Modify: `frontend/src/app/types/library.ts`
- Modify: `frontend/src/app/services/libraryService.ts`

- [ ] **Step 1: Update TypeScript types**

In `frontend/src/app/types/library.ts`, add `fileName` and `fileSize` to `LibraryDocumentVersionDTO`:

```typescript
export interface LibraryDocumentVersionDTO {
  versionId: string;
  documentId: string;
  versionNo: number;
  sourceFileId: string;
  fileName?: string;
  fileSize?: number;
  status: string;
  parseStatus: "pending" | "running" | "success" | "failed";
  chunkCount: number;
  tokenCount: number | null;
  createdAt: string;
  updatedAt: string;
}
```

Add new types at the end of the file:

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

- [ ] **Step 2: Add new service functions**

In `frontend/src/app/services/libraryService.ts`, add imports for the new types and add these functions:

```typescript
import type {
  // ... existing imports ...
  LibraryVersionUploadResponse,
  LibraryVersionActivateResponse,
} from "../types/library";

// --- Version Management ---

export async function fetchLibraryVersions(
  documentId: string,
): Promise<LibraryDocumentVersionDTO[]> {
  return apiGet(`/library/documents/${documentId}/versions`);
}

export function uploadLibraryVersionWithProgress(
  documentId: string,
  file: File,
): UploadWithProgressResult {
  const body = new FormData();
  body.set("file", file);

  const xhr = new XMLHttpRequest();
  let progressCallback: ((progress: UploadProgress) => void) | null = null;

  const promise = new Promise<LibraryVersionUploadResponse>((resolve, reject) => {
    xhr.open("POST", `${API_BASE_URL}/library/documents/${documentId}/versions`);

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
        resolve(JSON.parse(xhr.responseText) as LibraryVersionUploadResponse);
      } else {
        let message = `上传失败: ${xhr.status}`;
        try {
          const errBody = JSON.parse(xhr.responseText);
          message = errBody.detail || errBody.message || message;
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

export async function activateLibraryVersion(
  documentId: string,
  versionId: string,
  confirmImpact: boolean = true,
): Promise<LibraryVersionActivateResponse> {
  return apiPostJson(`/library/documents/${documentId}/versions/${versionId}/activate`, { confirmImpact });
}

export async function deleteLibraryVersion(
  documentId: string,
  versionId: string,
): Promise<void> {
  return apiDelete(`/library/documents/${documentId}/versions/${versionId}`);
}

export async function switchBindingVersion(
  kbId: string,
  bindingId: string,
  libraryVersionId: string,
): Promise<{ bindingId: string; status: string }> {
  return apiPostJson(`/knowledge-bases/${kbId}/library-bindings/${bindingId}/switch-version`, { libraryVersionId });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/types/library.ts frontend/src/app/services/libraryService.ts
git commit -m "feat(frontend): add version management types and API functions"
```

---

## Task 9: Frontend Page — P16_LibraryDetail restructure

**Files:**
- Rewrite: `frontend/src/app/pages/P16_LibraryDetail.tsx`

- [ ] **Step 1: Rewrite P16_LibraryDetail with Tabs layout**

Replace the entire content of `frontend/src/app/pages/P16_LibraryDetail.tsx`:

```tsx
import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Download, FileText, RefreshCw, Trash2, Upload } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Alert } from "../components/rag/Alert";
import { PdfPreview } from "../components/rag/PdfPreview";
import { TextPreview } from "../components/rag/TextPreview";
import { DocxPreview } from "../components/rag/DocxPreview";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import {
  fetchLibraryDocumentDetail,
  downloadLibraryDocument,
  fetchLibraryParseJobs,
  fetchDocumentUsage,
  retryLibraryParse,
  fetchLibraryVersions,
  uploadLibraryVersionWithProgress,
  activateLibraryVersion,
  deleteLibraryVersion,
  switchBindingVersion,
} from "../services/libraryService";
import type {
  LibraryDocumentDetailDTO,
  LibraryParseJobDTO,
  LibraryDocumentUsageDTO,
  LibraryDocumentVersionDTO,
  UploadProgress,
} from "../types/library";

function getPreviewType(fileName: string): "pdf" | "markdown" | "text" | "docx" | "unsupported" {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "md" || ext === "markdown") return "markdown";
  if (ext === "txt") return "text";
  if (ext === "docx") return "docx";
  return "unsupported";
}

function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function parseStatusVariant(status: string): "success" | "error" | "running" | "queued" {
  if (status === "success") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "running";
  return "queued";
}

export function LibraryDetail() {
  const navigate = useNavigate();
  const { docId = "" } = useParams();
  const { confirm } = useConfirmDialog();

  const [detail, setDetail] = useState<LibraryDocumentDetailDTO | null>(null);
  const [versions, setVersions] = useState<LibraryDocumentVersionDTO[]>([]);
  const [parseJobs, setParseJobs] = useState<LibraryParseJobDTO[]>([]);
  const [usages, setUsages] = useState<LibraryDocumentUsageDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  // Version upload state
  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [uploading, setUploading] = useState(false);

  // KB version switch drawer
  const [switchDrawer, setSwitchDrawer] = useState<{ bindingId: string; kbId: string; kbName: string } | null>(null);
  const [switchVersions, setSwitchVersions] = useState<LibraryDocumentVersionDTO[]>([]);
  const [switchLoading, setSwitchLoading] = useState(false);

  async function loadData() {
    setLoading(true);
    try {
      const [detailData, versionsData, jobsData] = await Promise.all([
        fetchLibraryDocumentDetail(docId),
        fetchLibraryVersions(docId),
        fetchLibraryParseJobs(docId),
      ]);
      setDetail(detailData);
      setVersions(versionsData);
      setParseJobs(jobsData);
      void loadUsage();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务。",
      });
    } finally {
      setLoading(false);
    }
  }

  async function loadUsage() {
    try {
      const usageData = await fetchDocumentUsage(docId);
      setUsages(usageData.usages);
    } catch {
      // 使用情况加载失败不影响主页面
    }
  }

  async function handleRetry() {
    try {
      await retryLibraryParse(docId);
      setFeedback({ variant: "info", title: "重试已触发", message: "解析作业已重新排队，请稍后刷新。" });
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "重试失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleDownload() {
    if (!detail) return;
    try {
      const result = await downloadLibraryDocument(docId);
      const url = URL.createObjectURL(result.blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = result.fileName ?? detail.document.name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setFeedback({ variant: "error", title: "下载失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleVersionUpload() {
    if (!uploadFile) return;
    setUploading(true);
    setUploadProgress(null);
    try {
      const { promise, onProgress } = uploadLibraryVersionWithProgress(docId, uploadFile);
      onProgress(setUploadProgress);
      await promise;
      setFeedback({ variant: "success", title: "上传成功", message: `版本文件已上传，解析任务已创建。` });
      setShowUpload(false);
      setUploadFile(null);
      setUploadProgress(null);
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "上传失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setUploading(false);
    }
  }

  async function handleActivateVersion(versionId: string, versionNo: number) {
    const confirmed = await confirm({
      title: "切换版本",
      description: `确定要将文档的活跃版本切换到 v${versionNo} 吗？此操作不会影响已绑定的知识库。`,
      confirmLabel: "确认切换",
    });
    if (!confirmed) return;
    try {
      await activateLibraryVersion(docId, versionId);
      setFeedback({ variant: "success", title: "切换成功", message: `已切换到 v${versionNo}。` });
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "切换失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleDeleteVersion(versionId: string, versionNo: number) {
    const confirmed = await confirm({
      title: "删除版本",
      description: `确定要删除 v${versionNo} 吗？此操作不可撤销。`,
      confirmLabel: "确认删除",
      destructive: true,
    });
    if (!confirmed) return;
    try {
      await deleteLibraryVersion(docId, versionId);
      setFeedback({ variant: "success", title: "删除成功", message: `v${versionNo} 已删除。` });
      await loadData();
    } catch (error) {
      const msg = error instanceof Error ? error.message : "请稍后重试。";
      if (msg.includes("VERSION_IN_USE")) {
        setFeedback({ variant: "warning", title: "无法删除", message: "该版本正在被知识库绑定引用，请先在知识库中切换版本或解绑。" });
      } else if (msg.includes("VERSION_IS_ACTIVE")) {
        setFeedback({ variant: "warning", title: "无法删除", message: "不能删除当前活跃版本，请先切换到其他版本。" });
      } else {
        setFeedback({ variant: "error", title: "删除失败", message: msg });
      }
    }
  }

  async function openSwitchDrawer(bindingId: string, kbId: string, kbName: string) {
    setSwitchDrawer({ bindingId, kbId, kbName });
    setSwitchLoading(true);
    try {
      const vers = await fetchLibraryVersions(docId);
      setSwitchVersions(vers.filter((v) => v.parseStatus === "success"));
    } catch {
      setSwitchVersions([]);
    } finally {
      setSwitchLoading(false);
    }
  }

  async function handleSwitchBindingVersion(targetVersionId: string, versionNo: number) {
    if (!switchDrawer) return;
    const confirmed = await confirm({
      title: "切换绑定版本",
      description: `确定要将「${switchDrawer.kbName}」的绑定切换到 v${versionNo} 吗？知识库将重新解析该文档。`,
      confirmLabel: "确认切换",
    });
    if (!confirmed) return;
    try {
      await switchBindingVersion(switchDrawer.kbId, switchDrawer.bindingId, targetVersionId);
      setFeedback({ variant: "success", title: "切换成功", message: `绑定已切换到 v${versionNo}，知识库正在重新解析。` });
      setSwitchDrawer(null);
      await loadUsage();
    } catch (error) {
      setFeedback({ variant: "error", title: "切换失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  useEffect(() => {
    void loadData();
  }, [docId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-stone-gray">加载中...</span>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-stone-gray">文档不存在或无权访问</p>
        <Button variant="secondary" onClick={() => navigate("/library")}>返回文档库</Button>
      </div>
    );
  }

  const doc = detail.document;
  const activeVersion = detail.activeVersion;
  const previewType = getPreviewType(doc.name);

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title={doc.name}
        breadcrumbs={[
          { label: "文档库", href: "/library" },
          { label: doc.name },
        ]}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={() => void handleDownload()}>
              <Download className="w-4 h-4 mr-2" /> 下载
            </Button>
            <Button variant="secondary" onClick={() => void loadData()}>
              <RefreshCw className="w-4 h-4 mr-2" /> 刷新
            </Button>
          </div>
        }
      />

      <div className="flex-1 min-h-0 overflow-auto p-8 space-y-6">
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        {/* Summary cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="rounded-xl border border-border-cream bg-ivory p-4">
            <p className="text-xs text-stone-gray">活跃版本</p>
            <p className="mt-2 font-serif text-xl text-near-black">{activeVersion ? `v${activeVersion.versionNo}` : "无"}</p>
          </div>
          <div className="rounded-xl border border-border-cream bg-ivory p-4">
            <p className="text-xs text-stone-gray">版本总数</p>
            <p className="mt-2 font-serif text-xl text-near-black">{versions.length}</p>
          </div>
          <div className="rounded-xl border border-border-cream bg-ivory p-4">
            <p className="text-xs text-stone-gray">解析状态</p>
            <p className="mt-2 font-serif text-xl text-near-black">
              {activeVersion ? (
                <Badge variant={parseStatusVariant(activeVersion.parseStatus)}>{activeVersion.parseStatus}</Badge>
              ) : "无"}
            </p>
          </div>
        </div>

        <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
          <Tabs.List className="flex border-b border-border-cream gap-6 mb-6">
            <Tabs.Trigger value="overview" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              概览
            </Tabs.Trigger>
            <Tabs.Trigger value="versions" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              版本（{versions.length}）
            </Tabs.Trigger>
            <Tabs.Trigger value="jobs" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              解析任务（{parseJobs.length}）
            </Tabs.Trigger>
            <Tabs.Trigger value="bindings" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              KB 绑定（{usages.length}）
            </Tabs.Trigger>
          </Tabs.List>

          {/* Tab 1: Overview */}
          <Tabs.Content value="overview" className="flex-1 overflow-auto outline-none space-y-6">
            <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
              <h2 className="font-serif text-near-black mb-4">文档信息</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-stone-gray">状态：</span>
                  <StatusBadge
                    status={doc.status === "active" ? "active" : doc.status === "disabled" ? "inactive" : "draft"}
                    className="ml-2"
                  />
                </div>
                <div>
                  <span className="text-stone-gray">创建时间：</span>
                  <span className="text-near-black ml-2">{new Date(doc.createdAt).toLocaleString("zh-CN")}</span>
                </div>
              </div>
            </div>

            <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
              <h2 className="font-serif text-near-black mb-4">文档预览</h2>
              {previewType === "pdf" ? (
                <PdfPreview documentId={docId} fileName={doc.name} />
              ) : previewType === "docx" ? (
                <DocxPreview documentId={docId} />
              ) : previewType === "markdown" || previewType === "text" ? (
                activeVersion?.parseStatus === "success" ? (
                  <TextPreview documentId={docId} />
                ) : (
                  <div className="text-center py-12">
                    <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
                    <p className="text-stone-gray">
                      {activeVersion?.parseStatus === "failed" ? "文本提取失败，无法预览" : "文本提取中，请稍后刷新..."}
                    </p>
                    {activeVersion?.parseStatus === "failed" && (
                      <Button variant="secondary" className="mt-4" onClick={() => void handleRetry()}>
                        <RefreshCw className="w-4 h-4 mr-2" /> 重试解析
                      </Button>
                    )}
                  </div>
                )
              ) : (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
                  <p className="text-stone-gray">暂不支持此文件格式的在线预览</p>
                </div>
              )}
            </div>
          </Tabs.Content>

          {/* Tab 2: Versions */}
          <Tabs.Content value="versions" className="flex-1 overflow-auto outline-none">
            <div className="mb-4 flex justify-between items-center">
              <h2 className="font-serif text-near-black">版本列表</h2>
              <Button variant="primary" onClick={() => setShowUpload(true)}>
                <Upload className="w-4 h-4 mr-2" /> 上传新版本
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>版本</TableHead>
                  <TableHead>文件名</TableHead>
                  <TableHead>文件大小</TableHead>
                  <TableHead>解析状态</TableHead>
                  <TableHead>分块数</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {versions.map((v) => {
                  const isActive = v.versionId === doc.activeVersionId;
                  const canDelete = !isActive;
                  return (
                    <TableRow key={v.versionId}>
                      <TableCell mono>v{v.versionNo}</TableCell>
                      <TableCell>{v.fileName ?? "-"}</TableCell>
                      <TableCell>{formatFileSize(v.fileSize)}</TableCell>
                      <TableCell>
                        <Badge variant={parseStatusVariant(v.parseStatus)}>{v.parseStatus}</Badge>
                      </TableCell>
                      <TableCell>{v.chunkCount}</TableCell>
                      <TableCell>
                        {isActive ? (
                          <Badge variant="success">当前生效</Badge>
                        ) : (
                          <StatusBadge status={v.status === "active" ? "active" : "inactive"} />
                        )}
                      </TableCell>
                      <TableCell>{new Date(v.createdAt).toLocaleString("zh-CN")}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {!isActive && v.parseStatus === "success" && (
                            <Button variant="ghost" size="sm" onClick={() => void handleActivateVersion(v.versionId, v.versionNo)}>
                              切换
                            </Button>
                          )}
                          {canDelete && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handleDeleteVersion(v.versionId, v.versionNo)}
                              title="删除版本"
                            >
                              <Trash2 className="w-4 h-4 text-stone-gray hover:text-red-500" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            {/* Upload drawer */}
            {showUpload && (
              <Drawer title="上传新版本" onClose={() => { setShowUpload(false); setUploadFile(null); setUploadProgress(null); }}>
                <DrawerSection>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-stone-gray mb-2">选择文件</label>
                      <input
                        type="file"
                        accept=".txt,.md,.pdf,.docx"
                        onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                        className="block w-full text-sm text-stone-gray file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-terracotta/10 file:text-terracotta hover:file:bg-terracotta/20"
                      />
                    </div>
                    {uploadProgress && (
                      <div>
                        <div className="flex justify-between text-xs text-stone-gray mb-1">
                          <span>上传进度</span>
                          <span>{uploadProgress.percent}%</span>
                        </div>
                        <div className="w-full bg-border-cream rounded-full h-2">
                          <div className="bg-terracotta h-2 rounded-full transition-all" style={{ width: `${uploadProgress.percent}%` }} />
                        </div>
                      </div>
                    )}
                    <div className="flex gap-2 justify-end">
                      <Button variant="secondary" onClick={() => { setShowUpload(false); setUploadFile(null); setUploadProgress(null); }}>取消</Button>
                      <Button variant="primary" disabled={!uploadFile || uploading} onClick={() => void handleVersionUpload()}>
                        {uploading ? "上传中..." : "上传"}
                      </Button>
                    </div>
                  </div>
                </DrawerSection>
              </Drawer>
            )}
          </Tabs.Content>

          {/* Tab 3: Parse Jobs */}
          <Tabs.Content value="jobs" className="flex-1 overflow-auto outline-none">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务 ID</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>进度</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>错误信息</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {parseJobs.map((job) => (
                  <TableRow key={job.jobId}>
                    <TableCell mono className="text-xs">{job.jobId.slice(0, 8)}...</TableCell>
                    <TableCell>{job.jobType}</TableCell>
                    <TableCell><StatusBadge status={job.status === "success" ? "active" : job.status === "failed" ? "error" : job.status === "running" ? "running" : "queued"} /></TableCell>
                    <TableCell>{job.progress}%</TableCell>
                    <TableCell>{new Date(job.createdAt).toLocaleString("zh-CN")}</TableCell>
                    <TableCell className="text-red-500 text-xs">{job.errorMessage ?? "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Tabs.Content>

          {/* Tab 4: KB Bindings */}
          <Tabs.Content value="bindings" className="flex-1 overflow-auto outline-none">
            {usages.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-stone-gray">该文档尚未绑定到任何知识库</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>知识库</TableHead>
                    <TableHead>绑定状态</TableHead>
                    <TableHead>分块数</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usages.map((usage) => (
                    <TableRow key={usage.bindingId}>
                      <TableCell className="font-medium">{usage.kbName}</TableCell>
                      <TableCell>
                        <Badge variant={usage.status === "active" ? "success" : "default"}>{usage.status}</Badge>
                      </TableCell>
                      <TableCell>{usage.chunkCount}</TableCell>
                      <TableCell>{new Date(usage.createdAt).toLocaleString("zh-CN")}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" onClick={() => void openSwitchDrawer(usage.bindingId, usage.kbId, usage.kbName)}>
                          切换版本
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {/* Switch version drawer */}
            {switchDrawer && (
              <Drawer title={`切换版本 — ${switchDrawer.kbName}`} onClose={() => setSwitchDrawer(null)}>
                <DrawerSection>
                  {switchLoading ? (
                    <p className="text-stone-gray text-sm">加载中...</p>
                  ) : switchVersions.length === 0 ? (
                    <p className="text-stone-gray text-sm">没有可用的已解析版本</p>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm text-stone-gray">选择要绑定到的库版本：</p>
                      {switchVersions.map((v) => (
                        <div
                          key={v.versionId}
                          className="rounded-lg border border-border-cream bg-parchment p-4 flex items-center justify-between gap-4 cursor-pointer hover:border-terracotta transition-colors"
                          onClick={() => void handleSwitchBindingVersion(v.versionId, v.versionNo)}
                        >
                          <div>
                            <p className="font-medium text-near-black">v{v.versionNo}</p>
                            <p className="text-xs text-stone-gray mt-1">{v.fileName ?? "-"} | 分块数: {v.chunkCount}</p>
                          </div>
                          <Badge variant={parseStatusVariant(v.parseStatus)}>{v.parseStatus}</Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </DrawerSection>
              </Drawer>
            )}
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/P16_LibraryDetail.tsx
git commit -m "feat(frontend): restructure LibraryDetail page with Tabs for version management"
```

---

## Verification

After all tasks are complete, verify the full flow end-to-end:

1. **Upload library document** — create a new document in the library
2. **Upload new version** — on the detail page, go to Versions tab, click "上传新版本", upload a different file
3. **Verify version list** — both versions should appear with correct file names and parse status
4. **Switch active version** — click "切换" on the non-active version, confirm, verify it becomes active
5. **Delete version** — try to delete the now-inactive version (should succeed if no bindings)
6. **Bind to KB** — from P06, bind the library document to a KB
7. **Upload another version** — upload a third version in the library
8. **Verify KB unaffected** — the KB should still use the old version
9. **Switch binding version** — in P16's KB Bindings tab, click "切换版本", select the new version
10. **Verify re-ingest** — the KB should start re-processing with the new version's content
11. **Try deleting bound version** — should fail with VERSION_IN_USE error
