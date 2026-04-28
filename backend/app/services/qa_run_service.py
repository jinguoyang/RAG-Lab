from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse
from app.schemas.qa_run import (
    EvaluationSampleCreateRequest,
    EvaluationSampleDTO,
    QARunCandidateDTO,
    QARunCitationDTO,
    QARunCreateRequest,
    QARunCreateResponse,
    QARunDetailDTO,
    QARunEvidenceDTO,
    QARunListItemDTO,
    QARunFeedbackResponse,
    QARunFeedbackUpdateRequest,
    QARunReplayContextDTO,
    QARunStatusDTO,
    QARunTraceStepDTO,
)
from app.schemas.common import PageResponse
from app.schemas.config import ConfigRevisionDTO
from app.services.audit_service import write_audit_log
from app.tables import (
    chunks,
    config_revisions,
    document_versions,
    evaluation_samples,
    knowledge_bases,
    qa_run_candidates,
    qa_run_citations,
    qa_run_evidence,
    qa_run_trace_steps,
    qa_runs,
)
from app.services.qa_providers import ProviderCandidate, ProviderError, QARunProviders, get_qa_run_providers
from app.services.permission_service import build_chunk_access_filter_context, has_kb_permission
from app.services.knowledge_base_service import KnowledgeBaseDisabledError


class QARunCreateConflict(ValueError):
    """创建 QARun 时遇到业务状态冲突，例如缺少可运行 Revision。"""


class QARunPermissionError(Exception):
    """当前用户缺少读取历史、标注或管理评估样本的权限。"""


RETRIEVAL_NODE_TO_OVERRIDE_KEY = {
    "denseRetrieval": "dense",
    "sparseRetrieval": "sparse",
    "graphRetrieval": "graph",
}
MOCK_EVIDENCE_CHUNK_ID = UUID("00000000-0000-0000-0000-000000000001")
FEEDBACK_STATUS_MAP = {
    "unrated": "unrated",
    "correct": "correct",
    "partiallyCorrect": "partially_correct",
    "partially_correct": "partially_correct",
    "wrong": "wrong",
    "citationError": "citation_error",
    "citation_error": "citation_error",
    "noEvidence": "no_evidence",
    "no_evidence": "no_evidence",
}


