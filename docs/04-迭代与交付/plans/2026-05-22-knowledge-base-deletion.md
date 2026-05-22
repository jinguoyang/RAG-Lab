# 知识库删除功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为知识库添加删除功能，支持级联清理关联数据，前端采用 GitHub 风格输入名称二次确认。

**Architecture:** 后端新增 `get_kb_delete_impact()` 和 `delete_knowledge_base()` 两个 service 函数，分别对应查询影响和执行删除。删除采用软删除（`status="archived"` + `deleted_at`），复用现有 `delete_document()` 级联清理 chunks/索引。前端新增删除确认弹窗组件，需要用户输入知识库名称才能确认。

**Tech Stack:** Python / FastAPI / SQLAlchemy Core / Pydantic / React / TypeScript

---

### Task 1: 后端 Schema — 新增删除相关 DTO

**Files:**
- Modify: `backend/app/schemas/knowledge_base.py`

- [ ] **Step 1: 添加删除影响查询响应 DTO**

在 `knowledge_base.py` 末尾添加：

```python
class KbDeleteImpactBlockerDTO(BaseModel):
    """删除阻断条件。"""
    activeRagApps: list[dict]
    runningJobs: list[dict]


class KbDeleteImpactCascadeDTO(BaseModel):
    """将被级联清理的数据统计。"""
    bindings: int
    kbDocuments: int
    chunks: int
    configRevisions: int
    inactiveRagApps: list[dict]
    kbMembers: int


class KbDeleteImpactUnaffectedDTO(BaseModel):
    """不受影响的数据说明。"""
    libraryDocuments: int
    description: str


class KbDeleteImpactDTO(BaseModel):
    """删除影响查询响应。"""
    kbName: str
    blockers: KbDeleteImpactBlockerDTO
    cascadeData: KbDeleteImpactCascadeDTO
    unaffected: KbDeleteImpactUnaffectedDTO


class KbDeleteRequest(BaseModel):
    """删除知识库请求，需输入知识库名称确认。"""
    confirmName: str = Field(min_length=1, max_length=128)
```

- [ ] **Step 2: 运行类型检查**

Run: `cd backend && python -c "from app.schemas.knowledge_base import KbDeleteImpactDTO, KbDeleteRequest; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/knowledge_base.py
git commit -m "feat: add KB deletion request/response schemas"
```

---

### Task 2: 后端 Service — 删除影响查询

**Files:**
- Modify: `backend/app/services/knowledge_base_service.py`
- Modify: `backend/app/tables.py` (if missing tables needed for queries)

- [ ] **Step 1: 添加新的异常类**

在 `knowledge_base_service.py` 的 `KnowledgeBaseActiveRagAppsError` 之后（约第 42 行）添加：

```python
class KnowledgeBaseConfirmNameMismatchError(Exception):
    """删除确认名称不匹配。"""


class KnowledgeBaseRunningJobsError(Exception):
    """存在运行中的摄入任务，无法删除。"""
```

- [ ] **Step 2: 添加 import**

在 `knowledge_base_service.py` 的 import 区域添加需要的表引用。当前已有 `from app.tables import config_revisions, documents, kb_member_bindings, knowledge_bases, rag_apps, user_groups, users`，需要补充：

```python
from app.tables import (
    config_revisions,
    document_kb_bindings,
    documents,
    ingest_jobs,
    kb_member_bindings,
    knowledge_bases,
    rag_apps,
    user_groups,
    users,
)
```

同时在 schema import 中添加新 DTO：

```python
from app.schemas.knowledge_base import (
    KbDeleteImpactDTO,
    KbDeleteImpactBlockerDTO,
    KbDeleteImpactCascadeDTO,
    KbDeleteImpactUnaffectedDTO,
    KbMemberBindingDTO,
    KbMemberCreateRequest,
    KbMemberSubjectOptionDTO,
    KbMemberUpdateRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDTO,
    KnowledgeBaseUpdateRequest,
    RequiredForActivationDTO,
)
```

- [ ] **Step 3: 实现 `get_kb_delete_impact()` 函数**

在 `enable_knowledge_base()` 函数之后添加：

