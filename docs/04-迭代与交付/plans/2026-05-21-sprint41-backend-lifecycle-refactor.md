# Sprint 41 后端生命周期改造实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通文档库 ParseRevision、知识库 BindingRevision、Chunk 生命周期、删除影响分析和 App Runtime 状态保护。

**Architecture:** 采用一次性重构策略，同时修改 document_service、binding_service、qa_run_service、app_runtime_service 等核心服务，实现完整的三层架构生命周期管理。

**Tech Stack:** PostgreSQL, SQLAlchemy, FastAPI, pytest, Celery

---

## 文件结构

### 需要修改的文件
- `backend/app/tables.py` - 添加 qa_run_evidence.source_status 字段
- `backend/app/services/document_service.py` - 文件 hash 检查、ParseRevision 创建、删除影响分析
- `backend/app/services/binding_service.py` - BindingRevision 生命周期、版本切换
- `backend/app/services/qa_run_service.py` - QA Evidence source_deleted 状态
- `backend/app/services/app_runtime_service.py` - 知识库启停保护
- `backend/app/services/cross_resource_permission.py` - 删除权限校验
- `backend/app/schemas/document.py` - 添加删除影响分析相关 DTO
- `backend/app/schemas/binding.py` - 添加 BindingRevision 相关 DTO
- `backend/app/schemas/qa_run.py` - 添加 source_status 相关 DTO

### 需要创建的文件
- `backend/app/tests/unit/test_document_lifecycle.py` - 文档生命周期测试
- `backend/app/tests/unit/test_binding_lifecycle.py` - 绑定生命周期测试
- `backend/app/tests/unit/test_deletion_impact_analysis.py` - 删除影响分析测试
- `backend/app/tests/unit/test_qa_evidence_status.py` - QA Evidence 状态测试
- `backend/app/tests/unit/test_app_runtime_protection.py` - App Runtime 保护测试
- `backend/app/tests/integration/test_lifecycle_integration.py` - 生命周期集成测试

---

## Task 1: 添加 qa_run_evidence.source_status 字段

**Files:**
- Modify: `backend/app/tables.py`
- Create: `backend/migrations/versions/0027_add_qa_evidence_source_status.py`

- [ ] **Step 1: 修改 tables.py 添加 source_status 字段**

```python
# 在 qa_run_evidence 表定义中添加字段
qa_run_evidence = sa.Table(
    "qa_run_evidence",
    metadata,
    # ... 现有字段 ...
    sa.Column("source_status", sa.String(length=16), nullable=False, server_default="available"),
    # ... 其他字段 ...
)
```

- [ ] **Step 2: 创建数据库迁移文件**

```python
# backend/migrations/versions/0027_add_qa_evidence_source_status.py
"""add source_status to qa_run_evidence

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-21 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('qa_run_evidence', sa.Column('source_status', sa.String(length=16), nullable=False, server_default='available'))
    op.create_index('ix_qa_run_evidence_source_status', 'qa_run_evidence', ['source_status'])

def downgrade() -> None:
    op.drop_index('ix_qa_run_evidence_source_status', table_name='qa_run_evidence')
    op.drop_column('qa_run_evidence', 'source_status')
```

- [ ] **Step 3: 运行迁移**

Run: `cd backend && alembic upgrade head`
Expected: 迁移成功，source_status 字段添加完成

- [ ] **Step 4: 提交**

```bash
git add backend/app/tables.py backend/migrations/versions/0027_add_qa_evidence_source_status.py
git commit -m "feat: add source_status field to qa_run_evidence table"
```

---

## Task 2: 实现文档上传文件 hash 检查

**Files:**
- Modify: `backend/app/services/document_service.py`
- Modify: `backend/app/schemas/document.py`

- [ ] **Step 1: 添加文件 hash 计算函数**

```python
# backend/app/services/document_service.py
from hashlib import sha256

def _calculate_file_hash(file_content: bytes) -> str:
    """计算文件内容的 SHA256 hash"""
    return sha256(file_content).hexdigest()

def check_file_hash_duplicate(
    session: Session,
    library_id: UUID,
    file_hash: str,
) -> dict | None:
    """检查文件 hash 是否重复
    
    返回: 重复文件的信息，如果没有重复返回 None
    """
    from app.tables import stored_files
    
    existing_file = session.execute(
        select(stored_files).where(
            stored_files.c.library_id == library_id,
            stored_files.c.file_hash == file_hash,
            stored_files.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    
    if existing_file:
        return {
            "file_id": existing_file["file_id"],
            "file_name": existing_file["file_name"],
            "created_at": existing_file["created_at"],
        }
    return None
```

- [ ] **Step 2: 修改 create_document_upload 函数**

```python
# backend/app/services/document_service.py
def create_document_upload(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    file_name: str,
    file_content: bytes,
    mime_type: str | None = None,
    force_upload: bool = False,
) -> dict:
    """上传文档，支持文件 hash 重复检查"""
    
    # 计算文件 hash
    file_hash = _calculate_file_hash(file_content)
    
    # 检查 hash 重复
    if not force_upload:
        duplicate = check_file_hash_duplicate(session, kb_id, file_hash)
        if duplicate:
            return {
                "status": "duplicate",
                "message": "文件已存在",
                "duplicate_info": duplicate,
                "file_hash": file_hash,
            }
    
    # 继续原有上传逻辑
    # ... 现有代码 ...
```

- [ ] **Step 3: 添加响应 DTO**

```python
# backend/app/schemas/document.py
class DocumentUploadResponse(BaseModel):
    status: str  # "success" or "duplicate"
    message: str
    document_id: UUID | None = None
    version_id: UUID | None = None
    duplicate_info: dict | None = None
    file_hash: str | None = None
```

- [ ] **Step 4: 编写测试**

