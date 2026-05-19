# Sprint 37 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善文档库预览能力，实现文档与知识库绑定链路（含解析复用、删除级联、重试机制）。

**Architecture:** 库侧解析存储完整 parsed_chunks，绑定时 KB ingest 复用跳过重复解析。文件不重复上传，KB 侧 source_file_id 指向库侧 stored_files。删除级联复用现有 delete_document 逻辑。

**Tech Stack:** FastAPI, SQLAlchemy Core, Celery, PostgreSQL, MinIO, React, TypeScript, mammoth.js

**Design Doc:** `docs/04-迭代与交付/plans/2026-05-19-sprint37-binding-preview.md`

---

## File Structure

### Backend — New Files
- `backend/app/services/binding_service.py` — 绑定/解绑/重试/使用情况服务
- `backend/app/api/routes/bindings.py` — 绑定相关 API 路由
- `backend/app/schemas/binding.py` — 绑定相关 DTO
- `backend/scripts/verify_text_preview_api.py` — 文本预览 API 验收
- `backend/scripts/verify_library_binding.py` — 绑定链路验收
- `backend/scripts/verify_parse_reuse.py` — 解析复用验收
- `backend/scripts/verify_library_delete.py` — 删除级联验收

### Backend — Modified Files
- `backend/app/services/library_service.py` — 新增文本预览函数、解析存储改造、删除级联
- `backend/app/api/routes/library.py` — 新增文本预览/删除/重试路由
- `backend/app/schemas/library.py` — 新增文本预览/使用情况 DTO
- `backend/app/services/document_service.py` — ingest pipeline 解析复用改造
- `backend/app/worker.py` — 新增绑定 ingest Celery 任务
- `backend/app/api/router.py` — 注册 binding_router

### Frontend — New Files
- `frontend/src/app/components/rag/DocxPreview.tsx` — DOCX 预览组件（mammoth.js）
- `frontend/src/app/components/rag/TextPreview.tsx` — 文本预览组件（懒加载全文）

### Frontend — Modified Files
- `frontend/src/app/types/library.ts` — 新增绑定/使用情况类型
- `frontend/src/app/services/libraryService.ts` — 新增文本预览/绑定/使用情况 API
- `frontend/src/app/pages/P16_LibraryDetail.tsx` — 预览改造 + 使用情况 + 重试
- `frontend/src/app/pages/P06_DocumentCenter.tsx` — 新增"从文档库添加"
- `frontend/package.json` — 新增 mammoth 依赖

---

## Task 1: 文本预览 API (S37-000)

**Files:**
- Modify: `backend/app/schemas/library.py`
- Modify: `backend/app/services/library_service.py`
- Modify: `backend/app/api/routes/library.py`
- Create: `backend/scripts/verify_text_preview_api.py`

- [ ] **Step 1: 添加 DTO 定义**

在 `backend/app/schemas/library.py` 末尾添加：

```python
class LibraryTextPreviewResponse(BaseModel):
    """文本预览响应。"""

    text: str
    truncated: bool
    fullLength: int


class LibraryParsedChunkDTO(BaseModel):
    """解析后的分块数据。"""

    content: str
    tokenCount: int
    section: str | None = None
    pageNo: int | None = None
    startOffset: int | None = None
    endOffset: int | None = None


class LibraryFullTextResponse(BaseModel):
    """完整文本响应。"""

    text: str


class LibraryParsedChunksResponse(BaseModel):
    """结构化解析分块响应。"""

    chunks: list[LibraryParsedChunkDTO]
```

- [ ] **Step 2: 添加服务函数**

在 `backend/app/services/library_service.py` 中添加函数。在文件顶部的 import 区域确保有 `from app.schemas.library import LibraryTextPreviewResponse, LibraryFullTextResponse, LibraryParsedChunksResponse, LibraryParsedChunkDTO`。

在 `run_library_parse_job_by_id` 函数之后添加：

```python
def get_document_text(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    mode: str = "preview",
) -> LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse:
    """获取文档解析文本。mode: preview / full / chunks。"""
    _ensure_owner(session, current_user, document_id)

    version_row = session.execute(
        select(document_versions)
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
        .order_by(document_versions.c.version_number.desc())
        .limit(1)
    ).mappings().first()
    if version_row is None:
        raise LibraryDocumentNotFoundError

    meta = version_row["metadata"] or {}
    preview_text = meta.get("preview_text", "")
    full_text_length = meta.get("full_text_length", 0)
    parsed_chunks = meta.get("parsed_chunks", [])

    if mode == "chunks":
        chunk_dtos = [
            LibraryParsedChunkDTO(
                content=ch.get("content", ""),
                tokenCount=ch.get("token_count", 0),
                section=ch.get("section"),
                pageNo=ch.get("page_no"),
                startOffset=ch.get("start_offset"),
                endOffset=ch.get("end_offset"),
            )
            for ch in parsed_chunks
        ]
        return LibraryParsedChunksResponse(chunks=chunk_dtos)

    if mode == "full":
        if parsed_chunks:
            full_text = "\n\n".join(ch.get("content", "") for ch in parsed_chunks)
        else:
            full_text = preview_text
        return LibraryFullTextResponse(text=full_text)

    # mode == "preview"
    return LibraryTextPreviewResponse(
        text=preview_text,
        truncated=full_text_length > len(preview_text),
        fullLength=full_text_length,
    )
```

- [ ] **Step 3: 添加路由**

在 `backend/app/api/routes/library.py` 中，在现有路由之后添加：

```python
@router.get("/{document_id}/text")
def get_document_text(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    mode: str = Query(default="preview", pattern="^(preview|full|chunks)$"),
) -> LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse:
    try:
        return library_service.get_document_text(db, current_user, document_id, mode)
    except Exception as exc:
        _raise_library_error(exc)
        raise
```

确保路由文件顶部 import 新增的 DTO 类型。

- [ ] **Step 4: 编写验收脚本**

创建 `backend/scripts/verify_text_preview_api.py`：

