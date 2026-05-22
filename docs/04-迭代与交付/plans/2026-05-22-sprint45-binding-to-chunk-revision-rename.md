# Sprint 45: BindingRevision → ChunkRevision 重命名与 Rechunk 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `binding_revisions` 表重命名为 `chunk_revisions`，全量替换后端标识符，引入 `strategy`/`params` 字段支持多分块策略，并实现 rechunk API。

**Architecture:** PG 原生 RENAME 重命名表/列/FK/index，Python 代码全量 find-replace 标识符，ingest worker 从 ChunkRevision 读取分块策略，新增 rechunk job type 复用现有 ParseRevision 重新分块。

**Tech Stack:** PostgreSQL, SQLAlchemy Core, Alembic, FastAPI, Pydantic, Celery

---

## 文件清单

### 修改的文件

| 文件 | 职责变更 |
|------|----------|
| `backend/migrations/versions/0031_rename_binding_revisions_to_chunk_revisions.py` | 新建：DB 迁移 |
| `backend/app/tables.py` | 表名/列名重命名，删除 chunk_size/chunk_overlap |
| `backend/app/schemas/binding.py` | BindingRevisionDTO → ChunkRevisionDTO，字段重命名 |
| `backend/app/schemas/document.py` | bindingRevisionId → chunkRevisionId |
| `backend/app/schemas/qa_run.py` | bindingRevisionId → chunkRevisionId |
| `backend/app/services/binding_service.py` | 函数名/变量名/表引用全量替换，create_chunk_revision 加 strategy/params |
| `backend/app/services/document_service.py` | 函数名/变量名/表引用全量替换，run_ingest_job 读 strategy |
| `backend/app/services/qa_run_service.py` | 列引用/metadata key 全量替换 |
| `backend/app/services/cross_resource_permission.py` | 表引用/列引用替换 |
| `backend/app/services/chunk_payload.py` | metadata key 替换 |
| `backend/app/services/document_parsing.py` | 确认 parse_document() 签名（已有 chunk_size/chunk_overlap 参数） |
| `backend/app/routers/knowledge_base_router.py` | 新增 rechunk 端点 |
| `backend/scripts/migrate_binding_revisions.py` | 函数名/SQL 全量替换 |
| `backend/scripts/migrate_chunks.py` | 函数名/SQL 全量替换 |
| `backend/app/tests/unit/test_binding_lifecycle.py` | 函数名/断言全量替换 |
| `backend/app/tests/unit/test_document_lifecycle.py` | 变量名/断言替换 |
| `backend/app/tests/unit/test_deletion_impact_analysis.py` | blocking_reasons 文案替换 |
| `backend/app/tests/unit/test_cross_resource_permission.py` | 变量名替换 |
| `backend/app/tests/integration/test_lifecycle_integration.py` | 函数名/类名全量替换 |
| `backend/app/tests/integration/test_data_migration.py` | 表名/列名/类名全量替换 |

### 不修改的文件

- `backend/migrations/versions/0024_*.py`, `0025_*.py`, `0027_*.py` — 历史迁移不动，Alembic 通过依赖链自动处理

---

## Task 1: 数据库迁移脚本

**Files:**
- Create: `backend/migrations/versions/0031_rename_binding_revisions_to_chunk_revisions.py`

- [ ] **Step 1: 创建迁移脚本**