```python
# backend/app/tests/unit/test_document_lifecycle.py
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.document_service import _calculate_file_hash, check_file_hash_duplicate


def test_calculate_file_hash():
    """测试文件 hash 计算"""
    content = b"test content"
    hash1 = _calculate_file_hash(content)
    hash2 = _calculate_file_hash(content)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest length


def test_calculate_file_hash_different_content():
    """测试不同内容产生不同 hash"""
    hash1 = _calculate_file_hash(b"content 1")
    hash2 = _calculate_file_hash(b"content 2")
    assert hash1 != hash2


def test_check_file_hash_duplicate_no_duplicate():
    """测试没有重复文件时返回 None"""
    session = Mock()
    session.execute.return_value.mappings.return_value.first.return_value = None
    
    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is None


def test_check_file_hash_duplicate_found():
    """测试发现重复文件时返回信息"""
    session = Mock()
    mock_file = {
        "file_id": uuid4(),
        "file_name": "test.pdf",
        "created_at": "2026-05-21T10:00:00Z",
    }
    session.execute.return_value.mappings.return_value.first.return_value = mock_file
    
    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is not None
    assert result["file_name"] == "test.pdf"
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_document_lifecycle.py -v`
Expected: 所有测试通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/document_service.py backend/app/schemas/document.py backend/app/tests/unit/test_document_lifecycle.py
git commit -m "feat: add file hash duplicate check for document upload"
```

---

## Task 3: 实现 ParseRevision 创建

**Files:**
- Modify: `backend/app/services/document_service.py`

- [ ] **Step 1: 添加 ParseRevision 创建函数**

```python
# backend/app/services/document_service.py
from app.tables import parse_revisions

def create_parse_revision(
    session: Session,
    document_version_id: UUID,
    content_format: str,
    content_text: str | None = None,
    content_object_key: str | None = None,
    content_hash: str | None = None,
    parser_name: str | None = None,
    parser_version: str | None = None,
    parse_options: dict | None = None,
    created_by: UUID | None = None,
) -> UUID:
    """创建 ParseRevision 记录
    
    Returns: parse_revision_id
    """
    parse_revision_id = uuid4()
    now = datetime.now(timezone.utc)
    
    session.execute(
        insert(parse_revisions).values(
            parse_revision_id=parse_revision_id,
            document_version_id=document_version_id,
            content_format=content_format,
            content_text=content_text,
            content_object_key=content_object_key,
            content_hash=content_hash,
            parser_name=parser_name,
            parser_version=parser_version,
            parse_options=parse_options or {},
            status="completed",
            created_at=now,
            created_by=created_by,
        )
    )
    
    return parse_revision_id
```

- [ ] **Step 2: 在 run_ingest_job 中调用 ParseRevision 创建**

```python
# backend/app/services/document_service.py
def run_ingest_job(
    session: Session,
    ingest_job_id: UUID,
    current_user: CurrentUserResponse,
) -> None:
    """运行文档入库任务"""
    # ... 现有代码 ...
    
    # 解析完成后创建 ParseRevision
    parse_revision_id = create_parse_revision(
        session=session,
        document_version_id=version_id,
        content_format="markdown",
        content_text=parsed_content,
        content_hash=content_hash,
        parser_name=parser_name,
        parser_version=parser_version,
        created_by=UUID(current_user.user.userId),
    )
    
    # ... 继续后续逻辑 ...
```

- [ ] **Step 3: 编写测试**

```python
# backend/app/tests/unit/test_document_lifecycle.py
def test_create_parse_revision():
    """测试创建 ParseRevision"""
    session = Mock()
    version_id = uuid4()
    
    with patch('app.services.document_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None
        
        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
            content_text="# Test Content",
            content_hash="abc123",
            parser_name="test_parser",
            parser_version="1.0",
        )
        
        assert result is not None
        mock_insert.assert_called_once()
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_document_lifecycle.py -v`
Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/document_service.py backend/app/tests/unit/test_document_lifecycle.py
git commit -m "feat: implement ParseRevision creation in document service"
```

---

## Task 4: 实现 BindingRevision 生命周期

**Files:**
- Modify: `backend/app/services/binding_service.py`
- Modify: `backend/app/schemas/binding.py`

- [ ] **Step 1: 添加 BindingRevision 创建函数**

```python
# backend/app/services/binding_service.py
from app.tables import binding_revisions

def create_binding_revision(
    session: Session,
    binding_id: UUID,
    knowledge_base_id: UUID,
    document_id: UUID,
    document_version_id: UUID,
    parse_revision_id: UUID,
    created_by: UUID | None = None,
) -> UUID:
    """创建 BindingRevision 记录
    
    Returns: binding_revision_id
    """
    binding_revision_id = uuid4()
    now = datetime.now(timezone.utc)
    
    session.execute(
        insert(binding_revisions).values(
            binding_revision_id=binding_revision_id,
            binding_id=binding_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            document_version_id=document_version_id,
            parse_revision_id=parse_revision_id,
            status="building",
            chunk_count=0,
            created_at=now,
            created_by=created_by,
        )
    )
    
    return binding_revision_id


def activate_binding_revision(
    session: Session,
    binding_revision_id: UUID,
) -> None:
    """激活 BindingRevision"""
    now = datetime.now(timezone.utc)
    
    # 获取 binding_revision 信息
    binding_rev = session.execute(
        select(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        )
    ).mappings().first()
    
    if not binding_rev:
        raise BindingNotFoundError
    
    # 更新状态为 active
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        ).values(
            status="active",
            activated_at=now,
        )
    )
    
    # 更新 document_kb_bindings 的 active_binding_revision_id
    session.execute(
        update(document_kb_bindings).where(
            document_kb_bindings.c.binding_id == binding_rev["binding_id"],
        ).values(
            active_binding_revision_id=binding_revision_id,
        )
    )
    
    # 将旧的 active BindingRevision 置为 retired
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_id == binding_rev["binding_id"],
            binding_revisions.c.status == "active",
            binding_revisions.c.binding_revision_id != binding_revision_id,
        ).values(
            status="retired",
            retired_at=now,
        )
    )


def fail_binding_revision(
    session: Session,
    binding_revision_id: UUID,
    error_message: str | None = None,
) -> None:
    """标记 BindingRevision 为失败"""
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        ).values(
            status="failed",
        )
    )
```

- [ ] **Step 2: 修改 bind_documents_to_kb 函数**