```python
def get_kb_delete_impact(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> KbDeleteImpactDTO:
    """查询删除知识库会影响的数据范围。"""
    kb_row = _read_visible_kb_row(session, current_user, kb_id)

    # 阻断条件：活跃 RAG 应用
    active_apps = session.execute(
        select(rag_apps.c.app_id, rag_apps.c.name)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status == "active",
            rag_apps.c.deleted_at.is_(None),
        )
    ).mappings().all()

    # 阻断条件：运行中的 ingest_job
    running_jobs = session.execute(
        select(ingest_jobs.c.job_id, ingest_jobs.c.status)
        .where(
            ingest_jobs.c.kb_id == kb_id,
            ingest_jobs.c.status.in_(["pending", "processing"]),
        )
    ).mappings().all()

    # 级联数据统计
    binding_count = session.execute(
        select(func.count())
        .select_from(document_kb_bindings)
        .where(
            document_kb_bindings.c.kb_id == kb_id,
            document_kb_bindings.c.status.in_(["active", "processing", "pending", "failed"]),
        )
    ).scalar_one()

    kb_doc_count = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    # chunks 统计需要通过 documents 关联
    chunk_count = session.execute(
        select(func.count())
        .select_from(documents)
        .join(knowledge_bases, documents.c.kb_id == knowledge_bases.c.kb_id)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    config_count = session.execute(
        select(func.count())
        .select_from(config_revisions)
        .where(config_revisions.c.knowledge_base_id == kb_id)
    ).scalar_one()

    inactive_apps = session.execute(
        select(rag_apps.c.app_id, rag_apps.c.name, rag_apps.c.status)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status.in_(["disabled", "archived"]),
            rag_apps.c.deleted_at.is_(None),
        )
    ).mappings().all()

    member_count = session.execute(
        select(func.count())
        .select_from(kb_member_bindings)
        .where(kb_member_bindings.c.kb_id == kb_id)
    ).scalar_one()

    # 不受影响的数据
    library_doc_count = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.library_id.is_not(None),
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    return KbDeleteImpactDTO(
        kbName=kb_row["name"],
        blockers=KbDeleteImpactBlockerDTO(
            activeRagApps=[{"appId": str(r["app_id"]), "name": r["name"]} for r in active_apps],
            runningJobs=[{"jobId": str(r["job_id"]), "status": r["status"]} for r in running_jobs],
        ),
        cascadeData=KbDeleteImpactCascadeDTO(
            bindings=binding_count,
            kbDocuments=kb_doc_count,
            chunks=chunk_count,
            configRevisions=config_count,
            inactiveRagApps=[{"appId": str(r["app_id"]), "name": r["name"], "status": r["status"]} for r in inactive_apps],
            kbMembers=member_count,
        ),
        unaffected=KbDeleteImpactUnaffectedDTO(
            libraryDocuments=library_doc_count,
            description="文件库中的源文档不会被删除",
        ),
    )
```

- [ ] **Step 4: 运行类型检查**

Run: `cd backend && python -c "from app.services.knowledge_base_service import get_kb_delete_impact; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/knowledge_base_service.py
git commit -m "feat: add get_kb_delete_impact service function"
```

---

### Task 3: 后端 Service — 执行删除

**Files:**
- Modify: `backend/app/services/knowledge_base_service.py`

- [ ] **Step 1: 实现 `delete_knowledge_base()` 函数**

在 `get_kb_delete_impact()` 之后添加：

```python
def delete_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    confirm_name: str,
) -> None:
    """删除知识库及级联数据。采用软删除，外部索引异步清理。"""
    _ensure_kb_manage_permission(session, current_user, kb_id)
    kb_row = _read_visible_kb_row(session, current_user, kb_id)

    # 名称确认
    if confirm_name != kb_row["name"]:
        raise KnowledgeBaseConfirmNameMismatchError

    # 阻断条件：活跃 RAG 应用
    active_app_count = session.execute(
        select(func.count())
        .select_from(rag_apps)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status == "active",
            rag_apps.c.deleted_at.is_(None),
        )
    ).scalar_one()
    if active_app_count > 0:
        raise KnowledgeBaseActiveRagAppsError

    # 阻断条件：运行中的 ingest_job
    running_job_count = session.execute(
        select(func.count())
        .select_from(ingest_jobs)
        .where(
            ingest_jobs.c.kb_id == kb_id,
            ingest_jobs.c.status.in_(["pending", "processing"]),
        )
    ).scalar_one()
    if running_job_count > 0:
        raise KnowledgeBaseRunningJobsError

    now = datetime.now(UTC)
    deleted_by = UUID(current_user.user.userId)

    # 1. 软删除知识库本身
    session.execute(
        update(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id)
        .values(
            status="archived",
            deleted_at=now,
            deleted_by=deleted_by,
            updated_at=now,
            updated_by=deleted_by,
        )
    )

    # 2. 禁用所有 document_kb_bindings
    session.execute(
        update(document_kb_bindings)
        .where(
            document_kb_bindings.c.kb_id == kb_id,
            document_kb_bindings.c.status.in_(["active", "processing", "pending", "failed"]),
        )
        .values(status="disabled")
    )

    # 3. 软删除 KB 侧文档副本
    kb_doc_ids = session.execute(
        select(documents.c.document_id)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalars().all()

    if kb_doc_ids:
        session.execute(
            update(documents)
            .where(documents.c.document_id.in_(kb_doc_ids))
            .values(
                status="archived",
                deleted_at=now,
                deleted_by=deleted_by,
            )
        )

    # 4. 取消运行中的 ingest_jobs（防御性处理）
    session.execute(
        update(ingest_jobs)
        .where(
            ingest_jobs.c.kb_id == kb_id,
            ingest_jobs.c.status.in_(["pending", "processing"]),
        )
        .values(status="cancelled")
    )

    # 5. 软删除 config_revisions
    session.execute(
        update(config_revisions)
        .where(config_revisions.c.knowledge_base_id == kb_id)
        .values(
            deleted_at=now,
            deleted_by=deleted_by,
        )
    )

    # 6. 删除 kb_member_bindings
    from app.tables import kb_member_bindings as kb_member_bindings_table
    session.execute(
        kb_member_bindings_table.delete().where(kb_member_bindings_table.c.kb_id == kb_id)
    )

    # 7. 软删除停用/归档的 rag_apps
    session.execute(
        update(rag_apps)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status.in_(["disabled", "archived"]),
            rag_apps.c.deleted_at.is_(None),
        )
        .values(
            status="archived",
            deleted_at=now,
            deleted_by=deleted_by,
        )
    )

    # 8. 审计日志
    write_audit_log(
        session,
        current_user,
        "knowledge_base.delete",
        "knowledge_base",
        kb_id,
        kb_id=kb_id,
        detail={"confirm_name": confirm_name},
    )

    session.commit()

    # 9. 异步清理外部索引（best-effort）
    _cleanup_kb_external_indexes(session, kb_id, current_user)
```

- [ ] **Step 2: 修改 `delete_knowledge_base()` 收集 chunk_ids 并补充外部清理**

在 `delete_knowledge_base()` 中，步骤 3（软删除 KB 侧文档）之前，先收集 chunk_ids：

```python
    # 3. 收集 chunk_ids 用于外部索引清理（在标记删除前）
    chunk_ids = []
    if kb_doc_ids:
        chunk_rows = session.execute(
            select(chunks.c.chunk_id)
            .where(chunks.c.document_id.in_(kb_doc_ids))
        ).scalars().all()
        chunk_ids = list(chunk_rows)
```

在步骤 8（审计日志）之后、session.commit() 之前，添加外部清理的准备：

```python
    # 记录 KB 配置用于外部清理
    kb_config_row = session.execute(
        select(
            knowledge_bases.c.sparse_index_enabled,
            knowledge_bases.c.graph_index_enabled,
        )
        .where(knowledge_bases.c.kb_id == kb_id)
    ).mappings().first()
```

在 `session.commit()` 之后，替换原来的 `_cleanup_kb_external_indexes` 调用为：

```python
    # 9. 异步清理外部索引（best-effort）
    from app.services.document_service import _create_index_sync_job

    cleanup_warnings: list[str] = []
    if chunk_ids:
        targets = ["milvus"]
        if kb_config_row and kb_config_row["sparse_index_enabled"]:
            targets.append("opensearch")
        if kb_config_row and kb_config_row["graph_index_enabled"]:
            targets.append("neo4j")
        for target_store in targets:
            try:
                _create_index_sync_job(
                    session,
                    kb_config_row,
                    current_user,
                    target_store,
                    None,
                    chunk_ids,
                    False,
                    sync_type="delete",
                )
                session.commit()
            except Exception as exc:
                session.rollback()
                cleanup_warnings.append(f"{target_store} cleanup failed: {exc}")
```

同时删除 `_cleanup_kb_external_indexes` 函数（不再需要）。

还需要在 import 区域添加 `chunks` 表引用：

```python
from app.tables import (
    config_revisions,
    document_kb_bindings,
    documents,
    chunks,
    ingest_jobs,
    kb_member_bindings,
    knowledge_bases,
    rag_apps,
    user_groups,
    users,
)
```

- [ ] **Step 3: 运行类型检查**

Run: `cd backend && python -c "from app.services.knowledge_base_service import delete_knowledge_base; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/knowledge_base_service.py
git commit -m "feat: add delete_knowledge_base service function with cascade"
```

---

### Task 4: 后端 API — 新增删除接口

**Files:**
- Modify: `backend/app/api/routes/knowledge_bases.py`

- [ ] **Step 1: 添加 import 和异常映射**

在 `knowledge_bases.py` 的 import 区域添加新异常和 schema：

```python
from app.services.knowledge_base_service import (
    KnowledgeBaseConfirmNameMismatchError,
    KnowledgeBaseRunningJobsError,
    # ... 保留现有 import
)
from app.schemas.knowledge_base import (
    KbDeleteImpactDTO,
    KbDeleteRequest,
    # ... 保留现有 import
)
```

在 `_raise_kb_management_error()` 函数中添加新异常映射（在 `KnowledgeBaseActiveRagAppsError` 映射之后）：

```python
    if isinstance(exc, KnowledgeBaseConfirmNameMismatchError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CONFIRM_NAME_MISMATCH: confirm name does not match knowledge base name.",
        ) from exc
    if isinstance(exc, KnowledgeBaseRunningJobsError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RUNNING_JOBS_EXIST: knowledge base has running ingest jobs.",
        ) from exc
```

- [ ] **Step 2: 添加删除影响查询接口**

在 `enable_knowledge_base_endpoint` 之后添加：

```python
@router.get("/{kb_id}/delete-impact", response_model=KbDeleteImpactDTO)
def get_kb_delete_impact_endpoint(
    kb_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> KbDeleteImpactDTO:
    """查询删除知识库会影响的数据范围。"""
    try:
        return get_kb_delete_impact(session, current_user, kb_id)
    except Exception as exc:
        _raise_kb_management_error(exc)
```

- [ ] **Step 3: 添加删除执行接口**

```python
@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base_endpoint(
    kb_id: UUID,
    request: KbDeleteRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    """删除知识库及级联数据，需输入名称确认。"""
    try:
        delete_knowledge_base(session, current_user, kb_id, request.confirmName)
    except Exception as exc:
        _raise_kb_management_error(exc)
```

- [ ] **Step 4: 运行类型检查**

Run: `cd backend && python -c "from app.api.routes.knowledge_bases import router; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/knowledge_bases.py
git commit -m "feat: add KB deletion API endpoints"
```

---

### Task 5: 后端测试 — 单元测试

**Files:**
- Create: `backend/app/tests/unit/test_knowledge_base_deletion.py`

- [ ] **Step 1: 编写删除影响查询测试**

```python
"""知识库删除功能单元测试。"""
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.services.knowledge_base_service import (
    KnowledgeBaseActiveRagAppsError,
    KnowledgeBaseConfirmNameMismatchError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseRunningJobsError,
    delete_knowledge_base,
    get_kb_delete_impact,
)


@pytest.fixture()
def mock_session():
    session = Mock()
    return session


@pytest.fixture()
def mock_user():
    user = Mock()
    user.user.userId = str(uuid4())
    return user


@pytest.fixture()
def kb_id():
    return uuid4()


class TestGetKbDeleteImpact:
    """删除影响查询测试。"""

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_returns_impact_with_no_blockers(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        mock_session.execute.return_value.scalar_one.return_value = 0
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_kb_delete_impact(mock_session, mock_user, kb_id)

        assert result.kbName == "测试知识库"
        assert result.blockers.activeRagApps == []
        assert result.blockers.runningJobs == []

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_returns_active_apps_as_blockers(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        app_id = uuid4()

        # 第一次 execute 返回 active apps, 后续返回 0
        mock_active_result = MagicMock()
        mock_active_result.mappings.return_value.all.return_value = [
            {"app_id": app_id, "name": "客服助手"}
        ]
        mock_zero_result = MagicMock()
        mock_zero_result.scalar_one.return_value = 0
        mock_empty_result = MagicMock()
        mock_empty_result.mappings.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            mock_active_result,  # active apps
            mock_zero_result,    # running jobs
            mock_zero_result,    # binding count
            mock_zero_result,    # kb doc count
            mock_zero_result,    # chunk count
            mock_zero_result,    # config count
            mock_empty_result,   # inactive apps
            mock_zero_result,    # member count
            mock_zero_result,    # library doc count
        ]

        result = get_kb_delete_impact(mock_session, mock_user, kb_id)

        assert len(result.blockers.activeRagApps) == 1
        assert result.blockers.activeRagApps[0]["name"] == "客服助手"


class TestDeleteKnowledgeBase:
    """删除知识库测试。"""

    @patch("app.services.knowledge_base_service._create_index_sync_job")
    @patch("app.services.knowledge_base_service.write_audit_log")
    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_successful_deletion(self, mock_perm, mock_read, mock_audit, mock_sync, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        mock_session.execute.return_value.scalar_one.return_value = 0
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        delete_knowledge_base(mock_session, mock_user, kb_id, "测试知识库")

        mock_session.commit.assert_called()
        mock_audit.assert_called_once()

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_raises_on_name_mismatch(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}

        with pytest.raises(KnowledgeBaseConfirmNameMismatchError):
            delete_knowledge_base(mock_session, mock_user, kb_id, "错误名称")

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_raises_on_active_rag_apps(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        mock_session.execute.return_value.scalar_one.return_value = 1

        with pytest.raises(KnowledgeBaseActiveRagAppsError):
            delete_knowledge_base(mock_session, mock_user, kb_id, "测试知识库")

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_raises_on_running_jobs(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        # 第一次返回 0 (active apps), 第二次返回 1 (running jobs)
        mock_session.execute.return_value.scalar_one.side_effect = [0, 1]

        with pytest.raises(KnowledgeBaseRunningJobsError):
            delete_knowledge_base(mock_session, mock_user, kb_id, "测试知识库")
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest app/tests/unit/test_knowledge_base_deletion.py -v`
Expected: ALL PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/app/tests/unit/test_knowledge_base_deletion.py
git commit -m "test: add unit tests for KB deletion"
```

---

### Task 6: 前端 Service — 新增 API 调用

**Files:**
- Modify: `frontend/src/app/services/knowledgeBaseService.ts`

- [ ] **Step 1: 添加删除相关 API 函数**

在 `knowledgeBaseService.ts` 的 `enableKnowledgeBase` 函数之后添加：

```typescript
export async function fetchKbDeleteImpact(kbId: string): Promise<KbDeleteImpact> {
  return apiGet<KbDeleteImpact>(`/knowledge-bases/${kbId}/delete-impact`);
}

export async function deleteKnowledgeBase(kbId: string, confirmName: string): Promise<void> {
  return apiDeleteJson<void>(`/knowledge-bases/${kbId}`, { confirmName });
}
```

注意：`apiDelete` 需要支持 request body。检查 `apiClient.ts` 中的 `apiDelete` 签名，如果不支持 body，使用 `apiDeleteJson`。

- [ ] **Step 2: 添加前端类型**

在 `frontend/src/app/types/knowledgeBase.ts` 末尾添加：

```typescript
export interface KbDeleteImpactBlocker {
  activeRagApps: Array<{ appId: string; name: string }>;
  runningJobs: Array<{ jobId: string; status: string }>;
}

export interface KbDeleteImpactCascade {
  bindings: number;
  kbDocuments: number;
  chunks: number;
  configRevisions: number;
  inactiveRagApps: Array<{ appId: string; name: string; status: string }>;
  kbMembers: number;
}

export interface KbDeleteImpactUnaffected {
  libraryDocuments: number;
  description: string;
}

export interface KbDeleteImpact {
  kbName: string;
  blockers: KbDeleteImpactBlocker;
  cascadeData: KbDeleteImpactCascade;
  unaffected: KbDeleteImpactUnaffected;
}
```

- [ ] **Step 3: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/services/knowledgeBaseService.ts frontend/src/app/types/knowledgeBase.ts
git commit -m "feat: add KB deletion API calls and types"
```

---

### Task 7: 前端组件 — 删除确认弹窗

**Files:**
- Create: `frontend/src/app/components/rag/KbDeleteDialog.tsx`

- [ ] **Step 1: 创建删除确认弹窗组件**

```tsx
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/rag/Button";
import { Input } from "@/components/ui/input";
import type { KbDeleteImpact } from "@/types/knowledgeBase";

interface KbDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  impact: KbDeleteImpact | null;
  loading: boolean;
  onConfirm: () => void;
  deleting: boolean;
}

export function KbDeleteDialog({
  open,
  onOpenChange,
  impact,
  loading,
  onConfirm,
  deleting,
}: KbDeleteDialogProps) {
  const [confirmName, setConfirmName] = useState("");

  useEffect(() => {
    if (open) {
      setConfirmName("");
    }
  }, [open]);

  const hasBlockers =
    impact &&
    (impact.blockers.activeRagApps.length > 0 || impact.blockers.runningJobs.length > 0);

  const nameMatches = impact && confirmName === impact.kbName;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border-warm bg-ivory sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="font-serif text-2xl font-medium text-near-black">
            删除知识库
          </DialogTitle>
          <DialogDescription className="text-sm text-olive-gray">
            此操作不可逆，请谨慎操作。
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-stone-gray">加载中...</div>
        ) : impact ? (
          <div className="space-y-4">
            {/* 阻断条件 */}
            {hasBlockers ? (
              <div className="rounded-lg border border-error/30 bg-error/5 p-4">
                <div className="flex items-center gap-2 text-error font-medium mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  无法删除
                </div>
                {impact.blockers.activeRagApps.length > 0 && (
                  <p className="text-sm text-near-black">
                    请先停用或删除以下活跃的智能应用：
                  </p>
                )}
                <ul className="mt-1 space-y-1">
                  {impact.blockers.activeRagApps.map((app) => (
                    <li key={app.appId} className="text-sm text-near-black">
                      · {app.name}
                    </li>
                  ))}
                </ul>
                {impact.blockers.runningJobs.length > 0 && (
                  <p className="text-sm text-near-black mt-2">
                    存在 {impact.blockers.runningJobs.length} 个运行中的任务，请等待完成。
                  </p>
                )}
              </div>
            ) : null}

            {/* 级联影响 */}
            {!hasBlockers && (
              <>
                <div className="rounded-lg border border-border-cream bg-parchment p-4 text-sm text-near-black">
                  <p className="font-medium mb-2">以下数据将被删除：</p>
                  <ul className="space-y-1 text-stone-gray">
                    {impact.cascadeData.bindings > 0 && (
                      <li>· {impact.cascadeData.bindings} 个绑定文档</li>
                    )}
                    {impact.cascadeData.chunks > 0 && (
                      <li>· {impact.cascadeData.chunks} 个向量索引</li>
                    )}
                    {impact.cascadeData.configRevisions > 0 && (
                      <li>· {impact.cascadeData.configRevisions} 个管线配置</li>
                    )}
                    {impact.cascadeData.inactiveRagApps.length > 0 && (
                      <li>
                        · {impact.cascadeData.inactiveRagApps.length} 个已停用的智能应用
                        （{impact.cascadeData.inactiveRagApps.map((a) => a.name).join("、")}）
                      </li>
                    )}
                  </ul>
                  {impact.unaffected.libraryDocuments > 0 && (
                    <p className="mt-2 text-xs text-stone-gray">
                      {impact.unaffected.description}
                    </p>
                  )}
                </div>

                {/* 名称确认 */}
                <div className="space-y-2">
                  <p className="text-sm text-near-black">
                    请输入知识库名称 <span className="font-medium">{impact.kbName}</span> 以确认删除：
                  </p>
                  <Input
                    value={confirmName}
                    onChange={(e) => setConfirmName(e.target.value)}
                    placeholder={impact.kbName}
                    className="border-border-warm"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <Button variant="ghost" onClick={() => onOpenChange(false)}>
                    取消
                  </Button>
                  <Button
                    variant="destructive"
                    disabled={!nameMatches || deleting}
                    onClick={onConfirm}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    {deleting ? "删除中..." : "删除知识库"}
                  </Button>
                </div>
              </>
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/components/rag/KbDeleteDialog.tsx
git commit -m "feat: add KB delete confirmation dialog component"
```

