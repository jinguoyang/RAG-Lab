from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.qa_run import (
    QARunCandidateDTO,
    QARunCitationDTO,
    QARunCreateRequest,
    QARunCreateResponse,
    QARunDetailDTO,
    QARunEvidenceDTO,
    QARunStatusDTO,
    QARunTraceStepDTO,
)
from app.tables import (
    config_revisions,
    knowledge_bases,
    qa_run_candidates,
    qa_run_citations,
    qa_run_evidence,
    qa_run_trace_steps,
    qa_runs,
)


class QARunCreateConflict(ValueError):
    """创建 QARun 时遇到业务状态冲突，例如缺少可运行 Revision。"""


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


def _execute_mock_qa_run(session: Session, run_id: UUID, query: str) -> None:
    """执行开发期 mock Provider，写入可追溯的最小 QA 结果。"""
    started_at = datetime.now(UTC)
    rewritten_query = query if query.endswith("?") or query.endswith("？") else f"{query}?"
    answer = f"这是基于 mock Provider 生成的调试回答：{query}"
    evidence_id = uuid4()
    candidate_id = uuid4()
    citation_id = uuid4()
    content_snapshot = "mock Provider 当前使用固定证据，用于验证 QARun 状态、Trace、Evidence 和 Citation 链路。"
    content_hash = sha256(content_snapshot.encode("utf-8")).hexdigest()

    # mock 链路保持安全边界显式可见，后续替换真实 Provider 时仍保留 permissionFilter。
    trace_steps = [
        (
            "queryRewrite",
            {"query": query},
            {"rewrittenQuery": rewritten_query},
            {"latencyMs": 5},
        ),
        (
            "mockRetrieval",
            {"query": rewritten_query},
            {"candidateCount": 1},
            {"latencyMs": 8},
        ),
        (
            "permissionFilter",
            {"inputCandidates": 1},
            {"authorizedCandidates": 1, "droppedCandidates": 0},
            {"latencyMs": 3},
        ),
        (
            "generation",
            {"evidenceCount": 1},
            {"answerPreview": answer[:80]},
            {"latencyMs": 12, "totalTokens": 128},
        ),
        (
            "citation",
            {"evidenceCount": 1},
            {"citationCount": 1},
            {"latencyMs": 2},
        ),
    ]

    for index, (step_key, input_summary, output_summary, metrics) in enumerate(trace_steps, start=1):
        session.execute(
            insert(qa_run_trace_steps).values(
                trace_step_id=uuid4(),
                run_id=run_id,
                step_order=index,
                step_key=step_key,
                status="success",
                input_summary=input_summary,
                output_summary=output_summary,
                metrics=metrics,
                started_at=started_at,
                ended_at=datetime.now(UTC),
            )
        )

    session.execute(
        insert(qa_run_candidates).values(
            candidate_id=candidate_id,
            run_id=run_id,
            source_type="mock",
            raw_score=1,
            rerank_score=1,
            rank_no=1,
            is_authorized=True,
            metadata={"documentName": "Mock Evidence", "section": "dev-provider"},
        )
    )
    session.execute(
        insert(qa_run_evidence).values(
            evidence_id=evidence_id,
            run_id=run_id,
            candidate_id=candidate_id,
            evidence_order=1,
            content_snapshot=content_snapshot,
            content_snapshot_hash=content_hash,
            snapshot_policy="redacted",
            redaction_status="none",
            source_snapshot={
                "documentName": "Mock Evidence",
                "pageNo": 1,
                "section": "dev-provider",
            },
        )
    )
    session.execute(
        insert(qa_run_citations).values(
            citation_id=citation_id,
            run_id=run_id,
            evidence_id=evidence_id,
            citation_order=1,
            label="Mock Evidence#1",
            location_snapshot={"pageNo": 1, "section": "dev-provider"},
        )
    )
    session.execute(
        update(qa_runs)
        .where(qa_runs.c.run_id == run_id)
        .values(
            rewritten_query=rewritten_query,
            status="success",
            answer=answer,
            metrics={
                "latencyMs": 30,
                "totalTokens": 128,
                "retrievalDiagnostics": {
                    "denseCount": 0,
                    "sparseCount": 0,
                    "graphCount": 0,
                    "mockCount": 1,
                    "droppedByPermission": 0,
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
        _execute_mock_qa_run(session, run_id, request.query)
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
                chunkId=str(evidence_row["chunk_id"]) if evidence_row["chunk_id"] else None,
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
