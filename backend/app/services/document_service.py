from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import PurePath
import time
from uuid import UUID

from app.core.db_types import new_id

import sqlalchemy as sa
from sqlalchemy import RowMapping, delete, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.schemas.auth import CurrentUserResponse, UserDTO
from app.schemas.document import (
    ChunkDTO,
    BulkDocumentGovernanceResponse,
    DocumentDetailDTO,
    DocumentDeleteCleanupJobDTO,
    DocumentDeleteResponse,
    ChunkGovernanceResponse,
    DocumentDTO,
    DocumentVersionActivateResponse,
    DocumentQualityIssueDTO,
    DocumentQualitySummaryDTO,
    DocumentUploadResponse,
    DocumentVersionDTO,
    IndexSyncJobDTO,
    IngestJobDTO,
    StoredFileDTO,
)
from app.schemas.common import PageResponse
from app.tables import (
    audit_logs,
    chunk_revisions,
    chunk_access_filters,
    chunks,
    document_kb_bindings,
    document_versions,
    documents,
    graph_chunk_refs,
    graph_snapshots,
    index_sync_jobs,
    index_sync_records,
    ingest_jobs,
    knowledge_bases,
    parse_revisions,
    qa_run_evidence,
    stored_files,
    users,
)
from app.services.chunk_payload import build_chunk_index_payload, build_chunk_retrieval_text
from app.services.dictionary_service import require_active_dict_item
from app.services.document_parsing import DocumentParseError, ParsedBlock, ParsedDocument
from app.services.contextual_chunking import generate_contextual_metadata_with_cache
from app.services.multi_view_chunking import ChunkResult, execute_chunking
from app.services.object_storage import ObjectStorageProvider, get_object_storage_provider
from app.services.parser_routing import ParseTaskRecord, route_and_parse
from app.services.parsed_document_v2 import ParsedDocumentV2, convert_parsed_document_to_v2
from app.services.graph_service import mark_graph_snapshots_stale
from app.services.knowledge_base_service import KnowledgeBaseDisabledError
from app.services.permission_service import build_chunk_access_filter_context, has_kb_permission
from app.services.qa_providers import ChunkGraphExtraction, ProviderError, QARunProviders, get_qa_run_providers

KB_DOCUMENT_BINDING_STATUSES = ("pending", "processing", "active", "failed")


@dataclass(frozen=True)
class DocumentSourceDownload:
    """文档原文件下载结果，包含响应所需文件名、类型和二进制内容。"""

    file_name: str
    mime_type: str | None
    content: bytes


class DocumentPermissionError(Exception):
    """当前用户缺少文档生命周期操作权限。"""


class DocumentConflictError(Exception):
    """文档生命周期状态冲突，例如作业不可重试或版本不可激活。"""


class DocumentSourceFileUnavailableError(Exception):
    """原始文件元数据存在，但对象存储中无法读取对应内容。"""


class DocumentIngestEnqueueError(Exception):
    """文档入库任务投递到后台队列失败。"""


def _calculate_file_hash(file_content: bytes) -> str:
    """计算文件内容的 SHA256 hash"""
    return sha256(file_content).hexdigest()


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
    parse_revision_id = new_id()
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


def check_file_hash_duplicate(
    session: Session,
    kb_id: UUID,
    file_hash: str,
) -> dict | None:
    """检查文件 hash 是否重复

    通过 stored_files -> document_versions -> documents 链路查找同一知识库内相同 checksum 的文件。
    返回: 重复文件的信息，如果没有重复返回 None
    """
    existing_file = session.execute(
        select(stored_files)
        .select_from(
            stored_files
            .join(document_versions, stored_files.c.file_id == document_versions.c.source_file_id)
            .join(documents, document_versions.c.document_id == documents.c.document_id)
        )
        .where(
            _document_belongs_to_kb_condition(kb_id),
            stored_files.c.checksum == file_hash,
            stored_files.c.status == "active",
        )
        .limit(1)
    ).mappings().first()

    if existing_file:
        return {
            "file_id": existing_file["file_id"],
            "file_name": existing_file["file_name"],
            "created_at": existing_file["created_at"].isoformat() if existing_file["created_at"] else None,
        }
    return None


def analyze_document_version_deletion_impact(
    session: Session,
    document_version_id: UUID,
) -> dict:
    """分析删除文档版本的影响。

    Returns: 影响分析结果，包含 can_delete、blocking_reasons 等字段。
    """
    # 1. 检查是否为 active version
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

    # 2. 检查是否存在 active ChunkRevision
    active_binding_count = session.execute(
        select(func.count()).select_from(chunk_revisions).where(
            chunk_revisions.c.document_version_id == document_version_id,
            chunk_revisions.c.status == "active",
        )
    ).scalar_one()

    # 3. 检查是否存在 pending/running 任务
    pending_ingest_jobs = session.execute(
        select(func.count()).select_from(ingest_jobs).where(
            ingest_jobs.c.version_id == document_version_id,
            ingest_jobs.c.status.in_(["queued", "running"]),
        )
    ).scalar_one()

    # 4. 汇总历史 QA 引用
    version_chunks = list(session.execute(
        select(chunks.c.chunk_id).where(
            chunks.c.version_id == document_version_id,
        )
    ).scalars().all())

    qa_evidence_count = 0
    qa_citation_count = 0

    if version_chunks:
        qa_evidence_count = session.execute(
            select(func.count()).select_from(qa_run_evidence).where(
                qa_run_evidence.c.chunk_id.in_(version_chunks),
            )
        ).scalar_one()

    # 5. 判断是否允许删除
    can_delete = True
    blocking_reasons: list[str] = []

    if is_active_version:
        can_delete = False
        blocking_reasons.append("不能删除文档库当前 active version")

    if active_binding_count > 0:
        can_delete = False
        blocking_reasons.append(f"该版本正在支撑 {active_binding_count} 个知识库的 active ChunkRevision")

    if pending_ingest_jobs > 0:
        can_delete = False
        blocking_reasons.append("该版本存在运行中的任务")

    return {
        "can_delete": can_delete,
        "blocking_reasons": blocking_reasons,
        "is_active_version": is_active_version,
        "active_binding_count": active_binding_count,
        "pending_jobs_count": pending_ingest_jobs,
        "qa_evidence_count": qa_evidence_count,
        "qa_citation_count": qa_citation_count,
        "requires_strong_confirmation": qa_evidence_count > 0 or qa_citation_count > 0,
    }