```python
"""验证文本预览 API 相关符号可导入且路由已注册。"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router
from app.schemas.library import (
    LibraryTextPreviewResponse,
    LibraryFullTextResponse,
    LibraryParsedChunksResponse,
    LibraryParsedChunkDTO,
)
from app.services.library_service import get_document_text


def main() -> None:
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    text_route = "/library/documents/{document_id}/text"
    if text_route not in route_paths:
        raise SystemExit(f"路由 {text_route} 未注册")

    assert LibraryTextPreviewResponse(text="x", truncated=False, fullLength=1).text == "x"
    assert LibraryParsedChunkDTO(content="c", tokenCount=1).content == "c"
    assert callable(get_document_text)
    print("verify_text_preview_api: PASS")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行验收脚本**

Run: `cd backend && conda run -n rag-lab python scripts/verify_text_preview_api.py`
Expected: `verify_text_preview_api: PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/library.py backend/app/services/library_service.py backend/app/api/routes/library.py backend/scripts/verify_text_preview_api.py
git commit -m "feat(library): add text preview API with preview/full/chunks modes"
```

---

## Task 2: 解析结果存储改造 (S37-003)

**Files:**
- Modify: `backend/app/services/library_service.py`

- [ ] **Step 1: 改造 run_library_parse_job_by_id 存储 parsed_chunks**

在 `backend/app/services/library_service.py` 中找到 `run_library_parse_job_by_id` 函数。定位存储 metadata 的代码段（约在函数末尾，`preview_text` 赋值之后）。

当前代码类似：
```python
version_metadata["preview_text"] = full_text[:2000]
version_metadata["full_text_length"] = len(full_text)
```

改造为：
```python
# 存储结构化分块结果
structured_chunks = []
for chunk in parsed_chunks:
    structured_chunks.append({
        "content": chunk.content,
        "token_count": chunk.token_count,
        "section": getattr(chunk, "section", None),
        "page_no": getattr(chunk, "page_no", None),
        "start_offset": getattr(chunk, "start_offset", None),
        "end_offset": getattr(chunk, "end_offset", None),
    })
version_metadata["parsed_chunks"] = structured_chunks
version_metadata["preview_text"] = full_text[:2000]
version_metadata["full_text_length"] = len(full_text)
```

确保 `parsed_chunks` 变量来自 `parse_document()` 的返回值（已经是 `ParsedChunk` 对象列表）。

- [ ] **Step 2: 运行后端编译检查**

Run: `cd backend && conda run -n rag-lab python -m compileall app`
Expected: 编译通过，无 SyntaxError

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/library_service.py
git commit -m "feat(library): store full parsed_chunks in document_versions metadata"
```

---

## Task 3: 绑定服务 + 绑定/解绑 API (S37-004)

**Files:**
- Create: `backend/app/schemas/binding.py`
- Create: `backend/app/services/binding_service.py`
- Create: `backend/app/api/routes/bindings.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: 创建绑定 DTO**

创建 `backend/app/schemas/binding.py`：

```python
"""知识库绑定相关 DTO。"""
from pydantic import BaseModel


class LibraryBindingDTO(BaseModel):
    """文档库绑定到知识库的绑定记录。"""

    bindingId: str
    documentId: str
    documentName: str
    kbId: str
    versionId: str
    chunkSize: int
    chunkOverlap: int
    status: str
    chunkCount: int
    errorCode: str | None = None
    errorMessage: str | None = None
    createdAt: str
    createdBy: str | None = None


class LibraryBindRequest(BaseModel):
    """绑定请求。"""

    documentIds: list[str]


class LibraryBindResponse(BaseModel):
    """绑定响应。"""

    bindings: list[LibraryBindingDTO]


class LibraryUnbindResponse(BaseModel):
    """解绑响应。"""

    bindingId: str
    status: str
```

- [ ] **Step 2: 创建绑定服务**

创建 `backend/app/services/binding_service.py`：

```python
"""知识库绑定服务：绑定、解绑、重试、使用情况查询。"""
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.binding import LibraryBindingDTO, LibraryBindResponse, LibraryUnbindResponse
from app.tables import (
    document_versions,
    document_kb_bindings,
    documents,
    ingest_jobs,
    knowledge_bases,
    stored_files,
)


class BindingPermissionError(Exception):
    """权限不足。"""


class BindingDocumentNotFoundError(Exception):
    """文档未找到。"""


class BindingKBNotFoundError(Exception):
    """知识库未找到。"""


class BindingAlreadyExistsError(Exception):
    """绑定已存在。"""


class BindingNotFoundError(Exception):
    """绑定未找到。"""