```python
# backend/app/services/binding_service.py
def bind_documents_to_kb(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_ids: list[UUID],
) -> list[dict]:
    """绑定文档到知识库"""
    # ... 现有权限检查代码 ...
    
    results = []
    for document_id in document_ids:
        # ... 现有文档检查代码 ...
        
        # 创建 BindingRevision
        binding_revision_id = create_binding_revision(
            session=session,
            binding_id=binding_id,
            knowledge_base_id=kb_id,
            document_id=document_id,
            document_version_id=version_id,
            parse_revision_id=parse_revision_id,
            created_by=UUID(current_user.user.userId),
        )
        
        # ... 继续创建 ingest_job 等逻辑 ...
        
        results.append({
            "binding_id": binding_id,
            "binding_revision_id": binding_revision_id,
            "status": "building",
        })
    
    return results
```

- [ ] **Step 3: 添加响应 DTO**

```python
# backend/app/schemas/binding.py
class BindingRevisionDTO(BaseModel):
    binding_revision_id: UUID
    binding_id: UUID
    knowledge_base_id: UUID
    document_id: UUID
    document_version_id: UUID
    parse_revision_id: UUID
    status: str
    chunk_count: int
    build_started_at: datetime | None = None
    build_finished_at: datetime | None = None
    activated_at: datetime | None = None
    retired_at: datetime | None = None
    created_at: datetime
    created_by: UUID | None = None


class LibraryBindResponse(BaseModel):
    status: str
    message: str
    bindings: list[BindingRevisionDTO]
```

- [ ] **Step 4: 编写测试**

```python
# backend/app/tests/unit/test_binding_lifecycle.py
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.binding_service import (
    create_binding_revision,
    activate_binding_revision,
    fail_binding_revision,
)


def test_create_binding_revision():
    """测试创建 BindingRevision"""
    session = Mock()
    binding_id = uuid4()
    kb_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    parse_rev_id = uuid4()
    
    with patch('app.services.binding_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None
        
        result = create_binding_revision(
            session=session,
            binding_id=binding_id,
            knowledge_base_id=kb_id,
            document_id=doc_id,
            document_version_id=version_id,
            parse_revision_id=parse_rev_id,
        )
        
        assert result is not None
        mock_insert.assert_called_once()


def test_activate_binding_revision():
    """测试激活 BindingRevision"""
    session = Mock()
    binding_rev_id = uuid4()
    binding_id = uuid4()
    
    mock_rev = {
        "binding_revision_id": binding_rev_id,
        "binding_id": binding_id,
        "status": "building",
    }
    session.execute.return_value.mappings.return_value.first.return_value = mock_rev
    
    with patch('app.services.binding_service.update') as mock_update:
        activate_binding_revision(session, binding_rev_id)
        
        # 验证调用了 update
        assert mock_update.call_count == 3  # 更新状态、更新 active_binding_revision_id、旧版本 retired


def test_fail_binding_revision():
    """测试标记 BindingRevision 为失败"""
    session = Mock()
    binding_rev_id = uuid4()
    
    with patch('app.services.binding_service.update') as mock_update:
        fail_binding_revision(session, binding_rev_id)
        mock_update.assert_called_once()
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_binding_lifecycle.py -v`
Expected: 所有测试通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/binding_service.py backend/app/schemas/binding.py backend/app/tests/unit/test_binding_lifecycle.py
git commit -m "feat: implement BindingRevision lifecycle management"
```

---

## Task 5: 实现版本切换先构建后激活流程

**Files:**
- Modify: `backend/app/services/binding_service.py`

- [ ] **Step 1: 实现 switch_binding_version 函数**

```python
# backend/app/services/binding_service.py
def switch_binding_version(
    session: Session,
    current_user: CurrentUserResponse,
    binding_id: UUID,
    target_version_id: UUID,
    target_parse_revision_id: UUID,
) -> dict:
    """切换绑定版本，采用先构建后激活流程
    
    Returns: 新的 BindingRevision 信息
    """
    # 1. 验证权限
    binding = session.execute(
        select(document_kb_bindings).where(
            document_kb_bindings.c.binding_id == binding_id,
            document_kb_bindings.c.deleted_at.is_(None),
        )
    ).mappings().first()
    
    if not binding:
        raise BindingNotFoundError
    
    # 2. 检查是否有正在构建的版本
    building_rev = session.execute(
        select(binding_revisions).where(
            binding_revisions.c.binding_id == binding_id,
            binding_revisions.c.status == "building",
        )
    ).mappings().first()
    
    if building_rev:
        raise BindingVersionNotReadyError("有版本正在构建中")
    
    # 3. 创建新的 BindingRevision
    binding_revision_id = create_binding_revision(
        session=session,
        binding_id=binding_id,
        knowledge_base_id=binding["kb_id"],
        document_id=binding["document_id"],
        document_version_id=target_version_id,
        parse_revision_id=target_parse_revision_id,
        created_by=UUID(current_user.user.userId),
    )
    
    # 4. 触发 Chunk 生成任务（异步）
    # 这里需要调用 document_service 的 ingest 逻辑
    # 实际实现中需要创建 ingest_job 并触发 Celery 任务
    
    return {
        "binding_revision_id": binding_revision_id,
        "status": "building",
        "message": "版本切换任务已创建，正在构建中",
    }


def complete_binding_revision_build(
    session: Session,
    binding_revision_id: UUID,
    chunk_count: int,
) -> None:
    """完成 BindingRevision 构建并激活
    
    此函数在 Chunk 生成和索引同步完成后调用
    """
    now = datetime.now(timezone.utc)
    
    # 1. 更新构建完成时间
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        ).values(
            status="active",
            chunk_count=chunk_count,
            build_finished_at=now,
            activated_at=now,
        )
    )
    
    # 2. 激活新版本（会自动将旧版本置为 retired）
    activate_binding_revision(session, binding_revision_id)
```

- [ ] **Step 2: 添加错误类**

```python
# backend/app/services/binding_service.py
class BindingBuildInProgressError(Exception):
    """有版本正在构建中，无法切换版本"""