```python
"""rename binding_revisions to chunk_revisions

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Rename table
    op.rename_table("binding_revisions", "chunk_revisions")

    # 2. Rename PK column
    op.alter_column("chunk_revisions", "binding_revision_id", new_column_name="chunk_revision_id")

    # 3. Rename FK columns on other tables
    op.alter_column("chunks", "binding_revision_id", new_column_name="chunk_revision_id")
    op.alter_column("document_kb_bindings", "active_binding_revision_id", new_column_name="active_chunk_revision_id")

    # 4. Add strategy and params columns
    op.add_column("chunk_revisions", sa.Column("strategy", sa.String(32), nullable=False, server_default="fixed_size"))
    op.add_column("chunk_revisions", sa.Column("params", JSONB, nullable=False, server_default="{}"))

    # 5. Backfill params for existing records
    op.execute("UPDATE chunk_revisions SET params = '{\"chunk_size\": 900, \"chunk_overlap\": 120}'")

    # 6. Drop chunk_size/chunk_overlap from document_kb_bindings
    op.drop_column("document_kb_bindings", "chunk_size")
    op.drop_column("document_kb_bindings", "chunk_overlap")

    # 7. Rename FK constraints
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT pk_binding_revisions TO pk_chunk_revisions")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_binding_id TO fk_chunk_revisions_binding_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_knowledge_base_id TO fk_chunk_revisions_knowledge_base_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_document_id TO fk_chunk_revisions_document_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_document_version_id TO fk_chunk_revisions_document_version_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_parse_revision_id TO fk_chunk_revisions_parse_revision_id")
    op.execute("ALTER TABLE chunks RENAME CONSTRAINT fk_chunks_binding_revision_id TO fk_chunks_chunk_revision_id")
    op.execute("ALTER TABLE document_kb_bindings RENAME CONSTRAINT fk_document_kb_bindings_active_binding_revision_id TO fk_document_kb_bindings_active_chunk_revision_id")

    # 8. Rename indexes
    op.execute("ALTER INDEX ix_binding_revisions_binding_id RENAME TO ix_chunk_revisions_binding_id")
    op.execute("ALTER INDEX ix_binding_revisions_knowledge_base_id RENAME TO ix_chunk_revisions_knowledge_base_id")
    op.execute("ALTER INDEX ix_binding_revisions_status RENAME TO ix_chunk_revisions_status")
    op.execute("ALTER INDEX ix_chunks_binding_revision_id RENAME TO ix_chunks_chunk_revision_id")
    op.execute("ALTER INDEX ix_document_kb_bindings_active_binding_revision_id RENAME TO ix_document_kb_bindings_active_chunk_revision_id")


def downgrade() -> None:
    # Reverse all operations in reverse order
    op.execute("ALTER INDEX ix_document_kb_bindings_active_chunk_revision_id RENAME TO ix_document_kb_bindings_active_binding_revision_id")
    op.execute("ALTER INDEX ix_chunks_chunk_revision_id RENAME TO ix_chunks_binding_revision_id")
    op.execute("ALTER INDEX ix_chunk_revisions_status RENAME TO ix_binding_revisions_status")
    op.execute("ALTER INDEX ix_chunk_revisions_knowledge_base_id RENAME TO ix_binding_revisions_knowledge_base_id")
    op.execute("ALTER INDEX ix_chunk_revisions_binding_id RENAME TO ix_binding_revisions_binding_id")

    op.execute("ALTER TABLE document_kb_bindings RENAME CONSTRAINT fk_document_kb_bindings_active_chunk_revision_id TO fk_document_kb_bindings_active_binding_revision_id")
    op.execute("ALTER TABLE chunks RENAME CONSTRAINT fk_chunks_chunk_revision_id TO fk_chunks_binding_revision_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_parse_revision_id TO fk_binding_revisions_parse_revision_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_document_version_id TO fk_binding_revisions_document_version_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_document_id TO fk_binding_revisions_document_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_knowledge_base_id TO fk_binding_revisions_knowledge_base_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_binding_id TO fk_binding_revisions_binding_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT pk_chunk_revisions TO pk_binding_revisions")

    op.add_column("document_kb_bindings", sa.Column("chunk_size", sa.Integer, nullable=False, server_default="900"))
    op.add_column("document_kb_bindings", sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default="120"))

    op.drop_column("chunk_revisions", "params")
    op.drop_column("chunk_revisions", "strategy")

    op.alter_column("document_kb_bindings", "active_chunk_revision_id", new_column_name="active_binding_revision_id")
    op.alter_column("chunks", "chunk_revision_id", new_column_name="binding_revision_id")
    op.alter_column("chunk_revisions", "chunk_revision_id", new_column_name="binding_revision_id")
    op.rename_table("chunk_revisions", "binding_revisions")
```

- [ ] **Step 2: 验证迁移脚本语法**