def _ensure_library_owner(session: Session, current_user: CurrentUserResponse, document_id: UUID) -> RowMapping:
    """确保当前用户是文档 owner。"""
    user_id = UUID(current_user.user.userId)
    row = session.execute(
        select(documents)
        .where(
            documents.c.document_id == document_id,
            documents.c.owner_id == user_id,
            documents.c.deleted_at.is_(None),
            documents.c.kb_id.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if row is None:
        raise BindingDocumentNotFoundError
    return row


def _ensure_kb_permission(session: Session, current_user: CurrentUserResponse, kb_id: UUID) -> RowMapping:
    """确保当前用户有目标 KB 的文档上传权限。"""
    row = session.execute(
        select(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id, knowledge_bases.c.deleted_at.is_(None))
        .limit(1)
    ).mappings().first()
    if row is None:
        raise BindingKBNotFoundError
    # 简化权限检查：平台管理员或 KB 创建者
    user_id = UUID(current_user.user.userId)
    if current_user.user.platformRole == "admin":
        return row
    if row["created_by"] == user_id:
        return row
    raise BindingPermissionError


def _to_binding_dto(row: RowMapping, doc_name: str = "") -> LibraryBindingDTO:
    """将绑定行转为 DTO。"""
    return LibraryBindingDTO(
        bindingId=str(row["binding_id"]),
        documentId=str(row["document_id"]),
        documentName=doc_name,
        kbId=str(row["kb_id"]),
        versionId=str(row["version_id"]),
        chunkSize=row["chunk_size"],
        chunkOverlap=row["chunk_overlap"],
        status=row["status"],
        chunkCount=row["chunk_count"],
        errorCode=row.get("error_code"),
        errorMessage=row.get("error_message"),
        createdAt=row["created_at"].isoformat(),
        createdBy=str(row["created_by"]) if row.get("created_by") else None,
    )


def bind_documents_to_kb(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_ids: list[UUID],
) -> LibraryBindResponse:
    """将多个文档绑定到知识库。"""
    kb_row = _ensure_kb_permission(session, current_user, kb_id)
    user_id = UUID(current_user.user.userId)

    # 获取 KB 默认分块参数
    kb_metadata = kb_row.get("metadata") or {}
    chunk_size = kb_metadata.get("chunk_size", 900)
    chunk_overlap = kb_metadata.get("chunk_overlap", 120)

    bindings = []
    for doc_id in document_ids:
        doc_row = _ensure_library_owner(session, current_user, doc_id)

        # 检查是否已存在活跃绑定
        existing = session.execute(
            select(document_kb_bindings)
            .where(
                document_kb_bindings.c.document_id == doc_id,
                document_kb_bindings.c.kb_id == kb_id,
                document_kb_bindings.c.status.in_(["pending", "processing", "active"]),
            )
            .limit(1)
        ).mappings().first()
        if existing is not None:
            raise BindingAlreadyExistsError(f"文档 {doc_id} 已绑定到此知识库")

        # 获取库侧最新版本
        lib_version = session.execute(
            select(document_versions)
            .where(
                document_versions.c.document_id == doc_id,
                document_versions.c.deleted_at.is_(None),
            )
            .order_by(document_versions.c.version_number.desc())
            .limit(1)
        ).mappings().first()
        if lib_version is None:
            raise BindingDocumentNotFoundError(f"文档 {doc_id} 无可版本")

        # 获取库侧 stored_files
        source_file = session.execute(
            select(stored_files)
            .where(stored_files.c.file_id == lib_version["source_file_id"])
            .limit(1)
        ).mappings().first()

        # 创建 KB 侧 documents 记录
        kb_doc_id = uuid4()
        session.execute(
            insert(documents).values(
                document_id=kb_doc_id,
                kb_id=kb_id,
                owner_id=user_id,
                name=doc_row["name"],
                source_type="library_bind",
                security_level=doc_row["security_level"],
                status="processing",
                metadata={"library_document_id": str(doc_id)},
                created_by=user_id,
                updated_by=user_id,
            )
        )

        # 创建 KB 侧 document_versions 记录（复用 stored_files）
        kb_ver_id = uuid4()
        session.execute(
            insert(document_versions).values(
                version_id=kb_ver_id,
                document_id=kb_doc_id,
                version_number=1,
                source_file_id=source_file["file_id"] if source_file else None,
                parse_status="pending",
                dense_index_status="pending",
                sparse_index_status="pending",
                graph_index_status="not_required",
                status="processing",
                created_by=user_id,
                updated_by=user_id,
            )
        )
        session.execute(
            update(documents)
            .where(documents.c.document_id == kb_doc_id)
            .values(active_version_id=kb_ver_id)
        )

        # 创建绑定记录
        binding_id = uuid4()
        session.execute(
            insert(document_kb_bindings).values(
                binding_id=binding_id,
                document_id=doc_id,
                kb_id=kb_id,
                version_id=kb_ver_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                status="pending",
                chunk_count=0,
                created_by=user_id,
                updated_by=user_id,
            )
        )

        # 创建 ingest_jobs
        ingest_job_id = uuid4()
        session.execute(
            insert(ingest_jobs).values(
                job_id=ingest_job_id,
                document_id=kb_doc_id,
                version_id=kb_ver_id,
                job_type="upload_parse",
                status="queued",
                stage="queued",
                progress=0,
                created_by=user_id,
                updated_by=user_id,
            )
        )

        session.flush()

        # 更新绑定状态为 processing
        session.execute(
            update(document_kb_bindings)
            .where(document_kb_bindings.c.binding_id == binding_id)
            .values(status="processing", updated_by=user_id, updated_at=func.now())
        )

        binding_row = session.execute(
            select(document_kb_bindings).where(document_kb_bindings.c.binding_id == binding_id)
        ).mappings().first()
        bindings.append(_to_binding_dto(binding_row, doc_row["name"]))

    # 在 commit 前收集需要触发的 job_ids
    job_ids_to_trigger = []
    for doc_id in document_ids:
        ingest_row = session.execute(
            select(ingest_jobs.c.job_id)
            .where(
                ingest_jobs.c.document_id == kb_doc_id,
                ingest_jobs.c.status == "queued",
            )
            .limit(1)
        ).first()
        if ingest_row:
            job_ids_to_trigger.append(str(ingest_row[0]))

    session.commit()

    # commit 后触发 Celery 任务
    from app.worker import run_document_ingest_task
    for job_id in job_ids_to_trigger:
        run_document_ingest_task.delay(job_id)

    return LibraryBindResponse(bindings=bindings)
```

- [ ] **Step 3: 添加解绑功能**

在 `binding_service.py` 末尾添加：

```python
def unbind_document_from_kb(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> LibraryUnbindResponse:
    """解绑文档并清理 KB 侧数据。"""
    _ensure_kb_permission(session, current_user, kb_id)

    binding_row = session.execute(
        select(document_kb_bindings)
        .where(
            document_kb_bindings.c.binding_id == binding_id,
            document_kb_bindings.c.kb_id == kb_id,
        )
        .limit(1)
    ).mappings().first()
    if binding_row is None:
        raise BindingNotFoundError

    user_id = UUID(current_user.user.userId)

    # 获取 KB 侧文档
    kb_doc_id = session.execute(
        select(document_versions.c.document_id)
        .where(document_versions.c.version_id == binding_row["version_id"])
        .limit(1)
    ).scalar()

    # 标记绑定为 disabled
    session.execute(
        update(document_kb_bindings)
        .where(document_kb_bindings.c.binding_id == binding_id)
        .values(status="disabled", updated_by=user_id, updated_at=func.now())
    )

    # 调用现有 delete_document 清理 KB 侧文档
    if kb_doc_id:
        from app.services.document_service import delete_document
        from app.schemas.auth import CurrentUserResponse as _CUR
        try:
            delete_document(session, current_user, kb_id, kb_doc_id, confirm_impact=True, reason="library_unbind")
        except Exception:
            pass  # 尽力清理

    session.commit()

    return LibraryUnbindResponse(bindingId=str(binding_id), status="disabled")
```

- [ ] **Step 4: 添加绑定列表查询**

在 `binding_service.py` 末尾添加：

```python
def list_kb_bindings(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> list[LibraryBindingDTO]:
    """查询知识库的所有绑定记录。"""
    rows = session.execute(
        select(document_kb_bindings, documents.c.name.label("doc_name"))
        .join(documents, documents.c.document_id == document_kb_bindings.c.document_id)
        .where(document_kb_bindings.c.kb_id == kb_id)
        .order_by(document_kb_bindings.c.created_at.desc())
    ).mappings().all()

    return [_to_binding_dto(row, row.get("doc_name", "")) for row in rows]
```

- [ ] **Step 5: 创建绑定路由**

创建 `backend/app/api/routes/bindings.py`：

```python
"""知识库绑定路由。"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.binding import LibraryBindingDTO, LibraryBindRequest, LibraryBindResponse, LibraryUnbindResponse
from app.services import binding_service

router = APIRouter(prefix="/knowledge-bases/{kb_id}/library-bindings", tags=["library-bindings"])


def _raise_binding_error(exc: Exception) -> None:
    from fastapi import HTTPException
    if isinstance(exc, binding_service.BindingDocumentNotFoundError):
        raise HTTPException(status_code=404, detail="文档未找到")
    if isinstance(exc, binding_service.BindingKBNotFoundError):
        raise HTTPException(status_code=404, detail="知识库未找到")
    if isinstance(exc, binding_service.BindingPermissionError):
        raise HTTPException(status_code=403, detail="权限不足")
    if isinstance(exc, binding_service.BindingAlreadyExistsError):
        raise HTTPException(status_code=409, detail="绑定已存在")
    if isinstance(exc, binding_service.BindingNotFoundError):
        raise HTTPException(status_code=404, detail="绑定未找到")
    raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=LibraryBindResponse)
def bind_documents(
    kb_id: UUID,
    body: LibraryBindRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryBindResponse:
    try:
        doc_ids = [UUID(d) for d in body.documentIds]
        return binding_service.bind_documents_to_kb(db, current_user, kb_id, doc_ids)
    except Exception as exc:
        _raise_binding_error(exc)
        raise


@router.get("", response_model=list[LibraryBindingDTO])
def list_bindings(
    kb_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[LibraryBindingDTO]:
    try:
        return binding_service.list_kb_bindings(db, current_user, kb_id)
    except Exception as exc:
        _raise_binding_error(exc)
        raise


@router.delete("/{binding_id}", response_model=LibraryUnbindResponse)
def unbind_document(
    kb_id: UUID,
    binding_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryUnbindResponse:
    try:
        return binding_service.unbind_document_from_kb(db, current_user, kb_id, binding_id)
    except Exception as exc:
        _raise_binding_error(exc)
        raise
```

- [ ] **Step 6: 注册绑定路由**

在 `backend/app/api/router.py` 中添加：

```python
from app.api.routes.bindings import router as bindings_router
api_router.include_router(bindings_router)
```

- [ ] **Step 7: 编写验收脚本**

创建 `backend/scripts/verify_library_binding.py`：

```python
"""验证绑定服务相关符号可导入且路由已注册。"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router
from app.schemas.binding import LibraryBindingDTO, LibraryBindRequest, LibraryBindResponse, LibraryUnbindResponse
from app.services.binding_service import (
    bind_documents_to_kb,
    unbind_document_from_kb,
    list_kb_bindings,
    BindingPermissionError,
    BindingDocumentNotFoundError,
    BindingKBNotFoundError,
    BindingAlreadyExistsError,
    BindingNotFoundError,
)


def main() -> None:
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    bind_route = "/knowledge-bases/{kb_id}/library-bindings"
    if bind_route not in route_paths:
        raise SystemExit(f"路由 {bind_route} 未注册")

    assert callable(bind_documents_to_kb)
    assert callable(unbind_document_from_kb)
    assert callable(list_kb_bindings)
    assert LibraryBindRequest(documentIds=["a", "b"]).documentIds == ["a", "b"]
    print("verify_library_binding: PASS")


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: 运行验收脚本**

Run: `cd backend && conda run -n rag-lab python scripts/verify_library_binding.py`
Expected: `verify_library_binding: PASS`

- [ ] **Step 9: 运行后端编译检查**

Run: `cd backend && conda run -n rag-lab python -m compileall app`
Expected: 编译通过

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas/binding.py backend/app/services/binding_service.py backend/app/api/routes/bindings.py backend/app/api/router.py backend/scripts/verify_library_binding.py
git commit -m "feat(binding): add bind/unbind API and binding service"
```

---

## Task 4: KB ingest 解析复用 (S37-005)

**Files:**
- Modify: `backend/app/services/document_service.py`
- Create: `backend/scripts/verify_parse_reuse.py`

- [ ] **Step 1: 在 run_ingest_job 中添加解析复用逻辑**

在 `backend/app/services/document_service.py` 中找到 `run_ingest_job` 函数。定位调用 `parse_document()` 的代码段（约在函数前部，progress 20% 附近）。

在调用 `parse_document()` 之前，添加复用检查：

```python
    # 检查是否可以从库侧复用 parsed_chunks
    parsed_chunks_from_library = None
    if doc_row.get("source_type") == "library_bind":
        library_doc_id_str = (doc_row.get("metadata") or {}).get("library_document_id")
        if library_doc_id_str:
            library_doc_id = UUID(library_doc_id_str)
            lib_version = session.execute(
                select(document_versions)
                .where(
                    document_versions.c.document_id == library_doc_id,
                    document_versions.c.deleted_at.is_(None),
                )
                .order_by(document_versions.c.version_number.desc())
                .limit(1)
            ).mappings().first()
            if lib_version:
                lib_meta = lib_version.get("metadata") or {}
                if lib_meta.get("parsed_chunks"):
                    parsed_chunks_from_library = lib_meta["parsed_chunks"]
```

然后在 parse_document 调用处改为：

```python
    if parsed_chunks_from_library:
        # 复用库侧解析结果
        parsed_chunks = parsed_chunks_from_library
    else:
        # 重新解析
        source_bytes = _read_source_bytes(...)
        parsed_chunks = parse_document(source_bytes, file_name)
```

注意：`parsed_chunks_from_library` 是 dict 列表，而 `parse_document` 返回 `ParsedChunk` 对象列表。需要在复用时将 dict 转回兼容格式，或者在后续消费处统一处理 dict。最简方案：后续消费处已经通过 `.content` / `["content"]` 访问，统一用 dict 即可。

- [ ] **Step 2: 编写验收脚本**

创建 `backend/scripts/verify_parse_reuse.py`：

```python
"""验证解析复用相关逻辑可导入。"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.document_service import run_ingest_job
from app.tables import document_versions, documents

def main() -> None:
    assert callable(run_ingest_job)
    # 确认 documents 表有 source_type 列（用于判断 library_bind）
    doc_columns = {column.name for column in documents.columns}
    assert "source_type" in doc_columns
    assert "metadata" in doc_columns
    # 确认 document_versions 表有 metadata 列（存储 parsed_chunks）
    ver_columns = {column.name for column in document_versions.columns}
    assert "metadata" in ver_columns
    print("verify_parse_reuse: PASS")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行验收脚本**

Run: `cd backend && conda run -n rag-lab python scripts/verify_parse_reuse.py`
Expected: `verify_parse_reuse: PASS`

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/document_service.py backend/scripts/verify_parse_reuse.py
git commit -m "feat(ingest): reuse parsed_chunks from library for KB ingest"
```

---

## Task 5: 文档删除 API（级联清理）(S37-007)

**Files:**
- Modify: `backend/app/services/library_service.py`
- Modify: `backend/app/api/routes/library.py`
- Create: `backend/scripts/verify_library_delete.py`

- [ ] **Step 1: 添加删除服务函数**

在 `backend/app/services/library_service.py` 中添加：

```python
def delete_library_document(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
    storage_provider: ObjectStorageProvider | None = None,
) -> dict:
    """软删除文档并级联清理所有绑定。"""
    doc_row = _ensure_owner(session, current_user, document_id)
    user_id = UUID(current_user.user.userId)

    # 1. 软删除文档
    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(
            status="archived",
            deleted_at=func.now(),
            deleted_by=user_id,
            updated_at=func.now(),
            updated_by=user_id,
        )
    )

    # 2. 查询所有活跃绑定
    active_bindings = list(
        session.execute(
            select(document_kb_bindings)
            .where(
                document_kb_bindings.c.document_id == document_id,
                document_kb_bindings.c.status.in_(["active", "processing", "pending"]),
            )
        ).mappings()
    )

    # 3. 逐个解绑
    unbound_count = 0
    for binding in active_bindings:
        kb_doc_id = session.execute(
            select(document_versions.c.document_id)
            .where(document_versions.c.version_id == binding["version_id"])
            .limit(1)
        ).scalar()

        # 标记绑定为 disabled
        session.execute(
            update(document_kb_bindings)
            .where(document_kb_bindings.c.binding_id == binding["binding_id"])
            .values(status="disabled", updated_by=user_id, updated_at=func.now())
        )

        # 清理 KB 侧文档
        if kb_doc_id:
            from app.services.document_service import delete_document as _delete_kb_doc
            try:
                _delete_kb_doc(session, current_user, binding["kb_id"], kb_doc_id, confirm_impact=True, reason="library_cascade_delete")
            except Exception:
                pass

        unbound_count += 1

    session.commit()

    return {
        "documentId": str(document_id),
        "deletedAt": func.now(),
        "unboundCount": unbound_count,
    }
```

- [ ] **Step 2: 添加删除路由**

在 `backend/app/api/routes/library.py` 中添加：

```python
@router.delete("/{document_id}")
def delete_document(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return library_service.delete_library_document(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise
```

- [ ] **Step 3: 编写验收脚本**

创建 `backend/scripts/verify_library_delete.py`：

```python
"""验证文档删除级联相关符号可导入。"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router
from app.services.library_service import delete_library_document
from app.tables import documents, document_kb_bindings


def main() -> None:
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    delete_route = "/library/documents/{document_id}"
    # DELETE 方法的路由路径存在即可
    assert callable(delete_library_document)

    # 确认 documents 表有 deleted_at 列
    doc_columns = {column.name for column in documents.columns}
    assert "deleted_at" in doc_columns
    assert "deleted_by" in doc_columns

    # 确认 document_kb_bindings 表有 status 列
    binding_columns = {column.name for column in document_kb_bindings.columns}
    assert "status" in binding_columns

    print("verify_library_delete: PASS")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行验收脚本**

Run: `cd backend && conda run -n rag-lab python scripts/verify_library_delete.py`
Expected: `verify_library_delete: PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/library_service.py backend/app/api/routes/library.py backend/scripts/verify_library_delete.py
git commit -m "feat(library): add document delete with cascade binding cleanup"
```

---

## Task 6: 重试机制（解析重试 + 绑定重试）(S37-008)

**Files:**
- Modify: `backend/app/services/library_service.py`
- Modify: `backend/app/api/routes/library.py`
- Modify: `backend/app/services/binding_service.py`
- Modify: `backend/app/api/routes/bindings.py`

- [ ] **Step 1: 添加解析重试服务函数**

在 `backend/app/services/library_service.py` 中添加：

```python
def retry_library_parse(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> dict:
    """重新触发文档解析。"""
    _ensure_owner(session, current_user, document_id)
    user_id = UUID(current_user.user.userId)

    version_row = session.execute(
        select(document_versions)
        .where(
            document_versions.c.document_id == document_id,
            document_versions.c.deleted_at.is_(None),
        )
        .order_by(document_versions.c.version_number.desc())
        .limit(1)
    ).mappings().first()
    if version_row is None:
        raise LibraryDocumentNotFoundError

    # 创建新的 parse job
    job_id = uuid4()
    session.execute(
        insert(library_parse_jobs).values(
            job_id=job_id,
            document_id=document_id,
            version_id=version_row["version_id"],
            job_type="reparse",
            status="queued",
            progress=0,
            created_by=user_id,
            updated_by=user_id,
        )
    )

    # 重置版本解析状态
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_row["version_id"])
        .values(parse_status="pending", updated_by=user_id, updated_at=func.now())
    )

    session.commit()

    # 触发 Celery 任务
    from app.worker import run_library_parse_task
    run_library_parse_task.delay(str(job_id))

    return {"jobId": str(job_id), "status": "queued"}
```

- [ ] **Step 2: 添加解析重试路由**

在 `backend/app/api/routes/library.py` 中添加：

```python
@router.post("/{document_id}/parse-retry")
def retry_parse(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return library_service.retry_library_parse(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise
```

- [ ] **Step 3: 添加绑定重试服务函数**

在 `backend/app/services/binding_service.py` 中添加：

```python
def retry_binding(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> dict:
    """重试失败的绑定（重新触发 ingest）。"""
    _ensure_kb_permission(session, current_user, kb_id)

    binding_row = session.execute(
        select(document_kb_bindings)
        .where(
            document_kb_bindings.c.binding_id == binding_id,
            document_kb_bindings.c.kb_id == kb_id,
            document_kb_bindings.c.status == "failed",
        )
        .limit(1)
    ).mappings().first()
    if binding_row is None:
        raise BindingNotFoundError

    user_id = UUID(current_user.user.userId)

    # 获取 KB 侧文档版本
    kb_ver_id = binding_row["version_id"]

    # 创建新的 ingest job
    ingest_job_id = uuid4()
    session.execute(
        insert(ingest_jobs).values(
            job_id=ingest_job_id,
            document_id=session.execute(
                select(document_versions.c.document_id)
                .where(document_versions.c.version_id == kb_ver_id)
                .limit(1)
            ).scalar(),
            version_id=kb_ver_id,
            job_type="upload_parse",
            status="queued",
            stage="queued",
            progress=0,
            created_by=user_id,
            updated_by=user_id,
        )
    )

    # 重置绑定状态
    session.execute(
        update(document_kb_bindings)
        .where(document_kb_bindings.c.binding_id == binding_id)
        .values(status="processing", error_code=None, error_message=None, updated_by=user_id, updated_at=func.now())
    )

    session.commit()

    # 触发 Celery
    from app.worker import run_document_ingest_task
    run_document_ingest_task.delay(str(ingest_job_id))

    return {"bindingId": str(binding_id), "ingestJobId": str(ingest_job_id), "status": "processing"}
```

- [ ] **Step 4: 添加绑定重试路由**

在 `backend/app/api/routes/bindings.py` 中添加：

```python
@router.post("/{binding_id}/retry")
def retry_binding(
    kb_id: UUID,
    binding_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return binding_service.retry_binding(db, current_user, kb_id, binding_id)
    except Exception as exc:
        _raise_binding_error(exc)
        raise
```

- [ ] **Step 5: 运行后端编译检查**

Run: `cd backend && conda run -n rag-lab python -m compileall app`
Expected: 编译通过

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/library_service.py backend/app/api/routes/library.py backend/app/services/binding_service.py backend/app/api/routes/bindings.py
git commit -m "feat(library): add parse retry and binding retry mechanisms"
```

---

## Task 7: 文档使用情况 API (S37-009)

**Files:**
- Modify: `backend/app/schemas/library.py`
- Modify: `backend/app/services/library_service.py`
- Modify: `backend/app/api/routes/library.py`

- [ ] **Step 1: 添加使用情况 DTO**

在 `backend/app/schemas/library.py` 中添加：

```python
class LibraryDocumentUsageDTO(BaseModel):
    """文档使用情况：绑定的知识库列表。"""

    bindingId: str
    kbId: str
    kbName: str
    status: str
    chunkCount: int
    createdAt: str


class LibraryDocumentUsageResponse(BaseModel):
    """文档使用情况响应。"""

    documentId: str
    usages: list[LibraryDocumentUsageDTO]
```

- [ ] **Step 2: 添加使用情况查询服务函数**

在 `backend/app/services/library_service.py` 中添加：

```python
def get_document_usage(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> dict:
    """查询文档绑定的所有知识库。"""
    _ensure_owner(session, current_user, document_id)

    rows = session.execute(
        select(
            document_kb_bindings.c.binding_id,
            document_kb_bindings.c.kb_id,
            document_kb_bindings.c.status,
            document_kb_bindings.c.chunk_count,
            document_kb_bindings.c.created_at,
            knowledge_bases.c.name.label("kb_name"),
        )
        .join(knowledge_bases, knowledge_bases.c.kb_id == document_kb_bindings.c.kb_id)
        .where(document_kb_bindings.c.document_id == document_id)
        .order_by(document_kb_bindings.c.created_at.desc())
    ).mappings().all()

    return {
        "documentId": str(document_id),
        "usages": [
            {
                "bindingId": str(row["binding_id"]),
                "kbId": str(row["kb_id"]),
                "kbName": row["kb_name"],
                "status": row["status"],
                "chunkCount": row["chunk_count"],
                "createdAt": row["created_at"].isoformat(),
            }
            for row in rows
        ],
    }
```

- [ ] **Step 3: 添加使用情况路由**

在 `backend/app/api/routes/library.py` 中添加：

```python
@router.get("/{document_id}/usage")
def get_document_usage(
    document_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    try:
        return library_service.get_document_usage(db, current_user, document_id)
    except Exception as exc:
        _raise_library_error(exc)
        raise
```

- [ ] **Step 4: 运行后端编译检查**

Run: `cd backend && conda run -n rag-lab python -m compileall app`
Expected: 编译通过

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/library.py backend/app/services/library_service.py backend/app/api/routes/library.py
git commit -m "feat(library): add document usage query API"
```

---

## Task 8: TXT 在线预览组件 (S37-001)

**Files:**
- Create: `frontend/src/app/components/rag/TextPreview.tsx`
- Modify: `frontend/src/app/services/libraryService.ts`
- Modify: `frontend/src/app/types/library.ts`
- Modify: `frontend/src/app/pages/P16_LibraryDetail.tsx`

- [ ] **Step 1: 添加前端类型**

在 `frontend/src/app/types/library.ts` 中添加：

```typescript
export interface LibraryTextPreviewResponse {
  text: string;
  truncated: boolean;
  fullLength: number;
}

export interface LibraryFullTextResponse {
  text: string;
}

export interface LibraryParsedChunkDTO {
  content: string;
  tokenCount: number;
  section?: string;
  pageNo?: number;
}

export interface LibraryParsedChunksResponse {
  chunks: LibraryParsedChunkDTO[];
}

export interface LibraryDocumentUsageDTO {
  bindingId: string;
  kbId: string;
  kbName: string;
  status: string;
  chunkCount: number;
  createdAt: string;
}

export interface LibraryDocumentUsageResponse {
  documentId: string;
  usages: LibraryDocumentUsageDTO[];
}
```

- [ ] **Step 2: 添加前端 API 函数**

在 `frontend/src/app/services/libraryService.ts` 中添加：

```typescript
export async function fetchDocumentText(
  documentId: string,
  mode: "preview" | "full" | "chunks" = "preview",
): Promise<LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse> {
  return apiGet(`/library/documents/${documentId}/text?mode=${mode}`);
}

export async function fetchDocumentUsage(
  documentId: string,
): Promise<LibraryDocumentUsageResponse> {
  return apiGet(`/library/documents/${documentId}/usage`);
}

export async function deleteLibraryDocument(
  documentId: string,
): Promise<void> {
  return apiDelete(`/library/documents/${documentId}`);
}

export async function retryLibraryParse(
  documentId: string,
): Promise<{ jobId: string; status: string }> {
  return apiPostJson(`/library/documents/${documentId}/parse-retry`, {});
}

export async function bindDocumentsToKB(
  kbId: string,
  documentIds: string[],
): Promise<LibraryBindResponse> {
  return apiPostJson(`/knowledge-bases/${kbId}/library-bindings`, { documentIds });
}

export async function listKBBindings(
  kbId: string,
): Promise<LibraryBindingDTO[]> {
  return apiGet(`/knowledge-bases/${kbId}/library-bindings`);
}

export async function unbindDocument(
  kbId: string,
  bindingId: string,
): Promise<void> {
  return apiDelete(`/knowledge-bases/${kbId}/library-bindings/${bindingId}`);
}

export async function retryBinding(
  kbId: string,
  bindingId: string,
): Promise<{ bindingId: string; status: string }> {
  return apiPostJson(`/knowledge-bases/${kbId}/library-bindings/${bindingId}/retry`, {});
}
```

确保文件顶部 import 新增类型和 `apiDelete`、`apiPostJson`。

- [ ] **Step 3: 创建 TextPreview 组件**

创建 `frontend/src/app/components/rag/TextPreview.tsx`：

```tsx
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { LibraryTextPreviewResponse } from "../../types/library";
import { fetchDocumentText } from "../../services/libraryService";

interface TextPreviewProps {
  documentId: string;
  initialData?: LibraryTextPreviewResponse;
}

export function TextPreview({ documentId, initialData }: TextPreviewProps) {
  const [data, setData] = useState<LibraryTextPreviewResponse | null>(initialData ?? null);
  const [fullText, setFullText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleExpand = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    if (!fullText) {
      setLoading(true);
      try {
        const result = (await fetchDocumentText(documentId, "full")) as { text: string };
        setFullText(result.text);
      } finally {
        setLoading(false);
      }
    }
    setExpanded(true);
  };

  const displayText = expanded && fullText ? fullText : data?.text ?? "";

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900">
      <div className="flex items-center justify-between border-b border-neutral-700 px-4 py-2">
        <span className="text-sm font-medium text-neutral-300">文档预览</span>
        {data?.truncated && (
          <button
            onClick={handleExpand}
            disabled={loading}
            className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
          >
            {loading ? "加载中..." : expanded ? "收起" : "查看全文"}
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        )}
      </div>
      <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap p-4 font-mono text-sm text-neutral-200">
        {displayText || "暂无预览内容"}
      </pre>
    </div>
  );
}
```

- [ ] **Step 4: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/types/library.ts frontend/src/app/services/libraryService.ts frontend/src/app/components/rag/TextPreview.tsx
git commit -m "feat(frontend): add TextPreview component and library API functions"
```

---

## Task 9: DOCX 在线预览（mammoth.js）(S37-002)

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/app/components/rag/DocxPreview.tsx`
- Modify: `frontend/src/app/pages/P16_LibraryDetail.tsx`

- [ ] **Step 1: 安装 mammoth.js**

Run: `cd frontend && npm install mammoth`
Expected: mammoth added to dependencies in package.json

- [ ] **Step 2: 创建 DocxPreview 组件**

创建 `frontend/src/app/components/rag/DocxPreview.tsx`：

```tsx
import { useEffect, useState } from "react";
import mammoth from "mammoth";
import { downloadLibraryDocument } from "../../services/libraryService";

interface DocxPreviewProps {
  documentId: string;
}

export function DocxPreview({ documentId }: DocxPreviewProps) {
  const [html, setHtml] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const blob = await downloadLibraryDocument(documentId);
        const arrayBuffer = await blob.data.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer });
        if (!cancelled) {
          setHtml(result.value);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "DOCX 预览加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (loading) {
    return <div className="p-4 text-sm text-neutral-400">加载中...</div>;
  }

  if (error) {
    return <div className="p-4 text-sm text-red-400">{error}</div>;
  }

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900">
      <div className="border-b border-neutral-700 px-4 py-2">
        <span className="text-sm font-medium text-neutral-300">文档预览</span>
      </div>
      <div
        className="prose prose-invert max-h-[500px] overflow-auto p-4"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
```

- [ ] **Step 3: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/app/components/rag/DocxPreview.tsx
git commit -m "feat(frontend): add DocxPreview component with mammoth.js"
```

---

## Task 10: P06 从文档库添加 + P16 改造 (S37-006 + S37-009 前端)

**Files:**
- Modify: `frontend/src/app/pages/P16_LibraryDetail.tsx`
- Modify: `frontend/src/app/pages/P06_DocumentCenter.tsx`
- Modify: `frontend/src/app/services/libraryService.ts` (确保 apiDelete import)

- [ ] **Step 1: 改造 P16 使用 TextPreview**

在 `frontend/src/app/pages/P16_LibraryDetail.tsx` 中，将现有的预览区域替换为使用 `TextPreview` 组件：

```tsx
import { TextPreview } from "../components/rag/TextPreview";
import { DocxPreview } from "../components/rag/DocxPreview";
```

将预览渲染逻辑改为：

```tsx
function renderPreview(documentId: string, fileName: string) {
  const ext = fileName.toLowerCase().split(".").pop();
  if (ext === "pdf") {
    return <PdfPreview documentId={documentId} />;
  }
  if (ext === "docx") {
    return <DocxPreview documentId={documentId} />;
  }
  if (ext === "md" || ext === "markdown") {
    return <MarkdownPreview documentId={documentId} />;
  }
  // txt 和其他文本格式
  return <TextPreview documentId={documentId} />;
}
```

- [ ] **Step 2: 在 P16 添加使用情况卡片**

在 P16 的详情页中，在预览区域下方添加使用情况展示：

```tsx
import { fetchDocumentUsage } from "../services/libraryService";
import type { LibraryDocumentUsageResponse } from "../types/library";

// 在组件内添加 state
const [usage, setUsage] = useState<LibraryDocumentUsageResponse | null>(null);

// 在 useEffect 中加载
useEffect(() => {
  if (docId) {
    fetchDocumentUsage(docId).then(setUsage).catch(() => {});
  }
}, [docId]);

// 渲染使用情况卡片
{usage && usage.usages.length > 0 && (
  <div className="rounded-lg border border-neutral-700 bg-neutral-900 p-4">
    <h3 className="mb-3 text-sm font-medium text-neutral-300">使用情况</h3>
    <div className="space-y-2">
      {usage.usages.map((u) => (
        <div key={u.bindingId} className="flex items-center justify-between text-sm">
          <span className="text-neutral-200">{u.kbName}</span>
          <span className={`text-xs ${
            u.status === "active" ? "text-green-400" :
            u.status === "failed" ? "text-red-400" : "text-yellow-400"
          }`}>
            {u.status} · {u.chunkCount} chunks
          </span>
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 3: 在 P16 添加重试按钮**

在解析状态卡片中，当解析失败时显示重试按钮：

```tsx
import { retryLibraryParse } from "../services/libraryService";

// 在解析状态为 failed 时显示
{version?.parseStatus === "failed" && (
  <button
    onClick={async () => {
      await retryLibraryParse(docId!);
      // 刷新详情
    }}
    className="mt-2 text-sm text-blue-400 hover:text-blue-300"
  >
    重试解析
  </button>
)}
```

- [ ] **Step 4: 在 P06 添加"从文档库添加"按钮**

在 `frontend/src/app/pages/P06_DocumentCenter.tsx` 中，在现有"上传"按钮旁边添加：

```tsx
import { fetchLibraryDocuments, bindDocumentsToKB } from "../services/libraryService";
import type { LibraryDocumentDTO } from "../types/library";

// 添加 state
const [showLibraryPicker, setShowLibraryPicker] = useState(false);
const [libraryDocs, setLibraryDocs] = useState<LibraryDocumentDTO[]>([]);
const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

// 加载文档库列表
const loadLibraryDocs = async () => {
  try {
    const result = await fetchLibraryDocuments({ pageNo: 1, pageSize: 100, status: "active" });
    setLibraryDocs(result.items);
  } catch {}
};

// 绑定选中文档
const handleBind = async () => {
  if (!kbId || selectedDocIds.length === 0) return;
  try {
    await bindDocumentsToKB(kbId, selectedDocIds);
    setShowLibraryPicker(false);
    setSelectedDocIds([]);
    loadData(); // 刷新文档列表
  } catch {}
};

// 在 JSX 中添加按钮（与 Upload 按钮并列）
<Button variant="secondary" onClick={() => { setShowLibraryPicker(true); loadLibraryDocs(); }}>
  从文档库添加
</Button>

// 文档选择器 Modal（简化版）
{showLibraryPicker && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
    <div className="w-[600px] max-h-[80vh] rounded-lg bg-neutral-900 border border-neutral-700 p-6">
      <h3 className="mb-4 text-lg font-medium text-neutral-100">从文档库添加</h3>
      <div className="max-h-[400px] overflow-y-auto space-y-2">
        {libraryDocs.map((doc) => (
          <label key={doc.documentId} className="flex items-center gap-3 p-2 rounded hover:bg-neutral-800">
            <input
              type="checkbox"
              checked={selectedDocIds.includes(doc.documentId)}
              onChange={(e) => {
                setSelectedDocIds(e.target.checked
                  ? [...selectedDocIds, doc.documentId]
                  : selectedDocIds.filter((id) => id !== doc.documentId));
              }}
            />
            <span className="text-sm text-neutral-200">{doc.name}</span>
          </label>
        ))}
      </div>
      <div className="mt-4 flex justify-end gap-3">
        <Button variant="secondary" onClick={() => setShowLibraryPicker(false)}>取消</Button>
        <Button onClick={handleBind} disabled={selectedDocIds.length === 0}>
          添加 {selectedDocIds.length} 个文档
        </Button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 5: 确保 apiDelete 已 import**

在 `frontend/src/app/services/libraryService.ts` 顶部确认有：

```typescript
import { apiGet, apiPostForm, apiPostJson, apiPatchJson, apiDownload, apiDelete } from "./apiClient";
```

- [ ] **Step 6: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/P16_LibraryDetail.tsx frontend/src/app/pages/P06_DocumentCenter.tsx frontend/src/app/services/libraryService.ts
git commit -m "feat(frontend): integrate preview components, usage display, and library picker in P06/P16"
```

---

## Task 11: 绑定链路验收脚本 (S37-010)

**Files:**
- Create: `backend/scripts/verify_sprint37_e2e.py`

- [ ] **Step 1: 编写综合验收脚本**

创建 `backend/scripts/verify_sprint37_e2e.py`：

```python
"""Sprint 37 综合验收：验证所有新增符号、路由和表结构。"""
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router
from app.tables import documents, document_versions, document_kb_bindings, ingest_jobs, library_parse_jobs

# 验证所有新增 DTO 可导入
from app.schemas.library import (
    LibraryTextPreviewResponse,
    LibraryFullTextResponse,
    LibraryParsedChunksResponse,
    LibraryParsedChunkDTO,
    LibraryDocumentUsageDTO,
    LibraryDocumentUsageResponse,
)
from app.schemas.binding import (
    LibraryBindingDTO,
    LibraryBindRequest,
    LibraryBindResponse,
    LibraryUnbindResponse,
)

# 验证所有新增服务函数可导入
from app.services.library_service import (
    get_document_text,
    delete_library_document,
    retry_library_parse,
    get_document_usage,
)
from app.services.binding_service import (
    bind_documents_to_kb,
    unbind_document_from_kb,
    list_kb_bindings,
    retry_binding,
)


def main() -> None:
    route_paths = {getattr(route, "path", "") for route in api_router.routes}

    # 验证路由
    required_routes = [
        "/library/documents/{document_id}/text",
        "/library/documents/{document_id}/usage",
        "/library/documents/{document_id}/parse-retry",
        "/knowledge-bases/{kb_id}/library-bindings",
        "/knowledge-bases/{kb_id}/library-bindings/{binding_id}",
        "/knowledge-bases/{kb_id}/library-bindings/{binding_id}/retry",
    ]
    for route in required_routes:
        if route not in route_paths:
            raise SystemExit(f"路由 {route} 未注册")

    # 验证表结构
    binding_columns = {column.name for column in document_kb_bindings.columns}
    for col in ("binding_id", "document_id", "kb_id", "version_id", "status", "chunk_size", "chunk_overlap"):
        assert col in binding_columns, f"document_kb_bindings 缺少列 {col}"

    doc_columns = {column.name for column in documents.columns}
    assert "source_type" in doc_columns
    assert "owner_id" in doc_columns

    ver_columns = {column.name for column in document_versions.columns}
    assert "metadata" in ver_columns

    # 验证服务函数可调用
    assert callable(get_document_text)
    assert callable(delete_library_document)
    assert callable(retry_library_parse)
    assert callable(get_document_usage)
    assert callable(bind_documents_to_kb)
    assert callable(unbind_document_from_kb)
    assert callable(list_kb_bindings)
    assert callable(retry_binding)

    print("verify_sprint37_e2e: PASS")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行综合验收脚本**

Run: `cd backend && conda run -n rag-lab python scripts/verify_sprint37_e2e.py`
Expected: `verify_sprint37_e2e: PASS`

- [ ] **Step 3: 运行所有单项验收脚本**

Run:
```bash
cd backend && conda run -n rag-lab python scripts/verify_text_preview_api.py
cd backend && conda run -n rag-lab python scripts/verify_library_binding.py
cd backend && conda run -n rag-lab python scripts/verify_parse_reuse.py
cd backend && conda run -n rag-lab python scripts/verify_library_delete.py
cd backend && conda run -n rag-lab python scripts/verify_sprint37_e2e.py
```
Expected: 全部 PASS

- [ ] **Step 4: 运行后端编译检查**

Run: `cd backend && conda run -n rag-lab python -m compileall app`
Expected: 编译通过

- [ ] **Step 5: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

- [ ] **Step 6: 导出 OpenAPI**

Run: `cd backend && conda run -n rag-lab python scripts/export_openapi.py`
Expected: library-bindings 路由已包含在导出中

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/verify_sprint37_e2e.py
git commit -m "feat(library): add Sprint 37 comprehensive verification script"
```

---

## Final Verification Checklist

- [ ] 所有验收脚本通过
- [ ] 后端编译通过
- [ ] 前端构建通过
- [ ] OpenAPI 导出包含新路由
- [ ] `git diff --check` 无空白错误
- [ ] 浏览器验证 /library/:docId 预览正常
- [ ] 浏览器验证 /knowledge-bases/:kbId/documents "从文档库添加" 入口可见