def _normalize_feedback_status(value: str) -> str:
    """兼容前端 camelCase 和数据库 snake_case 的反馈状态。"""
    normalized = FEEDBACK_STATUS_MAP.get(value)
    if normalized is None:
        raise QARunCreateConflict("Invalid feedback status.")
    return normalized


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用开发期最小权限：平台管理员可访问全部知识库。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库；不可见资源不暴露存在性。"""
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


def _resolve_runnable_revision(
    session: Session,
    kb_row: RowMapping,
    requested_revision_id: UUID | None,
) -> RowMapping:
    """锁定本次运行使用的 Revision；draft/invalid 不允许进入执行链路。"""
    revision_id = requested_revision_id or kb_row["active_config_revision_id"]
    if revision_id is None:
        raise QARunCreateConflict("Active config revision is required before creating QA run.")

    row = session.execute(
        select(config_revisions)
        .where(
            config_revisions.c.kb_id == kb_row["kb_id"],
            config_revisions.c.config_revision_id == revision_id,
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if row is None:
        raise QARunCreateConflict("Config revision not found for this knowledge base.")
    if row["status"] in {"draft", "invalid"}:
        raise QARunCreateConflict("Config revision is not runnable.")
    return row


def _assert_retrieval_enabled(revision_row: RowMapping, override_snapshot: dict) -> None:
    """校验本次有效运行配置至少启用一路检索，防止绕过前端护栏。"""
    nodes = revision_row["pipeline_definition"].get("nodes", [])
    if not isinstance(nodes, list):
        raise QARunCreateConflict("Pipeline definition is invalid.")

    channel_overrides = override_snapshot.get("channels", {})
    if channel_overrides is None:
        channel_overrides = {}
    if not isinstance(channel_overrides, dict):
        raise QARunCreateConflict("Override channels must be an object.")

    enabled_channels: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type")
        channel_key = RETRIEVAL_NODE_TO_OVERRIDE_KEY.get(str(node_type))
        if channel_key is None:
            continue
        base_enabled = node.get("enabled") is not False
        override_enabled = channel_overrides.get(channel_key, True)
        if not isinstance(override_enabled, bool):
            raise QARunCreateConflict(f"Override channel {channel_key} must be boolean.")
        if base_enabled and override_enabled:
            enabled_channels.append(channel_key)

    if not enabled_channels:
        raise QARunCreateConflict("At least one retrieval channel must be enabled.")


def _effective_retrieval_channels(revision_row: RowMapping, override_snapshot: dict) -> set[str]:
    """解析 Revision 与临时覆盖后的有效检索通道，供执行器调用对应 Provider。"""
    nodes = revision_row["pipeline_definition"].get("nodes", [])
    channel_overrides = override_snapshot.get("channels", {}) or {}
    enabled_channels: set[str] = set()
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        channel_key = RETRIEVAL_NODE_TO_OVERRIDE_KEY.get(str(node.get("type")))
        if channel_key is None:
            continue
        if node.get("enabled") is not False and channel_overrides.get(channel_key, True) is True:
            enabled_channels.add(channel_key)
    return enabled_channels


def _load_postgres_chunk_candidates(session: Session, kb_id: UUID, limit: int) -> list[ProviderCandidate]:
    """从 PostgreSQL Chunk 真值表读取 active 版本证据，供本地 Provider 降级链路回表。"""
    rows = session.execute(
        select(chunks)
        .select_from(chunks.join(document_versions, chunks.c.version_id == document_versions.c.version_id))
        .where(chunks.c.kb_id == kb_id, chunks.c.status == "active", document_versions.c.status == "active")
        .order_by(chunks.c.created_at.desc(), chunks.c.chunk_index.asc())
        .limit(limit)
    ).mappings()
    return [
        ProviderCandidate(
            source_type="postgres",
            chunk_id=row["chunk_id"],
            raw_score=0.7,
            content=row["content"],
            metadata={
                "provider": "postgres",
                "documentId": str(row["document_id"]),
                "versionId": str(row["version_id"]),
                "pageNo": row["page_no"],
                "section": row["section"],
            },
        )
        for row in rows
    ]


def _read_visible_qa_run(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
) -> RowMapping | None:
    """按知识库可见性和历史权限读取运行记录，避免通过 runId 枚举不可见数据。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    row = session.execute(
        select(qa_runs)
        .where(qa_runs.c.kb_id == kb_id, qa_runs.c.run_id == run_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    user_id = UUID(current_user.user.userId)
    if row["created_by"] == user_id or has_kb_permission(session, current_user, kb_id, "kb.qa.history.read"):
        return row
    return None


def _require_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    permission_code: str,
) -> None:
    """对历史增强接口做显式权限判断，避免页面入口替代后端授权。"""
    if not has_kb_permission(session, current_user, kb_id, permission_code):
        raise QARunPermissionError


def _status_progress(row: RowMapping) -> tuple[str, int, str, bool]:
    """将持久化状态转换为轮询展示所需的阶段、进度和详情可读标记。"""
    status = row["status"]
    if status == "queued":
        return "queued", 0, "已创建运行记录，等待执行", False
    if status == "running":
        return "generation", 60, "正在执行 QA Pipeline", False
    if status in {"success", "partial"}:
        return "completed", 100, "运行完成，可查看详情", True
    if status == "failed":
        return "failed", 100, "运行失败，可查看诊断信息", True
    if status == "cancelled":
        return "cancelled", 100, "运行已取消", True
    return "draft", 0, "运行尚未提交", False


def _insert_trace_step(
    session: Session,
    run_id: UUID,
    step_order: int,
    step_key: str,
    status_value: str,
    input_summary: dict,
    output_summary: dict,
    metrics: dict,
    error_code: str | None = None,
    error_message: str | None = None,
    started_at: datetime | None = None,
) -> None:
    """写入单个 Trace 步骤，保证成功、跳过和降级路径使用同一结构。"""
    session.execute(
        insert(qa_run_trace_steps).values(
            trace_step_id=uuid4(),
            run_id=run_id,
            step_order=step_order,
            step_key=step_key,
            status=status_value,
            input_summary=input_summary,
            output_summary=output_summary,
            metrics=metrics,
            error_code=error_code,
            error_message=error_message,
            started_at=started_at,
            ended_at=datetime.now(UTC),
        )
    )


def _execute_provider_qa_run(
    session: Session,
    current_user: CurrentUserResponse,
    run_id: UUID,
    kb_id: UUID,
    query: str,
    revision_row: RowMapping,
    override_snapshot: dict,
    providers: QARunProviders | None = None,
) -> None:
    """执行 E5 Provider 编排链路，并在外部组件失败时记录降级 Trace。"""
    started_at = datetime.now(UTC)
    provider_set = providers or get_qa_run_providers()
    settings = get_settings()
    enabled_channels = _effective_retrieval_channels(revision_row, override_snapshot)
    access_filter = build_chunk_access_filter_context(session, current_user, kb_id)
    trace_order = 1
    provider_errors: list[str] = []

    try:
        rewritten_query = provider_set.llm.rewrite_query(query)
        _insert_trace_step(
            session,
            run_id,
            trace_order,
            "queryRewrite",
            "success",
            {"query": query},
            {"rewrittenQuery": rewritten_query},
            {"provider": settings.llm_provider},
            started_at=started_at,
        )
    except ProviderError as exc:
        rewritten_query = query
        provider_errors.append("queryRewrite")
        _insert_trace_step(
            session,
            run_id,
            trace_order,
            "queryRewrite",
            "partial",
            {"query": query},
            {"rewrittenQuery": rewritten_query},
            {"provider": settings.llm_provider},
            error_code="PROVIDER_ERROR",
            error_message=str(exc),
            started_at=started_at,
        )
    trace_order += 1

    try:
        embedding = provider_set.embedding.embed_query(rewritten_query)
        _insert_trace_step(
            session,
            run_id,
            trace_order,
            "embedding",
            "success",
            {"query": rewritten_query},
            {"vectorReady": True, "dimension": len(embedding)},
            {"provider": settings.embedding_provider},
            started_at=started_at,
        )
        trace_order += 1
    except ProviderError as exc:
        embedding = []
        provider_errors.append("embedding")
        _insert_trace_step(
            session,
            run_id,
            trace_order,
            "embedding",
            "partial",
            {"query": rewritten_query},
            {"vectorReady": False},
            {"provider": settings.embedding_provider},
            error_code="PROVIDER_ERROR",
            error_message=str(exc),
            started_at=started_at,
        )
        trace_order += 1

    candidates: list[ProviderCandidate] = []
    retrieval_steps = [
        ("dense", "denseRetrieval", settings.dense_retrieval_provider),
        ("sparse", "sparseRetrieval", settings.sparse_retrieval_provider),
        ("graph", "graphRetrieval", settings.graph_retrieval_provider),
    ]
    for channel, step_key, provider_name in retrieval_steps:
        if channel not in enabled_channels:
            _insert_trace_step(
                session,
                run_id,
                trace_order,
                step_key,
                "skipped",
                {"query": rewritten_query},
                {"reason": "channelDisabled"},
                {"provider": provider_name},
                started_at=started_at,
            )
            trace_order += 1
            continue

        try:
            if channel == "dense":
                channel_candidates = provider_set.dense.retrieve(
                    kb_id,
                    rewritten_query,
                    embedding,
                    settings.provider_top_k,
                    access_filter,
                )
            elif channel == "sparse":
                channel_candidates = provider_set.sparse.retrieve(
                    kb_id,
                    rewritten_query,
                    settings.provider_top_k,
                    access_filter,
                )
            else:
                channel_candidates = provider_set.graph.retrieve(
                    kb_id,
                    rewritten_query,
                    None,
                    settings.provider_top_k,
                    access_filter,
                )
            candidates.extend(channel_candidates)
            _insert_trace_step(
                session,
                run_id,
                trace_order,
                step_key,
                "success",
                {"query": rewritten_query},
                {"candidateCount": len(channel_candidates)},
                {"provider": provider_name, "accessFilter": access_filter.to_trace_summary()},
                started_at=started_at,
            )
        except ProviderError as exc:
            provider_errors.append(step_key)
            _insert_trace_step(
                session,
                run_id,
                trace_order,
                step_key,
                "partial",
                {"query": rewritten_query},
                {"candidateCount": 0},
                {"provider": provider_name},
                error_code="PROVIDER_ERROR",
                error_message=str(exc),
                started_at=started_at,
            )
        trace_order += 1

    postgres_candidates = _load_postgres_chunk_candidates(session, kb_id, settings.provider_top_k)
    if postgres_candidates:
        candidates = postgres_candidates
        _insert_trace_step(
            session,
            run_id,
            trace_order,
            "postgresChunkFallback",
            "success",
            {"kbId": str(kb_id)},
            {"candidateCount": len(postgres_candidates)},
            {"source": "chunks"},
            started_at=started_at,
        )
        trace_order += 1

    if not candidates:
        candidates = [
            ProviderCandidate(
                source_type="mock",
                chunk_id=MOCK_EVIDENCE_CHUNK_ID,
                raw_score=1,
                content="Provider 未返回可用候选，系统使用本地兜底证据保持调试链路可追踪。",
                metadata={"provider": "fallback"},
            )
        ]
        provider_errors.append("fallbackEvidence")

    try:
        reranked_candidates = provider_set.rerank.rerank(rewritten_query, candidates, settings.provider_top_k)
        rerank_status = "success"
        rerank_error = None
    except ProviderError as exc:
        reranked_candidates = candidates[: settings.provider_top_k]
        rerank_status = "partial"
        rerank_error = str(exc)
        provider_errors.append("rerank")
    _insert_trace_step(
        session,
        run_id,
        trace_order,
        "rerank",
        rerank_status,
        {"inputCandidates": len(candidates)},
        {"candidateCount": len(reranked_candidates)},
        {"provider": settings.rerank_provider},
        error_code="PROVIDER_ERROR" if rerank_error else None,
        error_message=rerank_error,
        started_at=started_at,
    )
    trace_order += 1

    # 当前仓库尚未落地 Chunk 真值表；这里先用过滤摘要阻止无 Chunk 读取权的候选进入生成。
    authorized_candidates = reranked_candidates
    if not access_filter.allowed:
        authorized_candidates = []
        provider_errors.append("chunkPermissionDenied")
    permission_filter_pending = any(candidate.chunk_id is None for candidate in authorized_candidates)
    if permission_filter_pending:
        provider_errors.append("permissionFilterPending")
    _insert_trace_step(
        session,
        run_id,
        trace_order,
        "permissionFilter",
        "partial" if permission_filter_pending else "success",
        {"inputCandidates": len(reranked_candidates)},
        {
            "authorizedCandidates": len(authorized_candidates),
            "droppedCandidates": len(reranked_candidates) - len(authorized_candidates),
            "accessFilter": access_filter.to_trace_summary(),
            "note": "Chunk truth table is enforced by PostgreSQL fallback when Provider does not return chunk_id.",
        },
        {"latencyMs": 0},
        started_at=started_at,
    )
    trace_order += 1

    if not authorized_candidates:
        session.execute(
            update(qa_runs)
            .where(qa_runs.c.run_id == run_id)
            .values(
                rewritten_query=rewritten_query,
                status="failed",
                answer="当前用户没有可用于回答的授权证据。",
                metrics={
                    "latencyMs": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                    "retrievalDiagnostics": {
                        "denseCount": 0,
                        "sparseCount": 0,
                        "graphCount": 0,
                        "mockCount": 0,
                        "droppedByPermission": len(reranked_candidates),
                        "providerErrors": provider_errors,
                    },
                },
                started_at=started_at,
                finished_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        return

    try:
        answer = provider_set.llm.generate_answer(query, authorized_candidates)
        generation_status = "success"
        generation_error = None
    except ProviderError as exc:
        answer = f"Provider 生成失败，返回候选摘要供调试：{query}"
        generation_status = "partial"
        generation_error = str(exc)
        provider_errors.append("generation")
    _insert_trace_step(
        session,
        run_id,
        trace_order,
        "generation",
        generation_status,
        {"evidenceCount": len(authorized_candidates)},
        {"answerPreview": answer[:80]},
        {"provider": settings.llm_provider},
        error_code="PROVIDER_ERROR" if generation_error else None,
        error_message=generation_error,
        started_at=started_at,
    )
    trace_order += 1

    evidence_id = uuid4()
    citation_id = uuid4()
    top_candidate = authorized_candidates[0]
    candidate_id = uuid4()
    content_snapshot = top_candidate.content or "Provider 候选未返回正文，当前仅保留来源摘要。"
    content_hash = sha256(content_snapshot.encode("utf-8")).hexdigest()

    for index, candidate in enumerate(authorized_candidates, start=1):
        session.execute(
            insert(qa_run_candidates).values(
                candidate_id=candidate_id if index == 1 else uuid4(),
                run_id=run_id,
                chunk_id=candidate.chunk_id or MOCK_EVIDENCE_CHUNK_ID,
                source_type=candidate.source_type,
                raw_score=candidate.raw_score,
                rerank_score=candidate.raw_score,
                rank_no=index,
                is_authorized=True,
                metadata=candidate.metadata,
            )
        )

    session.execute(
        insert(qa_run_evidence).values(
            evidence_id=evidence_id,
            run_id=run_id,
            chunk_id=top_candidate.chunk_id or MOCK_EVIDENCE_CHUNK_ID,
            candidate_id=candidate_id,
            evidence_order=1,
            content_snapshot=content_snapshot,
            content_snapshot_hash=content_hash,
            snapshot_policy="redacted",
            redaction_status="none",
            source_snapshot={
                "sourceType": top_candidate.source_type,
                **top_candidate.metadata,
            },
        )
    )
    session.execute(
        insert(qa_run_citations).values(
            citation_id=citation_id,
            run_id=run_id,
            evidence_id=evidence_id,
            citation_order=1,
            label=f"{top_candidate.source_type}#1",
            location_snapshot=top_candidate.metadata,
        )
    )
    _insert_trace_step(
        session,
        run_id,
        trace_order,
        "citation",
        "success",
        {"evidenceCount": 1},
        {"citationCount": 1},
        {"latencyMs": 0},
        started_at=started_at,
    )

    channel_counts = {"denseCount": 0, "sparseCount": 0, "graphCount": 0, "mockCount": 0}
    for candidate in authorized_candidates:
        if candidate.source_type == "dense":
            channel_counts["denseCount"] += 1
        elif candidate.source_type == "sparse":
            channel_counts["sparseCount"] += 1
        elif candidate.source_type == "graph":
            channel_counts["graphCount"] += 1
        else:
            channel_counts["mockCount"] += 1

    session.execute(
        update(qa_runs)
        .where(qa_runs.c.run_id == run_id)
        .values(
            rewritten_query=rewritten_query,
            status="partial" if provider_errors else "success",
            answer=answer,
            metrics={
                "latencyMs": int((datetime.now(UTC) - started_at).total_seconds() * 1000),
                "retrievalDiagnostics": {
                    **channel_counts,
                    "droppedByPermission": 0,
                    "providerErrors": provider_errors,
                },
            },
            started_at=started_at,
            finished_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )


def create_qa_run(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: QARunCreateRequest,
) -> QARunCreateResponse | None:
    """创建 queued QARun 并锁定 ConfigRevision，后续执行器只更新该运行记录。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError

    revision_row = _resolve_runnable_revision(session, kb_row, request.configRevisionId)
    run_id = uuid4()
    actor_id = UUID(current_user.user.userId)
    override_snapshot = request.overrideParams or {}
    if request.sourceRunId is not None and _read_visible_qa_run(session, current_user, kb_id, request.sourceRunId) is None:
        raise QARunCreateConflict("Source QA run not found for this knowledge base.")
    if not has_kb_permission(session, current_user, kb_id, "kb.qa.run"):
        raise QARunCreateConflict("Current user cannot run QA in this knowledge base.")
    _assert_retrieval_enabled(revision_row, override_snapshot)

    try:
        row = session.execute(
            insert(qa_runs)
            .values(
                run_id=run_id,
                kb_id=kb_id,
                config_revision_id=revision_row["config_revision_id"],
                source_run_id=request.sourceRunId,
                query=request.query,
                status="queued",
                has_override=bool(override_snapshot),
                override_snapshot=override_snapshot,
                metrics={},
                feedback_status="unrated",
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(qa_runs)
        ).mappings().one()
        _execute_provider_qa_run(session, current_user, run_id, kb_id, request.query, revision_row, override_snapshot)
        row = session.execute(select(qa_runs).where(qa_runs.c.run_id == run_id).limit(1)).mappings().one()
        session.commit()
    except Exception:
        session.rollback()
        raise

    return QARunCreateResponse(
        runId=str(row["run_id"]),
        status=row["status"],
        kbId=str(row["kb_id"]),
        configRevisionId=str(row["config_revision_id"]),
        query=row["query"],
        createdAt=row["created_at"].isoformat(),
        statusUrl=f"/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}/status",
        detailUrl=f"/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}",
    )


def get_qa_run_status(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
) -> QARunStatusDTO | None:
    """读取 QARun 状态轮询信息；不可见和不存在统一返回 None。"""
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None

    current_stage, progress, stage_message, detail_ready = _status_progress(row)
    return QARunStatusDTO(
        runId=str(row["run_id"]),
        status=row["status"],
        currentStage=current_stage,
        progress=progress,
        stageMessage=stage_message,
        startedAt=row["started_at"].isoformat() if row["started_at"] else None,
        finishedAt=row["finished_at"].isoformat() if row["finished_at"] else None,
        detailReady=detail_ready,
    )


def _to_candidate_dto(row: RowMapping) -> QARunCandidateDTO:
    """转换候选摘要，并处理 Decimal 分数字段。"""
    raw_score = row["raw_score"]
    rerank_score = row["rerank_score"]
    return QARunCandidateDTO(
        candidateId=str(row["candidate_id"]),
        chunkId=str(row["chunk_id"]) if row["chunk_id"] else None,
        sourceType=row["source_type"],
        rawScore=float(raw_score) if isinstance(raw_score, Decimal) else raw_score,
        rerankScore=float(rerank_score) if isinstance(rerank_score, Decimal) else rerank_score,
        rankNo=row["rank_no"],
        isAuthorized=row["is_authorized"],
        dropReason=row["drop_reason"],
        metadata=row["metadata"],
    )


def _failure_type(row: RowMapping) -> str | None:
    """从 metrics 中读取失败归因，保持历史表结构稳定。"""
    metrics = row["metrics"] or {}
    value = metrics.get("failureType")
    return str(value) if value else None


def _to_evaluation_sample_dto(row: RowMapping) -> EvaluationSampleDTO:
    """将评估样本行转换为接口 DTO。"""
    return EvaluationSampleDTO(
        sampleId=str(row["sample_id"]),
        kbId=str(row["kb_id"]),
        sourceRunId=str(row["source_run_id"]) if row["source_run_id"] else None,
        query=row["query"],
        expectedAnswer=row["expected_answer"],
        expectedEvidence=row["expected_evidence"],
        status=row["status"],
        metadata=row["metadata"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_config_revision_dto(row: RowMapping) -> ConfigRevisionDTO:
    """将从 QARun 生成的 Revision 草稿行转换为配置 DTO。"""
    return ConfigRevisionDTO(
        configRevisionId=str(row["config_revision_id"]),
        kbId=str(row["kb_id"]),
        revisionNo=row["revision_no"],
        sourceTemplateId=str(row["source_template_id"]) if row["source_template_id"] else None,
        status=row["status"],
        pipelineDefinition=row["pipeline_definition"],
        validationSnapshot=row["validation_snapshot"],
        remark=row["remark"],
        activatedAt=row["activated_at"].isoformat() if row["activated_at"] else None,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def get_qa_run_detail(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
    include_trace: bool,
    include_candidates: bool,
) -> QARunDetailDTO | None:
    """读取 QARun 详情和可选明细；B-018 先返回 queued 记录和空明细。"""
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None

    candidates = []
    if include_candidates:
        candidate_rows = session.execute(
            select(qa_run_candidates)
            .where(qa_run_candidates.c.run_id == run_id)
            .order_by(qa_run_candidates.c.rank_no.asc().nullslast(), qa_run_candidates.c.created_at.asc())
        ).mappings()
        candidates = [_to_candidate_dto(candidate_row) for candidate_row in candidate_rows]

    evidence_rows = session.execute(
        select(qa_run_evidence)
        .where(qa_run_evidence.c.run_id == run_id)
        .order_by(qa_run_evidence.c.evidence_order.asc())
    ).mappings()
    citation_rows = session.execute(
        select(qa_run_citations)
        .where(qa_run_citations.c.run_id == run_id)
        .order_by(qa_run_citations.c.citation_order.asc())
    ).mappings()

    trace = []
    if include_trace:
        trace_rows = session.execute(
            select(qa_run_trace_steps)
            .where(qa_run_trace_steps.c.run_id == run_id)
            .order_by(qa_run_trace_steps.c.step_order.asc())
        ).mappings()
        trace = [
            QARunTraceStepDTO(
                stepKey=trace_row["step_key"],
                status=trace_row["status"],
                inputSummary=trace_row["input_summary"],
                outputSummary=trace_row["output_summary"],
                metrics=trace_row["metrics"],
                errorCode=trace_row["error_code"],
                errorMessage=trace_row["error_message"],
            )
            for trace_row in trace_rows
        ]

    return QARunDetailDTO(
        runId=str(row["run_id"]),
        status=row["status"],
        kbId=str(row["kb_id"]),
        configRevisionId=str(row["config_revision_id"]),
        query=row["query"],
        rewrittenQuery=row["rewritten_query"],
        answer=row["answer"],
        retrievalDiagnostics=row["metrics"].get("retrievalDiagnostics", {}),
        overrideSnapshot=row["override_snapshot"],
        feedbackStatus=row["feedback_status"],
        feedbackNote=row["feedback_note"],
        failureType=_failure_type(row),
        candidates=candidates,
        evidence=[
            QARunEvidenceDTO(
                evidenceId=str(evidence_row["evidence_id"]),
                chunkId=str(evidence_row["chunk_id"]),
                candidateId=str(evidence_row["candidate_id"]) if evidence_row["candidate_id"] else None,
                contentSnapshot=evidence_row["content_snapshot"],
                sourceSnapshot=evidence_row["source_snapshot"],
                redactionStatus=evidence_row["redaction_status"],
            )
            for evidence_row in evidence_rows
        ],
        citations=[
            QARunCitationDTO(
                citationId=str(citation_row["citation_id"]),
                evidenceId=str(citation_row["evidence_id"]),
                label=citation_row["label"],
                locationSnapshot=citation_row["location_snapshot"],
            )
            for citation_row in citation_rows
        ],
        trace=trace,
        metrics=row["metrics"],
        createdAt=row["created_at"].isoformat(),
    )


def list_qa_runs(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    keyword: str | None,
    status_filter: str | None = None,
    feedback_status: str | None = None,
) -> PageResponse[QARunListItemDTO] | None:
    """分页查询 QA 历史列表，支持状态、反馈和关键词筛选。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _require_permission(session, current_user, kb_id, "kb.qa.history.read")

    condition = qa_runs.c.kb_id == kb_id
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            qa_runs.c.query.ilike(keyword_pattern),
            qa_runs.c.run_id.cast(sa.String).ilike(keyword_pattern),
        )
    if status_filter:
        condition = condition & (qa_runs.c.status == status_filter)
    if feedback_status:
        condition = condition & (qa_runs.c.feedback_status == _normalize_feedback_status(feedback_status))

    total = session.execute(select(func.count()).select_from(qa_runs).where(condition)).scalar_one()
    rows = session.execute(
        select(qa_runs)
        .where(condition)
        .order_by(qa_runs.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return PageResponse(
        items=[
            QARunListItemDTO(
                runId=str(row["run_id"]),
                kbId=str(row["kb_id"]),
                configRevisionId=str(row["config_revision_id"]),
                query=row["query"],
                status=row["status"],
                answer=row["answer"],
                hasOverride=row["has_override"],
                feedbackStatus=row["feedback_status"],
                feedbackNote=row["feedback_note"],
                failureType=_failure_type(row),
                createdBy=str(row["created_by"]) if row["created_by"] else None,
                createdAt=row["created_at"].isoformat(),
                latencyMs=row["metrics"].get("latencyMs"),
            )
            for row in rows
        ],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def update_qa_run_feedback(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
    request: QARunFeedbackUpdateRequest,
) -> QARunFeedbackResponse | None:
    """更新历史运行人工反馈和失败归因。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _require_permission(session, current_user, kb_id, "kb.qa.history.read")
    row = session.execute(
        select(qa_runs).where(qa_runs.c.kb_id == kb_id, qa_runs.c.run_id == run_id).limit(1)
    ).mappings().first()
    if row is None:
        return None

    metrics = dict(row["metrics"] or {})
    if request.failureType:
        metrics["failureType"] = request.failureType
    else:
        metrics.pop("failureType", None)
    updated_at = datetime.now(UTC)
    feedback_status = _normalize_feedback_status(request.feedbackStatus)
    updated = session.execute(
        update(qa_runs)
        .where(qa_runs.c.run_id == run_id)
        .values(
            feedback_status=feedback_status,
            feedback_note=request.feedbackNote,
            metrics=metrics,
            updated_at=updated_at,
            updated_by=UUID(current_user.user.userId),
        )
        .returning(qa_runs)
    ).mappings().one()
    write_audit_log(
        session,
        current_user,
        "qa_run.feedback.update",
        "qa_run",
        run_id,
        kb_id=kb_id,
        detail={
            "feedbackStatus": updated["feedback_status"],
            "failureType": _failure_type(updated),
        },
    )
    session.commit()
    return QARunFeedbackResponse(
        runId=str(updated["run_id"]),
        feedbackStatus=updated["feedback_status"],
        failureType=_failure_type(updated),
        feedbackNote=updated["feedback_note"],
        updatedAt=updated["updated_at"].isoformat(),
    )


def get_qa_run_replay_context(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
) -> QARunReplayContextDTO | None:
    """获取回放上下文，不直接复用旧结果。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _require_permission(session, current_user, kb_id, "kb.qa.run")
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None

    warnings: list[str] = []
    revision_row = session.execute(
        select(config_revisions)
        .where(
            config_revisions.c.kb_id == kb_id,
            config_revisions.c.config_revision_id == row["config_revision_id"],
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if revision_row is None:
        warnings.append("原运行使用的配置版本已不可见，建议改用当前 active revision。")
    elif revision_row["status"] in {"archived", "invalid"}:
        warnings.append("原运行使用的配置版本不是当前可运行版本，回放时可复制为草稿或改用 active revision。")

    return QARunReplayContextDTO(
        sourceRunId=str(row["run_id"]),
        query=row["query"],
        configRevisionId=str(row["config_revision_id"]),
        overrideParams=row["override_snapshot"],
        suggestedMode="replay" if revision_row and revision_row["status"] in {"active", "saved"} else "copyAsNew",
        warnings=warnings,
    )


def create_config_revision_draft_from_qa_run(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
) -> ConfigRevisionDTO | None:
    """从 QARun 锁定的 Revision 复制 Pipeline，并附带回放来源信息生成草稿。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _require_permission(session, current_user, kb_id, "kb.config.manage")
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None
    source_revision = session.execute(
        select(config_revisions)
        .where(
            config_revisions.c.kb_id == kb_id,
            config_revisions.c.config_revision_id == row["config_revision_id"],
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if source_revision is None:
        return None

    actor_id = UUID(current_user.user.userId)
    revision_no = (
        session.execute(select(func.coalesce(func.max(config_revisions.c.revision_no), 0)).where(config_revisions.c.kb_id == kb_id)).scalar_one()
        + 1
    )
    validation_snapshot = {
        **source_revision["validation_snapshot"],
        "copiedFromRunId": str(run_id),
        "copiedFromRevisionId": str(source_revision["config_revision_id"]),
        "copiedAt": datetime.now(UTC).isoformat(),
    }
    draft = session.execute(
        insert(config_revisions)
        .values(
            config_revision_id=uuid4(),
            kb_id=kb_id,
            revision_no=revision_no,
            source_template_id=source_revision["source_template_id"],
            status="draft",
            pipeline_definition=source_revision["pipeline_definition"],
            validation_snapshot=validation_snapshot,
            remark=f"从 QA Run {str(run_id)[:8]} 生成草稿",
            created_by=actor_id,
            updated_by=actor_id,
        )
        .returning(config_revisions)
    ).mappings().one()
    session.commit()
    return _to_config_revision_dto(draft)


def create_evaluation_sample_from_run(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
    request: EvaluationSampleCreateRequest,
) -> EvaluationSampleDTO | None:
    """从历史运行沉淀评估样本，保留期望答案和关键证据快照。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _require_permission(session, current_user, kb_id, "kb.evaluation.manage")
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None

    evidence_rows = session.execute(
        select(qa_run_evidence.c.chunk_id, qa_run_evidence.c.evidence_order, qa_run_evidence.c.source_snapshot)
        .where(qa_run_evidence.c.run_id == run_id)
        .order_by(qa_run_evidence.c.evidence_order.asc())
    ).mappings()
    default_evidence = {
        "chunkIds": [str(evidence["chunk_id"]) for evidence in evidence_rows if evidence["chunk_id"]],
        "source": "qa_run_evidence",
    }
    sample = session.execute(
        insert(evaluation_samples)
        .values(
            sample_id=uuid4(),
            kb_id=kb_id,
            source_run_id=run_id,
            query=row["query"],
            expected_answer=request.expectedAnswer if request.expectedAnswer is not None else row["answer"],
            expected_evidence=request.expectedEvidence or default_evidence,
            status="active",
            metadata=request.metadata or {"feedbackStatus": row["feedback_status"], "failureType": _failure_type(row)},
            created_by=UUID(current_user.user.userId),
            updated_by=UUID(current_user.user.userId),
        )
        .returning(evaluation_samples)
    ).mappings().one()
    session.commit()
    return _to_evaluation_sample_dto(sample)


def list_evaluation_samples(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
) -> PageResponse[EvaluationSampleDTO] | None:
    """分页查询评估样本，作为回归验证入口的最小管理能力。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    _require_permission(session, current_user, kb_id, "kb.evaluation.manage")
    condition = (
        (evaluation_samples.c.kb_id == kb_id)
        & (evaluation_samples.c.deleted_at.is_(None))
        & (evaluation_samples.c.status == "active")
    )
    total = session.execute(select(func.count()).select_from(evaluation_samples).where(condition)).scalar_one()
    rows = session.execute(
        select(evaluation_samples)
        .where(condition)
        .order_by(evaluation_samples.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_evaluation_sample_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )
