from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse
from app.schemas.qa_run import (
    QARunCandidateDTO,
    QARunCitationDTO,
    QARunCreateRequest,
    QARunCreateResponse,
    QARunDetailDTO,
    QARunEvidenceDTO,
    QARunListItemDTO,
    QARunStatusDTO,
    QARunTraceStepDTO,
)
from app.schemas.common import PageResponse
from app.tables import (
    config_revisions,
    knowledge_bases,
    qa_run_candidates,
    qa_run_citations,
    qa_run_evidence,
    qa_run_trace_steps,
    qa_runs,
)
from app.services.qa_providers import ProviderCandidate, ProviderError, QARunProviders, get_qa_run_providers


class QARunCreateConflict(ValueError):
    """创建 QARun 时遇到业务状态冲突，例如缺少可运行 Revision。"""


RETRIEVAL_NODE_TO_OVERRIDE_KEY = {
    "denseRetrieval": "dense",
    "sparseRetrieval": "sparse",
    "graphRetrieval": "graph",
}
MOCK_EVIDENCE_CHUNK_ID = UUID("00000000-0000-0000-0000-000000000001")


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用开发期最小权限：平台管理员可访问全部知识库。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库；不可见资源不暴露存在性。"""
    condition = (knowledge_bases.c.deleted_at.is_(None)) & (knowledge_bases.c.kb_id == kb_id)
    if not _is_platform_admin(current_user):
        condition = condition & (knowledge_bases.c.owner_id == UUID(current_user.user.userId))
    return session.execute(select(knowledge_bases).where(condition).limit(1)).mappings().first()


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


def _read_visible_qa_run(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
) -> RowMapping | None:
    """按知识库可见性读取运行记录，避免通过 runId 枚举不可见数据。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    return session.execute(
        select(qa_runs)
        .where(qa_runs.c.kb_id == kb_id, qa_runs.c.run_id == run_id)
        .limit(1)
    ).mappings().first()


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
                channel_candidates = provider_set.dense.retrieve(kb_id, rewritten_query, embedding, settings.provider_top_k)
            elif channel == "sparse":
                channel_candidates = provider_set.sparse.retrieve(kb_id, rewritten_query, settings.provider_top_k)
            else:
                channel_candidates = provider_set.graph.retrieve(kb_id, rewritten_query, None, settings.provider_top_k)
            candidates.extend(channel_candidates)
            _insert_trace_step(
                session,
                run_id,
                trace_order,
                step_key,
                "success",
                {"query": rewritten_query},
                {"candidateCount": len(channel_candidates)},
                {"provider": provider_name},
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

    # 当前仓库尚未落地 Chunk 权限表；这里保留权限裁剪步骤，后续接入 PG Chunk 回表校验。
    authorized_candidates = reranked_candidates
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
            "droppedCandidates": 0,
            "note": "Chunk permission table is not available in current sprint.",
        },
        {"latencyMs": 0},
        started_at=started_at,
    )
    trace_order += 1

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

    revision_row = _resolve_runnable_revision(session, kb_row, request.configRevisionId)
    run_id = uuid4()
    actor_id = UUID(current_user.user.userId)
    override_snapshot = request.overrideParams or {}
    if request.sourceRunId is not None and _read_visible_qa_run(session, current_user, kb_id, request.sourceRunId) is None:
        raise QARunCreateConflict("Source QA run not found for this knowledge base.")
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
        _execute_provider_qa_run(session, run_id, kb_id, request.query, revision_row, override_snapshot)
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
) -> PageResponse[QARunListItemDTO] | None:
    """分页查询 QA 历史列表，当前按知识库可见性做最小过滤。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = qa_runs.c.kb_id == kb_id
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & qa_runs.c.query.ilike(keyword_pattern)

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