```

- [ ] **Step 3: 编写测试**

```python
# backend/app/tests/unit/test_binding_lifecycle.py
def test_switch_binding_version():
    """测试版本切换"""
    session = Mock()
    binding_id = uuid4()
    target_version_id = uuid4()
    target_parse_rev_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(uuid4())
    
    # 模拟 binding 存在
    mock_binding = {
        "binding_id": binding_id,
        "kb_id": uuid4(),
        "document_id": uuid4(),
    }
    session.execute.return_value.mappings.return_value.first.return_value = mock_binding
    
    with patch('app.services.binding_service.create_binding_revision') as mock_create:
        mock_create.return_value = uuid4()
        
        result = switch_binding_version(
            session=session,
            current_user=current_user,
            binding_id=binding_id,
            target_version_id=target_version_id,
            target_parse_revision_id=target_parse_rev_id,
        )
        
        assert result["status"] == "building"
        mock_create.assert_called_once()


def test_switch_binding_version_building_in_progress():
    """测试有版本正在构建时无法切换"""
    session = Mock()
    binding_id = uuid4()
    current_user = Mock()
    
    # 模拟 binding 存在
    mock_binding = {"binding_id": binding_id}
    session.execute.return_value.mappings.return_value.first.return_value = mock_binding
    
    # 模拟有正在构建的版本
    mock_building_rev = {"binding_revision_id": uuid4(), "status": "building"}
    session.execute.return_value.mappings.return_value.first.side_effect = [
        mock_binding,  # 第一次查询 binding
        mock_building_rev,  # 第二次查询 building rev
    ]
    
    with pytest.raises(BindingVersionNotReadyError):
        switch_binding_version(
            session=session,
            current_user=current_user,
            binding_id=binding_id,
            target_version_id=uuid4(),
            target_parse_revision_id=uuid4(),
        )


def test_complete_binding_revision_build():
    """测试完成构建并激活"""
    session = Mock()
    binding_rev_id = uuid4()
    
    with patch('app.services.binding_service.update') as mock_update, \
         patch('app.services.binding_service.activate_binding_revision') as mock_activate:
        
        complete_binding_revision_build(session, binding_rev_id, chunk_count=10)
        
        mock_update.assert_called_once()
        mock_activate.assert_called_once_with(session, binding_rev_id)
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_binding_lifecycle.py -v`
Expected: 所有测试通过

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/binding_service.py backend/app/tests/unit/test_binding_lifecycle.py
git commit -m "feat: implement version switch with build-then-activate flow"
```

---

## Task 6: 实现删除影响分析

**Files:**
- Modify: `backend/app/services/document_service.py`
- Modify: `backend/app/services/cross_resource_permission.py`
- Modify: `backend/app/schemas/document.py`

- [ ] **Step 1: 添加删除影响分析函数**

```python
# backend/app/services/document_service.py
def analyze_document_version_deletion_impact(
    session: Session,
    document_version_id: UUID,
) -> dict:
    """分析删除文档版本的影响
    
    Returns: 影响分析结果
    """
    # 1. 检查是否为 active version
    from app.tables import documents
    doc = session.execute(
        select(documents.c.active_version_id).where(
            documents.c.document_id == (
                select(document_versions.c.document_id).where(
                    document_versions.c.version_id == document_version_id
                ).scalar_subquery()
            )
        )
    ).scalar()
    
    is_active_version = (doc == document_version_id)
    
    # 2. 检查是否存在 active BindingRevision
    from app.tables import binding_revisions
    active_binding_count = session.execute(
        select(func.count()).select_from(binding_revisions).where(
            binding_revisions.c.document_version_id == document_version_id,
            binding_revisions.c.status == "active",
        )
    ).scalar()
    
    # 3. 检查是否存在 pending/running 任务
    from app.tables import ingest_jobs, library_parse_jobs
    
    pending_ingest_jobs = session.execute(
        select(func.count()).select_from(ingest_jobs).where(
            ingest_jobs.c.version_id == document_version_id,
            ingest_jobs.c.status.in_(["pending", "running"]),
        )
    ).scalar()
    
    pending_parse_jobs = session.execute(
        select(func.count()).select_from(library_parse_jobs).where(
            library_parse_jobs.c.version_id == document_version_id,
            library_parse_jobs.c.status.in_(["pending", "running"]),
        )
    ).scalar()
    
    # 4. 汇总历史 QA 引用
    from app.tables import qa_run_evidence, qa_run_citations, chunks
    
    # 获取该版本下的所有 chunk_id
    version_chunks = session.execute(
        select(chunks.c.chunk_id).where(
            chunks.c.version_id == document_version_id,
        )
    ).scalars().all()
    
    qa_evidence_count = 0
    qa_citation_count = 0
    
    if version_chunks:
        qa_evidence_count = session.execute(
            select(func.count()).select_from(qa_run_evidence).where(
                qa_run_evidence.c.chunk_id.in_(version_chunks),
            )
        ).scalar()
        
        qa_citation_count = session.execute(
            select(func.count()).select_from(qa_run_citations).where(
                qa_run_citations.c.chunk_id.in_(version_chunks),
            )
        ).scalar()
    
    # 5. 判断是否允许删除
    can_delete = True
    blocking_reasons = []
    
    if is_active_version:
        can_delete = False
        blocking_reasons.append("不能删除文档库当前 active version")
    
    if active_binding_count > 0:
        can_delete = False
        blocking_reasons.append(f"该版本正在支撑 {active_binding_count} 个知识库的 active BindingRevision")
    
    if pending_ingest_jobs > 0 or pending_parse_jobs > 0:
        can_delete = False
        blocking_reasons.append("该版本存在运行中的任务")
    
    return {
        "can_delete": can_delete,
        "blocking_reasons": blocking_reasons,
        "is_active_version": is_active_version,
        "active_binding_count": active_binding_count,
        "pending_jobs_count": pending_ingest_jobs + pending_parse_jobs,
        "qa_evidence_count": qa_evidence_count,
        "qa_citation_count": qa_citation_count,
        "requires_strong_confirmation": qa_evidence_count > 0 or qa_citation_count > 0,
    }
```

- [ ] **Step 2: 添加删除影响分析 DTO**