Run: `cd backend && python -c "import alembic.config; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/versions/0031_rename_binding_revisions_to_chunk_revisions.py
git commit -m "feat: add migration 0031 - rename binding_revisions to chunk_revisions"
```

---

## Task 2: tables.py 标识符重命名

**Files:**
- Modify: `backend/app/tables.py`

- [ ] **Step 1: 重命名 binding_revisions 表定义**

在 `tables.py` 中执行以下替换（用 Edit 工具的 replace_all）：

| 旧 | 新 |
|---|---|
| `binding_revisions` | `chunk_revisions` |
| `binding_revision_id` | `chunk_revision_id` |
| `active_binding_revision_id` | `active_chunk_revision_id` |

同时删除 `document_kb_bindings` 表定义中的 `chunk_size` 和 `chunk_overlap` 列（约 line 280-281）。

- [ ] **Step 2: 验证编译**

Run: `cd backend && python -c "from app.tables import *; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/tables.py
git commit -m "refactor: rename binding_revisions to chunk_revisions in tables.py"
```

---

## Task 3: Schemas 标识符重命名

**Files:**
- Modify: `backend/app/schemas/binding.py`
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/schemas/qa_run.py`

- [ ] **Step 1: binding.py 全量替换**

替换内容：

| 旧 | 新 |
|---|---|
| `BindingRevisionDTO` | `ChunkRevisionDTO` |
| `activeBindingRevisionId` | `activeChunkRevisionId` |
| `bindingRevisionStatus` | `chunkRevisionStatus` |
| `bindingRevisionChunkCount` | `chunkRevisionChunkCount` |
| `bindingRevisionVersionId` | `chunkRevisionVersionId` |
| `bindingRevisionId` | `chunkRevisionId` |

- [ ] **Step 2: document.py 替换**

在 `ChunkDTO` 类中：`bindingRevisionId` → `chunkRevisionId`

- [ ] **Step 3: qa_run.py 替换**

在 `QARunEvidenceDTO` 类中：`bindingRevisionId` → `chunkRevisionId`

- [ ] **Step 4: 验证编译**

Run: `cd backend && python -c "from app.schemas.binding import *; from app.schemas.document import *; from app.schemas.qa_run import *; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/
git commit -m "refactor: rename bindingRevision to chunkRevision in schemas"
```

---

## Task 4: binding_service.py 全量替换与改造

**Files:**
- Modify: `backend/app/services/binding_service.py`

- [ ] **Step 1: 标识符全量替换**

用 Edit replace_all 执行：

| 旧 | 新 |
|---|---|
| `binding_revisions` (表引用) | `chunk_revisions` |
| `binding_revision_id` | `chunk_revision_id` |
| `active_binding_revision_id` | `active_chunk_revision_id` |
| `BindingRevisionDTO` | `ChunkRevisionDTO` |
| `activeBindingRevisionId` | `activeChunkRevisionId` |
| `bindingRevisionStatus` | `chunkRevisionStatus` |
| `bindingRevisionChunkCount` | `chunkRevisionChunkCount` |
| `bindingRevisionVersionId` | `chunkRevisionVersionId` |
| `bindingRevisionId` | `chunkRevisionId` |
| `create_binding_revision` | `create_chunk_revision` |
| `activate_binding_revision` | `activate_chunk_revision` |
| `fail_binding_revision` | `fail_chunk_revision` |
| `complete_binding_revision_build` | `complete_chunk_revision_build` |
| `_to_binding_revision_dto` | `_to_chunk_revision_dto` |
| `_attach_binding_revision_summary` | `_attach_chunk_revision_summary` |

- [ ] **Step 2: 改造 create_chunk_revision 签名**

在 `create_chunk_revision()` 函数（原 line 86）中新增参数：

```python
def create_chunk_revision(
    session,
    binding_id: str,
    knowledge_base_id: str,
    document_id: str,
    document_version_id: str,
    parse_revision_id: str,
    strategy: str = "fixed_size",
    params: dict | None = None,
    created_by: str | None = None,
) -> UUID:
```

在 INSERT 语句中加入 `strategy` 和 `params` 列：

```python
insert_values = {
    "chunk_revision_id": chunk_revision_id,
    "binding_id": binding_id,
    "knowledge_base_id": knowledge_base_id,
    "document_id": document_id,
    "document_version_id": document_version_id,
    "parse_revision_id": parse_revision_id,
    "strategy": strategy,
    "params": params or {},
    "status": "building",
    "created_at": datetime.utcnow(),
}
```

- [ ] **Step 3: 改造 bind_documents_to_kb 读取分块策略**

在 `bind_documents_to_kb()` 中（原约 line 338-343），从 KB metadata 读取策略并传给 `create_chunk_revision`：

```python
# 原：chunk_size = kb_metadata.get("chunk_size", 900)
# 新：
chunk_strategy = kb_metadata.get("chunk_strategy", "fixed_size")
chunk_params = kb_metadata.get("chunk_params", {
    "chunk_size": kb_metadata.get("chunk_size", 900),
    "chunk_overlap": kb_metadata.get("chunk_overlap", 120),
})
```

调用 `create_chunk_revision()` 时传入 `strategy=chunk_strategy, params=chunk_params`。

- [ ] **Step 4: 改造 switch_binding_version 传入策略**

在 `switch_binding_version()` 中，创建新 ChunkRevision 时传入 strategy/params（可以从原 ChunkRevision 继承，或从 KB metadata 读取）。

- [ ] **Step 5: 验证编译**

Run: `cd backend && python -c "from app.services.binding_service import *; print('OK')"`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/binding_service.py
git commit -m "refactor: rename binding_service to chunk_revision identifiers and add strategy/params"
```