def delete_document_version(
    session: Session,
    current_user: CurrentUserResponse,
    document_version_id: UUID,
    strong_confirmation: bool = False,
) -> dict:
    """删除文档版本，执行影响分析和级联清理。

    Returns: 删除结果，包含 status、message 和 impact_analysis。
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
    user_id = current_user.user.userId

    # 4.1 删除 ParseRevision（软删除）
    parse_rev_ids = list(session.execute(
        select(parse_revisions.c.parse_revision_id).where(
            parse_revisions.c.document_version_id == document_version_id,
        )
    ).scalars().all())

    if parse_rev_ids:
        session.execute(
            update(parse_revisions).where(
                parse_revisions.c.parse_revision_id.in_(parse_rev_ids),
            ).values(
                deleted_at=now,
                deleted_by=user_id,
            )
        )

    # 4.2 清理 retired/failed ChunkRevision
    session.execute(
        update(chunk_revisions).where(
            chunk_revisions.c.document_version_id == document_version_id,
            chunk_revisions.c.status.in_(["retired", "failed"]),
        ).values(
            status="deleted",
            deleted_at=now,
        )
    )

    # 4.3 清理 Chunk
    version_chunks = list(session.execute(
        select(chunks.c.chunk_id).where(
            chunks.c.version_id == document_version_id,
        )
    ).scalars().all())

    if version_chunks:
        session.execute(
            update(chunks).where(
                chunks.c.chunk_id.in_(version_chunks),
            ).values(
                status="deleted",
            )
        )
        session.execute(
            update(chunk_access_filters).where(
                chunk_access_filters.c.chunk_id.in_(version_chunks),
            ).values(
                chunk_status="deleted",
                updated_at=now,
            )
        )
        session.execute(
            delete(graph_chunk_refs).where(
                graph_chunk_refs.c.chunk_id.in_(version_chunks),
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
    _insert_audit_log(
        session,
        current_user,
        "document_version.delete",
        "document_version",
        document_version_id,
        UUID("00000000-0000-0000-0000-000000000000"),  # 无特定 KB
        None,
        {
            "qa_evidence_count": impact["qa_evidence_count"],
            "qa_citation_count": impact["qa_citation_count"],
            "chunks_deleted": len(version_chunks),
            "parse_revisions_deleted": len(parse_rev_ids),
        },
    )

    return {
        "status": "success",
        "message": "文档版本已删除",
        "deleted_version_id": str(document_version_id),
        "impact_analysis": impact,
    }


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用 E1 最小权限：平台管理员可访问全部知识库。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库，文档模块以后端权限摘要为最终判断。"""
    row = session.execute(
        select(knowledge_bases)
        .where(knowledge_bases.c.deleted_at.is_(None), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    if not has_kb_permission(session, current_user, kb_id, "kb.view"):
        return None
    return row


def _ensure_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    permission_code: str,
) -> None:
    """写操作和正文读取必须显式校验权限，避免只依赖资源可见性。"""
    if not has_kb_permission(session, current_user, kb_id, permission_code):
        raise DocumentPermissionError


def _to_document_dto(row: RowMapping) -> DocumentDTO:
    """将 documents 行转换为文档 DTO。"""
    effective_kb_id = row.get("effective_kb_id") or row["kb_id"]
    return DocumentDTO(
        documentId=str(row["document_id"]),
        kbId=str(effective_kb_id),
        name=row["name"],
        sourceType=row["source_type"],
        status=row["status"],
        activeVersionId=str(row["active_version_id"]) if row["active_version_id"] else None,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _document_belongs_to_kb_condition(kb_id: UUID) -> sa.ColumnElement[bool]:
    """判断文档是否属于知识库；绑定表是新口径，documents.kb_id 仅作历史兼容。"""
    binding_exists = sa.exists().where(
        document_kb_bindings.c.document_id == documents.c.document_id,
        document_kb_bindings.c.kb_id == kb_id,
        document_kb_bindings.c.status.in_(KB_DOCUMENT_BINDING_STATUSES),
    )
    return (
        documents.c.deleted_at.is_(None)
        & or_(
            documents.c.kb_id == kb_id,
            binding_exists,
        )
    )


def _select_kb_documents(kb_id: UUID) -> sa.Select:
    """构造知识库文档查询，并为绑定表口径补充有效 kb_id。"""
    return select(documents, sa.literal(str(kb_id)).label("effective_kb_id"))


def _to_version_dto(row: RowMapping) -> DocumentVersionDTO:
    """将 document_versions 行转换为版本 DTO。"""
    metadata = row.get("metadata") or {}
    source_modality = metadata.get("sourceModality")
    image_info = metadata.get("image") if source_modality == "image" else None
    return DocumentVersionDTO(
        versionId=str(row["version_id"]),
        documentId=str(row["document_id"]),
        versionNo=row["version_no"],
        sourceFileId=str(row["source_file_id"]),
        status=row["status"],
        parseStatus=row["parse_status"],
        denseIndexStatus=row["dense_index_status"],
        sparseIndexStatus=row["sparse_index_status"],
        graphIndexStatus=row["graph_index_status"],
        retrievalReady=row["retrieval_ready"],
        chunkCount=row["chunk_count"],
        tokenCount=row["token_count"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
        sourceModality=source_modality,
        image=image_info,
    )


def _to_ingest_job_dto(row: RowMapping) -> IngestJobDTO:
    """将 ingest_jobs 行转换为作业 DTO。"""
    return IngestJobDTO(
        jobId=str(row["job_id"]),
        kbId=str(row["kb_id"]),
        documentId=str(row["document_id"]) if row["document_id"] else None,
        versionId=str(row["version_id"]) if row["version_id"] else None,
        jobType=row["job_type"],
        status=row["status"],
        stage=row["stage"],
        progress=row["progress"],
        errorCode=row["error_code"],
        errorMessage=row["error_message"],
        resultSummary=row["result_summary"],
        createdAt=row["created_at"].isoformat(),
    )


def _to_chunk_dto(row: RowMapping) -> ChunkDTO:
    """将 Chunk 真值行转换为 API DTO。"""
    metadata = row["metadata"] or {}
    # B-319: 从 metadata 中提取 provenance 信息
    source_block_ids = metadata.get("sourceBlockIds")
    source_block_range = metadata.get("sourceBlockRange")
    provenance = metadata.get("provenance")

    return ChunkDTO(
        chunkId=str(row["chunk_id"]),
        versionId=str(row["version_id"]),
        documentId=str(row["document_id"]),
        kbId=str(row["kb_id"]),
        chunkRevisionId=str(row["chunk_revision_id"]) if row.get("chunk_revision_id") else None,
        parseRevisionId=str(row["parse_revision_id"]) if row.get("parse_revision_id") else None,
        documentVersionId=str(row["document_version_id"]) if row.get("document_version_id") else None,
        chunkIndex=row["chunk_index"],
        pageNo=row["page_no"],
        section=row["section"],
        startOffset=row.get("start_offset"),
        endOffset=row.get("end_offset"),
        sectionPath=row.get("section_path"),
        heading=row.get("heading"),
        summary=row.get("summary"),
        content=row["content"],
        contentHash=row["content_hash"],
        tokenCount=row["token_count"],
        status=row["status"],
        metadata=metadata,
        createdAt=row["created_at"].isoformat(),
        sourceBlockIds=source_block_ids,
        sourceBlockRange=source_block_range,
        provenance=provenance,
    )


def _read_active_chunk_revision_id(
    session: Session,
    kb_id: UUID,
    version_id: UUID,
) -> UUID | None:
    """读取当前 KB 版本对应的 active ChunkRevision，用于过滤当前可检索 Chunk。"""
    return session.execute(
        select(document_kb_bindings.c.active_chunk_revision_id)
        .where(
            document_kb_bindings.c.kb_id == kb_id,
            document_kb_bindings.c.version_id == version_id,
            document_kb_bindings.c.status.in_(["pending", "processing", "active"]),
        )
        .limit(1)
    ).scalar_one_or_none()


def _read_ingest_chunk_revision(
    session: Session,
    job_row: RowMapping,
    version_row: RowMapping,
) -> RowMapping | None:
    """从入库任务、版本 metadata 或绑定表中定位本次构建的 ChunkRevision。"""
    result_summary = job_row["result_summary"] or {}
    version_metadata = version_row["metadata"] or {}
    chunk_revision_id_str = result_summary.get("chunk_revision_id") or version_metadata.get("chunk_revision_id")
    if chunk_revision_id_str:
        return session.execute(
            select(chunk_revisions)
            .where(
                chunk_revisions.c.chunk_revision_id == UUID(str(chunk_revision_id_str)),
                chunk_revisions.c.deleted_at.is_(None),
            )
            .limit(1)
        ).mappings().first()

    binding_row = session.execute(
        select(document_kb_bindings.c.binding_id)
        .where(
            document_kb_bindings.c.kb_id == job_row["kb_id"],
            document_kb_bindings.c.version_id == version_row["version_id"],
            document_kb_bindings.c.status.in_(["pending", "processing", "active"]),
        )
        .limit(1)
    ).mappings().first()
    if binding_row is None:
        return None

    return session.execute(
        select(chunk_revisions)
        .where(
            chunk_revisions.c.binding_id == binding_row["binding_id"],
            chunk_revisions.c.status == "building",
            chunk_revisions.c.deleted_at.is_(None),
        )
        .order_by(chunk_revisions.c.created_at.desc())
        .limit(1)
    ).mappings().first()


def _to_index_sync_job_dto(row: RowMapping) -> IndexSyncJobDTO:
    """将索引同步作业行转换为 API DTO。"""
    return IndexSyncJobDTO(
        syncJobId=str(row["sync_job_id"]),
        kbId=str(row["kb_id"]),
        targetStore=row["target_store"],
        syncType=row["sync_type"],
        scope=row["scope"],
        requiredForActivation=row["required_for_activation"],
        status=row["status"],
        errorMessage=row["error_message"],
        createdAt=row["created_at"].isoformat(),
        startedAt=row["started_at"].isoformat() if row["started_at"] else None,
        finishedAt=row["finished_at"].isoformat() if row["finished_at"] else None,
    )


def _to_stored_file_dto(row: RowMapping) -> StoredFileDTO:
    """将 stored_files 行转换为文件元数据 DTO。"""
    return StoredFileDTO(
        fileId=str(row["file_id"]),
        fileName=row["file_name"],
        mimeType=row["mime_type"],
        fileSize=row["file_size"],
        checksum=row["checksum"],
        objectKey=row["object_key"],
    )


def _read_scope_ids(scope: object, key: str) -> set[str]:
    """从 IndexSyncJob scope 中读取字符串 ID 集合，兼容历史 JSON 结构。"""
    if not isinstance(scope, dict):
        return set()
    value = scope.get(key)
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _index_sync_job_matches_document(
    row: RowMapping,
    document_id: UUID,
    version_ids: set[str],
    chunk_ids: set[str],
) -> bool:
    """判断 KB 级索引同步作业是否属于指定文档的历史范围。"""
    scope = row["scope"]
    document_id_text = str(document_id)
    if document_id_text in _read_scope_ids(scope, "documentIds"):
        return True
    if version_ids & _read_scope_ids(scope, "versionIds"):
        return True
    return bool(chunk_ids & _read_scope_ids(scope, "chunkIds"))


def _safe_file_name(file_name: str) -> str:
    """提取上传文件名，避免客户端路径片段进入对象引用。"""
    name = PurePath(file_name).name.strip()
    return name or "uploaded-document"


def _insert_audit_log(
    session: Session,
    current_user: CurrentUserResponse,
    action: str,
    resource_type: str,
    resource_id: UUID,
    kb_id: UUID,
    document_id: UUID | None,
    detail: dict,
) -> UUID:
    """写入文档生命周期审计日志，支撑高风险操作可追溯。"""
    audit_log_id = new_id()
    session.execute(
        insert(audit_logs).values(
            audit_log_id=audit_log_id,
            actor_id=current_user.user.userId,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            kb_id=kb_id,
            document_id=document_id,
            detail=detail,
        )
    )
    return audit_log_id


def _read_source_bytes(
    session: Session,
    version_row: RowMapping,
    storage_provider: ObjectStorageProvider,
) -> tuple[bytes | None, RowMapping | None]:
    """按版本读取原始文件内容；开发期元数据存储可能只能返回 None。"""
    file_row = session.execute(
        select(stored_files)
        .where(stored_files.c.file_id == version_row["source_file_id"])
        .limit(1)
    ).mappings().first()
    if file_row is None:
        return None, None
    return storage_provider.get_object(file_row["object_key"]), file_row


def _write_graph_chunk_refs(
    session: Session,
    graph_snapshot_id: UUID,
    graph_items: list[ChunkGraphExtraction],
) -> None:
    """将图抽取结果写成 Graph 对象到 Chunk 的回溯摘要。"""
    session.execute(delete(graph_chunk_refs).where(graph_chunk_refs.c.graph_snapshot_id == graph_snapshot_id))
    seen: set[tuple[str, str, str | None, str | None]] = set()

    for item in graph_items:
        for entity in item.entities:
            key = ("entity_support", entity.chunk_id, entity.entity_key, None)
            if key in seen:
                continue
            seen.add(key)
            session.execute(
                insert(graph_chunk_refs).values(
                    graph_chunk_ref_id=new_id(),
                    graph_snapshot_id=graph_snapshot_id,
                    chunk_id=entity.chunk_id,
                    neo4j_node_key=entity.entity_key,
                    neo4j_relation_key=None,
                    community_key=None,
                    ref_type="entity_support",
                    metadata={
                        "entityName": entity.name,
                        "entityType": entity.entity_type,
                        "aliases": entity.aliases,
                    },
                    created_at=func.now(),
                )
            )

        for relation in item.relations:
            key = ("relation_support", relation.chunk_id, relation.source_entity_key, relation.relation_key)
            if key in seen:
                continue
            seen.add(key)
            session.execute(
                insert(graph_chunk_refs).values(
                    graph_chunk_ref_id=new_id(),
                    graph_snapshot_id=graph_snapshot_id,
                    chunk_id=relation.chunk_id,
                    neo4j_node_key=relation.source_entity_key,
                    neo4j_relation_key=relation.relation_key,
                    community_key=None,
                    ref_type="relation_support",
                    metadata={
                        "sourceEntityKey": relation.source_entity_key,
                        "targetEntityKey": relation.target_entity_key,
                        "relationType": relation.relation_type,
                    },
                    created_at=func.now(),
                )
            )


def _create_index_sync_job(
    session: Session,
    kb_row: RowMapping,
    current_user: CurrentUserResponse,
    target_store: str,
    version_id: UUID | None,
    chunk_ids: list[UUID],
    required_for_activation: bool,
    sync_type: str = "upsert",
    status: str = "queued",
    error_message: str | None = None,
    provider_payloads: dict[UUID, dict] | None = None,
    provider_set: QARunProviders | None = None,
    graph_items: list[ChunkGraphExtraction] | None = None,
    document_ids: list[UUID] | None = None,
    graph_snapshot_id: UUID | None = None,
) -> tuple[UUID, str, str | None]:
    """创建并执行 IndexSyncJob，真实 Provider 成功后才标记 success。"""
    sync_job_id = new_id()
    scope = {"chunkIds": [str(chunk_id) for chunk_id in chunk_ids]}
    if version_id:
        scope["versionIds"] = [str(version_id)]
    if document_ids:
        scope["documentIds"] = [str(document_id) for document_id in document_ids]
    session.execute(
        insert(index_sync_jobs).values(
            sync_job_id=sync_job_id,
            kb_id=kb_row["kb_id"],
            target_store=target_store,
            sync_type=sync_type,
            scope=scope,
            required_for_activation=required_for_activation,
            status="running",
            error_message=None,
            created_by=current_user.user.userId,
            started_at=func.now(),
        )
    )
    if status == "failed" and not chunk_ids:
        provider_summary = {
            "targetStore": target_store,
            "errorCode": "INDEX_SYNC_FAILED",
            "errorMessage": error_message,
        }
        final_status = "failed"
        final_error_message = error_message
    else:
        try:
            resolved_graph_items = graph_items or []
            provider_summary = _run_index_sync_job(
                provider_set or get_qa_run_providers(),
                target_store,
                sync_type,
                list((provider_payloads or {}).values()),
                chunk_ids,
                resolved_graph_items,
            )
            final_status = status if status != "queued" else "success"
            final_error_message = error_message
            if target_store == "neo4j" and sync_type != "delete" and final_status == "success" and graph_snapshot_id:
                _write_graph_chunk_refs(session, graph_snapshot_id, resolved_graph_items)
        except ProviderError as exc:
            provider_summary = {
                "targetStore": target_store,
                "errorCode": "INDEX_SYNC_FAILED",
                "errorMessage": str(exc),
            }
            final_status = "failed"
            final_error_message = f"{target_store}: {exc}"
    session.execute(
        update(index_sync_jobs)
        .where(index_sync_jobs.c.sync_job_id == sync_job_id)
        .values(status=final_status, error_message=final_error_message, finished_at=func.now())
    )
    for chunk_id in chunk_ids:
        session.execute(
            insert(index_sync_records).values(
                sync_record_id=new_id(),
                sync_job_id=sync_job_id,
                target_store=target_store,
                resource_type="chunk",
                resource_id=chunk_id,
                operation="upsert" if sync_type != "delete" else "delete",
                status=final_status,
                error_message=final_error_message,
                provider_payload={
                    **provider_summary,
                    "versionId": str(version_id) if version_id else None,
                    "chunkId": str(chunk_id),
                    "payload": (provider_payloads or {}).get(chunk_id),
                },
            )
        )
    return sync_job_id, final_status, final_error_message


def _run_index_sync_job(
    provider_set: QARunProviders,
    target_store: str,
    sync_type: str,
    chunk_payloads: list[dict],
    chunk_ids: list[UUID],
    graph_items: list[ChunkGraphExtraction],
) -> dict:
    """按 targetStore 调用真实副本 Provider，失败交由调用方记录状态。"""
    if target_store == "milvus":
        if sync_type == "delete":
            return provider_set.dense.delete_chunks(chunk_ids)
        return provider_set.dense.upsert_chunks(chunk_payloads)
    if target_store == "opensearch":
        if sync_type == "delete":
            return provider_set.sparse.delete_chunks(chunk_ids)
        return provider_set.sparse.upsert_chunks(chunk_payloads)
    if target_store == "neo4j":
        if sync_type == "delete":
            return provider_set.graph.delete_chunks(chunk_ids)
        return provider_set.graph.upsert_chunks(chunk_payloads, graph_items)
    raise ProviderError(f"Unsupported target store: {target_store}")


def _create_minio_cleanup_job(
    session: Session,
    kb_id: UUID,
    current_user: CurrentUserResponse,
    stored_file_rows: list[RowMapping],
    storage_provider: ObjectStorageProvider | None = None,
) -> DocumentDeleteCleanupJobDTO | None:
    """执行 MinIO 对象清理；MinIO 不属于 index_sync_jobs 的受约束目标集合。"""
    _ = (session, kb_id, current_user)
    unique_rows = {row["object_key"]: row for row in stored_file_rows}
    if not unique_rows:
        return None

    storage = storage_provider or get_object_storage_provider()
    errors: list[str] = []
    for object_key in unique_rows:
        try:
            storage.delete_object(object_key)
        except Exception as exc:
            errors.append(f"{object_key}: {exc}")

    final_status = "failed" if errors else "success"
    final_error = "; ".join(errors) if errors else None
    return DocumentDeleteCleanupJobDTO(
        targetStore="minio",
        syncJobId=None,
        status=final_status,
        errorMessage=final_error,
    )


def _write_chunk_access_filters(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    chunk_rows: list[RowMapping],
    version_status: str,
) -> dict:
    """为新 Chunk 写入访问过滤摘要，供检索副本同步和 QA 前置过滤复用。"""
    access_filter = build_chunk_access_filter_context(session, current_user, kb_id)
    for row in chunk_rows:
        session.execute(
            insert(chunk_access_filters).values(
                access_filter_id=new_id(),
                chunk_id=row["chunk_id"],
                kb_id=kb_id,
                permission_code=access_filter.permission_code,
                allow_subject_keys=access_filter.allow_subject_keys,
                deny_subject_keys=access_filter.deny_subject_keys,
                document_status="active",
                version_status=version_status,
                chunk_status=row["status"],
                filter_hash=access_filter.filter_hash,
            )
        )
    return access_filter.to_trace_summary()


def _update_ingest_progress(
    session: Session,
    job_id: UUID,
    stage: str,
    progress: int,
    message: str,
    chunk_count: int = 0,
    processed_count: int = 0,
    stage_timings: dict[str, float] | None = None,
    extra: dict | None = None,
) -> None:
    """更新 IngestJob 进度并提交，让前端轮询能看到长任务当前阶段。"""
    job_row = session.execute(
        select(ingest_jobs.c.result_summary).where(ingest_jobs.c.job_id == job_id).limit(1)
    ).mappings().first()
    result_summary = dict(job_row["result_summary"] or {}) if job_row else {}
    stage_summary = {
        "message": message,
        "chunkCount": chunk_count,
        "processedCount": processed_count,
    }
    if stage_timings:
        result_summary["stageTimings"] = stage_timings
    if extra:
        stage_summary.update(extra)
    stage_summaries = dict(result_summary.get("stageSummaries") or {})
    stage_summaries[stage] = stage_summary
    result_summary.update(
        {
            "currentStage": stage,
            "stageMessage": message,
            "chunkCount": chunk_count,
            "processedCount": processed_count,
            "stageSummaries": stage_summaries,
        }
    )
    session.execute(
        update(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id)
        .values(status="running", stage=stage, progress=progress, result_summary=result_summary)
    )
    session.commit()


class _DictAsObj:
    """Wrap a dict so downstream code can use attribute access (chunk.content)."""

    def __init__(self, d: dict):
        self._d = d

    def __getattr__(self, name: str):
        return self._d.get(name)


def _normalize_chunk_strategy(strategy: str | None) -> str:
    """兼容历史 fixed_size 与新多视图策略命名。"""
    if strategy in {None, "", "fixed_size"}:
        return "fixed"
    return str(strategy)


def _chunk_param(params: dict | None, camel_key: str, snake_key: str, default: int) -> int:
    """读取新旧分块参数名，保持历史 params 兼容。"""
    if not isinstance(params, dict):
        return default
    value = params.get(camel_key, params.get(snake_key, default))
    return int(value) if isinstance(value, (int, float)) and value > 0 else default


def _parse_strategy_param(params: dict | None) -> str:
    """读取入库解析策略，默认走基础解析路由。"""
    if not isinstance(params, dict):
        return "default"
    value = params.get("parseStrategy") or params.get("parse_strategy") or "default"
    return str(value) if value else "default"


def _parse_task_record_to_options(record: ParseTaskRecord | None) -> dict:
    """把 Parser Routing 记录写成 ParseRevision 可持久化的结构。"""
    if record is None:
        return {}
    return {
        "parserRouting": {
            "taskId": record.task_id,
            "fileName": record.file_name,
            "strategy": record.strategy,
            "parserName": record.parser_name,
            "parserVersion": record.parser_version,
            "durationMs": record.duration_ms,
            "success": record.success,
            "qualityFlags": record.quality_flags,
            "errorCode": record.error_code,
            "errorMessage": record.error_message,
            "fallbackUsed": record.fallback_used,
            "fallbackReason": record.fallback_reason,
        }
    }


def _parsed_document_v2_to_options(parsed_v2: ParsedDocumentV2 | None) -> dict:
    """把 ParsedDocumentV2 摘要写入 ParseRevision，避免在状态源外维护重复证据。"""
    if parsed_v2 is None:
        return {}
    return {
        "parsedDocumentV2": {
            "documentId": parsed_v2.document_id,
            "sourceFileName": parsed_v2.source_file_name,
            "mimeType": parsed_v2.mime_type,
            "contentHash": parsed_v2.content_hash,
            "parseVersion": parsed_v2.parse_version,
            "providerName": parsed_v2.provider_name,
            "providerVersion": parsed_v2.provider_version,
            "pageCount": len(parsed_v2.pages),
            "blockCount": len(parsed_v2.blocks),
        }
    }


def _parse_document_for_ingest(
    file_name: str,
    mime_type: str | None,
    source_bytes: bytes,
    chunk_params: dict | None,
) -> tuple[ParsedDocument, ParseTaskRecord]:
    """入库解析统一走 Parser Routing，并沿用 ChunkRevision 的解析与分块参数。"""
    return route_and_parse(
        file_name=file_name,
        mime_type=mime_type,
        file_bytes=source_bytes,
        strategy=_parse_strategy_param(chunk_params),
        chunk_size=_chunk_param(chunk_params, "chunkSize", "chunk_size", 900),
        chunk_overlap=_chunk_param(chunk_params, "chunkOverlap", "chunk_overlap", 120),
    )


def _attach_parsed_document_v2_provenance_to_chunks(
    parsed_document: ParsedDocument,
    parsed_chunks: list,
    document_id: str | UUID,
) -> tuple[list[_DictAsObj], ParsedDocumentV2]:
    """为入库 Chunk 补充 ParsedDocumentV2 块级来源，供引用和后续结构化索引追溯。"""
    parsed_v2 = convert_parsed_document_to_v2(parsed_document)
    parsed_v2.document_id = str(document_id)
    parsed_v2_summary = _parsed_document_v2_to_options(parsed_v2)["parsedDocumentV2"]

    chunks_with_provenance: list[_DictAsObj] = []
    for index, parsed in enumerate(parsed_chunks):
        metadata = dict(parsed.metadata or {})
        block = parsed_v2.blocks[index] if index < len(parsed_v2.blocks) else None
        block_ids = metadata.get("sourceBlockIds") or metadata.get("source_block_ids")
        if not isinstance(block_ids, list) or not block_ids:
            block_ids = [block.block_id if block is not None else f"block_{index}"]
        block_ids = [str(block_id) for block_id in block_ids]

        section_path = _metadata_section_path(metadata, parsed.section)
        metadata.update(
            {
                "parsedDocumentV2": parsed_v2_summary,
                "sourceBlockIds": block_ids,
                "sourceBlockRange": metadata.get("sourceBlockRange") or block_ids,
                "sectionPath": section_path,
                "provenance": {
                    "blockIds": block_ids,
                    "pageNo": parsed.page_no,
                    "section": parsed.section,
                    "contentHash": parsed_v2.content_hash,
                },
            }
        )
        chunks_with_provenance.append(_DictAsObj({
            "content": parsed.content,
            "token_count": parsed.token_count,
            "section": parsed.section,
            "page_no": parsed.page_no,
            "metadata": metadata,
        }))

    return chunks_with_provenance, parsed_v2


def _blocks_to_chunks_from_dicts(
    blocks: list[dict],
    parser_name: str,
    source_extension: str,
    chunk_strategy: str,
    chunk_params: dict,
    document_id: str | UUID,
) -> list[_DictAsObj]:
    """从字典列表形式的 blocks 生成 chunks，根据 chunk 策略执行分块。"""
    # 将字典转换为 ParsedBlock 对象
    parsed_blocks = [
        ParsedBlock(
            content=str(b.get("content", "")).strip(),
            section=b.get("section"),
            page_no=b.get("page_no"),
            metadata=b.get("metadata", {}),
        )
        for b in blocks
        if str(b.get("content", "")).strip()
    ]
    if not parsed_blocks:
        return []

    # 构造临时 ParsedDocument 供分块使用
    temp_parsed = ParsedDocument(
        parser_name=parser_name,
        parser_version="blocks_reuse",
        source_file_name="",
        mime_type=None,
        blocks=parsed_blocks,
    )
    return _apply_chunk_strategy_to_parsed_document(
        temp_parsed, chunk_strategy, chunk_params, document_id
    )


def _blocks_to_chunks_from_parsed_document(
    parsed_document: ParsedDocument,
    chunk_strategy: str,
    chunk_params: dict,
    document_id: str | UUID,
) -> list[_DictAsObj]:
    """从 ParsedDocument 的 blocks 生成 chunks，根据 chunk 策略执行分块。"""
    if not parsed_document.blocks:
        return []
    return _apply_chunk_strategy_to_parsed_document(
        parsed_document, chunk_strategy, chunk_params, document_id
    )


def _apply_chunk_strategy_to_parsed_document(
    parsed_document: ParsedDocument,
    strategy: str,
    params: dict | None,
    document_id: str | UUID,
) -> list[_DictAsObj]:
    """将旧解析结果适配到多视图分块输出，供入库 Worker 统一写入 chunks。"""
    parsed_v2 = convert_parsed_document_to_v2(parsed_document)
    parsed_v2.document_id = str(document_id)
    if _normalize_chunk_strategy(strategy) == "heading":
        last_section = object()
        heading_blocks = []
        for block in parsed_v2.blocks:
            block_type = "heading" if block.section and block.section != last_section else block.block_type
            heading_blocks.append(replace(block, block_type=block_type))
            last_section = block.section
        parsed_v2.blocks = heading_blocks
    chunk_results, revision = execute_chunking(parsed_v2, _normalize_chunk_strategy(strategy), params or {})
    return [
        _DictAsObj(
            {
                "content": chunk.content,
                "token_count": chunk.token_count,
                "section": chunk.section,
                "page_no": chunk.page_no,
                "metadata": {
                    **chunk.metadata,
                    "chunkStrategy": revision.strategy,
                    "chunkViewType": revision.chunk_view_type,
                    "sourceBlockIds": chunk.source_block_ids,
                    "sourceBlockRange": revision.source_block_range,
                    "parentChunkId": chunk.parent_chunk_id,
                },
            }
        )
        for chunk in chunk_results
    ]


def _metadata_section_path(metadata: dict, fallback_section: str | None) -> list[str]:
    """统一旧 metadata 中章节路径的字符串和列表表示。"""
    section_path = metadata.get("sectionPath") or metadata.get("section_path")
    if isinstance(section_path, list):
        return [str(item) for item in section_path if item]
    if isinstance(section_path, str) and section_path:
        return [section_path]
    return [fallback_section] if fallback_section else []


def _ingest_chunk_to_chunk_result(parsed, index: int) -> ChunkResult:
    """把入库前的 ParsedChunk/_DictAsObj 适配为上下文服务使用的 ChunkResult。"""
    metadata = parsed.metadata or {}
    chunk_id = metadata.get("chunkId") or metadata.get("chunk_id") or f"chunk_{index}"
    source_block_ids = metadata.get("sourceBlockIds") or metadata.get("source_block_ids")
    if not isinstance(source_block_ids, list) or not source_block_ids:
        source_block_ids = [f"block_{index}"]
    return ChunkResult(
        chunk_id=str(chunk_id),
        content=parsed.content,
        token_count=parsed.token_count,
        chunk_index=index,
        section=parsed.section,
        page_no=parsed.page_no,
        source_block_ids=[str(block_id) for block_id in source_block_ids],
        parent_chunk_id=metadata.get("parentChunkId") or metadata.get("parent_chunk_id"),
        metadata=dict(metadata),
    )


def _attach_contextual_metadata_to_chunks(
    parsed_document: ParsedDocument,
    parsed_chunks: list,
    chunk_revision_id: str | UUID | None,
    document_id: str | UUID,
) -> list[_DictAsObj]:
    """为入库 Chunk 补充 Contextual Chunking 元数据，保留原始正文作为引用来源。"""
    if chunk_revision_id is None:
        return [_DictAsObj(getattr(chunk, "_d", None) or {
            "content": chunk.content,
            "token_count": chunk.token_count,
            "section": chunk.section,
            "page_no": chunk.page_no,
            "metadata": chunk.metadata or {},
        }) for chunk in parsed_chunks]

    parsed_v2 = convert_parsed_document_to_v2(parsed_document)
    parsed_v2.document_id = str(document_id)
    chunk_results = [
        _ingest_chunk_to_chunk_result(parsed, index)
        for index, parsed in enumerate(parsed_chunks)
    ]
    contextual_by_chunk_id = {
        item.chunk_id: item
        for item in generate_contextual_metadata_with_cache(
            parsed_v2,
            chunk_results,
            str(chunk_revision_id),
        )
    }

    contextual_chunks: list[_DictAsObj] = []
    for index, parsed in enumerate(parsed_chunks):
        metadata = dict(parsed.metadata or {})
        chunk_result = chunk_results[index]
        contextual = contextual_by_chunk_id.get(chunk_result.chunk_id)
        if contextual is not None:
            metadata.update(
                {
                    "contextualSummary": contextual.contextual_summary,
                    "documentBrief": contextual.document_brief,
                    "generationMeta": contextual.generation_meta,
                    "sectionPath": contextual.section_path
                    or _metadata_section_path(metadata, parsed.section),
                    "contextualChunking": {
                        "enabled": True,
                        "source": "ingest_worker",
                        "cache": "memory",
                    },
                    "lateChunking": {
                        "status": "reserved",
                        "enabled": False,
                    },
                }
            )
        contextual_chunks.append(_DictAsObj({
            "content": parsed.content,
            "token_count": parsed.token_count,
            "section": parsed.section,
            "page_no": parsed.page_no,
            "metadata": metadata,
        }))

    return contextual_chunks


def run_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_row: RowMapping,
    job_id: UUID,
    source_bytes: bytes | None = None,
    storage_provider: ObjectStorageProvider | None = None,
) -> RowMapping:
    """执行本地解析切块 Worker，并同步更新版本、作业和副本状态。"""
    job_row = session.execute(
        select(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id, ingest_jobs.c.kb_id == kb_row["kb_id"])
        .limit(1)
    ).mappings().first()
    if job_row is None:
        raise DocumentConflictError("Ingest job not found.")
    if job_row["status"] == "cancelled":
        return job_row
    if job_row["version_id"] is None or job_row["document_id"] is None:
        raise DocumentConflictError("Ingest job has no document version.")

    version_row = session.execute(
        select(document_versions)
        .where(document_versions.c.version_id == job_row["version_id"])
        .limit(1)
    ).mappings().first()
    document_row = session.execute(
        select(documents)
        .where(documents.c.document_id == job_row["document_id"], documents.c.kb_id == kb_row["kb_id"])
        .limit(1)
    ).mappings().first()
    if version_row is None or document_row is None:
        raise DocumentConflictError("Document version not found.")
    chunk_revision_row = _read_ingest_chunk_revision(session, job_row, version_row)
    chunk_revision_id = chunk_revision_row["chunk_revision_id"] if chunk_revision_row else None
    chunk_strategy = chunk_revision_row.get("strategy", "fixed_size") if chunk_revision_row else "fixed_size"
    chunk_params = chunk_revision_row.get("params", {}) if chunk_revision_row else {}
    normalized_chunk_strategy = _normalize_chunk_strategy(chunk_strategy)

    storage = storage_provider or get_object_storage_provider()
    file_row = None
    if source_bytes is None:
        source_bytes, file_row = _read_source_bytes(session, version_row, storage)
    else:
        file_row = session.execute(
            select(stored_files).where(stored_files.c.file_id == version_row["source_file_id"]).limit(1)
        ).mappings().first()

    file_name = file_row["file_name"] if file_row else document_row["name"]
    if source_bytes is None:
        raise DocumentConflictError("Source file content is unavailable.")
    stage_timings: dict[str, float] = {}
    stage_started_at = time.perf_counter()
    _update_ingest_progress(session, job_id, "parse", 20, "正在解析原始文档")
    session.execute(
        update(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id, ingest_jobs.c.started_at.is_(None))
        .values(started_at=func.now())
    )
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_row["version_id"])
        .values(status="processing", parse_status="running", updated_by=current_user.user.userId, updated_at=func.now())
    )

    try:
        job_type = job_row.get("job_type", "upload_parse")
        is_rechunk = job_type == "rechunk" or (job_type == "reparse" and chunk_revision_row is not None)
        parsed_document_for_context: ParsedDocument | None = None
        parsed_document_v2_for_revision: ParsedDocumentV2 | None = None
        parse_task_record: ParseTaskRecord | None = None

        # Check if we can reuse parsed blocks from library
        parsed_blocks_from_library = None
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
                if lib_meta.get("parsed_blocks"):
                    parsed_blocks_from_library = lib_meta["parsed_blocks"]
                elif lib_meta.get("parsed_chunks"):
                    # 兼容旧数据：旧数据存的是 chunks，直接用作 blocks（内容相同）
                    parsed_blocks_from_library = lib_meta["parsed_chunks"]

        if parsed_blocks_from_library:
            # Reuse library parsed blocks (convert dicts to ParsedBlock objects)
            parsed_blocks = [_DictAsObj(d) for d in parsed_blocks_from_library]
            parser_name = "library_reuse"
            parser_version = "library_reuse"
            # 从 blocks 生成 chunks（根据知识库配置的 chunk 策略）
            parsed_chunks = _blocks_to_chunks_from_dicts(
                parsed_blocks_from_library,
                parser_name=parser_name,
                source_extension="",
                chunk_strategy=normalized_chunk_strategy,
                chunk_params=chunk_params,
                document_id=document_row["document_id"],
            )
        elif is_rechunk:
            # Rechunk: try to reuse parsed_blocks, fall back to re-parsing
            version_meta = version_row.get("metadata") or {}
            rechunk_blocks = version_meta.get("parsed_blocks")
            if not rechunk_blocks and version_meta.get("parsed_chunks"):
                # 兼容旧数据
                rechunk_blocks = version_meta.get("parsed_chunks")
            if rechunk_blocks:
                parsed_chunks = _blocks_to_chunks_from_dicts(
                    rechunk_blocks,
                    parser_name=version_meta.get("parserName", "rechunk_reuse"),
                    source_extension="",
                    chunk_strategy=normalized_chunk_strategy,
                    chunk_params=chunk_params,
                    document_id=document_row["document_id"],
                )
                parser_name = version_meta.get("parserName", "rechunk_reuse")
                parser_version = version_meta.get("parserVersion", "rechunk_reuse")
            else:
                # No stored parsed_blocks: re-parse from source file
                parsed_document, parse_task_record = _parse_document_for_ingest(
                    file_name=file_name,
                    mime_type=file_row["mime_type"] if file_row else None,
                    source_bytes=source_bytes or b"",
                    chunk_params=chunk_params,
                )
                parsed_document_for_context = parsed_document
                parsed_chunks = _blocks_to_chunks_from_parsed_document(
                    parsed_document,
                    chunk_strategy=normalized_chunk_strategy,
                    chunk_params=chunk_params,
                    document_id=document_row["document_id"],
                )
                parser_name = parsed_document.parser_name
                parser_version = parsed_document.parser_version
        else:
            parsed_document, parse_task_record = _parse_document_for_ingest(
                file_name=file_name,
                mime_type=file_row["mime_type"] if file_row else None,
                source_bytes=source_bytes or b"",
                chunk_params=chunk_params,
            )
            parsed_document_for_context = parsed_document
            parsed_chunks = _blocks_to_chunks_from_parsed_document(
                parsed_document,
                chunk_strategy=normalized_chunk_strategy,
                chunk_params=chunk_params,
                document_id=document_row["document_id"],
            )
            parser_name = parsed_document.parser_name
            parser_version = parsed_document.parser_version
        if parsed_document_for_context is not None:
            parsed_chunks, parsed_document_v2_for_revision = _attach_parsed_document_v2_provenance_to_chunks(
                parsed_document_for_context,
                parsed_chunks,
                document_row["document_id"],
            )
        if parsed_document_for_context is not None and chunk_revision_id is not None:
            parsed_chunks = _attach_contextual_metadata_to_chunks(
                parsed_document_for_context,
                parsed_chunks,
                chunk_revision_id,
                document_row["document_id"],
            )
        stage_timings["parse"] = round(time.perf_counter() - stage_started_at, 3)

        # 解析完成后创建 ParseRevision（仅复用 parsed_chunks 时跳过）
        rechunk_reused_chunks = is_rechunk and parser_name == "rechunk_reuse"
        content_text = "\n\n".join(chunk.content for chunk in parsed_chunks if chunk.content)
        is_image = parser_name == "vision_text"
        content_format = "markdown" if (parser_name == "markdown" or is_image) else "text"
        if rechunk_reused_chunks:
            generated_parse_revision_id = (
                chunk_revision_row["parse_revision_id"]
                if chunk_revision_row is not None
                else None
            )
        else:
            parse_options_for_revision = _parse_task_record_to_options(parse_task_record)
            parse_options_for_revision.update(_parsed_document_v2_to_options(parsed_document_v2_for_revision))
            if is_image:
                vision_settings = get_settings()
                parse_options_for_revision.update(
                    {
                        "sourceModality": "image",
                        "provider": vision_settings.vision_text_provider,
                        "model": vision_settings.vision_text_model or vision_settings.llm_model,
                        "maxImageSide": vision_settings.vision_text_max_image_side,
                        "authHeader": vision_settings.vision_text_auth_header,
                    }
                )
            generated_parse_revision_id = create_parse_revision(
                session=session,
                document_version_id=version_row["version_id"],
                content_format=content_format,
                content_text=content_text,
                content_hash=_calculate_file_hash(content_text.encode("utf-8")) if content_text else None,
                parser_name=parser_name,
                parser_version=parser_version,
                parse_options=parse_options_for_revision,
                created_by=current_user.user.userId,
            )
        chunk_parse_revision_id = (
            chunk_revision_row["parse_revision_id"]
            if chunk_revision_row is not None
            else generated_parse_revision_id
        )
        old_chunk_ids = [
            row[0]
            for row in session.execute(
                select(chunks.c.chunk_id).where(chunks.c.version_id == version_row["version_id"])
            )
        ]
        provider_set = get_qa_run_providers()
        if old_chunk_ids:
            delete_targets = ["milvus"]
            if kb_row["sparse_index_enabled"]:
                delete_targets.append("opensearch")
            if kb_row["graph_index_enabled"]:
                delete_targets.append("neo4j")
            for target_store in delete_targets:
                _, delete_status, delete_error = _create_index_sync_job(
                    session,
                    kb_row,
                    current_user,
                    target_store,
                    version_row["version_id"],
                    old_chunk_ids,
                    target_store == "milvus",
                    sync_type="delete",
                    provider_set=provider_set,
                )
                if delete_status != "success":
                    raise ProviderError(delete_error or f"{target_store} delete sync failed.")
        session.execute(delete(chunk_access_filters).where(chunk_access_filters.c.chunk_id.in_(select(chunks.c.chunk_id).where(chunks.c.version_id == version_row["version_id"]))))
        session.execute(delete(graph_chunk_refs).where(graph_chunk_refs.c.chunk_id.in_(select(chunks.c.chunk_id).where(chunks.c.version_id == version_row["version_id"]))))
        session.execute(delete(chunks).where(chunks.c.version_id == version_row["version_id"]))
        mark_graph_snapshots_stale(session, kb_row["kb_id"], "chunk_changed", current_user)

        chunk_rows: list[RowMapping] = []
        embedding_by_chunk_id: dict[UUID, list[float]] = {}
        embedding_provider = provider_set.embedding
        chunk_count = len(parsed_chunks)
        stage_started_at = time.perf_counter()
        _update_ingest_progress(
            session,
            job_id,
            "embedding",
            35,
            "正在生成 Chunk Embedding",
            chunk_count=chunk_count,
            processed_count=0,
            stage_timings=stage_timings,
        )
        for index, parsed in enumerate(parsed_chunks, start=1):
            content = parsed.content
            parsed_metadata = parsed.metadata or {}
            # B-321: 使用 contextual 字段构造检索文本
            retrieval_text = build_chunk_retrieval_text({
                "content": content,
                "section_path": parsed_metadata.get("sectionPath"),
                "metadata": parsed_metadata,
            })
            embedding = embedding_provider.embed_query(retrieval_text)
            row = session.execute(
                insert(chunks)
                .values(
                    chunk_id=new_id(),
                    version_id=version_row["version_id"],
                    document_id=document_row["document_id"],
                    kb_id=kb_row["kb_id"],
                    chunk_revision_id=chunk_revision_id,
                    parse_revision_id=chunk_parse_revision_id,
                    document_version_id=version_row["version_id"],
                    chunk_index=index,
                    page_no=parsed.page_no,
                    section=parsed.section,
                    content=content,
                    content_hash=sha256(content.encode("utf-8")).hexdigest(),
                    token_count=parsed.token_count,
                    status="active",
                    section_path=parsed_metadata.get("sectionPath") or parsed_metadata.get("section_path") or parsed.section,
                    heading=parsed_metadata.get("heading") or parsed.section,
                    summary=parsed_metadata.get("summary"),
                    metadata={
                        **parsed_metadata,
                        "sourceFileId": str(file_row["file_id"]) if file_row else None,
                        "sourceFileName": file_name,
                        "embeddingProvider": get_settings().embedding_provider,
                        "embeddingModel": get_settings().embedding_model,
                        "embeddingDimension": len(embedding),
                    },
                )
                .returning(chunks)
            ).mappings().one()
            chunk_rows.append(row)
            embedding_by_chunk_id[row["chunk_id"]] = embedding
            if index == chunk_count or index % 5 == 0:
                _update_ingest_progress(
                    session,
                    job_id,
                    "embedding",
                    min(50, 35 + int(index / max(chunk_count, 1) * 15)),
                    "正在生成 Chunk Embedding",
                    chunk_count=chunk_count,
                    processed_count=index,
                    stage_timings=stage_timings,
                )

        chunk_ids = [row["chunk_id"] for row in chunk_rows]
        stage_timings["embedding"] = round(time.perf_counter() - stage_started_at, 3)
        new_version_status = "active" if document_row["active_version_id"] == version_row["version_id"] else "inactive"
        access_filter = _write_chunk_access_filters(session, current_user, kb_row["kb_id"], chunk_rows, new_version_status)
        dense_payloads = {
            row["chunk_id"]: build_chunk_index_payload(
                row,
                document_status=document_row["status"],
                version_status=new_version_status,
                access_filter=access_filter,
                embedding=embedding_by_chunk_id[row["chunk_id"]],
            )
            for row in chunk_rows
        }
        stage_started_at = time.perf_counter()
        _update_ingest_progress(
            session,
            job_id,
            "dense_index",
            55,
            "正在写入 Dense/Milvus 副本",
            chunk_count=len(chunk_ids),
            processed_count=0,
            stage_timings=stage_timings,
        )
        _, dense_status, dense_error = _create_index_sync_job(
            session,
            kb_row,
            current_user,
            "milvus",
            version_row["version_id"],
            chunk_ids,
            True,
            provider_payloads=dense_payloads,
            provider_set=provider_set,
        )
        stage_timings["dense_index"] = round(time.perf_counter() - stage_started_at, 3)
        sparse_status = "not_required"
        sparse_error = None
        graph_status = "not_required"
        graph_error = None
        graph_extraction_errors: list[dict] = []
        if kb_row["sparse_index_enabled"]:
            stage_started_at = time.perf_counter()
            _update_ingest_progress(
                session,
                job_id,
                "sparse_index",
                65,
                "正在写入 Sparse/OpenSearch 副本",
                chunk_count=len(chunk_ids),
                processed_count=0,
                stage_timings=stage_timings,
            )
            _, sparse_status, sparse_error = _create_index_sync_job(
                session,
                kb_row,
                current_user,
                "opensearch",
                version_row["version_id"],
                chunk_ids,
                kb_row["sparse_required_for_activation"],
                provider_payloads=dense_payloads,
                provider_set=provider_set,
            )
            stage_timings["sparse_index"] = round(time.perf_counter() - stage_started_at, 3)
        if kb_row["graph_index_enabled"]:
            if new_version_status == "active":
                mark_graph_snapshots_stale(session, kb_row["kb_id"], "chunk_changed", current_user)
            graph_snapshot_id = new_id()
            graph_payloads = {
                chunk_id: {**payload, "graphSnapshotId": str(graph_snapshot_id)}
                for chunk_id, payload in dense_payloads.items()
            }
            try:
                stage_started_at = time.perf_counter()
                _update_ingest_progress(
                    session,
                    job_id,
                    "graph_extract",
                    75,
                    "正在并发抽取 Graph 实体关系",
                    chunk_count=len(graph_payloads),
                    processed_count=0,
                    stage_timings=stage_timings,
                )
                graph_items = provider_set.llm.extract_graph(list(graph_payloads.values()))
                graph_extraction_errors = list(getattr(provider_set.llm, "last_graph_extraction_errors", []) or [])
                stage_timings["graph_extract"] = round(time.perf_counter() - stage_started_at, 3)
                _update_ingest_progress(
                    session,
                    job_id,
                    "graph_extract",
                    85,
                    "Graph 实体关系抽取完成",
                    chunk_count=len(graph_payloads),
                    processed_count=len(graph_items),
                    stage_timings=stage_timings,
                    extra={"graphExtractionErrors": graph_extraction_errors},
                )
            except ProviderError as exc:
                graph_items = []
                graph_error = str(exc)
                graph_extraction_errors = list(getattr(provider_set.llm, "last_graph_extraction_errors", []) or [])
                stage_timings["graph_extract"] = round(time.perf_counter() - stage_started_at, 3)
            entity_count = sum(len(item.entities) for item in graph_items)
            relation_count = sum(len(item.relations) for item in graph_items)
            session.execute(
                insert(graph_snapshots).values(
                    graph_snapshot_id=graph_snapshot_id,
                    kb_id=kb_row["kb_id"],
                    source_scope={"versionIds": [str(version_row["version_id"])]},
                    status="running",
                    neo4j_graph_key=f"neo4j:{graph_snapshot_id}",
                    entity_count=entity_count,
                    relation_count=relation_count,
                    community_count=0,
                    job_id=job_id,
                    created_by=current_user.user.userId,
                    updated_by=current_user.user.userId,
                )
            )
            if graph_error is None:
                stage_started_at = time.perf_counter()
                _update_ingest_progress(
                    session,
                    job_id,
                    "graph_index",
                    90,
                    "正在写入 Graph/Neo4j 副本",
                    chunk_count=len(chunk_ids),
                    processed_count=len(graph_items),
                    stage_timings=stage_timings,
                    extra={"graphExtractionErrors": graph_extraction_errors},
                )
                _, graph_status, graph_error = _create_index_sync_job(
                    session,
                    kb_row,
                    current_user,
                    "neo4j",
                    version_row["version_id"],
                    chunk_ids,
                    kb_row["graph_required_for_activation"],
                    provider_payloads=graph_payloads,
                    provider_set=provider_set,
                    graph_items=graph_items,
                    graph_snapshot_id=graph_snapshot_id,
                )
                stage_timings["graph_index"] = round(time.perf_counter() - stage_started_at, 3)
            else:
                graph_status = "failed"
                _create_index_sync_job(
                    session,
                    kb_row,
                    current_user,
                    "neo4j",
                    version_row["version_id"],
                    chunk_ids,
                    kb_row["graph_required_for_activation"],
                    status="failed",
                    error_message=graph_error,
                    provider_payloads=graph_payloads,
                    provider_set=provider_set,
                    graph_items=[],
                )
            session.execute(
                update(graph_snapshots)
                .where(graph_snapshots.c.graph_snapshot_id == graph_snapshot_id)
                .values(
                    status="success" if graph_status == "success" else "failed",
                    stale_reason=graph_error,
                    updated_by=current_user.user.userId,
                    updated_at=func.now(),
                )
            )

        retrieval_ready = dense_status == "success"
        if kb_row["sparse_required_for_activation"] and sparse_status != "success":
            retrieval_ready = False
        if kb_row["graph_required_for_activation"] and graph_status != "success":
            retrieval_ready = False
        index_errors = [
            {"targetStore": "milvus", "errorMessage": dense_error} if dense_status != "success" else None,
            {"targetStore": "opensearch", "errorMessage": sparse_error} if sparse_status == "failed" else None,
            {"targetStore": "neo4j", "errorMessage": graph_error} if graph_status == "failed" else None,
        ]
        index_errors = [item for item in index_errors if item]
        version_final_status = new_version_status if not index_errors else "failed"
        ingest_final_status = "success" if not index_errors else "failed"

        total_tokens = sum(row["token_count"] or 0 for row in chunk_rows)
        error_summary = {
            "parse": {"status": "success", "error": None},
            "embedding": {"status": "success", "error": None},
            "milvus": {"status": dense_status, "error": dense_error},
            "opensearch": {"status": sparse_status, "error": sparse_error},
            "neo4j": {"status": graph_status, "error": graph_error},
        }
        stage_timings["completed"] = 0
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == version_row["version_id"])
            .values(
                status=version_final_status,
                parse_status="success",
                dense_index_status=dense_status,
                sparse_index_status=sparse_status,
                graph_index_status=graph_status,
                retrieval_ready=retrieval_ready,
                chunk_count=len(chunk_rows),
                token_count=total_tokens,
                error_code="INDEX_SYNC_FAILED" if index_errors else None,
                error_message="; ".join(
                    f"{item['targetStore']}: {item['errorMessage']}" for item in index_errors
                ) if index_errors else None,
                metadata={
                    **(version_row["metadata"] or {}),
                    "parserName": parser_name,
                    "parserVersion": parser_version,
                    "sourceFileName": file_name,
                    "embeddingProvider": get_settings().embedding_provider,
                    "embeddingModel": get_settings().embedding_model,
                    "error_summary": error_summary,
                    "graphExtractionErrors": graph_extraction_errors,
                    **({"sourceModality": "image",
                        "visionTextProvider": get_settings().vision_text_provider,
                        "visionModel": get_settings().vision_text_model or get_settings().llm_model,
                        "sourceMimeType": (parsed_chunks[0].metadata.get("sourceMimeType") if parsed_chunks else None),
                        "sourceFileSize": (parsed_chunks[0].metadata.get("sourceFileSize") if parsed_chunks else None),
                        "imageTokens": (parsed_chunks[0].metadata.get("imageTokens") if parsed_chunks else None),
                        "image": {
                            "region": (parsed_chunks[0].metadata.get("region", "full") if parsed_chunks else "full"),
                            "visionConfidence": (parsed_chunks[0].metadata.get("visionConfidence", "unknown") if parsed_chunks else "unknown"),
                        }} if is_image else {}),
                },
                updated_by=current_user.user.userId,
                updated_at=func.now(),
            )
        )
        job_row = session.execute(
            update(ingest_jobs)
            .where(ingest_jobs.c.job_id == job_id)
            .values(
                status=ingest_final_status,
                stage="completed" if not index_errors else "failed",
                progress=100,
                error_code="INDEX_SYNC_FAILED" if index_errors else None,
                error_message="; ".join(
                    f"{item['targetStore']}: {item['errorMessage']}" for item in index_errors
                ) if index_errors else None,
                result_summary={
                    **({"chunk_revision_id": str(chunk_revision_id)} if chunk_revision_id else {}),
                    "chunkCount": len(chunk_rows),
                    "tokenCount": total_tokens,
                    "parserName": parser_name,
                    "parserVersion": parser_version,
                    "embeddingProvider": get_settings().embedding_provider,
                    "embeddingModel": get_settings().embedding_model,
                    "indexErrors": index_errors,
                    "error_summary": error_summary,
                    "stageTimings": stage_timings,
                    "graphExtractionErrors": graph_extraction_errors,
                },
                finished_at=func.now(),
            )
            .returning(ingest_jobs)
        ).mappings().one()
        if chunk_revision_id is not None and ingest_final_status == "success":
            from app.services.binding_service import complete_chunk_revision_build

            complete_chunk_revision_build(session, chunk_revision_id, len(chunk_rows))
    except (DocumentParseError, ProviderError) as exc:
        if chunk_revision_id is not None:
            from app.services.binding_service import fail_chunk_revision

            fail_chunk_revision(session, chunk_revision_id, str(exc))
        error_code = exc.error_code if isinstance(exc, DocumentParseError) else "INGEST_EMBEDDING_FAILED"
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == version_row["version_id"])
            .values(
                status="failed",
                parse_status="failed",
                dense_index_status="failed",
                sparse_index_status="failed" if kb_row["sparse_index_enabled"] else "not_required",
                graph_index_status="failed" if kb_row["graph_index_enabled"] else "not_required",
                retrieval_ready=False,
                error_code=error_code,
                error_message=str(exc),
                metadata={
                    **(version_row["metadata"] or {}),
                    "error_summary": {
                        "parse": {"status": "failed" if isinstance(exc, DocumentParseError) else "success", "error": str(exc)},
                        "embedding": {"status": "failed" if not isinstance(exc, DocumentParseError) else "not_started", "error": str(exc)},
                        "milvus": {"status": "failed", "error": None},
                        "opensearch": {
                            "status": "failed" if kb_row["sparse_index_enabled"] else "not_required",
                            "error": None,
                        },
                        "neo4j": {
                            "status": "failed" if kb_row["graph_index_enabled"] else "not_required",
                            "error": None,
                        },
                    },
                },
                updated_by=current_user.user.userId,
                updated_at=func.now(),
            )
        )
        job_row = session.execute(
            update(ingest_jobs)
            .where(ingest_jobs.c.job_id == job_id)
            .values(
                status="failed",
                stage="failed",
                progress=100,
                error_code=error_code,
                error_message=str(exc),
                result_summary={
                    "error_summary": {
                        "parse": {"status": "failed" if isinstance(exc, DocumentParseError) else "success", "error": str(exc)},
                        "embedding": {"status": "failed" if not isinstance(exc, DocumentParseError) else "not_started", "error": str(exc)},
                    }
                },
                finished_at=func.now(),
            )
            .returning(ingest_jobs)
        ).mappings().one()
    except Exception as exc:
        if chunk_revision_id is not None:
            from app.services.binding_service import fail_chunk_revision

            fail_chunk_revision(session, chunk_revision_id, str(exc))
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == version_row["version_id"])
            .values(
                status="failed",
                parse_status="failed",
                dense_index_status="failed",
                sparse_index_status="failed" if kb_row["sparse_index_enabled"] else "not_required",
                graph_index_status="failed" if kb_row["graph_index_enabled"] else "not_required",
                retrieval_ready=False,
                error_code="INGEST_PARSE_FAILED",
                error_message=str(exc),
                metadata={
                    **(version_row["metadata"] or {}),
                    "error_summary": {
                        "parse": {"status": "failed", "error": str(exc)},
                        "embedding": {"status": "not_started", "error": None},
                        "milvus": {"status": "failed", "error": None},
                        "opensearch": {
                            "status": "failed" if kb_row["sparse_index_enabled"] else "not_required",
                            "error": None,
                        },
                        "neo4j": {
                            "status": "failed" if kb_row["graph_index_enabled"] else "not_required",
                            "error": None,
                        },
                    },
                },
                updated_by=current_user.user.userId,
                updated_at=func.now(),
            )
        )
        job_row = session.execute(
            update(ingest_jobs)
            .where(ingest_jobs.c.job_id == job_id)
            .values(
                status="failed",
                stage="failed",
                progress=100,
                error_code="INGEST_PARSE_FAILED",
                error_message=str(exc),
                result_summary={
                    "error_summary": {
                        "parse": {"status": "failed", "error": str(exc)},
                        "embedding": {"status": "not_started", "error": None},
                    }
                },
                finished_at=func.now(),
            )
            .returning(ingest_jobs)
        ).mappings().one()
    return job_row