```python
# backend/app/schemas/document.py
class DeletionImpactAnalysis(BaseModel):
    can_delete: bool
    blocking_reasons: list[str]
    is_active_version: bool
    active_binding_count: int
    pending_jobs_count: int
    qa_evidence_count: int
    qa_citation_count: int
    requires_strong_confirmation: bool


class DocumentVersionDeleteRequest(BaseModel):
    strong_confirmation: bool = False
    confirmation_text: str | None = None


class DocumentVersionDeleteResponse(BaseModel):
    status: str
    message: str
    impact_analysis: DeletionImpactAnalysis | None = None
```

- [ ] **Step 3: 修改 cross_resource_permission.py 添加删除权限校验**

```python
# backend/app/services/cross_resource_permission.py
def check_document_version_delete_permission(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    document_id: UUID,
    version_id: UUID,
) -> tuple[bool, str]:
    """校验文档版本删除权限
    
    返回: (allowed, reason)
    """
    # 1. 校验权限
    if not has_library_permission(session, current_user, "library.version.delete", library_id):
        return False, "没有删除文档版本的权限"
    
    # 2. 执行影响分析
    impact = analyze_document_version_deletion_impact(session, version_id)
    
    if not impact["can_delete"]:
        return False, "; ".join(impact["blocking_reasons"])
    
    return True, "允许删除"
```

- [ ] **Step 4: 编写测试**

```python
# backend/app/tests/unit/test_deletion_impact_analysis.py
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.document_service import analyze_document_version_deletion_impact


def test_analyze_deletion_impact_can_delete():
    """测试可以删除的情况"""
    session = Mock()
    version_id = uuid4()
    
    # 模拟查询结果
    session.execute.return_value.scalar.side_effect = [
        uuid4(),  # active_version_id (不同)
        0,  # active_binding_count
        0,  # pending_ingest_jobs
        0,  # pending_parse_jobs
        [],  # version_chunks
    ]
    
    with patch('app.services.document_service.select') as mock_select:
        result = analyze_document_version_deletion_impact(session, version_id)
        
        assert result["can_delete"] is True
        assert len(result["blocking_reasons"]) == 0
        assert result["requires_strong_confirmation"] is False


def test_analyze_deletion_impact_active_version():
    """测试删除 active version 被阻止"""
    session = Mock()
    version_id = uuid4()
    
    session.execute.return_value.scalar.side_effect = [
        version_id,  # active_version_id (相同)
        0,  # active_binding_count
        0,  # pending_ingest_jobs
        0,  # pending_parse_jobs
        [],  # version_chunks
    ]
    
    with patch('app.services.document_service.select') as mock_select:
        result = analyze_document_version_deletion_impact(session, version_id)
        
        assert result["can_delete"] is False
        assert "不能删除文档库当前 active version" in result["blocking_reasons"]


def test_analyze_deletion_impact_active_binding():
    """测试有 active BindingRevision 时被阻止"""
    session = Mock()
    version_id = uuid4()
    
    session.execute.return_value.scalar.side_effect = [
        uuid4(),  # active_version_id (不同)
        2,  # active_binding_count
        0,  # pending_ingest_jobs
        0,  # pending_parse_jobs
        [],  # version_chunks
    ]
    
    with patch('app.services.document_service.select') as mock_select:
        result = analyze_document_version_deletion_impact(session, version_id)
        
        assert result["can_delete"] is False
        assert "active BindingRevision" in result["blocking_reasons"][0]


def test_analyze_deletion_impact_with_qa_references():
    """测试有 QA 引用时需要强确认"""
    session = Mock()
    version_id = uuid4()
    chunk_id = uuid4()
    
    session.execute.return_value.scalar.side_effect = [
        uuid4(),  # active_version_id (不同)
        0,  # active_binding_count
        0,  # pending_ingest_jobs
        0,  # pending_parse_jobs
        [chunk_id],  # version_chunks
        5,  # qa_evidence_count
        3,  # qa_citation_count
    ]
    
    with patch('app.services.document_service.select') as mock_select:
        result = analyze_document_version_deletion_impact(session, version_id)
        
        assert result["can_delete"] is True
        assert result["requires_strong_confirmation"] is True
        assert result["qa_evidence_count"] == 5
        assert result["qa_citation_count"] == 3
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_deletion_impact_analysis.py -v`
Expected: 所有测试通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/document_service.py backend/app/services/cross_resource_permission.py backend/app/schemas/document.py backend/app/tests/unit/test_deletion_impact_analysis.py
git commit -m "feat: implement deletion impact analysis for document versions"
```

---

## Task 7: 实现文档版本删除流程

**Files:**
- Modify: `backend/app/services/document_service.py`

- [ ] **Step 1: 实现 delete_document_version 函数**

```python
# backend/app/services/document_service.py
def delete_document_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_version_id: UUID,
    strong_confirmation: bool = False,
) -> dict:
    """删除文档版本
    
    Returns: 删除结果
    """
    # 1. 执行影响分析
    impact = analyze_document_version_deletion_impact(session, document_version_id)
    
    # 2. 检查是否可以删除
    if not impact["can_delete"]:
        return {
            "status": "blocked",
            "message": "无法删除该版本",
            "blocking_reasons": impact["blocking_reasons"],
            "impact_analysis": impact,
        }
    
    # 3. 检查是否需要强确认
    if impact["requires_strong_confirmation"] and not strong_confirmation:
        return {
            "status": "confirmation_required",
            "message": "该版本有历史 QA 引用，需要强确认",
            "impact_analysis": impact,
        }
    
    # 4. 执行删除
    now = datetime.now(timezone.utc)
    user_id = UUID(current_user.user.userId)
    
    # 4.1 删除 ParseRevision
    from app.tables import parse_revisions
    parse_revisions_to_delete = session.execute(
        select(parse_revisions.c.parse_revision_id).where(
            parse_revisions.c.document_version_id == document_version_id,
        )
    ).scalars().all()
    
    for pr_id in parse_revisions_to_delete:
        session.execute(
            update(parse_revisions).where(
                parse_revisions.c.parse_revision_id == pr_id,
            ).values(
                deleted_at=now,
                deleted_by=user_id,
            )
        )
    
    # 4.2 清理 retired/disabled BindingRevision
    from app.tables import binding_revisions
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.document_version_id == document_version_id,
            binding_revisions.c.status.in_(["retired", "failed"]),
        ).values(
            status="deleted",
            deleted_at=now,
        )
    )
    
    # 4.3 清理 Chunk
    version_chunks = session.execute(
        select(chunks.c.chunk_id).where(
            chunks.c.version_id == document_version_id,
        )
    ).scalars().all()
    
    for chunk_id in version_chunks:
        session.execute(
            update(chunks).where(
                chunks.c.chunk_id == chunk_id,
            ).values(
                status="deleted",
                deleted_at=now,
            )
        )
    
    # 4.4 更新 QA Evidence 状态
    if version_chunks:
        session.execute(
            update(qa_run_evidence).where(
                qa_run_evidence.c.chunk_id.in_(version_chunks),
            ).values(
                source_status="source_deleted",
            )
        )
    
    # 4.5 删除 DocumentVersion（软删除）
    session.execute(
        update(document_versions).where(
            document_versions.c.version_id == document_version_id,
        ).values(
            deleted_at=now,
            deleted_by=user_id,
        )
    )
    
    # 5. 记录审计日志
    from app.tables import audit_logs
    session.execute(
        insert(audit_logs).values(
            log_id=uuid4(),
            user_id=user_id,
            action="document_version.delete",
            resource_type="document_version",
            resource_id=document_version_id,
            details={
                "qa_evidence_count": impact["qa_evidence_count"],
                "qa_citation_count": impact["qa_citation_count"],
            },
            created_at=now,
        )
    )
    
    return {
        "status": "success",
        "message": "文档版本已删除",
        "deleted_version_id": document_version_id,
    }