---

## Task 5: document_service.py 全量替换与改造

**Files:**
- Modify: `backend/app/services/document_service.py`

- [ ] **Step 1: 标识符全量替换**

| 旧 | 新 |
|---|---|
| `binding_revisions` | `chunk_revisions` |
| `binding_revision_id` | `chunk_revision_id` |
| `active_binding_revision_id` | `active_chunk_revision_id` |
| `_read_active_binding_revision_id` | `_read_active_chunk_revision_id` |
| `_read_ingest_binding_revision` | `_read_ingest_chunk_revision` |
| `binding_revision_row` | `chunk_revision_row` |
| `complete_binding_revision_build` | `complete_chunk_revision_build` |
| `fail_binding_revision` | `fail_chunk_revision` |

注意：`binding_revision_id` 出现在变量名、列引用、字符串 key 中，全部替换。

- [ ] **Step 2: 改造 run_ingest_job 读取分块策略**

在 `run_ingest_job()` 中（原约 line 991），从 ChunkRevision 读取 strategy 和 params：

```python
chunk_revision_row = _read_ingest_chunk_revision(session, job_row, version_row)
# ...
chunk_strategy = chunk_revision_row.get("strategy", "fixed_size")
chunk_params = chunk_revision_row.get("params", {})
```

在调用 `parse_document()` 时（原约 line 1063）传入分块参数：

```python
if chunk_strategy == "fixed_size":
    parsed_document = parse_document(
        file_name,
        file_row["mime_type"] if file_row else None,
        source_bytes or b"",
        chunk_size=chunk_params.get("chunk_size", 900),
        chunk_overlap=chunk_params.get("chunk_overlap", 120),
    )
else:
    raise ValueError(f"Unsupported chunking strategy: {chunk_strategy}")
```

- [ ] **Step 3: 验证编译**

Run: `cd backend && python -c "from app.services.document_service import *; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/document_service.py
git commit -m "refactor: rename document_service to chunk_revision identifiers and read strategy from revision"
```

---

## Task 6: 其他 service 文件替换

**Files:**
- Modify: `backend/app/services/qa_run_service.py`
- Modify: `backend/app/services/cross_resource_permission.py`
- Modify: `backend/app/services/chunk_payload.py`

- [ ] **Step 1: qa_run_service.py 替换**

