# Sprint 40 三层架构迁移实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现三层架构模型的数据结构迁移、权限服务重构和历史数据回填，为后续后端生命周期改造提供可验证基线。

**Architecture:** 采用一次性重构方法，一次性修改所有相关表结构，创建 parse_revisions 和 binding_revisions 新表，修改 chunks 和 document_kb_bindings 表结构，重构权限服务以支持三层角色映射。

**Tech Stack:** PostgreSQL, SQLAlchemy, FastAPI, pytest

---

## 文件结构

### 数据库迁移文件
- Create: `backend/alembic/versions/20260521_01_create_parse_revisions.py`
- Create: `backend/alembic/versions/20260521_02_create_binding_revisions.py`
- Create: `backend/alembic/versions/20260521_03_modify_chunks_table.py`
- Create: `backend/alembic/versions/20260521_04_modify_document_kb_bindings.py`

### 数据模型文件
- Modify: `backend/app/tables.py`
- Create: `backend/app/models/parse_revision.py`
- Create: `backend/app/models/binding_revision.py`

### 权限服务文件
- Modify: `backend/app/services/permission_service.py`
- Create: `backend/app/services/cross_resource_permission.py`

### 数据迁移脚本
- Create: `backend/scripts/migrate_parse_revisions.py`
- Create: `backend/scripts/migrate_binding_revisions.py`
- Create: `backend/scripts/migrate_chunks.py`

### 测试文件
- Create: `backend/app/tests/unit/test_parse_revision_model.py`
- Create: `backend/app/tests/unit/test_binding_revision_model.py`
- Create: `backend/app/tests/unit/test_permission_service_v2.py`
- Create: `backend/app/tests/unit/test_cross_resource_permission.py`
- Create: `backend/app/tests/integration/test_data_migration.py`

---

## Task 1: 创建 parse_revisions 表

**Files:**
- Create: `backend/alembic/versions/20260521_01_create_parse_revisions.py`
- Modify: `backend/app/tables.py`

- [ ] **Step 1: 创建 Alembic 迁移文件**

```python
# backend/alembic/versions/20260521_01_create_parse_revisions.py
"""create parse_revisions table

Revision ID: 20260521_01
Revises: <previous_revision>
Create Date: 2026-05-21 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260521_01'
down_revision = '<previous_revision>'  # 替换为实际的前一个 revision
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'parse_revisions',
        sa.Column('parse_revision_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_format', sa.String(length=16), nullable=False),
        sa.Column('content_object_key', sa.String(length=512), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(length=128), nullable=True),
        sa.Column('parser_name', sa.String(length=64), nullable=True),
        sa.Column('parser_version', sa.String(length=32), nullable=True),
        sa.Column('parse_options', postgresql.JSONB(), server_default='{}'),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.version_id'], ),
    )
    op.create_index('ix_parse_revisions_document_version_id', 'parse_revisions', ['document_version_id'])
    op.create_index('ix_parse_revisions_status', 'parse_revisions', ['status'])

def downgrade() -> None:
    op.drop_index('ix_parse_revisions_status', table_name='parse_revisions')
    op.drop_index('ix_parse_revisions_document_version_id', table_name='parse_revisions')
    op.drop_table('parse_revisions')
```

- [ ] **Step 2: 更新 tables.py 添加 parse_revisions 表定义**

```python
# backend/app/tables.py 添加以下内容
parse_revisions = sa.Table(
    "parse_revisions",
    metadata,
    sa.Column("parse_revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("content_format", sa.String(length=16), nullable=False),
    sa.Column("content_object_key", sa.String(length=512), nullable=True),
    sa.Column("content_text", sa.Text(), nullable=True),
    sa.Column("content_hash", sa.String(length=128), nullable=True),
    sa.Column("parser_name", sa.String(length=64), nullable=True),
    sa.Column("parser_version", sa.String(length=32), nullable=True),
    sa.Column("parse_options", postgresql.JSONB(), nullable=False, server_default='{}'),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
)
```

- [ ] **Step 3: 运行迁移**

Run: `cd backend && alembic upgrade head`
Expected: 迁移成功，parse_revisions 表创建完成

- [ ] **Step 4: 验证表结构**