def _to_current_user_from_user_row(user_row: RowMapping) -> CurrentUserResponse:
    """将作业创建人行转换为 Worker 执行所需的用户上下文。"""
    return CurrentUserResponse(
        user=UserDTO(
            userId=str(user_row["user_id"]),
            username=user_row["username"],
            displayName=user_row["display_name"],
            email=user_row["email"],
            platformRole=user_row["platform_role"],
            securityLevel=user_row["security_level"],
            status=user_row["status"],
        ),
        platformPermissions=[],
        visibleKbCount=0,
    )


def _mark_ingest_enqueue_failed(session: Session, job_id: UUID, error_message: str) -> None:
    """记录 Celery 入队失败，避免 queued 作业永久悬挂。"""
    job_row = session.execute(
        select(ingest_jobs).where(ingest_jobs.c.job_id == job_id).limit(1)
    ).mappings().first()
    if job_row is None:
        return
    kb_row = session.execute(
        select(knowledge_bases).where(knowledge_bases.c.kb_id == job_row["kb_id"]).limit(1)
    ).mappings().first()
    if job_row["version_id"] is not None:
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == job_row["version_id"])
            .values(
                status="failed",
                parse_status="failed",
                dense_index_status="failed",
                sparse_index_status="failed" if kb_row and kb_row["sparse_index_enabled"] else "not_required",
                graph_index_status="failed" if kb_row and kb_row["graph_index_enabled"] else "not_required",
                retrieval_ready=False,
                error_code="INGEST_ENQUEUE_FAILED",
                error_message=error_message,
                updated_at=func.now(),
            )
        )
    session.execute(
        update(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id)
        .values(
            status="failed",
            stage="enqueue",
            progress=100,
            error_code="INGEST_ENQUEUE_FAILED",
            error_message=error_message,
            result_summary={"error_summary": {"enqueue": {"status": "failed", "error": error_message}}},
            finished_at=func.now(),
        )
    )
    session.commit()