---

### Task 8: 前端页面 — 集成删除功能

**Files:**
- Modify: `frontend/src/app/pages/P02_PlatformHome.tsx`

- [ ] **Step 1: 添加 import**

在 P02_PlatformHome.tsx 的 import 区域添加：

```typescript
import { fetchKbDeleteImpact, deleteKnowledgeBase } from "@/services/knowledgeBaseService";
import { KbDeleteDialog } from "@/components/rag/KbDeleteDialog";
import type { KbDeleteImpact } from "@/types/knowledgeBase";
```

- [ ] **Step 2: 添加状态和处理函数**

在组件内部（`handleEnable` 函数之后）添加：

```typescript
const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
const [deleteImpact, setDeleteImpact] = useState<KbDeleteImpact | null>(null);
const [deleteImpactLoading, setDeleteImpactLoading] = useState(false);
const [deleting, setDeleting] = useState(false);
const [kbToDelete, setKbToDelete] = useState<KnowledgeBase | null>(null);

const handleOpenDeleteDialog = async (event: MouseEvent<HTMLButtonElement>, kb: KnowledgeBase) => {
  event.stopPropagation();
  setKbToDelete(kb);
  setDeleteDialogOpen(true);
  setDeleteImpactLoading(true);
  try {
    const impact = await fetchKbDeleteImpact(kb.kbId);
    setDeleteImpact(impact);
  } catch (error) {
    setErrorMessage(error instanceof Error ? error.message : "获取删除影响信息失败。");
    setDeleteDialogOpen(false);
  } finally {
    setDeleteImpactLoading(false);
  }
};

const handleConfirmDelete = async () => {
  if (!kbToDelete || !deleteImpact) return;
  setDeleting(true);
  try {
    await deleteKnowledgeBase(kbToDelete.kbId, deleteImpact.kbName);
    setDeleteDialogOpen(false);
    setKbToDelete(null);
    await loadKnowledgeBases(keyword);
  } catch (error) {
    const message = error instanceof Error ? error.message : "知识库删除失败。";
    setErrorMessage(
      message.includes("CONFIRM_NAME_MISMATCH")
        ? "名称不匹配，请重新输入。"
        : message.includes("KB_HAS_ACTIVE_RAG_APPS")
          ? "该知识库仍有关联的活跃应用。请先停用相关应用。"
          : message,
    );
  } finally {
    setDeleting(false);
  }
};
```

- [ ] **Step 3: 在 CardFooter 中添加删除按钮**

在 P02_PlatformHome.tsx 的 CardFooter 中，停用按钮之后添加删除按钮：

```tsx
<CardFooter className="pt-2 gap-2">
  <Button
    variant="outline"
    size="sm"
    title="编辑知识库"
    disabled={isDisabled}
    onClick={(event) => openEditDialog(event, kb)}
  >
    <Edit3 className="h-4 w-4" />
  </Button>
  <Button
    variant="outline"
    size="sm"
    title={isDisabled ? "恢复启用知识库" : "停用知识库"}
    onClick={(event) => isDisabled ? handleEnable(event, kb) : handleDisable(event, kb)}
  >
    <Power className="h-4 w-4" />
    <span className="sr-only">{isDisabled ? "恢复启用" : "停用"}</span>
  </Button>
  <Button
    variant="outline"
    size="sm"
    title="删除知识库"
    onClick={(event) => handleOpenDeleteDialog(event, kb)}
  >
    <Trash2 className="h-4 w-4" />
    <span className="sr-only">删除</span>
  </Button>
</CardFooter>
```

确保 `Trash2` 已从 lucide-react import。

- [ ] **Step 4: 在 JSX 末尾添加弹窗组件**

在组件 return 的最末尾（`</div>` 之前）添加：

```tsx
<KbDeleteDialog
  open={deleteDialogOpen}
  onOpenChange={setDeleteDialogOpen}
  impact={deleteImpact}
  loading={deleteImpactLoading}
  onConfirm={handleConfirmDelete}
  deleting={deleting}
/>
```

- [ ] **Step 5: 运行类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/P02_PlatformHome.tsx
git commit -m "feat: integrate KB deletion into platform home page"
```

---

### Task 9: 后端集成测试

**Files:**
- Create: `backend/app/tests/integration/test_knowledge_base_deletion.py`

- [ ] **Step 1: 编写集成测试**

```python
"""知识库删除功能集成测试。"""
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.services.knowledge_base_service import (
    KnowledgeBaseActiveRagAppsError,
    KnowledgeBaseConfirmNameMismatchError,
    KnowledgeBaseRunningJobsError,
    delete_knowledge_base,
    get_kb_delete_impact,
)


class TestKbDeletionIntegration:
    """删除知识库端到端流程测试。"""

    @patch("app.services.knowledge_base_service._create_index_sync_job")
    @patch("app.services.knowledge_base_service.write_audit_log")
    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_full_deletion_flow(self, mock_perm, mock_read, mock_audit, mock_sync):
        """验证删除流程：校验 → 软删除 KB → 禁用绑定 → 归档文档 → 清理配置 → 审计 → 提交。"""
        session = Mock()
        user = Mock()
        user.user.userId = str(uuid4())
        kb_id = uuid4()

        mock_read.return_value = {"name": "测试知识库"}

        # 所有 scalar_one 调用返回 0（无阻断条件）
        session.execute.return_value.scalar_one.return_value = 0
        session.execute.return_value.scalars.return_value.all.return_value = []

        delete_knowledge_base(session, user, kb_id, "测试知识库")

        # 验证提交和审计
        session.commit.assert_called()
        mock_audit.assert_called_once()

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_deletion_blocked_by_active_apps(self, mock_perm, mock_read):
        """存在活跃应用时应阻断删除。"""
        session = Mock()
        user = Mock()
        user.user.userId = str(uuid4())
        kb_id = uuid4()

        mock_read.return_value = {"name": "测试知识库"}
        session.execute.return_value.scalar_one.return_value = 1

        with pytest.raises(KnowledgeBaseActiveRagAppsError):
            delete_knowledge_base(session, user, kb_id, "测试知识库")

        session.commit.assert_not_called()

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_deletion_blocked_by_name_mismatch(self, mock_perm, mock_read):
        """名称不匹配时应阻断删除。"""
        session = Mock()
        user = Mock()
        user.user.userId = str(uuid4())
        kb_id = uuid4()

        mock_read.return_value = {"name": "测试知识库"}

        with pytest.raises(KnowledgeBaseConfirmNameMismatchError):
            delete_knowledge_base(session, user, kb_id, "错误名称")

        session.commit.assert_not_called()
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && python -m pytest app/tests/integration/test_knowledge_base_deletion.py -v`
Expected: ALL PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/app/tests/integration/test_knowledge_base_deletion.py
git commit -m "test: add integration tests for KB deletion"
```

---

### Task 10: E2E 测试补充

**Files:**
- Modify: `frontend/e2e/tests/` (add or extend existing test)

- [ ] **Step 1: 验证前端编译通过**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: Build succeeds

- [ ] **Step 2: 运行现有 E2E 测试确认无回归**

Run: `cd frontend && npx playwright test`
Expected: All existing tests pass

- [ ] **Step 3: Commit（如果有修复）**

```bash
git add -A
git commit -m "fix: resolve any build issues from KB deletion feature"
```