Run: `psql -d database_name -c "\d parse_revisions"`
Expected: 显示 parse_revisions 表结构

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/20260521_01_create_parse_revisions.py backend/app/tables.py
git commit -m "feat: create parse_revisions table for three-layer architecture"
```

---

## Task 2: 创建 binding_revisions 表

**Files:**
- Create: `backend/alembic/versions/20260521_02_create_binding_revisions.py`
- Modify: `backend/app/tables.py`

- [ ] **Step 1: 创建 Alembic 迁移文件**

```python
# backend/alembic/versions/20260521_02_create_binding_revisions.py
"""create binding_revisions table

Revision ID: 20260521_02
Revises: 20260521_01
Create Date: 2026-05-21 11:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260521_02'
down_revision = '20260521_01'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'binding_revisions',
        sa.Column('binding_revision_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('binding_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('knowledge_base_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_version_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parse_revision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('chunk_count', sa.Integer(), server_default='0'),
        sa.Column('index_status', sa.String(length=16), nullable=True),
        sa.Column('build_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('build_finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['binding_id'], ['document_kb_bindings.binding_id'], ),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.kb_id'], ),
        sa.ForeignKeyConstraint(['document_id'], ['documents.document_id'], ),
        sa.ForeignKeyConstraint(['document_version_id'], ['document_versions.version_id'], ),
        sa.ForeignKeyConstraint(['parse_revision_id'], ['parse_revisions.parse_revision_id'], ),
    )
    op.create_index('ix_binding_revisions_binding_id', 'binding_revisions', ['binding_id'])
    op.create_index('ix_binding_revisions_knowledge_base_id', 'binding_revisions', ['knowledge_base_id'])
    op.create_index('ix_binding_revisions_status', 'binding_revisions', ['status'])

def downgrade() -> None:
    op.drop_index('ix_binding_revisions_status', table_name='binding_revisions')
    op.drop_index('ix_binding_revisions_knowledge_base_id', table_name='binding_revisions')
    op.drop_index('ix_binding_revisions_binding_id', table_name='binding_revisions')
    op.drop_table('binding_revisions')
```

- [ ] **Step 2: 更新 tables.py 添加 binding_revisions 表定义**

```python
# backend/app/tables.py 添加以下内容
binding_revisions = sa.Table(
    "binding_revisions",
    metadata,
    sa.Column("binding_revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("binding_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("parse_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("chunk_count", sa.Integer(), nullable=False, server_default='0'),
    sa.Column("index_status", sa.String(length=16), nullable=True),
    sa.Column("build_started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("build_finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
```

- [ ] **Step 3: 运行迁移**

Run: `cd backend && alembic upgrade head`
Expected: 迁移成功，binding_revisions 表创建完成

- [ ] **Step 4: 验证表结构**

Run: `psql -d database_name -c "\d binding_revisions"`
Expected: 显示 binding_revisions 表结构

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/20260521_02_create_binding_revisions.py backend/app/tables.py
git commit -m "feat: create binding_revisions table for three-layer architecture"
```

---

## Task 3: 修改 chunks 表结构

**Files:**
- Create: `backend/alembic/versions/20260521_03_modify_chunks_table.py`
- Modify: `backend/app/tables.py`

- [ ] **Step 1: 创建 Alembic 迁移文件**

```python
# backend/alembic/versions/20260521_03_modify_chunks_table.py
"""modify chunks table structure