| 旧 | 新 |
|---|---|
| `chunks.c.binding_revision_id` | `chunks.c.chunk_revision_id` |
| `document_kb_bindings.c.active_binding_revision_id` | `document_kb_bindings.c.active_chunk_revision_id` |
| `"binding_revision_id"` (字符串 key) | `"chunk_revision_id"` |
| `"bindingRevisionId"` (camelCase key) | `"chunkRevisionId"` |
| `metadata.get("binding_revision_id")` | `metadata.get("chunk_revision_id")` |

- [ ] **Step 2: cross_resource_permission.py 替换**

| 旧 | 新 |
|---|---|
| `binding_revisions` (表引用) | `chunk_revisions` |
| `binding_revisions.c.binding_revision_id` | `chunk_revisions.c.chunk_revision_id` |

- [ ] **Step 3: chunk_payload.py 替换**

| 旧 | 新 |
|---|---|
| `chunk.get("binding_revision_id")` | `chunk.get("chunk_revision_id")` |
| `"bindingRevisionId"` | `"chunkRevisionId"` |

- [ ] **Step 4: 验证编译**

Run: `cd backend && python -c "from app.services.qa_run_service import *; from app.services.cross_resource_permission import *; from app.services.chunk_payload import *; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/qa_run_service.py backend/app/services/cross_resource_permission.py backend/app/services/chunk_payload.py
git commit -m "refactor: rename binding_revision identifiers in qa_run, permission and chunk_payload services"
```

---

## Task 7: 回填脚本替换

**Files:**
- Modify: `backend/scripts/migrate_binding_revisions.py`
- Modify: `backend/scripts/migrate_chunks.py`

- [ ] **Step 1: migrate_binding_revisions.py 全量替换**

| 旧 | 新 |
|---|---|
| `backfill_binding_revisions` | `backfill_chunk_revisions` |
| `link_active_binding_revisions` | `link_active_chunk_revisions` |
| `binding_revisions` (表名) | `chunk_revisions` |
| `binding_revision_id` (列名) | `chunk_revision_id` |
| `active_binding_revision_id` | `active_chunk_revision_id` |

同时在 backfill SQL 中加入 `strategy` 和 `params` 列的写入（默认值 `fixed_size` + `{}`）。

- [ ] **Step 2: migrate_chunks.py 全量替换**

| 旧 | 新 |
|---|---|
| `update_binding_revision_id` | `update_chunk_revision_id` |
| `binding_revisions` (表名) | `chunk_revisions` |
| `binding_revision_id` (列名) | `chunk_revision_id` |

- [ ] **Step 3: 验证语法**

Run: `cd backend && python -c "import scripts.migrate_binding_revisions; import scripts.migrate_chunks; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/
git commit -m "refactor: rename binding_revision identifiers in migration scripts"
```

---

## Task 8: 测试文件替换

**Files:**
- Modify: `backend/app/tests/unit/test_binding_lifecycle.py`
- Modify: `backend/app/tests/unit/test_document_lifecycle.py`
- Modify: `backend/app/tests/unit/test_deletion_impact_analysis.py`
- Modify: `backend/app/tests/unit/test_cross_resource_permission.py`
- Modify: `backend/app/tests/integration/test_lifecycle_integration.py`
- Modify: `backend/app/tests/integration/test_data_migration.py`

- [ ] **Step 1: test_binding_lifecycle.py 全量替换**

| 旧 | 新 |
|---|---|
| `create_binding_revision` | `create_chunk_revision` |
| `activate_binding_revision` | `activate_chunk_revision` |
| `fail_binding_revision` | `fail_chunk_revision` |
| `complete_binding_revision_build` | `complete_chunk_revision_build` |
| `_to_binding_revision_dto` | `_to_chunk_revision_dto` |
| `BindingRevisionDTO` | `ChunkRevisionDTO` |
| `activeBindingRevisionId` | `activeChunkRevisionId` |
| `bindingRevisionStatus` | `chunkRevisionStatus` |
| `bindingRevisionChunkCount` | `chunkRevisionChunkCount` |
| `bindingRevisionVersionId` | `chunkRevisionVersionId` |
| `test_create_binding_revision` | `test_create_chunk_revision` |
| `test_activate_binding_revision` | `test_activate_chunk_revision` |
| `test_activate_binding_revision_not_found` | `test_activate_chunk_revision_not_found` |
| `test_fail_binding_revision` | `test_fail_chunk_revision` |
| `test_complete_binding_revision_build` | `test_complete_chunk_revision_build` |
| `test_create_binding_revision_with_created_by` | `test_create_chunk_revision_with_created_by` |
| `test_to_binding_dto_exposes_active_revision_status` | `test_to_binding_dto_exposes_active_revision_status` (保持不变) |