def enqueue_ingest_job(session: Session, job_id: UUID) -> None:
    """将文档入库作业投递给 Celery，失败时落库为 failed 并抛出业务异常。"""
    try:
        from app.worker import run_document_ingest_task

        run_document_ingest_task.delay(str(job_id))
    except Exception as exc:
        error_message = f"Failed to enqueue ingest job: {exc}"
        _mark_ingest_enqueue_failed(session, job_id, error_message)
        raise DocumentIngestEnqueueError(error_message) from exc


def run_ingest_job_by_id(job_id: UUID) -> dict:
    """Worker 入口：重新打开数据库会话并按作业创建人上下文执行入库。"""
    import time

    session = get_session_factory()()
    try:
        job_row = None
        for attempt in range(4):
            job_row = session.execute(
                select(ingest_jobs).where(ingest_jobs.c.job_id == job_id).limit(1)
            ).mappings().first()
            if job_row is not None:
                break
            if attempt < 3:
                time.sleep(0.5 * (attempt + 1))
                session.close()
                session = get_session_factory()()
        if job_row is None:
            raise DocumentConflictError("Ingest job not found.")
        kb_row = session.execute(
            select(knowledge_bases)
            .where(knowledge_bases.c.kb_id == job_row["kb_id"], knowledge_bases.c.deleted_at.is_(None))
            .limit(1)
        ).mappings().first()
        if kb_row is None:
            raise DocumentConflictError("Knowledge base not found.")
        user_row = session.execute(
            select(users).where(users.c.user_id == job_row["created_by"]).limit(1)
        ).mappings().first()
        if user_row is None:
            raise DocumentConflictError("Ingest job creator not found.")

        current_user = _to_current_user_from_user_row(user_row)
        final_job_row = run_ingest_job(session, current_user, kb_row, job_id)
        session.commit()
        return {
            "jobId": str(final_job_row["job_id"]),
            "kbId": str(final_job_row["kb_id"]),
            "status": final_job_row["status"],
            "stage": final_job_row["stage"],
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_document_upload(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    file_name: str,
    mime_type: str | None,
    file_bytes: bytes,
    name: str | None,
    storage_provider: ObjectStorageProvider | None = None,
    force_upload: bool = False,
) -> DocumentUploadResponse | None:
    """写入原始文件对象，并事务内创建文件、文档、首版本和 queued IngestJob。

    force_upload 为 False 时，如果同一知识库内已存在相同 checksum 的文件，返回 duplicate 响应。
    """
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")
    require_active_dict_item(session, "document_source_type", "upload", "sourceType")
    require_active_dict_item(session, "file_role", "source", "fileRole")

    file_hash = _calculate_file_hash(file_bytes)

    if not force_upload:
        duplicate = check_file_hash_duplicate(session, kb_id, file_hash)
        if duplicate:
            return DocumentUploadResponse(
                status="duplicate",
                message="文件已存在",
                duplicateInfo=duplicate,
                fileHash=file_hash,
            )

    settings = get_settings()
    actor_id = current_user.user.userId
    document_id = new_id()
    version_id = new_id()
    file_id = new_id()
    job_id = new_id()
    normalized_file_name = _safe_file_name(file_name)
    document_name = (name or normalized_file_name).strip() or normalized_file_name
    checksum = file_hash
    object_prefix = settings.storage_object_prefix.strip("/")
    object_path = f"kb/{kb_id}/documents/{document_id}/versions/{version_id}/{normalized_file_name}"
    object_key = f"{object_prefix}/{object_path}" if object_prefix else object_path
    sparse_status = "pending" if kb_row["sparse_index_enabled"] else "not_required"
    graph_status = "pending" if kb_row["graph_index_enabled"] else "not_required"
    storage = storage_provider or get_object_storage_provider()
    stored_object = storage.put_object(object_key=object_key, data=file_bytes, content_type=mime_type)

    try:
        stored_file_row = session.execute(
            insert(stored_files)
            .values(
                file_id=file_id,
                bucket=stored_object.bucket,
                object_key=stored_object.object_key,
                file_name=normalized_file_name,
                mime_type=mime_type,
                file_size=stored_object.size,
                checksum=checksum,
                file_role="source",
                status="active",
                created_by=actor_id,
            )
            .returning(stored_files)
        ).mappings().one()
        document_row = session.execute(
            insert(documents)
            .values(
                document_id=document_id,
                kb_id=kb_id,
                name=document_name,
                source_type="upload",
                status="active",
                metadata={},
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(documents)
        ).mappings().one()
        version_row = session.execute(
            insert(document_versions)
            .values(
                version_id=version_id,
                document_id=document_id,
                version_no=1,
                source_file_id=file_id,
                status="processing",
                parse_status="pending",
                dense_index_status="pending",
                sparse_index_status=sparse_status,
                graph_index_status=graph_status,
                retrieval_ready=False,
                chunk_count=0,
                metadata={},
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(document_versions)
        ).mappings().one()
        document_row = session.execute(
            update(documents)
            .where(documents.c.document_id == document_id)
            .values(active_version_id=version_id)
            .returning(documents)
        ).mappings().one()
        job_row = session.execute(
            insert(ingest_jobs)
            .values(
                job_id=job_id,
                kb_id=kb_id,
                document_id=document_id,
                version_id=version_id,
                job_type="upload_parse",
                status="queued",
                stage="queued",
                progress=0,
                result_summary={},
                created_by=actor_id,
            )
            .returning(ingest_jobs)
        ).mappings().one()
        _insert_audit_log(
            session,
            current_user,
            "document.upload",
            "document",
            document_id,
            kb_id,
            document_id,
            {"versionId": str(version_id), "jobId": str(job_id), "fileName": normalized_file_name},
        )
        document_row = session.execute(select(documents).where(documents.c.document_id == document_id)).mappings().one()
        version_row = session.execute(select(document_versions).where(document_versions.c.version_id == version_id)).mappings().one()
        session.commit()
    except Exception:
        session.rollback()
        try:
            storage.delete_object(stored_object.object_key)
        except Exception:
            # 保留原始数据库异常，补偿删除失败交给后续运维巡检处理。
            pass
        raise
    enqueue_ingest_job(session, job_id)

    return DocumentUploadResponse(
        status="success",
        message="上传成功",
        document=_to_document_dto(document_row),
        version=_to_version_dto(version_row),
        ingestJob=_to_ingest_job_dto(job_row),
        storedFile=_to_stored_file_dto(stored_file_row),
        fileHash=file_hash,
    )


def list_documents(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    keyword: str | None,
) -> PageResponse[DocumentDTO] | None:
    """分页查询文档中心列表，按更新时间倒序返回当前知识库文档。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = _document_belongs_to_kb_condition(kb_id)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            documents.c.name.ilike(keyword_pattern),
            documents.c.document_id.cast(sa.String).ilike(keyword_pattern),
        )

    total = session.execute(select(func.count()).select_from(documents).where(condition)).scalar_one()
    rows = session.execute(
        _select_kb_documents(kb_id)
        .where(condition)
        .order_by(documents.c.updated_at.desc(), documents.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_document_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_document_detail(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
) -> DocumentDetailDTO | None:
    """读取文档详情，并附带 active version 摘要用于 P07 顶部信息区。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    document_row = session.execute(
        _select_kb_documents(kb_id)
        .where(
            _document_belongs_to_kb_condition(kb_id),
            documents.c.document_id == document_id,
        )
        .limit(1)
    ).mappings().first()
    if document_row is None:
        return None

    active_version = None
    if document_row["active_version_id"]:
        active_version = session.execute(
            select(document_versions)
            .where(document_versions.c.version_id == document_row["active_version_id"])
            .limit(1)
        ).mappings().first()

    return DocumentDetailDTO(
        document=_to_document_dto(document_row),
        activeVersion=_to_version_dto(active_version) if active_version else None,
    )


def download_document_source(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    storage_provider: ObjectStorageProvider | None = None,
) -> DocumentSourceDownload | None:
    """读取当前 active version 的原始文件内容，供 API 层返回文件流。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.document.download")

    document_row = session.execute(
        _select_kb_documents(kb_id)
        .where(
            _document_belongs_to_kb_condition(kb_id),
            documents.c.document_id == document_id,
        )
        .limit(1)
    ).mappings().first()
    if document_row is None:
        return None
    if not document_row["active_version_id"]:
        raise DocumentSourceFileUnavailableError("文档没有可下载的 active version，请先完成文档入库。")

    source_row = session.execute(
        select(document_versions, stored_files)
        .select_from(
            document_versions.join(stored_files, document_versions.c.source_file_id == stored_files.c.file_id)
        )
        .where(
            document_versions.c.version_id == document_row["active_version_id"],
            document_versions.c.document_id == document_id,
            stored_files.c.status == "active",
        )
        .limit(1)
    ).mappings().first()
    if source_row is None:
        raise DocumentSourceFileUnavailableError("原始文件元数据不可用，请重新上传文档或联系管理员。")

    storage = storage_provider or get_object_storage_provider()
    content = storage.get_object(source_row["object_key"])
    if content is None:
        raise DocumentSourceFileUnavailableError("原始文件在对象存储中不存在，请重新上传文档或联系管理员恢复备份。")

    return DocumentSourceDownload(
        file_name=source_row["file_name"],
        mime_type=source_row["mime_type"],
        content=content,
    )


def delete_document(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    confirm_impact: bool,
    reason: str | None,
    storage_provider: ObjectStorageProvider | None = None,
) -> DocumentDeleteResponse | None:
    """逻辑删除文档并尽力物理清理外部副本；PostgreSQL 状态先提交为准。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")
    if not confirm_impact:
        raise DocumentConflictError("confirmImpact must be true.")

    document_row = session.execute(
        _select_kb_documents(kb_id)
        .where(
            _document_belongs_to_kb_condition(kb_id),
            documents.c.document_id == document_id,
        )
        .limit(1)
    ).mappings().first()
    if document_row is None:
        return None

    chunk_ids = [
        row[0]
        for row in session.execute(
            select(chunks.c.chunk_id).where(chunks.c.kb_id == kb_id, chunks.c.document_id == document_id)
        )
    ]
    stored_file_rows = list(
        session.execute(
            select(stored_files)
            .where(
                stored_files.c.file_id.in_(
                    select(document_versions.c.source_file_id).where(document_versions.c.document_id == document_id)
                )
            )
        ).mappings()
    )
    stored_file_ids = [row["file_id"] for row in stored_file_rows]
    actor_id = current_user.user.userId
    audit_log_id = _insert_audit_log(
        session,
        current_user,
        "document.delete_requested",
        "document",
        document_id,
        kb_id,
        document_id,
        {
            "reason": reason,
            "chunkCount": len(chunk_ids),
            "sourceFileIds": [str(file_id) for file_id in stored_file_ids],
        },
    )

    deleted_document_row = session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(
            status="archived",
            deleted_at=func.now(),
            deleted_by=actor_id,
            updated_at=func.now(),
            updated_by=actor_id,
        )
        .returning(documents)
    ).mappings().one()
    if chunk_ids:
        session.execute(
            update(chunks)
            .where(chunks.c.chunk_id.in_(chunk_ids))
            .values(status="deleted")
        )
        session.execute(
            update(chunk_access_filters)
            .where(chunk_access_filters.c.chunk_id.in_(chunk_ids))
            .values(chunk_status="deleted", updated_at=func.now())
        )
        session.execute(delete(graph_chunk_refs).where(graph_chunk_refs.c.chunk_id.in_(chunk_ids)))
    if stored_file_ids:
        session.execute(
            update(stored_files)
            .where(stored_files.c.file_id.in_(stored_file_ids))
            .values(status="deleted", deleted_at=func.now(), deleted_by=actor_id)
        )
    mark_graph_snapshots_stale(session, kb_id, "document_deleted", current_user)
    session.commit()

    cleanup_jobs: list[DocumentDeleteCleanupJobDTO] = []
    warnings: list[str] = []
    if chunk_ids:
        targets = ["milvus"]
        if kb_row["sparse_index_enabled"]:
            targets.append("opensearch")
        if kb_row["graph_index_enabled"]:
            targets.append("neo4j")
        for target_store in targets:
            try:
                sync_job_id, cleanup_status, cleanup_error = _create_index_sync_job(
                    session,
                    kb_row,
                    current_user,
                    target_store,
                    None,
                    chunk_ids,
                    False,
                    sync_type="delete",
                )
                session.commit()
                cleanup_jobs.append(
                    DocumentDeleteCleanupJobDTO(
                        targetStore=target_store,
                        syncJobId=str(sync_job_id),
                        status=cleanup_status,
                        errorMessage=cleanup_error,
                    )
                )
                if cleanup_status != "success":
                    warnings.append(f"{target_store} 副本清理失败，业务删除已生效。")
            except Exception as exc:
                session.rollback()
                warnings.append(f"{target_store} 副本清理作业创建失败，业务删除已生效：{exc}")

    try:
        minio_job = _create_minio_cleanup_job(session, kb_id, current_user, stored_file_rows, storage_provider)
        if minio_job is not None:
            session.commit()
            cleanup_jobs.append(minio_job)
            if minio_job.status != "success":
                warnings.append("minio 原始文件清理失败，业务删除已生效。")
    except Exception as exc:
        session.rollback()
        warnings.append(f"minio 原始文件清理作业创建失败，业务删除已生效：{exc}")

    return DocumentDeleteResponse(
        documentId=str(document_id),
        deletedAt=deleted_document_row["deleted_at"].isoformat(),
        auditLogId=str(audit_log_id),
        cleanupJobs=cleanup_jobs,
        warnings=warnings,
    )


def get_document_quality_summary(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> DocumentQualitySummaryDTO | None:
    """汇总文档解析、Chunk 和权限过滤摘要质量问题，作为治理入口数据源。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    document_count = session.execute(
        select(func.count()).select_from(documents).where(_document_belongs_to_kb_condition(kb_id))
    ).scalar_one()
    active_chunk_count = session.execute(
        select(func.count()).select_from(chunks).where(chunks.c.kb_id == kb_id, chunks.c.status == "active")
    ).scalar_one()
    failed_versions = session.execute(
        select(document_versions.c.document_id, document_versions.c.version_id, document_versions.c.error_message)
        .select_from(document_versions.join(documents, document_versions.c.document_id == documents.c.document_id))
        .where(_document_belongs_to_kb_condition(kb_id), document_versions.c.parse_status == "failed")
    ).mappings().all()
    empty_chunks = session.execute(
        select(chunks.c.document_id, chunks.c.version_id, chunks.c.chunk_id)
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active", func.length(func.trim(chunks.c.content)) == 0)
    ).mappings().all()
    duplicate_groups = session.execute(
        select(chunks.c.content_hash, func.count().label("chunk_count"))
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active", chunks.c.content_hash.is_not(None))
        .group_by(chunks.c.content_hash)
        .having(func.count() > 1)
    ).mappings().all()
    duplicate_hashes = [row["content_hash"] for row in duplicate_groups if row["content_hash"]]
    duplicate_samples: dict[str, list[str]] = {content_hash: [] for content_hash in duplicate_hashes}
    if duplicate_hashes:
        sample_rows = session.execute(
            select(chunks.c.content_hash, chunks.c.chunk_id)
            .where(
                chunks.c.kb_id == kb_id,
                chunks.c.status == "active",
                chunks.c.content_hash.in_(duplicate_hashes),
            )
            .order_by(chunks.c.content_hash.asc(), chunks.c.chunk_index.asc())
        ).mappings().all()
        for row in sample_rows:
            samples = duplicate_samples.setdefault(row["content_hash"], [])
            if len(samples) < 5:
                samples.append(str(row["chunk_id"]))
    permission_anomalies = session.execute(
        select(chunks.c.document_id, chunks.c.version_id, chunks.c.chunk_id)
        .select_from(chunks.outerjoin(chunk_access_filters, chunks.c.chunk_id == chunk_access_filters.c.chunk_id))
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active", chunk_access_filters.c.chunk_id.is_(None))
    ).mappings().all()

    issues: list[DocumentQualityIssueDTO] = []
    for row in failed_versions[:20]:
        issues.append(
            DocumentQualityIssueDTO(
                issueType="parse_failed",
                severity="high",
                documentId=str(row["document_id"]),
                versionId=str(row["version_id"]),
                recommendedAction="reparse",
                count=1,
                message=row["error_message"] or "文档版本解析失败。",
            )
        )
    for row in empty_chunks[:20]:
        issues.append(
            DocumentQualityIssueDTO(
                issueType="empty_chunk",
                severity="medium",
                documentId=str(row["document_id"]),
                versionId=str(row["version_id"]),
                chunkId=str(row["chunk_id"]),
                sampleChunkIds=[str(row["chunk_id"])],
                recommendedAction="exclude_or_reparse",
                count=1,
                message="Chunk 正文为空，建议重解析或排除。",
            )
        )
    for row in duplicate_groups[:20]:
        content_hash = row["content_hash"]
        issues.append(
            DocumentQualityIssueDTO(
                issueType="duplicate_chunk",
                severity="low",
                contentHash=str(content_hash),
                sampleChunkIds=duplicate_samples.get(content_hash, []),
                recommendedAction="review_duplicate_chunks",
                count=row["chunk_count"],
                message=f"存在 {row['chunk_count']} 个重复正文 Chunk，contentHash={content_hash}。",
            )
        )
    for row in permission_anomalies[:20]:
        issues.append(
            DocumentQualityIssueDTO(
                issueType="permission_filter_missing",
                severity="high",
                documentId=str(row["document_id"]),
                versionId=str(row["version_id"]),
                chunkId=str(row["chunk_id"]),
                sampleChunkIds=[str(row["chunk_id"])],
                recommendedAction="rebuild_index",
                targetStore="milvus",
                count=1,
                message="Chunk 缺少访问过滤摘要，检索副本同步前应重建。",
            )
        )

    return DocumentQualitySummaryDTO(
        kbId=str(kb_id),
        documentCount=document_count,
        activeChunkCount=active_chunk_count,
        failedVersionCount=len(failed_versions),
        emptyChunkCount=len(empty_chunks),
        duplicateChunkGroupCount=len(duplicate_groups),
        permissionAnomalyCount=len(permission_anomalies),
        issues=issues,
    )


def run_bulk_document_governance(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    operation: str,
    document_ids: list[UUID],
    confirm_impact: bool,
    reason: str | None,
    target_store: str | None,
) -> BulkDocumentGovernanceResponse | None:
    """执行批量文档治理动作；所有高影响动作必须带二次确认。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")
    if not confirm_impact:
        raise DocumentConflictError("confirmImpact must be true.")

    if operation in ("reparse", "full_governance"):
        affected: list[str] = []
        errors: list[str] = []
        for document_id in document_ids:
            try:
                response = reparse_document(session, current_user, kb_id, document_id, reason)
                if response is None:
                    errors.append(f"{document_id}: document not found")
                else:
                    affected.append(str(document_id))
            except Exception as exc:
                errors.append(f"{document_id}: {exc}")
        return BulkDocumentGovernanceResponse(
            operation=operation,
            requestedCount=len(document_ids),
            successCount=len(affected),
            failedCount=len(errors),
            affectedIds=affected,
            errors=errors,
        )

    if operation == "disable":
        result = session.execute(
            update(documents)
            .where(_document_belongs_to_kb_condition(kb_id), documents.c.document_id.in_(document_ids))
            .values(status="disabled", updated_by=current_user.user.userId, updated_at=func.now())
            .returning(documents.c.document_id)
        )
        affected_ids = [str(row[0]) for row in result]
        for document_id in affected_ids:
            _insert_audit_log(
                session,
                current_user,
                "document.batch_disable",
                "document",
                UUID(document_id),
                kb_id,
                UUID(document_id),
                {"reason": reason},
            )
        session.commit()
        return BulkDocumentGovernanceResponse(
            operation=operation,
            requestedCount=len(document_ids),
            successCount=len(affected_ids),
            failedCount=len(document_ids) - len(affected_ids),
            affectedIds=affected_ids,
            errors=[],
        )

    if operation == "rebuild_index":
        if not target_store:
            raise DocumentConflictError("targetStore is required for rebuild_index.")
        if target_store not in {"milvus", "opensearch", "neo4j"}:
            raise DocumentConflictError("Unsupported target store.")
        affected_sync_job_ids: list[str] = []
        errors: list[str] = []
        success_count = 0
        for document_id in document_ids:
            try:
                response = rebuild_index_sync(
                    session,
                    current_user,
                    kb_id,
                    target_store,
                    document_id=document_id,
                )
                if response is None:
                    errors.append(f"{document_id}: document not found")
                elif response.status == "failed":
                    errors.append(f"{document_id}: {response.errorMessage or 'index rebuild failed'}")
                    affected_sync_job_ids.append(response.syncJobId)
                else:
                    success_count += 1
                    affected_sync_job_ids.append(response.syncJobId)
            except Exception as exc:
                errors.append(f"{document_id}: {exc}")
        return BulkDocumentGovernanceResponse(
            operation=operation,
            requestedCount=len(document_ids),
            successCount=success_count,
            failedCount=len(errors),
            affectedIds=affected_sync_job_ids,
            errors=errors,
        )

    raise DocumentConflictError("Unsupported batch governance operation.")


def list_document_versions(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
) -> list[DocumentVersionDTO] | None:
    """返回指定文档的版本列表，默认按版本号倒序。"""
    if get_document_detail(session, current_user, kb_id, document_id) is None:
        return None

    rows = session.execute(
        select(document_versions)
        .where(document_versions.c.document_id == document_id)
        .order_by(document_versions.c.version_no.desc(), document_versions.c.created_at.desc())
    ).mappings()
    return [_to_version_dto(row) for row in rows]


def list_ingest_jobs(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    document_id: UUID | None = None,
) -> PageResponse[IngestJobDTO] | None:
    """分页查询知识库入库作业，可按文档 ID 收窄范围。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = ingest_jobs.c.kb_id == kb_id
    if document_id is not None:
        condition = condition & (ingest_jobs.c.document_id == document_id)

    total = session.execute(select(func.count()).select_from(ingest_jobs).where(condition)).scalar_one()
    rows = session.execute(
        select(ingest_jobs)
        .where(condition)
        .order_by(ingest_jobs.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_ingest_job_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    job_id: UUID,
) -> IngestJobDTO | None:
    """读取单个入库作业；不可见知识库和不存在作业统一返回 None。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    row = session.execute(
        select(ingest_jobs)
        .where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.job_id == job_id)
        .limit(1)
    ).mappings().first()
    return _to_ingest_job_dto(row) if row else None


def list_chunks(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    version_id: UUID,
    page_no: int,
    page_size: int,
) -> PageResponse[ChunkDTO] | None:
    """分页读取当前可检索 Chunk；绑定文档优先限定 active ChunkRevision。"""
    if get_document_detail(session, current_user, kb_id, document_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.chunk.read")

    active_chunk_revision_id = _read_active_chunk_revision_id(session, kb_id, version_id)
    condition = (
        (chunks.c.kb_id == kb_id)
        & (chunks.c.document_id == document_id)
        & (chunks.c.version_id == version_id)
        & (chunks.c.status == "active")
    )
    if active_chunk_revision_id is not None:
        condition = condition & (chunks.c.chunk_revision_id == active_chunk_revision_id)
    total = session.execute(select(func.count()).select_from(chunks).where(condition)).scalar_one()
    rows = session.execute(
        select(chunks)
        .where(condition)
        .order_by(chunks.c.chunk_index.asc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_chunk_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_chunk(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    chunk_id: UUID,
) -> ChunkDTO | None:
    """读取单个 Chunk 正文，允许历史 Evidence 回溯 retired Chunk。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.chunk.read")

    row = session.execute(
        select(chunks)
        .where(
            chunks.c.kb_id == kb_id,
            chunks.c.chunk_id == chunk_id,
            chunks.c.status.in_(["active", "retired"]),
            chunks.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    return _to_chunk_dto(row) if row else None


def get_block_provenance(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    block_id: str,
) -> dict | None:
    """获取指定 block 的 provenance 信息。

    从 Chunk metadata 中查找包含指定 block_id 的 chunk，返回其 provenance 信息。
    """
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.chunk.read")

    # 查找包含该 block_id 的 chunk
    # PostgreSQL JSON 查询：metadata->'sourceBlockIds' 包含指定 block_id
    rows = session.execute(
        select(chunks).where(
            chunks.c.kb_id == kb_id,
            chunks.c.document_id == document_id,
            chunks.c.status == "active",
            chunks.c.deleted_at.is_(None),
        )
    ).mappings().all()

    for row in rows:
        metadata = row["metadata"] or {}
        source_block_ids = metadata.get("sourceBlockIds", [])
        if block_id in source_block_ids:
            provenance = metadata.get("provenance", {})
            return {
                "blockId": block_id,
                "chunkId": str(row["chunk_id"]),
                "pageNo": row["page_no"],
                "section": row["section"],
                "contentHash": provenance.get("contentHash"),
                "sourceBlockIds": source_block_ids,
            }

    return None


def get_page_blocks(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    page_no: int,
) -> list[dict]:
    """获取指定页面的所有块及其 provenance。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return []
    _ensure_permission(session, current_user, kb_id, "kb.chunk.read")

    rows = session.execute(
        select(chunks).where(
            chunks.c.kb_id == kb_id,
            chunks.c.document_id == document_id,
            chunks.c.page_no == page_no,
            chunks.c.status == "active",
            chunks.c.deleted_at.is_(None),
        ).order_by(chunks.c.chunk_index.asc())
    ).mappings().all()

    result = []
    for row in rows:
        metadata = row["metadata"] or {}
        provenance = metadata.get("provenance", {})
        result.append({
            "chunkId": str(row["chunk_id"]),
            "chunkIndex": row["chunk_index"],
            "pageNo": row["page_no"],
            "section": row["section"],
            "content": row["content"][:200] + "..." if len(row["content"]) > 200 else row["content"],
            "sourceBlockIds": metadata.get("sourceBlockIds", []),
            "provenance": provenance,
        })

    return result


def update_chunk_governance(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    chunk_id: UUID,
    excluded: bool,
    note: str | None,
) -> ChunkGovernanceResponse | None:
    """更新 Chunk 治理标记；排除只影响检索上下文，不删除 PostgreSQL 正文。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    row = session.execute(
        select(chunks).where(chunks.c.kb_id == kb_id, chunks.c.chunk_id == chunk_id, chunks.c.status == "active").limit(1)
    ).mappings().first()
    if row is None:
        return None

    metadata = dict(row["metadata"] or {})
    governance = dict(metadata.get("governance") or {})
    governance["excluded"] = excluded
    governance["note"] = note
    governance["updatedBy"] = current_user.user.userId
    metadata["governance"] = governance
    updated_row = session.execute(
        update(chunks)
        .where(chunks.c.chunk_id == chunk_id)
        .values(metadata=metadata)
        .returning(chunks)
    ).mappings().one()
    _insert_audit_log(
        session,
        current_user,
        "chunk.governance_update",
        "chunk",
        chunk_id,
        kb_id,
        row["document_id"],
        {"excluded": excluded, "note": note},
    )
    session.commit()
    return ChunkGovernanceResponse(
        chunk=_to_chunk_dto(updated_row),
        excluded=excluded,
        governanceNote=note,
        permissionInheritance="Chunk 继承文档密级、文档状态和知识库成员权限；治理排除只影响后续检索上下文。",
    )


def reparse_document(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    reason: str | None,
) -> DocumentUploadResponse | None:
    """基于当前 active version 的源文件创建新版本，并投递后台解析 Worker。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    document_row = session.execute(
        _select_kb_documents(kb_id)
        .where(_document_belongs_to_kb_condition(kb_id), documents.c.document_id == document_id)
        .limit(1)
    ).mappings().first()
    if document_row is None:
        return None

    source_version = session.execute(
        select(document_versions)
        .where(document_versions.c.version_id == document_row["active_version_id"])
        .limit(1)
    ).mappings().first()
    if source_version is None:
        raise DocumentConflictError("Active version is required before reparse.")

    next_version_no = session.execute(
        select(func.coalesce(func.max(document_versions.c.version_no), 0) + 1).where(
            document_versions.c.document_id == document_id
        )
    ).scalar_one()
    version_id = new_id()
    job_id = new_id()
    actor_id = current_user.user.userId
    sparse_status = "pending" if kb_row["sparse_index_enabled"] else "not_required"
    graph_status = "pending" if kb_row["graph_index_enabled"] else "not_required"

    try:
        version_row = session.execute(
            insert(document_versions)
            .values(
                version_id=version_id,
                document_id=document_id,
                version_no=next_version_no,
                source_file_id=source_version["source_file_id"],
                status="processing",
                parse_status="pending",
                dense_index_status="pending",
                sparse_index_status=sparse_status,
                graph_index_status=graph_status,
                retrieval_ready=False,
                chunk_count=0,
                metadata={"reparseReason": reason},
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(document_versions)
        ).mappings().one()
        job_row = session.execute(
            insert(ingest_jobs)
            .values(
                job_id=job_id,
                kb_id=kb_id,
                document_id=document_id,
                version_id=version_id,
                job_type="reparse",
                status="queued",
                stage="queued",
                progress=0,
                result_summary={"reason": reason},
                created_by=actor_id,
            )
            .returning(ingest_jobs)
        ).mappings().one()
        _insert_audit_log(
            session,
            current_user,
            "document.reparse",
            "document",
            document_id,
            kb_id,
            document_id,
            {"versionId": str(version_id), "jobId": str(job_id), "reason": reason},
        )
        version_row = session.execute(select(document_versions).where(document_versions.c.version_id == version_id)).mappings().one()
        stored_file_row = session.execute(
            select(stored_files).where(stored_files.c.file_id == version_row["source_file_id"]).limit(1)
        ).mappings().one()
        session.commit()
    except Exception:
        session.rollback()
        raise
    enqueue_ingest_job(session, job_id)

    return DocumentUploadResponse(
        document=_to_document_dto(document_row),
        version=_to_version_dto(version_row),
        ingestJob=_to_ingest_job_dto(job_row),
        storedFile=_to_stored_file_dto(stored_file_row),
    )


def activate_document_version(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_id: UUID,
    version_id: UUID,
    confirm_impact: bool,
    reason: str | None,
) -> DocumentVersionActivateResponse | None:
    """切换文档 active version，并将旧图快照标记 stale。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")
    if not confirm_impact:
        raise DocumentConflictError("confirmImpact must be true.")

    document_row = session.execute(
        _select_kb_documents(kb_id)
        .where(_document_belongs_to_kb_condition(kb_id), documents.c.document_id == document_id)
        .limit(1)
    ).mappings().first()
    version_row = session.execute(
        select(document_versions)
        .where(document_versions.c.document_id == document_id, document_versions.c.version_id == version_id)
        .limit(1)
    ).mappings().first()
    if document_row is None or version_row is None:
        return None
    if version_row["status"] == "failed" or version_row["parse_status"] != "success":
        raise DocumentConflictError("Version is not parse-ready.")
    if not version_row["retrieval_ready"]:
        raise DocumentConflictError("Version is not retrieval-ready.")

    previous_active_version_id = document_row["active_version_id"]
    audit_log_id = _insert_audit_log(
        session,
        current_user,
        "document.version.activate",
        "document_version",
        version_id,
        kb_id,
        document_id,
        {
            "previousActiveVersionId": str(previous_active_version_id) if previous_active_version_id else None,
            "activeVersionId": str(version_id),
            "reason": reason,
        },
    )
    session.execute(
        update(document_versions)
        .where(document_versions.c.document_id == document_id, document_versions.c.status == "active")
        .values(status="inactive", updated_by=current_user.user.userId, updated_at=func.now())
    )
    session.execute(
        update(document_versions)
        .where(document_versions.c.version_id == version_id)
        .values(status="active", updated_by=current_user.user.userId, updated_at=func.now())
    )
    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(active_version_id=version_id, updated_by=current_user.user.userId, updated_at=func.now())
    )
    mark_graph_snapshots_stale(session, kb_id, "active_version_changed", current_user)
    session.commit()
    return DocumentVersionActivateResponse(
        documentId=str(document_id),
        activeVersionId=str(version_id),
        previousActiveVersionId=str(previous_active_version_id) if previous_active_version_id else None,
        auditLogId=str(audit_log_id),
    )


def retry_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    job_id: UUID,
) -> IngestJobDTO | None:
    """重试失败或取消的 IngestJob；同一失败作业的并发重试按已有补偿作业幂等返回。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    old_job = session.execute(
        select(ingest_jobs).where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.job_id == job_id).limit(1)
    ).mappings().first()
    if old_job is None:
        return None
    if old_job["status"] not in {"failed", "cancelled"}:
        raise DocumentConflictError("Ingest job is not retryable.")

    # idempotency: 同一个失败/取消作业已有补偿作业时直接返回，避免重复执行生成不可解释副本。
    existing_retry = session.execute(
        select(ingest_jobs)
        .where(
            ingest_jobs.c.kb_id == kb_id,
            ingest_jobs.c.retry_of_job_id == old_job["job_id"],
            ingest_jobs.c.status.in_(["queued", "running", "success"]),
        )
        .order_by(ingest_jobs.c.created_at.desc())
        .limit(1)
    ).mappings().first()
    if existing_retry is not None:
        return _to_ingest_job_dto(existing_retry)

    new_job_id = new_id()
    job_row = session.execute(
        insert(ingest_jobs)
        .values(
            job_id=new_job_id,
            kb_id=kb_id,
            document_id=old_job["document_id"],
            version_id=old_job["version_id"],
            job_type=old_job["job_type"],
            status="queued",
            stage="queued",
            progress=0,
            retry_of_job_id=old_job["job_id"],
            result_summary={
                "retryOfJobId": str(old_job["job_id"]),
                "idempotency": "retry_of_job_id",
                "compensationStatus": "created",
            },
            created_by=current_user.user.userId,
        )
        .returning(ingest_jobs)
    ).mappings().one()
    _insert_audit_log(
        session,
        current_user,
        "ingest_job.retry",
        "ingest_job",
        new_job_id,
        kb_id,
        old_job["document_id"],
        {"retryOfJobId": str(old_job["job_id"])},
    )
    session.commit()
    enqueue_ingest_job(session, new_job_id)
    return _to_ingest_job_dto(job_row)


def cancel_ingest_job(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    job_id: UUID,
) -> IngestJobDTO | None:
    """取消 queued/running 作业；已完成作业不允许回退状态。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    old_job = session.execute(
        select(ingest_jobs).where(ingest_jobs.c.kb_id == kb_id, ingest_jobs.c.job_id == job_id).limit(1)
    ).mappings().first()
    if old_job is None:
        return None
    if old_job["status"] not in {"queued", "running"}:
        raise DocumentConflictError("Only queued or running ingest jobs can be cancelled.")

    job_row = session.execute(
        update(ingest_jobs)
        .where(ingest_jobs.c.job_id == job_id)
        .values(status="cancelled", stage="cancelled", progress=100, finished_at=func.now())
        .returning(ingest_jobs)
    ).mappings().one()
    _insert_audit_log(
        session,
        current_user,
        "ingest_job.cancel",
        "ingest_job",
        job_id,
        kb_id,
        old_job["document_id"],
        {},
    )
    session.commit()
    return _to_ingest_job_dto(job_row)


def list_index_sync_jobs(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    document_id: UUID | None = None,
) -> PageResponse[IndexSyncJobDTO] | None:
    """分页查询知识库副本同步作业状态。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    condition = index_sync_jobs.c.kb_id == kb_id
    if document_id is not None:
        document_exists = session.execute(
            select(documents.c.document_id)
            .where(_document_belongs_to_kb_condition(kb_id), documents.c.document_id == document_id)
            .limit(1)
        ).scalar_one_or_none()
        if document_exists is None:
            return PageResponse(items=[], pageNo=page_no, pageSize=page_size, total=0)

        version_ids = {
            str(row[0])
            for row in session.execute(
                select(document_versions.c.version_id).where(document_versions.c.document_id == document_id)
            )
        }
        chunk_ids = {
            str(row[0])
            for row in session.execute(select(chunks.c.chunk_id).where(chunks.c.document_id == document_id))
        }
        rows = [
            row
            for row in session.execute(
                select(index_sync_jobs).where(condition).order_by(index_sync_jobs.c.created_at.desc())
            ).mappings()
            if _index_sync_job_matches_document(row, document_id, version_ids, chunk_ids)
        ]
        total = len(rows)
        offset = (page_no - 1) * page_size
        return PageResponse(
            items=[_to_index_sync_job_dto(row) for row in rows[offset : offset + page_size]],
            pageNo=page_no,
            pageSize=page_size,
            total=total,
        )

    total = session.execute(select(func.count()).select_from(index_sync_jobs).where(condition)).scalar_one()
    rows = session.execute(
        select(index_sync_jobs)
        .where(condition)
        .order_by(index_sync_jobs.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_index_sync_job_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def rebuild_index_sync(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    target_store: str,
    document_id: UUID | None = None,
    version_id: UUID | None = None,
) -> IndexSyncJobDTO | None:
    """基于 PostgreSQL Chunk 真值创建副本重建作业，并记录空范围失败原因。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if target_store not in {"milvus", "opensearch", "neo4j"}:
        raise DocumentConflictError("Unsupported target store.")
    _ensure_permission(session, current_user, kb_id, "kb.document.upload")

    condition = (
        (chunks.c.kb_id == kb_id)
        & (chunks.c.status == "active")
        & (document_versions.c.status == "active")
    )
    if document_id is not None:
        condition = condition & (chunks.c.document_id == document_id)
    if version_id is not None:
        condition = condition & (chunks.c.version_id == version_id)

    rows = list(
        session.execute(
            select(chunks, documents.c.status.label("document_status"), document_versions.c.status.label("version_status"))
            .select_from(
                chunks.join(document_versions, chunks.c.version_id == document_versions.c.version_id).join(
                    documents, chunks.c.document_id == documents.c.document_id
                )
            )
            .where(condition)
        ).mappings()
    )
    chunk_ids = [row["chunk_id"] for row in rows]
    status = "queued" if chunk_ids else "failed"
    error_message = None if chunk_ids else "No active chunks found for rebuild scope."
    provider_set = get_qa_run_providers()
    access_filter = build_chunk_access_filter_context(session, current_user, kb_id).to_trace_summary()
    provider_payloads = {
        row["chunk_id"]: build_chunk_index_payload(
            row,
            document_status=row["document_status"],
            version_status=row["version_status"],
            access_filter=access_filter,
            embedding=provider_set.embedding.embed_query(row["content"]) if row["content"] else [],
        )
        for row in rows
    }
    graph_snapshot_id = new_id() if target_store == "neo4j" and chunk_ids else None
    if graph_snapshot_id is not None:
        provider_payloads = {
            chunk_id: {**payload, "graphSnapshotId": str(graph_snapshot_id)}
            for chunk_id, payload in provider_payloads.items()
        }
    graph_items = provider_set.llm.extract_graph(list(provider_payloads.values())) if target_store == "neo4j" and chunk_ids else []
    if graph_snapshot_id is not None:
        session.execute(
            insert(graph_snapshots).values(
                graph_snapshot_id=graph_snapshot_id,
                kb_id=kb_row["kb_id"],
                source_scope={
                    "documentIds": [str(document_id)] if document_id else [],
                    "versionIds": [str(version_id)] if version_id else [],
                    "syncType": "rebuild",
                },
                status="running",
                neo4j_graph_key=f"neo4j:{graph_snapshot_id}",
                entity_count=sum(len(item.entities) for item in graph_items),
                relation_count=sum(len(item.relations) for item in graph_items),
                community_count=0,
                job_id=None,
                created_by=current_user.user.userId,
                updated_by=current_user.user.userId,
            )
        )
    sync_job_id, final_status, final_error = _create_index_sync_job(
        session,
        kb_row,
        current_user,
        target_store,
        version_id,
        chunk_ids,
        target_store == "milvus",
        sync_type="rebuild",
        status=status,
        error_message=error_message,
        provider_payloads=provider_payloads,
        provider_set=provider_set,
        graph_items=graph_items,
        document_ids=[document_id] if document_id else None,
        graph_snapshot_id=graph_snapshot_id,
    )
    if graph_snapshot_id is not None:
        session.execute(
            update(graph_snapshots)
            .where(graph_snapshots.c.graph_snapshot_id == graph_snapshot_id)
            .values(
                status="success" if final_status == "success" else "failed",
                stale_reason=final_error,
                updated_by=current_user.user.userId,
                updated_at=func.now(),
            )
        )
    _insert_audit_log(
        session,
        current_user,
        "index_sync.rebuild",
        "index_sync_job",
        sync_job_id,
        kb_id,
        document_id,
        {
            "targetStore": target_store,
            "documentId": str(document_id) if document_id else None,
            "versionId": str(version_id) if version_id else None,
            "chunkCount": len(chunk_ids),
            "status": final_status,
            "errorMessage": final_error,
        },
    )
    row = session.execute(select(index_sync_jobs).where(index_sync_jobs.c.sync_job_id == sync_job_id)).mappings().one()
    session.commit()
    return _to_index_sync_job_dto(row)