Revision ID: 20260521_03
Revises: 20260521_02
Create Date: 2026-05-21 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260521_03'
down_revision = '20260521_02'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 添加新字段
    op.add_column('chunks', sa.Column('binding_revision_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('chunks', sa.Column('parse_revision_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('chunks', sa.Column('document_version_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('chunks', sa.Column('start_offset', sa.Integer(), nullable=True))
    op.add_column('chunks', sa.Column('end_offset', sa.Integer(), nullable=True))
    op.add_column('chunks', sa.Column('section_path', sa.String(length=255), nullable=True))
    op.add_column('chunks', sa.Column('heading', sa.String(length=255), nullable=True))
    op.add_column('chunks', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('chunks', sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('chunks', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    
    # 添加外键约束
    op.create_foreign_key('fk_chunks_binding_revision_id', 'chunks', 'binding_revisions', ['binding_revision_id'], ['binding_revision_id'])
    op.create_foreign_key('fk_chunks_parse_revision_id', 'chunks', 'parse_revisions', ['parse_revision_id'], ['parse_revision_id'])
    op.create_foreign_key('fk_chunks_document_version_id', 'chunks', 'document_versions', ['document_version_id'], ['version_id'])
    
    # 添加索引
    op.create_index('ix_chunks_binding_revision_id', 'chunks', ['binding_revision_id'])
    op.create_index('ix_chunks_parse_revision_id', 'chunks', ['parse_revision_id'])

def downgrade() -> None:
    # 删除索引
    op.drop_index('ix_chunks_parse_revision_id', table_name='chunks')
    op.drop_index('ix_chunks_binding_revision_id', table_name='chunks')
    
    # 删除外键约束
    op.drop_constraint('fk_chunks_document_version_id', 'chunks', type_='foreignkey')
    op.drop_constraint('fk_chunks_parse_revision_id', 'chunks', type_='foreignkey')
    op.drop_constraint('fk_chunks_binding_revision_id', 'chunks', type_='foreignkey')
    
    # 删除字段
    op.drop_column('chunks', 'deleted_at')
    op.drop_column('chunks', 'retired_at')
    op.drop_column('chunks', 'summary')
    op.drop_column('chunks', 'heading')
    op.drop_column('chunks', 'section_path')
    op.drop_column('chunks', 'end_offset')
    op.drop_column('chunks', 'start_offset')
    op.drop_column('chunks', 'document_version_id')
    op.drop_column('chunks', 'parse_revision_id')
    op.drop_column('chunks', 'binding_revision_id')
```

- [ ] **Step 2: 更新 tables.py 修改 chunks 表定义**

```python
# backend/app/tables.py 修改 chunks 表定义
chunks = sa.Table(
    "chunks",
    metadata,
    sa.Column("chunk_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("chunk_index", sa.Integer(), nullable=False),
    sa.Column("page_no", sa.Integer(), nullable=True),
    sa.Column("section", sa.String(length=255), nullable=True),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("content_hash", sa.String(length=128), nullable=True),
    sa.Column("token_count", sa.Integer(), nullable=True),
    sa.Column("security_level", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("metadata", postgresql.JSONB(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    # 新增字段
    sa.Column("binding_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("parse_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("start_offset", sa.Integer(), nullable=True),
    sa.Column("end_offset", sa.Integer(), nullable=True),
    sa.Column("section_path", sa.String(length=255), nullable=True),
    sa.Column("heading", sa.String(length=255), nullable=True),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
)
```

- [ ] **Step 3: 运行迁移**

Run: `cd backend && alembic upgrade head`
Expected: 迁移成功，chunks 表结构修改完成

- [ ] **Step 4: 验证表结构**

Run: `psql -d database_name -c "\d chunks"`
Expected: 显示 chunks 表新字段

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/20260521_03_modify_chunks_table.py backend/app/tables.py
git commit -m "feat: modify chunks table structure for three-layer architecture"
```

---

## Task 4: 修改 document_kb_bindings 表结构

**Files:**
- Create: `backend/alembic/versions/20260521_04_modify_document_kb_bindings.py`
- Modify: `backend/app/tables.py`

- [ ] **Step 1: 创建 Alembic 迁移文件**

```python
# backend/alembic/versions/20260521_04_modify_document_kb_bindings.py
"""modify document_kb_bindings table structure

Revision ID: 20260521_04
Revises: 20260521_03
Create Date: 2026-05-21 13:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260521_04'
down_revision = '20260521_03'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 添加新字段
    op.add_column('document_kb_bindings', sa.Column('active_binding_revision_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # 添加外键约束
    op.create_foreign_key('fk_document_kb_bindings_active_binding_revision_id', 'document_kb_bindings', 'binding_revisions', ['active_binding_revision_id'], ['binding_revision_id'])
    
    # 添加索引
    op.create_index('ix_document_kb_bindings_active_binding_revision_id', 'document_kb_bindings', ['active_binding_revision_id'])

def downgrade() -> None:
    # 删除索引
    op.drop_index('ix_document_kb_bindings_active_binding_revision_id', table_name='document_kb_bindings')
    
    # 删除外键约束
    op.drop_constraint('fk_document_kb_bindings_active_binding_revision_id', 'document_kb_bindings', type_='foreignkey')
    
    # 删除字段
    op.drop_column('document_kb_bindings', 'active_binding_revision_id')
```

- [ ] **Step 2: 更新 tables.py 修改 document_kb_bindings 表定义**

```python
# backend/app/tables.py 修改 document_kb_bindings 表定义
document_kb_bindings = sa.Table(
    "document_kb_bindings",
    metadata,
    sa.Column("binding_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("chunk_size", sa.Integer(), nullable=False),
    sa.Column("chunk_overlap", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("chunk_count", sa.Integer(), nullable=False),
    sa.Column("error_code", sa.String(length=64), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    # 新增字段
    sa.Column("active_binding_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
)
```

- [ ] **Step 3: 运行迁移**

Run: `cd backend && alembic upgrade head`
Expected: 迁移成功，document_kb_bindings 表结构修改完成

- [ ] **Step 4: 验证表结构**

Run: `psql -d database_name -c "\d document_kb_bindings"`
Expected: 显示 document_kb_bindings 表新字段

- [ ] **Step 5: 提交**

```bash
git add backend/alembic/versions/20260521_04_modify_document_kb_bindings.py backend/app/tables.py
git commit -m "feat: modify document_kb_bindings table structure for three-layer architecture"
```

---

## Task 5: 配置三层角色权限映射

**Files:**
- Modify: `backend/app/services/permission_service.py`
- Create: `backend/scripts/seed_role_permissions.py`

- [ ] **Step 1: 创建角色权限种子脚本**

```python
# backend/scripts/seed_role_permissions.py
"""Seed role permissions for three-layer architecture"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 数据库连接
DATABASE_URL = "postgresql://username:password@localhost/database_name"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# 角色权限映射
ROLE_PERMISSIONS = {
    # 平台角色
    "platform": {
        "platform_admin": [
            "platform.user.manage",
            "platform.group.manage",
            "platform.resource.manage",
            "platform.permission.manage",
            "platform.audit.read",
            "library.document.admin",
        ],
        "platform_user": [
            "library.create",
            "kb.create",
        ],
    },
    # 文档库角色
    "library": {
        "library_owner": [
            "library.view",
            "library.member.manage",
            "library.document.read",
            "library.document.download",
            "library.document.create",
            "library.document.update",
            "library.document.delete",
            "library.version.create",
            "library.version.activate",
            "library.version.delete",
            "library.document.bind",
        ],
        "library_manager": [
            "library.view",
            "library.member.manage",
            "library.document.read",
            "library.document.download",
            "library.document.create",
            "library.document.update",
            "library.document.delete",
            "library.version.create",
            "library.version.activate",
            "library.version.delete",
            "library.document.bind",
        ],
        "library_editor": [
            "library.view",
            "library.document.read",
            "library.document.download",
            "library.document.create",
            "library.document.update",
            "library.document.delete",
            "library.version.create",
            "library.version.activate",
            "library.version.delete",
            "library.document.bind",
        ],
        "library_binder": [
            "library.view",
            "library.document.read",
            "library.document.download",
            "library.document.bind",
        ],
        "library_viewer": [
            "library.view",
            "library.document.read",
            "library.document.download",
        ],
    },
    # 知识库角色
    "kb": {
        "kb_owner": [
            "kb.view",
            "kb.manage",
            "kb.member.manage",
            "kb.document.bind",
            "kb.document.unbind",
            "kb.document.rebuild",
            "kb.document.read",
            "kb.chunk.read",
            "kb.config.manage",
            "kb.qa.run",
            "kb.qa.history.read",
            "kb.qa.history.read_own",
            "kb.evaluation.manage",
            "kb.app.manage",
        ],
        "kb_manager": [
            "kb.view",
            "kb.manage",
            "kb.member.manage",
            "kb.document.bind",
            "kb.document.unbind",
            "kb.document.rebuild",
            "kb.document.read",
            "kb.chunk.read",
            "kb.config.manage",
            "kb.qa.run",
            "kb.qa.history.read",
            "kb.qa.history.read_own",
            "kb.evaluation.manage",
            "kb.app.manage",
        ],
        "kb_editor": [
            "kb.view",
            "kb.document.bind",
            "kb.document.unbind",
            "kb.document.rebuild",
            "kb.document.read",
            "kb.chunk.read",
            "kb.config.manage",
            "kb.qa.run",
            "kb.qa.history.read",
            "kb.evaluation.manage",
        ],
        "kb_viewer": [
            "kb.view",
            "kb.document.read",
            "kb.qa.history.read",
        ],
        "kb_qa_runner": [
            "kb.view",
            "kb.qa.run",
            "kb.qa.history.read_own",
        ],
    },
    # 应用角色
    "app": {
        "app_owner": [
            "app.view",
            "app.manage",
            "app.owner.transfer",
            "app.delete",
            "app.key.manage",
            "app.invocation.read",
            "app.stats.read",
            "app.runtime.test",
        ],
        "app_operator": [
            "app.view",
            "app.key.manage",
            "app.invocation.read",
            "app.stats.read",
            "app.runtime.test",
        ],
        "app_viewer": [
            "app.view",
            "app.invocation.read",
            "app.stats.read",
        ],
    },
}

def seed_role_permissions():
    """插入角色权限映射数据"""
    session = Session()
    try:
        # 清空现有数据
        session.execute(text("DELETE FROM role_permission_bindings"))
        
        # 插入新数据
        now = datetime.now(timezone.utc)
        for role_scope, roles in ROLE_PERMISSIONS.items():
            for role_code, permissions in roles.items():
                for permission_code in permissions:
                    session.execute(
                        text("""
                            INSERT INTO role_permission_bindings 
                            (role_permission_id, role_scope, role_code, permission_code, effect, status, created_at, created_by)
                            VALUES 
                            (:id, :scope, :role, :permission, 'allow', 'active', :created_at, NULL)
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "scope": role_scope,
                            "role": role_code,
                            "permission": permission_code,
                            "created_at": now,
                        }
                    )
        
        session.commit()
        print("角色权限映射数据插入成功")
    except Exception as e:
        session.rollback()
        print(f"插入失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_role_permissions()
```

- [ ] **Step 2: 运行种子脚本**

Run: `cd backend && python scripts/seed_role_permissions.py`
Expected: 角色权限映射数据插入成功

- [ ] **Step 3: 验证数据**

Run: `psql -d database_name -c "SELECT role_scope, role_code, COUNT(*) FROM role_permission_bindings GROUP BY role_scope, role_code"`
Expected: 显示各角色的权限数量

- [ ] **Step 4: 提交**

```bash
git add backend/scripts/seed_role_permissions.py
git commit -m "feat: seed role permissions for three-layer architecture"
```

---

## Task 6: 实现跨资源权限校验

**Files:**
- Create: `backend/app/services/cross_resource_permission.py`
- Modify: `backend/app/services/permission_service.py`

- [ ] **Step 1: 创建跨资源权限校验服务**

```python
# backend/app/services/cross_resource_permission.py
"""Cross-resource permission checking service"""
from uuid import UUID
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.services.permission_service import has_library_permission, has_kb_permission


def check_cross_resource_permission(
    session: Session,
    current_user: CurrentUserResponse,
    source_library_id: UUID,
    target_kb_id: UUID,
) -> bool:
    """校验跨资源权限：绑定文档到知识库
    
    规则：
    1. 校验源文档库权限：library.document.bind
    2. 校验目标知识库权限：kb.document.bind
    3. 两侧权限都满足才允许
    """
    # 1. 校验源文档库权限
    library_permission = has_library_permission(
        session, current_user, "library.document.bind", source_library_id
    )
    
    # 2. 校验目标知识库权限
    kb_permission = has_kb_permission(
        session, current_user, target_kb_id, "kb.document.bind"
    )
    
    # 3. 两侧权限都满足才允许
    return library_permission and kb_permission


def check_document_version_delete_permission(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    document_id: UUID,
    version_id: UUID,
) -> tuple[bool, str]:
    """校验文档版本删除权限
    
    规则：
    1. 校验 library.version.delete 权限
    2. 检查是否为文档库当前 active version
    3. 检查是否存在 active BindingRevision
    4. 检查是否存在 pending/running 任务
    
    返回: (allowed, reason)
    """
    # 1. 校验权限
    if not has_library_permission(session, current_user, "library.version.delete", library_id):
        return False, "没有删除文档版本的权限"
    
    # 2. 检查是否为 active version
    from app.tables import documents
    from sqlalchemy import select
    
    doc = session.execute(
        select(documents.c.active_version_id).where(
            documents.c.document_id == document_id
        )
    ).scalar()
    
    if doc == version_id:
        return False, "不能删除文档库当前 active version"
    
    # 3. 检查是否存在 active BindingRevision
    from app.tables import binding_revisions
    
    active_binding = session.execute(
        select(binding_revisions.c.binding_revision_id).where(
            binding_revisions.c.document_version_id == version_id,
            binding_revisions.c.status == 'active',
        )
    ).scalar()
    
    if active_binding:
        return False, "该版本正在支撑知识库 active BindingRevision"
    
    # 4. 检查是否存在 pending/running 任务
    from app.tables import library_parse_jobs, ingest_jobs
    
    pending_jobs = session.execute(
        select(library_parse_jobs.c.job_id).where(
            library_parse_jobs.c.version_id == version_id,
            library_parse_jobs.c.status.in_(['pending', 'running']),
        )
    ).scalar()
    
    if pending_jobs:
        return False, "该版本存在运行中的任务"
    
    return True, "允许删除"
```

- [ ] **Step 2: 更新 permission_service.py 导入新服务**

```python
# backend/app/services/permission_service.py 添加导入
from app.services.cross_resource_permission import (
    check_cross_resource_permission,
    check_document_version_delete_permission,
)
```

- [ ] **Step 3: 编写测试**

```python
# backend/app/tests/unit/test_cross_resource_permission.py
"""Tests for cross-resource permission checking"""
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.cross_resource_permission import (
    check_cross_resource_permission,
    check_document_version_delete_permission,
)


def test_check_cross_resource_permission_both_allowed():
    """测试两侧权限都满足时允许"""
    session = Mock()
    current_user = Mock()
    source_library_id = uuid4()
    target_kb_id = uuid4()
    
    with patch('app.services.cross_resource_permission.has_library_permission', return_value=True), \
         patch('app.services.cross_resource_permission.has_kb_permission', return_value=True):
        result = check_cross_resource_permission(session, current_user, source_library_id, target_kb_id)
        assert result is True


def test_check_cross_resource_permission_library_denied():
    """测试文档库权限不满足时拒绝"""
    session = Mock()
    current_user = Mock()
    source_library_id = uuid4()
    target_kb_id = uuid4()
    
    with patch('app.services.cross_resource_permission.has_library_permission', return_value=False), \
         patch('app.services.cross_resource_permission.has_kb_permission', return_value=True):
        result = check_cross_resource_permission(session, current_user, source_library_id, target_kb_id)
        assert result is False


def test_check_cross_resource_permission_kb_denied():
    """测试知识库权限不满足时拒绝"""
    session = Mock()
    current_user = Mock()
    source_library_id = uuid4()
    target_kb_id = uuid4()
    
    with patch('app.services.cross_resource_permission.has_library_permission', return_value=True), \
         patch('app.services.cross_resource_permission.has_kb_permission', return_value=False):
        result = check_cross_resource_permission(session, current_user, source_library_id, target_kb_id)
        assert result is False


def test_check_document_version_delete_permission_no_permission():
    """测试没有删除权限时拒绝"""
    session = Mock()
    current_user = Mock()
    library_id = uuid4()
    document_id = uuid4()
    version_id = uuid4()
    
    with patch('app.services.cross_resource_permission.has_library_permission', return_value=False):
        allowed, reason = check_document_version_delete_permission(
            session, current_user, library_id, document_id, version_id
        )
        assert allowed is False
        assert "没有删除文档版本的权限" in reason
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_cross_resource_permission.py -v`
Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/cross_resource_permission.py backend/app/services/permission_service.py backend/app/tests/unit/test_cross_resource_permission.py
git commit -m "feat: implement cross-resource permission checking"
```

---

## Task 7: 创建历史数据回填脚本

**Files:**
- Create: `backend/scripts/migrate_parse_revisions.py`
- Create: `backend/scripts/migrate_binding_revisions.py`
- Create: `backend/scripts/migrate_chunks.py`

- [ ] **Step 1: 创建 parse_revisions 回填脚本**

```python
# backend/scripts/migrate_parse_revisions.py
"""Migrate existing data to parse_revisions table"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://username:password@localhost/database_name"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def migrate_parse_revisions():
    """为每个 document_version 创建 parse_revision 记录"""
    session = Session()
    try:
        # 查询所有 document_version
        versions = session.execute(text("""
            SELECT version_id, created_at, created_by, metadata
            FROM document_versions
            WHERE deleted_at IS NULL
        """)).fetchall()
        
        print(f"找到 {len(versions)} 个 document_version")
        
        # 为每个 version 创建 parse_revision
        now = datetime.now(timezone.utc)
        for version in versions:
            version_id, created_at, created_by, metadata = version
            
            # 检查是否已存在 parse_revision
            existing = session.execute(text("""
                SELECT parse_revision_id FROM parse_revisions 
                WHERE document_version_id = :version_id
            """), {"version_id": version_id}).scalar()
            
            if existing:
                print(f"跳过已存在的 parse_revision: {existing}")
                continue
            
            # 创建 parse_revision
            parse_revision_id = str(uuid.uuid4())
            session.execute(text("""
                INSERT INTO parse_revisions 
                (parse_revision_id, document_version_id, content_format, content_hash, 
                 parser_name, parser_version, status, created_at, created_by)
                VALUES 
                (:id, :version_id, 'markdown', NULL, 'legacy_parser', '1.0', 
                 'completed', :created_at, :created_by)
            """), {
                "id": parse_revision_id,
                "version_id": version_id,
                "created_at": created_at or now,
                "created_by": created_by,
            })
            
            print(f"创建 parse_revision: {parse_revision_id} for version: {version_id}")
        
        session.commit()
        print("parse_revisions 迁移完成")
    except Exception as e:
        session.rollback()
        print(f"迁移失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate_parse_revisions()
```

- [ ] **Step 2: 创建 binding_revisions 回填脚本**

```python
# backend/scripts/migrate_binding_revisions.py
"""Migrate existing data to binding_revisions table"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://username:password@localhost/database_name"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def migrate_binding_revisions():
    """为每个 document_kb_binding 创建 binding_revision 记录"""
    session = Session()
    try:
        # 查询所有 document_kb_binding
        bindings = session.execute(text("""
            SELECT binding_id, kb_id, document_id, version_id, chunk_count, created_at, created_by
            FROM document_kb_bindings
            WHERE status = 'active'
        """)).fetchall()
        
        print(f"找到 {len(bindings)} 个 document_kb_binding")
        
        # 为每个 binding 创建 binding_revision
        now = datetime.now(timezone.utc)
        for binding in bindings:
            binding_id, kb_id, document_id, version_id, chunk_count, created_at, created_by = binding
            
            # 检查是否已存在 binding_revision
            existing = session.execute(text("""
                SELECT binding_revision_id FROM binding_revisions 
                WHERE binding_id = :binding_id
            """), {"binding_id": binding_id}).scalar()
            
            if existing:
                print(f"跳过已存在的 binding_revision: {existing}")
                continue
            
            # 获取对应的 parse_revision_id
            parse_revision = session.execute(text("""
                SELECT parse_revision_id FROM parse_revisions 
                WHERE document_version_id = :version_id
                LIMIT 1
            """), {"version_id": version_id}).scalar()
            
            if not parse_revision:
                print(f"警告: 找不到 version_id {version_id} 对应的 parse_revision")
                continue
            
            # 创建 binding_revision
            binding_revision_id = str(uuid.uuid4())
            session.execute(text("""
                INSERT INTO binding_revisions 
                (binding_revision_id, binding_id, knowledge_base_id, document_id, 
                 document_version_id, parse_revision_id, status, chunk_count, 
                 created_at, created_by)
                VALUES 
                (:id, :binding_id, :kb_id, :document_id, :version_id, 
                 :parse_revision_id, 'active', :chunk_count, :created_at, :created_by)
            """), {
                "id": binding_revision_id,
                "binding_id": binding_id,
                "kb_id": kb_id,
                "document_id": document_id,
                "version_id": version_id,
                "parse_revision_id": parse_revision,
                "chunk_count": chunk_count or 0,
                "created_at": created_at or now,
                "created_by": created_by,
            })
            
            # 更新 document_kb_bindings 的 active_binding_revision_id
            session.execute(text("""
                UPDATE document_kb_bindings 
                SET active_binding_revision_id = :binding_revision_id
                WHERE binding_id = :binding_id
            """), {
                "binding_revision_id": binding_revision_id,
                "binding_id": binding_id,
            })
            
            print(f"创建 binding_revision: {binding_revision_id} for binding: {binding_id}")
        
        session.commit()
        print("binding_revisions 迁移完成")
    except Exception as e:
        session.rollback()
        print(f"迁移失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate_binding_revisions()
```

- [ ] **Step 3: 创建 chunks 回填脚本**

```python
# backend/scripts/migrate_chunks.py
"""Migrate existing chunks data to new structure"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://username:password@localhost/database_name"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def migrate_chunks():
    """更新现有 chunks 表，添加新字段关联"""
    session = Session()
    try:
        # 更新 chunks 表，添加 binding_revision_id
        result = session.execute(text("""
            UPDATE chunks 
            SET binding_revision_id = (
                SELECT br.binding_revision_id 
                FROM binding_revisions br
                JOIN document_kb_bindings db ON br.binding_id = db.binding_id
                WHERE db.document_id = chunks.document_id 
                AND db.kb_id = chunks.kb_id 
                AND br.status = 'active'
                LIMIT 1
            )
            WHERE binding_revision_id IS NULL
        """))
        print(f"更新 {result.rowcount} 个 chunk 的 binding_revision_id")
        
        # 更新 chunks 表，添加 parse_revision_id
        result = session.execute(text("""
            UPDATE chunks 
            SET parse_revision_id = (
                SELECT pr.parse_revision_id 
                FROM parse_revisions pr
                WHERE pr.document_version_id = chunks.version_id 
                AND pr.status = 'completed'
                LIMIT 1
            )
            WHERE parse_revision_id IS NULL
        """))
        print(f"更新 {result.rowcount} 个 chunk 的 parse_revision_id")
        
        # 更新 chunks 表，添加 document_version_id
        result = session.execute(text("""
            UPDATE chunks 
            SET document_version_id = version_id
            WHERE document_version_id IS NULL
        """))
        print(f"更新 {result.rowcount} 个 chunk 的 document_version_id")
        
        session.commit()
        print("chunks 迁移完成")
    except Exception as e:
        session.rollback()
        print(f"迁移失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    migrate_chunks()
```

- [ ] **Step 4: 运行回填脚本**

Run: `cd backend && python scripts/migrate_parse_revisions.py && python scripts/migrate_binding_revisions.py && python scripts/migrate_chunks.py`
Expected: 所有脚本执行成功

- [ ] **Step 5: 验证数据完整性**

```sql
-- 验证 parse_revisions 数量
SELECT COUNT(*) FROM parse_revisions;

-- 验证 binding_revisions 数量
SELECT COUNT(*) FROM binding_revisions;

-- 验证 chunks 关联完整性
SELECT COUNT(*) FROM chunks 
WHERE binding_revision_id IS NULL 
OR parse_revision_id IS NULL 
OR document_version_id IS NULL;
```

- [ ] **Step 6: 提交**

```bash
git add backend/scripts/migrate_parse_revisions.py backend/scripts/migrate_binding_revisions.py backend/scripts/migrate_chunks.py
git commit -m "feat: add historical data migration scripts"
```

---

## Task 8: 编写集成测试

**Files:**
- Create: `backend/app/tests/integration/test_data_migration.py`

- [ ] **Step 1: 创建集成测试**

```python
# backend/app/tests/integration/test_data_migration.py
"""Integration tests for data migration"""
import pytest
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.tables import metadata


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    DATABASE_URL = "postgresql://username:password@localhost/test_database"
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # 创建表
    metadata.create_all(engine)
    
    yield session
    
    # 清理
    session.close()
    metadata.drop_all(engine)


def test_parse_revisions_creation(db_session):
    """测试 parse_revisions 表创建"""
    # 插入测试数据
    db_session.execute(text("""
        INSERT INTO parse_revisions 
        (parse_revision_id, document_version_id, content_format, status, created_at)
        VALUES 
        (:id, :version_id, 'markdown', 'completed', NOW())
    """), {
        "id": str(uuid4()),
        "version_id": str(uuid4()),
    })
    
    # 查询验证
    result = db_session.execute(text("SELECT COUNT(*) FROM parse_revisions")).scalar()
    assert result == 1


def test_binding_revisions_creation(db_session):
    """测试 binding_revisions 表创建"""
    # 插入测试数据
    db_session.execute(text("""
        INSERT INTO binding_revisions 
        (binding_revision_id, binding_id, knowledge_base_id, document_id, 
         document_version_id, parse_revision_id, status, created_at)
        VALUES 
        (:id, :binding_id, :kb_id, :doc_id, :version_id, :parse_id, 'active', NOW())
    """), {
        "id": str(uuid4()),
        "binding_id": str(uuid4()),
        "kb_id": str(uuid4()),
        "doc_id": str(uuid4()),
        "version_id": str(uuid4()),
        "parse_id": str(uuid4()),
    })
    
    # 查询验证
    result = db_session.execute(text("SELECT COUNT(*) FROM binding_revisions")).scalar()
    assert result == 1


def test_chunks_table_migration(db_session):
    """测试 chunks 表迁移"""
    # 插入测试数据
    db_session.execute(text("""
        INSERT INTO chunks 
        (chunk_id, version_id, document_id, kb_id, chunk_index, content, 
         security_level, status, metadata, created_at, binding_revision_id, 
         parse_revision_id, document_version_id)
        VALUES 
        (:id, :version_id, :doc_id, :kb_id, 1, 'test content', 
         'public', 'active', '{}', NOW(), :binding_id, :parse_id, :version_id)
    """), {
        "id": str(uuid4()),
        "version_id": str(uuid4()),
        "doc_id": str(uuid4()),
        "kb_id": str(uuid4()),
        "binding_id": str(uuid4()),
        "parse_id": str(uuid4()),
    })
    
    # 查询验证
    result = db_session.execute(text("""
        SELECT binding_revision_id, parse_revision_id, document_version_id 
        FROM chunks WHERE chunk_index = 1
    """)).fetchone()
    
    assert result is not None
    assert result[0] is not None  # binding_revision_id
    assert result[1] is not None  # parse_revision_id
    assert result[2] is not None  # document_version_id


def test_data_integrity_after_migration(db_session):
    """测试迁移后数据完整性"""
    # 插入完整的测试数据链
    version_id = str(uuid4())
    parse_revision_id = str(uuid4())
    binding_revision_id = str(uuid4())
    binding_id = str(uuid4())
    document_id = str(uuid4())
    kb_id = str(uuid4())
    chunk_id = str(uuid4())
    
    # 插入 parse_revision
    db_session.execute(text("""
        INSERT INTO parse_revisions 
        (parse_revision_id, document_version_id, content_format, status, created_at)
        VALUES (:id, :version_id, 'markdown', 'completed', NOW())
    """), {"id": parse_revision_id, "version_id": version_id})
    
    # 插入 binding_revision
    db_session.execute(text("""
        INSERT INTO binding_revisions 
        (binding_revision_id, binding_id, knowledge_base_id, document_id, 
         document_version_id, parse_revision_id, status, created_at)
        VALUES (:id, :binding_id, :kb_id, :doc_id, :version_id, :parse_id, 'active', NOW())
    """), {
        "id": binding_revision_id,
        "binding_id": binding_id,
        "kb_id": kb_id,
        "doc_id": document_id,
        "version_id": version_id,
        "parse_id": parse_revision_id,
    })
    
    # 插入 chunk
    db_session.execute(text("""
        INSERT INTO chunks 
        (chunk_id, version_id, document_id, kb_id, chunk_index, content, 
         security_level, status, metadata, created_at, binding_revision_id, 
         parse_revision_id, document_version_id)
        VALUES (:id, :version_id, :doc_id, :kb_id, 1, 'test content', 
                'public', 'active', '{}', NOW(), :binding_id, :parse_id, :version_id)
    """), {
        "id": chunk_id,
        "version_id": version_id,
        "doc_id": document_id,
        "kb_id": kb_id,
        "binding_id": binding_revision_id,
        "parse_id": parse_revision_id,
    })
    
    # 验证数据完整性
    result = db_session.execute(text("""
        SELECT c.chunk_id, c.binding_revision_id, c.parse_revision_id,
               br.binding_revision_id, pr.parse_revision_id
        FROM chunks c
        JOIN binding_revisions br ON c.binding_revision_id = br.binding_revision_id
        JOIN parse_revisions pr ON c.parse_revision_id = pr.parse_revision_id
        WHERE c.chunk_id = :chunk_id
    """), {"chunk_id": chunk_id}).fetchone()
    
    assert result is not None
    assert result[0] == chunk_id
    assert result[1] == binding_revision_id
    assert result[2] == parse_revision_id
```

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && python -m pytest app/tests/integration/test_data_migration.py -v`
Expected: 所有测试通过

- [ ] **Step 3: 提交**

```bash
git add backend/app/tests/integration/test_data_migration.py
git commit -m "test: add integration tests for data migration"
```

---

## Task 9: 运行完整测试套件

**Files:**
- None (使用现有测试文件)

- [ ] **Step 1: 运行单元测试**

Run: `cd backend && python -m pytest app/tests/unit/ -v`
Expected: 所有单元测试通过

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && python -m pytest app/tests/integration/ -v`
Expected: 所有集成测试通过

- [ ] **Step 3: 运行权限服务测试**

Run: `cd backend && python -m pytest app/tests/unit/test_permission_service.py -v`
Expected: 所有权限服务测试通过

- [ ] **Step 4: 验证代码编译**

Run: `cd backend && python -m compileall app`
Expected: 编译成功，无错误

- [ ] **Step 5: 提交最终状态**

```bash
git add .
git commit -m "feat: complete Sprint 40 three-layer architecture migration"
```

---

## 验收标准

### 数据模型验收
- [ ] `parse_revisions` 表创建成功
- [ ] `binding_revisions` 表创建成功
- [ ] `chunks` 表字段添加成功
- [ ] `document_kb_bindings` 表字段添加成功
- [ ] 数据完整性验证通过

### 权限服务验收
- [ ] 三层角色映射配置完成
- [ ] 权限码映射配置完成
- [ ] 跨资源权限校验实现完成
- [ ] 权限服务测试通过

### 历史数据回填验收
- [ ] `parse_revisions` 数据回填完成
- [ ] `binding_revisions` 数据回填完成
- [ ] `chunks` 数据更新完成
- [ ] 数据一致性验证通过

### 测试验收
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 回归测试通过
- [ ] 性能测试通过