- [ ] **Step 2: test_document_lifecycle.py 替换**

| 旧 | 新 |
|---|---|
| `binding_revision_id` | `chunk_revision_id` |
| `active_binding_revision_id` | `active_chunk_revision_id` |
| `retired_binding_revision_id` | `retired_chunk_revision_id` |
| `dto.bindingRevisionId` | `dto.chunkRevisionId` |
| `test_list_chunks_filters_active_binding_revision` | `test_list_chunks_filters_active_chunk_revision` |

- [ ] **Step 3: test_deletion_impact_analysis.py 替换**

替换断言中的文案 `"active BindingRevision"` → `"active ChunkRevision"`。

- [ ] **Step 4: test_cross_resource_permission.py 替换**

`binding_revision_id` → `chunk_revision_id`。

- [ ] **Step 5: test_lifecycle_integration.py 替换**

| 旧 | 新 |
|---|---|
| `create_binding_revision` | `create_chunk_revision` |
| `activate_binding_revision` | `activate_chunk_revision` |
| `fail_binding_revision` | `fail_chunk_revision` |
| `complete_binding_revision_build` | `complete_chunk_revision_build` |
| `test_create_binding_revision` | `test_create_chunk_revision` |
| `test_activate_binding_revision` | `test_activate_chunk_revision` |
| `test_fail_binding_revision` | `test_fail_chunk_revision` |
| `test_complete_binding_revision_build` | `test_complete_chunk_revision_build` |
| `TestBindingLifecycle` | `TestChunkRevisionLifecycle` |

- [ ] **Step 6: test_data_migration.py 替换**

| 旧 | 新 |
|---|---|
| `TestBindingRevisionsCreation` | `TestChunkRevisionsCreation` |
| `test_binding_revisions_creation` | `test_chunk_revisions_creation` |
| `binding_revisions` (表名) | `chunk_revisions` |
| `binding_revision_id` (列名) | `chunk_revision_id` |

- [ ] **Step 7: 运行全量测试**

Run: `cd backend && python -m pytest app/tests -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/tests/
git commit -m "test: rename binding_revision identifiers in all tests"
```

---

## Task 9: Rechunk API 端点

**Files:**
- Modify: `backend/app/routers/knowledge_base_router.py`
- Modify: `backend/app/services/binding_service.py`

- [ ] **Step 1: 在 binding_service.py 中新增 rechunk_document 函数**

```python
class RechunkStrategyError(Exception):
    pass


def rechunk_document(
    session,
    current_user: str,
    kb_id: str,
    document_id: str,
    strategy: str = "fixed_size",
    params: dict | None = None,
) -> dict:
    """对已绑定的文档用新策略重新分块。"""
    params = params or {}

    # 1. 校验 binding 存在
    binding_row = session.execute(
        sa.select(document_kb_bindings).where(
            document_kb_bindings.c.knowledge_base_id == kb_id,
            document_kb_bindings.c.document_id == document_id,
        )
    ).mappings().first()
    if not binding_row:
        raise BindingNotFoundError(f"Binding not found for kb={kb_id}, doc={document_id}")

    binding_id = binding_row["binding_id"]

    # 2. 校验无 building 状态的 ChunkRevision
    building = session.execute(
        sa.select(chunk_revisions).where(
            chunk_revisions.c.binding_id == str(binding_id),
            chunk_revisions.c.status == "building",
        )
    ).mappings().first()
    if building:
        raise BindingBuildInProgressError("A chunk revision is already building")

    # 3. 获取当前 active ChunkRevision 的 parse_revision_id
    active_rev_id = binding_row.get("active_chunk_revision_id")
    if not active_rev_id:
        raise BindingVersionNotReadyError("No active chunk revision")

    active_rev = session.execute(
        sa.select(chunk_revisions).where(
            chunk_revisions.c.chunk_revision_id == str(active_rev_id)
        )
    ).mappings().first()
    if not active_rev:
        raise BindingVersionNotReadyError("Active chunk revision not found")

    parse_revision_id = active_rev["parse_revision_id"]
    document_version_id = active_rev["document_version_id"]

    # 4. 创建新 ChunkRevision
    new_rev_id = create_chunk_revision(
        session,
        binding_id=str(binding_id),
        knowledge_base_id=kb_id,
        document_id=document_id,
        document_version_id=str(document_version_id),
        parse_revision_id=str(parse_revision_id),
        strategy=strategy,
        params=params,
        created_by=current_user,
    )

    # 5. 创建 rechunk ingest job
    from app.services.document_service import dispatch_ingest_job

    job_id = dispatch_ingest_job(
        session,
        document_id=document_id,
        version_id=str(document_version_id),
        job_type="rechunk",
        result_summary={"chunk_revision_id": str(new_rev_id)},
    )

    session.commit()

    return {
        "chunk_revision_id": str(new_rev_id),
        "job_id": str(job_id),
        "strategy": strategy,
        "params": params,
    }
```

- [ ] **Step 2: 在 knowledge_base_router.py 中新增 rechunk 端点**

```python
class RechunkRequest(BaseModel):
    strategy: str = "fixed_size"
    params: dict | None = None


@router.post("/{kb_id}/documents/{document_id}/rechunk")
def rechunk_document_endpoint(
    kb_id: str,
    document_id: str,
    body: RechunkRequest,
    current_user: str = Depends(get_current_user),
    session=Depends(get_session),
):
    from app.services.binding_service import rechunk_document

    result = rechunk_document(
        session,
        current_user=current_user,
        kb_id=kb_id,
        document_id=document_id,
        strategy=body.strategy,
        params=body.params,
    )
    return result
```

- [ ] **Step 3: 验证编译**

Run: `cd backend && python -c "from app.services.binding_service import rechunk_document; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/binding_service.py backend/app/routers/knowledge_base_router.py
git commit -m "feat: add rechunk API endpoint and rechunk_document service function"
```

---

## Task 10: Ingest Worker 支持 rechunk job type

**Files:**
- Modify: `backend/app/services/document_service.py`

- [ ] **Step 1: 在 run_ingest_job 中处理 rechunk 类型**

在 `run_ingest_job()` 的 job_type 分支中（原约 line 960-970），添加 rechunk 处理：

```python
if job_type == "rechunk":
    # rechunk 复用现有 ParseRevision，只重新分块
    chunk_revision_row = _read_ingest_chunk_revision(session, job_row, version_row)
    chunk_strategy = chunk_revision_row.get("strategy", "fixed_size")
    chunk_params = chunk_revision_row.get("params", {})
    # 继续走正常的分块流程（不重新解析）
```

确保 rechunk 类型跳过重新解析步骤，直接使用现有 ParseRevision 的 parsed_chunks。

- [ ] **Step 2: 验证编译**

Run: `cd backend && python -c "from app.services.document_service import run_ingest_job; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/document_service.py
git commit -m "feat: support rechunk job type in ingest worker"
```

---

## Task 11: 全量回归验证

- [ ] **Step 1: Python 编译检查**

Run: `cd backend && python -m compileall app`
Expected: No errors

- [ ] **Step 2: 全量测试**

Run: `cd backend && python -m pytest app/tests -v`
Expected: All tests pass

- [ ] **Step 3: 检查残留引用**

Run: `cd backend && grep -r "binding_revision" app/ scripts/ --include="*.py" | grep -v "__pycache__" | grep -v ".pyc"`
Expected: No results (除了注释和迁移历史文件)

- [ ] **Step 4: OpenAPI 导出**

Run: `cd backend && python scripts/export_openapi.py`
Expected: No errors

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: sprint 45 complete - binding_revision to chunk_revision rename with rechunk support"
```