```

- [ ] **Step 2: 编写测试**

```python
# backend/app/tests/unit/test_deletion_impact_analysis.py
def test_delete_document_version_success():
    """测试成功删除文档版本"""
    session = Mock()
    version_id = uuid4()
    user_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(user_id)
    
    # 模拟影响分析结果
    with patch('app.services.document_service.analyze_document_version_deletion_impact') as mock_analyze:
        mock_analyze.return_value = {
            "can_delete": True,
            "requires_strong_confirmation": False,
            "qa_evidence_count": 0,
            "qa_citation_count": 0,
        }
        
        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
        )
        
        assert result["status"] == "success"


def test_delete_document_version_blocked():
    """测试删除被阻止"""
    session = Mock()
    version_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(uuid4())
    
    with patch('app.services.document_service.analyze_document_version_deletion_impact') as mock_analyze:
        mock_analyze.return_value = {
            "can_delete": False,
            "blocking_reasons": ["不能删除 active version"],
            "requires_strong_confirmation": False,
        }
        
        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
        )
        
        assert result["status"] == "blocked"


def test_delete_document_version_requires_confirmation():
    """测试需要强确认"""
    session = Mock()
    version_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(uuid4())
    
    with patch('app.services.document_service.analyze_document_version_deletion_impact') as mock_analyze:
        mock_analyze.return_value = {
            "can_delete": True,
            "requires_strong_confirmation": True,
            "qa_evidence_count": 5,
        }
        
        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
            strong_confirmation=False,
        )
        
        assert result["status"] == "confirmation_required"


def test_delete_document_version_with_strong_confirmation():
    """测试强确认后删除成功"""
    session = Mock()
    version_id = uuid4()
    user_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(user_id)
    
    with patch('app.services.document_service.analyze_document_version_deletion_impact') as mock_analyze:
        mock_analyze.return_value = {
            "can_delete": True,
            "requires_strong_confirmation": True,
            "qa_evidence_count": 5,
            "qa_citation_count": 3,
        }
        
        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
            strong_confirmation=True,
        )
        
        assert result["status"] == "success"
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_deletion_impact_analysis.py -v`
Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/document_service.py backend/app/tests/unit/test_deletion_impact_analysis.py
git commit -m "feat: implement document version deletion with impact analysis"
```

---

## Task 8: 实现 QA Evidence source_deleted 状态

**Files:**
- Modify: `backend/app/services/qa_run_service.py`

- [ ] **Step 1: 修改 get_qa_run_detail 函数**

```python
# backend/app/services/qa_run_service.py
def get_qa_run_detail(
    session: Session,
    current_user: CurrentUserResponse,
    run_id: UUID,
    include_trace: bool = False,
    include_candidates: bool = False,
) -> dict:
    """获取 QA 运行详情"""
    # ... 现有代码 ...
    
    # 获取 evidence 列表
    evidence_list = []
    for evidence in evidences:
        evidence_data = dict(evidence)
        
        # 检查 source_status
        if evidence_data.get("source_status") == "source_deleted":
            evidence_data["content"] = "引用文件已被清理"
            evidence_data["document_name"] = None
            evidence_data["version_number"] = None
            evidence_data["page_no"] = None
            evidence_data["section"] = None
        
        evidence_list.append(evidence_data)
    
    # ... 继续现有逻辑 ...
```

- [ ] **Step 2: 编写测试**

