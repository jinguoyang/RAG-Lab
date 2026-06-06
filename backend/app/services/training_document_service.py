"""员工培训知识库文档查询服务。"""
from __future__ import annotations

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.schemas.training_document import TrainingDocumentDTO
from app.services.training_agent_service import evidence_preview, evidence_title, resolve_training_context
from app.tables import chunks, document_kb_bindings, documents


def _list_documents_from_chunks(
    session: Session,
    kb_id: str,
    *,
    query: str,
    category: str | None,
    difficulty: str | None,
    limit: int,
) -> list[TrainingDocumentDTO]:
    """兼容没有文档主记录的历史数据，仅从 active Chunk 聚合文档。"""
    normalized_query = query.strip().lower()
    stmt = (
        select(
            chunks.c.document_id,
            documents.c.name.label("document_name"),
            chunks.c.heading,
            chunks.c.section,
            chunks.c.content,
            chunks.c.metadata,
            chunks.c.chunk_index,
        )
        .select_from(chunks.outerjoin(documents, chunks.c.document_id == documents.c.document_id))
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active")
        .order_by(chunks.c.document_id.asc(), chunks.c.chunk_index.asc())
    )
    if normalized_query:
        stmt = stmt.where(
            or_(
                chunks.c.content.ilike(f"%{normalized_query}%"),
                documents.c.name.ilike(f"%{normalized_query}%"),
                chunks.c.heading.ilike(f"%{normalized_query}%"),
                chunks.c.section.ilike(f"%{normalized_query}%"),
            )
        )

    rows = session.execute(stmt.limit(max(limit * 5, limit))).mappings().all()
    document_map: dict[str, TrainingDocumentDTO] = {}
    for row in rows:
        metadata = row["metadata"] or {}
        row_category = str(metadata.get("category") or "") if isinstance(metadata, dict) else ""
        row_difficulty = str(metadata.get("difficulty") or "") if isinstance(metadata, dict) else ""
        if category and row_category != category:
            continue
        if difficulty and row_difficulty != difficulty:
            continue

        document_id = str(row["document_id"])
        document_map.setdefault(
            document_id,
            TrainingDocumentDTO(
                documentId=document_id,
                title=evidence_title(row),
                category=row_category or None,
                difficulty=row_difficulty or None,
                summary=evidence_preview(row, limit=160),
            ),
        )
        if len(document_map) >= limit:
            break
    return list(document_map.values())


def list_training_documents(
    session: Session,
    credential: str,
    *,
    query: str = "",
    category: str | None = None,
    difficulty: str | None = None,
    limit: int = 50,
) -> list[TrainingDocumentDTO]:
    """查询当前员工培训 App 知识库中的可选文档。

    文档主记录和知识库绑定决定可选范围，active Chunk 仅用于补充摘要与正文搜索。
    """
    context = resolve_training_context(session, credential)
    kb_id = context.kb_row["kb_id"]
    normalized_query = query.strip().lower()

    active_binding = exists().where(
        document_kb_bindings.c.document_id == documents.c.document_id,
        document_kb_bindings.c.kb_id == kb_id,
        document_kb_bindings.c.status == "active",
    )
    document_stmt = (
        select(documents.c.document_id, documents.c.name, documents.c.metadata)
        .where(
            documents.c.deleted_at.is_(None),
            documents.c.status == "active",
            or_(documents.c.kb_id == kb_id, active_binding),
        )
        .order_by(documents.c.name.asc(), documents.c.document_id.asc())
    )
    if normalized_query:
        matching_chunk = exists().where(
            chunks.c.document_id == documents.c.document_id,
            chunks.c.kb_id == kb_id,
            chunks.c.status == "active",
            or_(
                chunks.c.content.ilike(f"%{normalized_query}%"),
                chunks.c.heading.ilike(f"%{normalized_query}%"),
                chunks.c.section.ilike(f"%{normalized_query}%"),
            ),
        )
        document_stmt = document_stmt.where(
            or_(documents.c.name.ilike(f"%{normalized_query}%"), matching_chunk)
        )

    document_rows = session.execute(document_stmt.limit(limit)).mappings().all()
    if not document_rows:
        return _list_documents_from_chunks(
            session,
            str(kb_id),
            query=query,
            category=category,
            difficulty=difficulty,
            limit=limit,
        )

    document_ids = [row["document_id"] for row in document_rows]
    ranked_chunks = (
        select(
            chunks.c.document_id,
            chunks.c.heading,
            chunks.c.section,
            chunks.c.content,
            chunks.c.metadata,
            chunks.c.chunk_index,
            func.row_number()
            .over(partition_by=chunks.c.document_id, order_by=chunks.c.chunk_index.asc())
            .label("row_number"),
        )
        .where(
            chunks.c.kb_id == kb_id,
            chunks.c.status == "active",
            chunks.c.document_id.in_(document_ids),
        )
        .subquery()
    )
    preview_rows = session.execute(
        select(ranked_chunks).where(ranked_chunks.c.row_number == 1)
    ).mappings().all()
    preview_map = {str(row["document_id"]): row for row in preview_rows}

    result: list[TrainingDocumentDTO] = []
    for document_row in document_rows:
        document_id = str(document_row["document_id"])
        preview_row = preview_map.get(document_id)
        metadata = (preview_row or document_row)["metadata"] or {}
        row_category = str(metadata.get("category") or "") if isinstance(metadata, dict) else ""
        row_difficulty = str(metadata.get("difficulty") or "") if isinstance(metadata, dict) else ""
        if category and row_category != category:
            continue
        if difficulty and row_difficulty != difficulty:
            continue

        result.append(
            TrainingDocumentDTO(
                documentId=document_id,
                title=str(document_row["name"]),
                category=row_category or None,
                difficulty=row_difficulty or None,
                summary=evidence_preview(preview_row, limit=160) if preview_row else None,
            )
        )

    return result
