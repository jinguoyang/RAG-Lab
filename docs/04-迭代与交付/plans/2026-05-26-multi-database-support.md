# Multi-Database Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使项目支持 PostgreSQL 和 MySQL 双数据库，通过配置文件切换，遵循已有 Provider 接口模式，尽量减少方言特殊处理。

**Architecture:** 引入 `DialectAdapter` 接口（遵循 QARunProviders/ObjectStorageProvider 模式）封装数据库方言差异。UUID 列统一改为 `String(36)` 由代码生成，JSONB 统一改为 `sa.JSON()`。现有 32 个 PG 迁移保持不动，新增一个 PG 转换迁移 + MySQL 基线迁移。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x Core, Alembic, psycopg3, pymysql

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/core/db_types.py` | **Create** | DialectAdapter 接口 + PG/MySQL 实现 + 工厂函数 + `new_id()` |
| `backend/app/core/database.py` | **Modify** | Engine 创建增加方言适配（pool 参数等） |
| `backend/app/core/config.py` | **Modify** | 无需改动（database_url 已可配） |
| `backend/app/tables.py` | **Modify** | 221 处 UUID → String(36)，41 处 JSONB → JSON |
| `backend/app/services/*.py` (14 files) | **Modify** | `uuid4()` → `new_id()`，`UUID(x)` → 直接传字符串 |
| `backend/app/services/library_service.py` | **Modify** | 修复 2 处 PG 泄漏（`.astext`、`date_trunc`） |
| `backend/app/worker.py` | **Modify** | `UUID(job_id)` → 直接传字符串 |
| `backend/app/tests/conftest.py` | **Modify** | 移除 JSONB→JSON 编译映射（不再需要） |
| `backend/requirements.txt` | **Modify** | 添加 `pymysql` |
| `backend/.env.example` | **Modify** | 添加 MySQL URL 示例 |
| `backend/migrations/versions/0033_*.py` | **Create** | PG 转换迁移（UUID→VARCHAR, JSONB→JSON, 索引重建） |
| `backend/migrations/versions/0034_*.py` | **Create** | MySQL 基线迁移（使用通用类型） |

---

## Task 1: Create `db_types.py` — DialectAdapter Interface

**Files:**
- Create: `backend/app/core/db_types.py`

本任务创建方言适配层，遵循项目已有的 Provider 接口模式（参考 `qa_providers.py` 的 `QARunProviders` 和 `object_storage.py` 的 `ObjectStorageProvider`）。

- [ ] **Step 1: 创建 db_types.py**

```python
"""数据库方言适配层。

遵循项目 Provider 接口模式（参考 QARunProviders、ObjectStorageProvider），
封装 PostgreSQL / MySQL 的方言差异，使 tables.py 和 service 层无需感知底层数据库。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Protocol
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.engine import URL


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------

def new_id() -> str:
    """生成全局唯一 ID（UUID v4 字符串），替代各处 uuid4() 调用。"""
    return str(uuid4())


# ---------------------------------------------------------------------------
# DialectAdapter 接口
# ---------------------------------------------------------------------------

class DialectAdapter(Protocol):
    """数据库方言适配器接口。

    每个属性返回一个可直接用于 sa.Column() 的 SQLAlchemy 类型实例。
    tables.py 通过此接口获取列类型，不再直接引用 postgresql 模块。
    """

    @property
    def uuid_type(self) -> type[sa.types.TypeEngine]:
        """UUID / 主键列类型。"""
        ...

    @property
    def json_type(self) -> type[sa.types.TypeEngine]:
        """JSON 列类型。"""
        ...

    def json_default(self, value: str = "{}") -> sa.TextClause:
        """JSON 列的 server_default 值。"""
        ...

    def timestamp_default(self) -> sa.TextClause:
        """时间戳列的 server_default 值（如 now() / CURRENT_TIMESTAMP）。"""
        ...

    def supports_partial_index(self) -> bool:
        """是否支持带 WHERE 条件的部分索引。"""
        ...


# ---------------------------------------------------------------------------
# PostgreSQL 实现
# ---------------------------------------------------------------------------

class PostgresAdapter:
    """PostgreSQL 方言适配器。"""

    @property
    def uuid_type(self) -> type[sa.types.TypeEngine]:
        return sa.String(36)

    @property
    def json_type(self) -> type[sa.types.TypeEngine]:
        return sa.JSON

    def json_default(self, value: str = "{}") -> sa.TextClause:
        return sa.text(f"'{value}'")

    def timestamp_default(self) -> sa.TextClause:
        return sa.text("now()")

    def supports_partial_index(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# MySQL 实现
# ---------------------------------------------------------------------------

class MySqlAdapter:
    """MySQL 方言适配器。"""

    @property
    def uuid_type(self) -> type[sa.types.TypeEngine]:
        return sa.String(36)

    @property
    def json_type(self) -> type[sa.types.TypeEngine]:
        return sa.JSON

    def json_default(self, value: str = "{}") -> sa.TextClause:
        # MySQL JSON 列不支持 server_default，需在应用层处理
        return sa.text("NULL")

    def timestamp_default(self) -> sa.TextClause:
        return sa.text("CURRENT_TIMESTAMP")

    def supports_partial_index(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_dialect_adapter(database_url: str | None = None) -> DialectAdapter:
    """根据数据库 URL 返回对应的方言适配器。"""
    if database_url is None:
        from app.core.config import get_settings
        database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("Database URL is required.")

    url = sa.engine.url.make_url(database_url)
    drivername = url.drivername.lower()

    if "mysql" in drivername or "pymysql" in drivername:
        return MySqlAdapter()
    # 默认 PostgreSQL
    return PostgresAdapter()
```

- [ ] **Step 2: 验证 db_types.py 可导入**

Run: `cd backend && python -c "from app.core.db_types import new_id, get_dialectAdapter; print(new_id())"`
Expected: 打印一个 UUID 字符串

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/db_types.py
git commit -m "feat: add DialectAdapter interface for multi-database support"
```

---

## Task 2: Update `tables.py` — UUID + JSON 通用化

**Files:**
- Modify: `backend/app/tables.py` (221 处 UUID + 41 处 JSONB)

将所有 `postgresql.UUID(as_uuid=True)` 替换为 `sa.String(36)`，所有 `postgresql.JSONB()` 替换为 `sa.JSON()`，所有 `server_default=sa.text("'{}'::jsonb")` 替换为 `server_default=sa.text("'{}'")`。同时移除 `from sqlalchemy.dialects import postgresql` 导入。

- [ ] **Step 1: 替换 tables.py 中的类型**

将文件开头的：
```python
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
```

替换为：
```python
import sqlalchemy as sa
```

将所有 `postgresql.UUID(as_uuid=True)` 替换为 `sa.String(36)`：
```python
# 旧
sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True)
# 新
sa.Column("user_id", sa.String(36), primary_key=True)
```

将所有 `postgresql.JSONB()` 替换为 `sa.JSON()`：
```python
# 旧
sa.Column("extra", postgresql.JSONB(), nullable=False)
# 新
sa.Column("extra", sa.JSON(), nullable=False)
```

将所有 `server_default=sa.text("'{}'::jsonb")` 替换为 `server_default=sa.text("'{}'")`：
```python
# 旧
server_default=sa.text("'{}'::jsonb")
# 新
server_default=sa.text("'{}'")
```

- [ ] **Step 2: 验证 tables.py 可导入**

Run: `cd backend && python -c "from app.tables import metadata; print(len(metadata.tables))"`
Expected: 打印表数量（约 39）

- [ ] **Step 3: 验证测试仍通过**

Run: `cd backend && python -m pytest app/tests/ -x -q`
Expected: 所有测试通过

- [ ] **Step 4: Commit**

```bash
git add backend/app/tables.py
git commit -m "refactor: replace postgresql.UUID/JSONB with generic sa.String(36)/sa.JSON"
```

---

## Task 3: Update Service Layer — `uuid4()` → `new_id()`

**Files:**
- Modify: 14 service files (75 处 `uuid4()` 调用)
- Modify: `backend/app/worker.py`

将所有 `from uuid import UUID, uuid4` 改为 `from uuid import UUID` + `from app.core.db_types import new_id`，将 `uuid4()` 替换为 `new_id()`。

由于 `new_id()` 返回 `str`，而 `sa.String(36)` 列接受 `str`，因此 `UUID(string)` 转换也可以移除——直接传字符串即可。

**注意：** `UUID()` 构造函数在某些地方用于类型注解和 Pydantic schema 校验，这些保留不动。只移除作为值传递给 SQLAlchemy 的 `UUID()` 调用。

- [ ] **Step 3a: 修改 audit_service.py**

将：
```python
from uuid import UUID, uuid4
```
改为：
```python
from uuid import UUID

from app.core.db_types import new_id
```

将 `uuid4()` 替换为 `new_id()`（1 处，line 25）。

将 `UUID(current_user.user.userId)` 替换为 `current_user.user.userId`（1 处，line 29）。

- [ ] **Step 3b: 修改 user_group_service.py**

同样模式：替换 `uuid4()` → `new_id()`（3 处），移除 `UUID()` 值转换（~1 处）。

- [ ] **Step 3c: 修改 dictionary_service.py**

同样模式：替换 `uuid4()` → `new_id()`（1 处），移除 `UUID()` 值转换（~1 处）。

- [ ] **Step 3d: 修改 governance_service.py**

同样模式：替换 `uuid4()` → `new_id()`（1 处），移除 `UUID()` 值转换（~2 处）。

- [ ] **Step 3e: 修改 config_service.py**

同样模式：替换 `uuid4()` → `new_id()`（2 处），移除 `UUID()` 值转换（~4 处）。

- [ ] **Step 3f: 修改 knowledge_base_service.py**

同样模式：替换 `uuid4()` → `new_id()`（4 处），移除 `UUID()` 值转换（~10 处）。

- [ ] **Step 3g: 修改 library_management_service.py**

同样模式：替换 `uuid4()` → `new_id()`（2 处），移除 `UUID()` 值转换（~8 处）。

- [ ] **Step 3h: 修改 rag_app_service.py**

同样模式：替换 `uuid4()` → `new_id()`（3 处），移除 `UUID()` 值转换（~5 处）。

- [ ] **Step 3i: 修改 binding_service.py**

同样模式：替换 `uuid4()` → `new_id()`（11 处），移除 `UUID()` 值转换（~13 处）。

- [ ] **Step 3j: 修改 document_service.py**

同样模式：替换 `uuid4()` → `new_id()`（~14 处），移除 `UUID()` 值转换（~30 处）。

- [ ] **Step 3k: 修改 library_service.py**

同样模式：替换 `uuid4()` → `new_id()`（~8 处），移除 `UUID()` 值转换（~15 处）。

- [ ] **Step 3l: 修改 qa_run_service.py**

同样模式：替换 `uuid4()` → `new_id()`（~10 处），移除 `UUID()` 值转换（~15 处）。

- [ ] **Step 3m: 修改 app_runtime_service.py**

同样模式：替换 `uuid4()` → `new_id()`（6 处），移除 `UUID()` 值转换（~6 处）。

- [ ] **Step 3n: 修改 observability_service.py**

同样模式：替换 `uuid4()` → `new_id()`（1 处）。

- [ ] **Step 3o: 修改 worker.py**

将：
```python
from uuid import UUID
```
改为直接传字符串，移除 `UUID(job_id)` 转换。

- [ ] **Step 3p: 验证全部测试通过**

Run: `cd backend && python -m pytest app/tests/ -x -q`
Expected: 所有测试通过

- [ ] **Step 3q: Commit**

```bash
git add backend/app/services/ backend/app/worker.py
git commit -m "refactor: replace uuid4() with new_id(), remove UUID() value conversions"
```

---

## Task 4: Fix PostgreSQL-Specific Leaks in Service Layer

**Files:**
- Modify: `backend/app/services/library_service.py` (2 处泄漏)
- Modify: 多个 service 文件（统一 `func.now()` 用法）

- [ ] **Step 4a: 修复 `date_trunc` 泄漏（library_service.py:1257）**

将：
```python
today_start = sa.text("date_trunc('day', now())")
```

替换为：
```python
from datetime import date
today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=UTC)
```

或使用 SQLAlchemy 通用函数（如果 PG 和 MySQL 都支持）：
```python
today_start = func.date_trunc(sa.text("'day'"), func.now())
```

推荐使用 Python 侧计算，完全消除数据库差异：
```python
from datetime import UTC, date, datetime
today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)
```

- [ ] **Step 4b: 修复 `.astext` JSONB 泄漏（library_service.py:1742-1744）**

将：
```python
kb_versions.c.metadata["library_version_id"].astext == str(version_id),
sa.and_(
    kb_versions.c.metadata["library_version_id"].astext.is_(None),
    kb_versions.c.source_file_id == ver_row["source_file_id"],
),
```

替换为 Python 侧过滤：
```python
# 先查出候选行，再在 Python 侧过滤 metadata
candidate_rows = session.execute(
    select(
        document_kb_bindings.c.binding_id,
        document_kb_bindings.c.document_id,
        document_kb_bindings.c.version_id,
        document_kb_bindings.c.status,
        kb_versions.c.metadata.label("kb_metadata"),
        kb_versions.c.source_file_id.label("kb_source_file_id"),
        knowledge_bases.c.name.label("kb_name"),
    )
    .select_from(
        document_kb_bindings
        .join(knowledge_bases, knowledge_bases.c.kb_id == document_kb_bindings.c.kb_id)
        .join(kb_versions, kb_versions.c.version_id == document_kb_bindings.c.version_id)
    )
    .where(
        document_kb_bindings.c.document_id == document_id,
        document_kb_bindings.c.status.in_(["active", "processing", "pending"]),
    )
).mappings().all()

# Python 侧过滤 metadata["library_version_id"]
binding_rows = [
    row for row in candidate_rows
    if (row["kb_metadata"] or {}).get("library_version_id") == str(version_id)
    or (
        (row["kb_metadata"] or {}).get("library_version_id") is None
        and row["kb_source_file_id"] == ver_row["source_file_id"]
    )
]
```

- [ ] **Step 4c: 统一时间戳策略（可选，推荐）**

当前代码中 `func.now()` 和 `datetime.now(UTC)` 混用。建议统一为：
- **SQL 侧时间戳**（`created_at`, `updated_at`, `deleted_at` 的 `server_default`）：保持 `func.now()`
- **Python 侧时间戳**（service 层手动赋值）：统一使用 `datetime.now(UTC)`

此步骤为可选清理，不影响多数据库兼容性。`func.now()` 在 PG 和 MySQL 上都能工作。

- [ ] **Step 4d: 验证测试通过**

Run: `cd backend && python -m pytest app/tests/ -x -q`
Expected: 所有测试通过

- [ ] **Step 4e: Commit**

```bash
git add backend/app/services/library_service.py
git commit -m "fix: remove PostgreSQL-specific leaks (date_trunc, .astext)"
```

---

## Task 5: Update `database.py` — Engine 创建适配

**Files:**
- Modify: `backend/app/core/database.py`

当前 `database.py` 直接用 `create_engine(settings.database_url, pool_pre_ping=True)` 创建引擎。MySQL 可能需要额外参数（如 `pool_recycle` 防止连接超时）。通过 DialectAdapter 或 URL 检测来添加方言特定参数。

- [ ] **Step 1: 修改 database.py**

将：
```python
_engine = create_engine(settings.database_url, pool_pre_ping=True)
```

替换为：
```python
from app.core.db_types import get_dialect_adapter

def _build_engine_kwargs(url: str) -> dict:
    """根据方言返回额外引擎参数。"""
    kwargs: dict = {"pool_pre_ping": True}
    adapter = get_dialect_adapter(url)
    if hasattr(adapter, '__class__') and adapter.__class__.__name__ == 'MySqlAdapter':
        kwargs["pool_recycle"] = 3600  # MySQL 连接超时回收
    return kwargs

def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("Database URL is required.")
        _engine = create_engine(settings.database_url, **_build_engine_kwargs(settings.database_url))
    return _engine
```

- [ ] **Step 2: 验证测试通过**

Run: `cd backend && python -m pytest app/tests/ -x -q`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/database.py
git commit -m "feat: add dialect-aware engine creation for MySQL support"
```

---

## Task 6: Update `conftest.py` — 移除 JSONB 编译映射

**Files:**
- Modify: `backend/app/tests/conftest.py`

由于 tables.py 已不再使用 `postgresql.JSONB()`，SQLite 测试中的 JSONB→JSON 编译映射不再需要。

- [ ] **Step 1: 清理 conftest.py**

移除以下代码块（当前 lines 27-33）：
```python
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

@compiles(PG_JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"
```

同时移除不再需要的导入：
```python
from sqlalchemy.dialects.postgresql import JSONB  # 如果存在
```

- [ ] **Step 2: 验证测试通过**

Run: `cd backend && python -m pytest app/tests/ -x -q`
Expected: 所有测试通过（不再需要 JSONB shim）

- [ ] **Step 3: Commit**

```bash
git add backend/app/tests/conftest.py
git commit -m "refactor: remove JSONB-to-JSON compile shim (no longer needed)"
```

---

## Task 7: Add `pymysql` Dependency + Update `.env.example`

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`

- [ ] **Step 1: 添加 pymysql 到 requirements.txt**

在 `psycopg[binary]` 行之后添加：
```
pymysql>=1.1,<2.0
```

- [ ] **Step 2: 更新 .env.example**

在现有 PG URL 示例之后添加：
```bash
# MySQL 示例（取消注释以使用 MySQL）
# RAG_LAB_DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/rag-lab?charset=utf8mb4
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt backend/.env.example
git commit -m "feat: add pymysql dependency and MySQL URL example"
```

---

## Task 8: PG Conversion Migration (0033)

**Files:**
- Create: `backend/migrations/versions/0033_convert_uuid_json_to_generic.py`

为现有 PostgreSQL 数据库创建迁移，将 UUID 列转为 VARCHAR(36)，JSONB 列转为 JSON，重建索引。

- [ ] **Step 1: 创建迁移文件**

```python
"""convert uuid and jsonb to generic types

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


# 需要转换的 UUID 列（表名, 列名）
UUID_COLUMNS = [
    ("users", "user_id"),
    ("users", "created_by"),
    ("users", "updated_by"),
    ("users", "deleted_by"),
    ("user_groups", "group_id"),
    ("user_groups", "created_by"),
    ("user_groups", "updated_by"),
    ("user_groups", "deleted_by"),
    ("user_group_members", "group_member_id"),
    ("user_group_members", "group_id"),
    ("user_group_members", "user_id"),
    ("user_group_members", "created_by"),
    # ... 所有 UUID 列需要在此列出
    # 实际实现时需从 tables.py 提取完整列表
]

# 需要转换的 JSONB 列
JSONB_COLUMNS = [
    ("system_dict_items", "extra"),
    ("documents", "metadata"),
    # ... 所有 JSONB 列需要在此列出
]


def upgrade() -> None:
    # 1. UUID 列：uuid → varchar(36)
    for table, column in UUID_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.String(36),
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
            postgresql_using=f"{column}::varchar(36)",
        )

    # 2. JSONB 列：jsonb → json
    for table, column in JSONB_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.JSON(),
            existing_type=sa.dialects.postgresql.JSONB(),
        )

    # 3. 移除 GIN 索引（JSON 列不支持）
    op.drop_index("idx_index_sync_jobs_scope", if_exists=True)

    # 4. 移除部分索引的 postgresql_where（MySQL 不支持，但 PG 上保留无害）
    # 部分索引在 PG 上仍可工作，无需删除


def downgrade() -> None:
    # 逆向操作：varchar(36) → uuid, json → jsonb
    for table, column in JSONB_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.dialects.postgresql.JSONB(),
            existing_type=sa.JSON(),
        )
    for table, column in UUID_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.dialects.postgresql.UUID(as_uuid=True),
            existing_type=sa.String(36),
            postgresql_using=f"{column}::uuid",
        )
```

**注意：** 完整实现时需要从 `tables.py` 提取所有 UUID 和 JSONB 列的完整列表。上述为示例骨架。

- [ ] **Step 2: 验证迁移可执行**

Run: `cd backend && alembic upgrade head`
Expected: 迁移成功执行

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/versions/0033_*.py
git commit -m "feat: add PG migration to convert UUID/JSONB to generic types"
```

---

## Task 9: MySQL Baseline Migration (0034)

**Files:**
- Create: `backend/migrations/versions/0034_mysql_baseline.py`

为全新 MySQL 数据库创建基线迁移。使用通用类型（`sa.String(36)`, `sa.JSON()`），不依赖任何 PostgreSQL 方言。

- [ ] **Step 1: 创建迁移文件**

此迁移可采用两种策略：

**策略 A（推荐）：** 使用 `metadata.create_all()` 一次性建表，跳过逐步迁移。
```python
"""mysql baseline

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from app.tables import metadata

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """为 MySQL 创建所有表（使用通用类型）。"""
    bind = op.get_bind()
    if "mysql" in str(bind.dialect.name):
        metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(bind)
```

**策略 B：** 逐步创建表（完整迁移）。适用于需要精细控制的场景。代码量大但更可控。

- [ ] **Step 2: 在 MySQL 上验证**

Run: `cd backend && DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3306/rag_lab_test alembic upgrade head`
Expected: 所有表创建成功

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/versions/0034_*.py
git commit -m "feat: add MySQL baseline migration"
```

---

## Task 10: Integration Testing — PG + MySQL 双库验证

**Files:**
- Create: `backend/app/tests/test_multi_db.py`（可选集成测试）

- [ ] **Step 1: 在 PostgreSQL 上运行全量测试**

Run: `cd backend && python -m pytest app/tests/ -x -q`
Expected: 所有测试通过

- [ ] **Step 2: 在 MySQL 上运行全量测试**

Run: `cd backend && DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3306/rag_lab_test python -m pytest app/tests/ -x -q`
Expected: 所有测试通过

- [ ] **Step 3: 在 SQLite 上运行全量测试（回归）**

Run: `cd backend && TEST_DATABASE_URL=sqlite:///:memory: python -m pytest app/tests/ -x -q`
Expected: 所有测试通过

- [ ] **Step 4: Commit**

```bash
git add backend/app/tests/
git commit -m "test: verify multi-database compatibility (PG, MySQL, SQLite)"
```

---

## Design Decisions Log

| 决策 | 选择 | 原因 |
|------|------|------|
| UUID 列类型 | `sa.String(36)` 通用 | PG 和 MySQL 一致，无需方言分支 |
| UUID 生成 | Python `new_id()` 返回 str | 项目已全部由 Python 生成 UUID，不依赖数据库 |
| JSON 列类型 | `sa.JSON()` 通用 | 项目 98% 的 JSONB 使用是 Python dict 读写，不走 SQL JSON 操作 |
| 时间戳 | `func.now()` + `datetime.now(UTC)` | 两者 PG/MySQL 都兼容，保持现状 |
| 接口模式 | `DialectAdapter` Protocol | 遵循项目 QARunProviders/ObjectStorageProvider 模式 |
| 迁移策略 | 保留现有 PG 迁移 + 新增转换迁移 | 最小化对现有数据库的影响 |
| 部分索引 | PG 保留，MySQL 不创建 | MySQL 不支持 WHERE 索引，功能降级但不报错 |
| GIN 索引 | 迁移中删除 | JSON 列不支持 GIN，改为无索引或应用层查询 |

## Risks and Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| UUID 列转 VARCHAR 后性能下降 | 低 — UUID 查询走等值匹配，VARCHAR(36) 索引效率接近 | 确保所有 UUID 列有索引 |
| JSON 列在 MySQL 上无 GIN 索引 | 中 — 大 JSON 字段查询变慢 | 项目仅 1 处 JSON 字段查询，影响极小 |
| 迁移 0033 失败导致数据丢失 | 高 — UUID→VARCHAR 不可逆 | 先备份数据库，迁移前验证 |
| 部分索引在 MySQL 上不生效 | 中 — 软删除唯一约束失效 | MySQL 上改用普通唯一索引 + 应用层检查 |
| 32 个旧迁移在 MySQL 上不可用 | 低 — 新部署用 0034 基线 | 文档说明：MySQL 仅支持新部署 |