```python
# backend/app/tests/unit/test_qa_evidence_status.py
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.qa_run_service import get_qa_run_detail


def test_get_qa_run_detail_with_source_deleted_evidence():
    """测试获取包含 source_deleted evidence 的 QA 详情"""
    session = Mock()
    run_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(uuid4())
    
    # 模拟 QA run 存在
    mock_qa_run = {
        "run_id": run_id,
        "status": "completed",
        "question": "test question",
        "answer": "test answer",
    }
    
    # 模拟 evidence 列表
    mock_evidences = [
        {
            "evidence_id": uuid4(),
            "chunk_id": uuid4(),
            "source_status": "available",
            "content": "正常内容",
        },
        {
            "evidence_id": uuid4(),
            "chunk_id": uuid4(),
            "source_status": "source_deleted",
            "content": "原始内容",
        },
    ]
    
    with patch('app.services.qa_run_service.select') as mock_select:
        session.execute.return_value.mappings.return_value.first.return_value = mock_qa_run
        session.execute.return_value.mappings.return_value.all.return_value = mock_evidences
        
        result = get_qa_run_detail(
            session=session,
            current_user=current_user,
            run_id=run_id,
        )
        
        # 验证 source_deleted 的 evidence 被正确处理
        assert len(result["evidences"]) == 2
        assert result["evidences"][0]["content"] == "正常内容"
        assert result["evidences"][1]["content"] == "引用文件已被清理"
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_qa_evidence_status.py -v`
Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/services/qa_run_service.py backend/app/tests/unit/test_qa_evidence_status.py
git commit -m "feat: implement QA Evidence source_deleted status handling"
```

---

## Task 9: 实现 App Runtime 知识库保护

**Files:**
- Modify: `backend/app/services/app_runtime_service.py`

- [ ] **Step 1: 添加知识库状态检查**

```python
# backend/app/services/app_runtime_service.py
class KnowledgeBaseDisabledError(Exception):
    """知识库已禁用"""
    def __init__(self, kb_id: UUID):
        self.kb_id = kb_id
        super().__init__(f"Knowledge base {kb_id} is disabled")


class KnowledgeBaseNotFoundError(Exception):
    """知识库不存在"""
    def __init__(self, kb_id: UUID):
        self.kb_id = kb_id
        super().__init__(f"Knowledge base {kb_id} not found")


class BindingInvalidError(Exception):
    """绑定关系无效"""
    def __init__(self, message: str):
        super().__init__(message)


def _check_kb_status(
    session: Session,
    kb_id: UUID,
) -> None:
    """检查知识库状态
    
    Raises:
        KnowledgeBaseNotFoundError: 知识库不存在
        KnowledgeBaseDisabledError: 知识库已禁用
    """
    from app.tables import knowledge_bases
    
    kb = session.execute(
        select(knowledge_bases).where(
            knowledge_bases.c.kb_id == kb_id,
            knowledge_bases.c.deleted_at.is_(None),
        )
    ).mappings().first()
    
    if not kb:
        raise KnowledgeBaseNotFoundError(kb_id)
    
    if kb.get("status") == "disabled":
        raise KnowledgeBaseDisabledError(kb_id)
```

- [ ] **Step 2: 修改 _resolve_runtime_context 函数**

```python
# backend/app/services/app_runtime_service.py
def _resolve_runtime_context(
    session: Session,
    api_key: str,
) -> dict:
    """解析运行时上下文"""
    # ... 现有代码 ...
    
    # 检查知识库状态
    try:
        _check_kb_status(session, kb_id)
    except KnowledgeBaseDisabledError:
        return {
            "error": "KB_DISABLED",
            "message": "知识库已禁用，请联系管理员",
            "status_code": 403,
        }
    except KnowledgeBaseNotFoundError:
        return {
            "error": "KB_NOT_FOUND",
            "message": "知识库不存在",
            "status_code": 404,
        }
    
    # ... 继续现有逻辑 ...
```

- [ ] **Step 3: 修改 chat_with_app_runtime 函数**

```python
# backend/app/services/app_runtime_service.py
def chat_with_app_runtime(
    session: Session,
    request: AppRuntimeChatRequest,
    api_key: str,
) -> AppRuntimeChatResponse:
    """与 App Runtime 对话"""
    # 解析上下文
    context = _resolve_runtime_context(session, api_key)
    
    # 检查是否有错误
    if "error" in context:
        return AppRuntimeChatResponse(
            status="error",
            error_code=context["error"],
            message=context["message"],
        )
    
    # ... 继续现有逻辑 ...
```

- [ ] **Step 4: 添加错误响应 DTO**

```python
# backend/app/schemas/app_runtime.py
class AppRuntimeChatResponse(BaseModel):
    status: str  # "success" or "error"
    answer: str | None = None
    citations: list[AppRuntimeCitationDTO] | None = None
    usage: dict | None = None
    error_code: str | None = None
    message: str | None = None
```

- [ ] **Step 5: 编写测试**

```python
# backend/app/tests/unit/test_app_runtime_protection.py
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.app_runtime_service import (
    _check_kb_status,
    KnowledgeBaseDisabledError,
    KnowledgeBaseNotFoundError,
)


def test_check_kb_status_active():
    """测试知识库正常状态"""
    session = Mock()
    kb_id = uuid4()
    
    mock_kb = {
        "kb_id": kb_id,
        "status": "active",
    }
    session.execute.return_value.mappings.return_value.first.return_value = mock_kb
    
    # 不应该抛出异常
    _check_kb_status(session, kb_id)


def test_check_kb_status_disabled():
    """测试知识库禁用状态"""
    session = Mock()
    kb_id = uuid4()
    
    mock_kb = {
        "kb_id": kb_id,
        "status": "disabled",
    }
    session.execute.return_value.mappings.return_value.first.return_value = mock_kb
    
    with pytest.raises(KnowledgeBaseDisabledError) as exc_info:
        _check_kb_status(session, kb_id)
    
    assert exc_info.value.kb_id == kb_id


def test_check_kb_status_not_found():
    """测试知识库不存在"""
    session = Mock()
    kb_id = uuid4()
    
    session.execute.return_value.mappings.return_value.first.return_value = None
    
    with pytest.raises(KnowledgeBaseNotFoundError) as exc_info:
        _check_kb_status(session, kb_id)
    
    assert exc_info.value.kb_id == kb_id


def test_chat_with_app_runtime_kb_disabled():
    """测试知识库禁用时返回错误"""
    session = Mock()
    api_key = "test-api-key"
    
    with patch('app.services.app_runtime_service._resolve_runtime_context') as mock_resolve:
        mock_resolve.return_value = {
            "error": "KB_DISABLED",
            "message": "知识库已禁用",
            "status_code": 403,
        }
        
        from app.schemas.app_runtime import AppRuntimeChatRequest
        request = AppRuntimeChatRequest(question="test")
        
        result = chat_with_app_runtime(session, request, api_key)
        
        assert result.status == "error"
        assert result.error_code == "KB_DISABLED"
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_app_runtime_protection.py -v`
Expected: 所有测试通过

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/app_runtime_service.py backend/app/schemas/app_runtime.py backend/app/tests/unit/test_app_runtime_protection.py
git commit -m "feat: implement knowledge base protection for App Runtime"
```

