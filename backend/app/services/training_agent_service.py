"""员工培训 Agent 平台侧公共能力。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import RowMapping, select
from sqlalchemy.orm import Session

from app.services.app_runtime_service import (
    AppRuntimeConflictError,
    _require_employee_training_app,
    _resolve_runtime_context_without_quota,
)
from app.tables import chunks


class TrainingAgentConflictError(ValueError):
    """员工培训 Agent 调用状态冲突。"""


class TrainingAgentNotFoundError(Exception):
    """员工培训 Agent 资源不存在。"""


def resolve_training_context(session: Session, credential: str, app_id: str | None = None):
    """解析 App API Key，并限制调用对象必须是员工培训场景。"""
    try:
        context = _resolve_runtime_context_without_quota(session, credential, datetime.now(UTC))
        _require_employee_training_app(context)
    except AppRuntimeConflictError as exc:
        raise TrainingAgentConflictError(str(exc)) from exc
    if app_id is not None and str(context.app_row["app_id"]) != str(app_id):
        raise TrainingAgentConflictError("APP_ID_NOT_MATCHED")
    return context


def read_training_evidence(
    session: Session,
    kb_id: Any,
    query: str,
    limit: int = 6,
    document_ids: list[str] | None = None,
) -> list[RowMapping]:
    """从当前 App 知识库读取培训证据，优先关键词命中，缺省回退到前几个有效 Chunk。"""
    stmt = select(
        chunks.c.chunk_id,
        chunks.c.document_id,
        chunks.c.chunk_index,
        chunks.c.section,
        chunks.c.heading,
        chunks.c.content,
        chunks.c.metadata,
    ).where(chunks.c.kb_id == kb_id, chunks.c.status == "active")
    if document_ids:
        stmt = stmt.where(chunks.c.document_id.in_(document_ids))

    terms = [term.strip() for term in query.replace("，", " ").replace(",", " ").split() if len(term.strip()) >= 2]
    matched_rows: list[RowMapping] = []
    if terms:
        matched_stmt = stmt
        for term in terms[:4]:
            matched_stmt = matched_stmt.where(chunks.c.content.ilike(f"%{term}%"))
        matched_rows = session.execute(matched_stmt.order_by(chunks.c.chunk_index.asc()).limit(limit)).mappings().all()

    if matched_rows:
        return matched_rows
    return session.execute(stmt.order_by(chunks.c.chunk_index.asc()).limit(limit)).mappings().all()


def evidence_title(row: RowMapping) -> str:
    """从 Chunk 元数据中提取对应用端友好的文档标题。"""
    metadata = row["metadata"] or {}
    if isinstance(metadata, dict):
        for key in ("documentName", "title", "sourceName"):
            value = metadata.get(key)
            if value:
                return str(value)
    return str(row["heading"] or row["section"] or f"文档 {str(row['document_id'])[:8]}")


def evidence_preview(row: RowMapping, limit: int = 220) -> str:
    """生成课堂和题目使用的证据摘要。"""
    text = " ".join(str(row["content"] or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."