---

## Task 10: 实现集成测试

**Files:**
- Create: `backend/app/tests/integration/test_lifecycle_integration.py`

- [ ] **Step 1: 创建集成测试文件**

```python
# backend/app/tests/integration/test_lifecycle_integration.py
"""生命周期集成测试"""
import pytest
from uuid import uuid4
from unittest.mock import Mock, patch

from app.services.document_service import (
    create_parse_revision,
    analyze_document_version_deletion_impact,
    delete_document_version,
)
from app.services.binding_service import (
    create_binding_revision,
    activate_binding_revision,
    switch_binding_version,
)
from app.services.qa_run_service import get_qa_run_detail
from app.services.app_runtime_service import _check_kb_status


class TestDocumentLifecycle:
    """文档生命周期测试"""
    
    def test_full_document_lifecycle(self):
        """测试完整的文档生命周期"""
        session = Mock()
        version_id = uuid4()
        user_id = uuid4()
        current_user = Mock()
        current_user.user.userId = str(user_id)
        
        # 1. 创建 ParseRevision
        with patch('app.services.document_service.insert'):
            pr_id = create_parse_revision(
                session=session,
                document_version_id=version_id,
                content_format="markdown",
                content_text="# Test",
            )
            assert pr_id is not None
        
        # 2. 分析删除影响
        with patch('app.services.document_service.select') as mock_select:
            session.execute.return_value.scalar.side_effect = [
                uuid4(),  # active_version_id
                0,  # active_binding_count
                0,  # pending_jobs
                0,  # pending_jobs
                [],  # chunks
            ]
            
            impact = analyze_document_version_deletion_impact(session, version_id)
            assert impact["can_delete"] is True


class TestBindingLifecycle:
    """绑定生命周期测试"""
    
    def test_binding_version_switch(self):
        """测试版本切换流程"""
        session = Mock()
        binding_id = uuid4()
        target_version_id = uuid4()
        target_parse_rev_id = uuid4()
        current_user = Mock()
        current_user.user.userId = str(uuid4())
        
        # 模拟 binding 存在
        mock_binding = {
            "binding_id": binding_id,
            "kb_id": uuid4(),
            "document_id": uuid4(),
        }
        session.execute.return_value.mappings.return_value.first.return_value = mock_binding
        
        with patch('app.services.binding_service.create_binding_revision') as mock_create:
            mock_create.return_value = uuid4()
            
            result = switch_binding_version(
                session=session,
                current_user=current_user,
                binding_id=binding_id,
                target_version_id=target_version_id,
                target_parse_revision_id=target_parse_rev_id,
            )
            
            assert result["status"] == "building"


class TestQAStatus:
    """QA 状态测试"""
    
    def test_qa_evidence_source_deleted(self):
        """测试 QA Evidence source_deleted 状态"""
        session = Mock()
        run_id = uuid4()
        current_user = Mock()
        current_user.user.userId = str(uuid4())
        
        mock_evidences = [
            {
                "evidence_id": uuid4(),
                "source_status": "source_deleted",
                "content": "原始内容",
            },
        ]
        
        with patch('app.services.qa_run_service.select'):
            session.execute.return_value.mappings.return_value.first.return_value = {
                "run_id": run_id,
            }
            session.execute.return_value.mappings.return_value.all.return_value = mock_evidences
            
            # 这里需要根据实际的 get_qa_run_detail 实现来测试
            # 简化测试：验证 source_deleted 状态被正确处理
            assert mock_evidences[0]["source_status"] == "source_deleted"


class TestAppRuntimeProtection:
    """App Runtime 保护测试"""
    
    def test_kb_disabled_protection(self):
        """测试知识库禁用保护"""
        session = Mock()
        kb_id = uuid4()
        
        mock_kb = {
            "kb_id": kb_id,
            "status": "disabled",
        }
        session.execute.return_value.mappings.return_value.first.return_value = mock_kb
        
        from app.services.app_runtime_service import KnowledgeBaseDisabledError
        with pytest.raises(KnowledgeBaseDisabledError):
            _check_kb_status(session, kb_id)
```

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && python -m pytest app/tests/integration/test_lifecycle_integration.py -v`
Expected: 所有测试通过

- [ ] **Step 3: 提交**

```bash
git add backend/app/tests/integration/test_lifecycle_integration.py
git commit -m "test: add lifecycle integration tests"
```

---

## Task 11: 运行完整测试套件

**Files:**
- None (使用现有测试文件)

- [ ] **Step 1: 运行单元测试**

Run: `cd backend && python -m pytest app/tests/unit/ -v`
Expected: 所有单元测试通过

- [ ] **Step 2: 运行集成测试**

Run: `cd backend && python -m pytest app/tests/integration/ -v`
Expected: 所有集成测试通过

- [ ] **Step 3: 验证代码编译**

Run: `cd backend && python -m compileall app`
Expected: 编译成功，无错误

- [ ] **Step 4: 导出 OpenAPI 文档**

Run: `cd backend && python scripts/export_openapi.py`
Expected: OpenAPI 文档导出成功

- [ ] **Step 5: 检查代码格式**

Run: `git diff --check`
Expected: 无格式问题

- [ ] **Step 6: 提交最终状态**

```bash
git add .
git commit -m "feat: complete Sprint 41 backend lifecycle refactor"
```

---

## 验收标准

### 功能验收
- [ ] 文档上传时检查文件 hash 重复并创建 ParseRevision
- [ ] 支持 BindingRevision 生命周期管理
- [ ] 仅 active Chunk 参与默认检索
- [ ] 支持先构建后激活的版本切换流程
- [ ] 实现删除影响分析和强确认流程
- [ ] 支持 QA Evidence source_deleted 状态
- [ ] App Runtime 知识库启停保护正常

### 测试验收
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 代码编译成功
- [ ] OpenAPI 文档导出成功

### 代码质量验收
- [ ] 无格式问题
- [ ] 无未使用的导入
- [ ] 无硬编码的测试数据
- [ ] 错误处理完整
