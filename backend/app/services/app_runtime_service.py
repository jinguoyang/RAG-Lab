from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.orm import Session

from app.schemas.app_runtime import (
    AppRuntimeChatRequest,
    AppRuntimeChatResponse,
    AppRuntimeCitationDTO,
    AppRuntimeFeedbackRequest,
    AppRuntimeFeedbackResponse,
)
from app.schemas.auth import CurrentUserResponse, UserDTO
from app.schemas.qa_run import QARunCreateRequest
from app.services.qa_run_service import QARunCreateConflict, create_qa_run, get_qa_run_detail
from app.tables import (
    app_conversations,
    app_invocations,
    app_messages,
    config_revisions,
    evaluation_samples,
    knowledge_bases,
    qa_run_evidence,
    qa_runs,
    rag_app_api_keys,
    rag_apps,
    users,
)


class AppRuntimeAuthError(Exception):
    """App API Key 无效、过期或已禁用。"""


class AppRuntimeNotFoundError(Exception):
    """App Runtime 请求访问了不属于当前 App 的资源。"""


class AppRuntimeConflictError(ValueError):
    """App Runtime 请求遇到应用、知识库或配置状态冲突。"""


class AppRuntimeQuotaExceededError(ValueError):
    """App Runtime 调用超过应用级短窗口限流或日配额。"""


FEEDBACK_STATUS_MAP = {
    "correct": "correct",
    "partiallyCorrect": "partially_correct",
    "partially_correct": "partially_correct",
    "wrong": "wrong",
    "citationError": "citation_error",
    "citation_error": "citation_error",
    "noEvidence": "no_evidence",
    "no_evidence": "no_evidence",
}


@dataclass(frozen=True)
class _RuntimeContext:
    """一次 Runtime 调用解析出的最小执行上下文。"""

    app_row: RowMapping
    key_row: RowMapping
    kb_row: RowMapping
    revision_id: UUID
    actor: CurrentUserResponse


def _hash_api_key(api_key: str) -> str:
    """按管理端相同规则计算 API Key 哈希。"""
    return sha256(api_key.encode("utf-8")).hexdigest()


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    """兼容数据库返回 naive datetime 的过期判断。"""
    if expires_at is None:
        return False
    comparable_expires_at = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    return comparable_expires_at <= now


def _read_key_context(session: Session, api_key: str, now: datetime) -> tuple[RowMapping, RowMapping, RowMapping]:
    """读取 active API Key 及其 App/KB；失败统一按鉴权失败处理。"""
    key_hash = _hash_api_key(api_key)
    key_row = session.execute(
        select(rag_app_api_keys)
        .where(rag_app_api_keys.c.key_hash == key_hash)
        .limit(1)
    ).mappings().first()
    if key_row is None or key_row["status"] != "active" or _is_expired(key_row["expires_at"], now):
        raise AppRuntimeAuthError
    app_row = session.execute(
        select(rag_apps)
        .where(
            rag_apps.c.app_id == key_row["app_id"],
            rag_apps.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if app_row is None:
        raise AppRuntimeAuthError
    kb_row = session.execute(
        select(knowledge_bases)
        .where(
            knowledge_bases.c.kb_id == app_row["kb_id"],
            knowledge_bases.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if kb_row is None:
        raise AppRuntimeAuthError
    return key_row, app_row, kb_row


def _read_revision_id(session: Session, app_row: RowMapping, kb_row: RowMapping) -> UUID:
    """解析 App 默认 Revision，缺省时回落到知识库 active revision。"""
    revision_id = app_row["default_config_revision_id"] or kb_row["active_config_revision_id"]
    if revision_id is None:
        raise AppRuntimeConflictError("RAG_APP_NO_RUNNABLE_REVISION")
    row = session.execute(
        select(config_revisions.c.config_revision_id, config_revisions.c.status)
        .where(
            config_revisions.c.kb_id == kb_row["kb_id"],
            config_revisions.c.config_revision_id == revision_id,
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if row is None or row["status"] in {"draft", "invalid"}:
        raise AppRuntimeConflictError("RAG_APP_NO_RUNNABLE_REVISION")
    return row["config_revision_id"]


def _read_runtime_actor(session: Session, app_row: RowMapping, kb_row: RowMapping) -> CurrentUserResponse:
    """使用 App 创建人或 KB Owner 作为内部执行主体，以复用现有 QARun 权限链路。"""
    actor_id = app_row["created_by"] or kb_row["owner_id"]
    row = session.execute(
        select(users)
        .where(
            users.c.user_id == actor_id,
            users.c.status == "active",
            users.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if row is None:
        raise AppRuntimeConflictError("RAG_APP_NO_RUNTIME_ACTOR")
    return CurrentUserResponse(
        user=UserDTO(
            userId=str(row["user_id"]),
            username=row["username"],
            displayName=row["display_name"],
            email=row["email"],
            platformRole=row["platform_role"],
            securityLevel=row["security_level"],
            status=row["status"],
        ),
        platformPermissions=[],
        visibleKbCount=0,
    )


def _insert_failed_invocation_for_known_app(
    session: Session,
    app_row: RowMapping,
    key_row: RowMapping,
    request: AppRuntimeChatRequest,
    started_at: datetime,
    started_counter: float,
    error_code: str,
) -> None:
    """已解析 App/Key 的拒绝调用也写入审计，便于来源排障。"""
    latency_ms = int((perf_counter() - started_counter) * 1000)
    session.execute(
        insert(app_invocations).values(
            invocation_id=uuid4(),
            app_id=app_row["app_id"],
            api_key_id=key_row["api_key_id"],
            status="failed",
            error_code=error_code,
            latency_ms=latency_ms,
            request_summary={
                "queryLength": len(request.query),
                "hasConversationId": request.conversationId is not None,
                "hasInputs": bool(request.inputs),
                "responseMode": request.responseMode,
            },
            response_summary={},
            created_at=started_at,
        )
    )
    session.commit()


def _positive_limit(value: object) -> int | None:
    """将应用元数据中的限流值收口为正整数；无效值视为未配置。"""
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    return limit if limit > 0 else None


def _runtime_limits(app_row: RowMapping) -> tuple[int | None, int | None]:
    """从 outputPolicy 或 metadata 读取最小生产化限流配置。"""
    output_policy = app_row["output_policy"] or {}
    metadata = app_row["metadata"] or {}
    limits = {}
    if isinstance(output_policy, dict) and isinstance(output_policy.get("runtimeLimits"), dict):
        limits.update(output_policy["runtimeLimits"])
    if isinstance(metadata, dict) and isinstance(metadata.get("runtimeLimits"), dict):
        limits.update(metadata["runtimeLimits"])
    minute_limit = _positive_limit(limits.get("minuteLimit") or limits.get("requestsPerMinute"))
    daily_quota = _positive_limit(limits.get("dailyQuota") or limits.get("dailyRequestQuota"))
    return minute_limit, daily_quota


def _count_invocations_since(
    session: Session,
    app_id: UUID,
    since: datetime,
    success_only: bool = False,
) -> int:
    """基于 app_invocations 做轻量聚合，避免引入额外配额表。"""
    condition = (app_invocations.c.app_id == app_id) & (app_invocations.c.created_at >= since)
    if success_only:
        condition = condition & (app_invocations.c.status == "success")
    return session.execute(select(func.count()).select_from(app_invocations).where(condition)).scalar_one()


def _assert_runtime_quota(
    session: Session,
    app_row: RowMapping,
    key_row: RowMapping,
    request: AppRuntimeChatRequest,
    now: datetime,
    started_counter: float,
) -> None:
    """在创建 QARun 前执行应用级限流和日配额检查。"""
    minute_limit, daily_quota = _runtime_limits(app_row)
    quota_exceeded = False
    if minute_limit is not None:
        minute_count = _count_invocations_since(session, app_row["app_id"], now - timedelta(minutes=1))
        quota_exceeded = minute_count >= minute_limit
    if not quota_exceeded and daily_quota is not None:
        day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        daily_success_count = _count_invocations_since(session, app_row["app_id"], day_start, success_only=True)
        quota_exceeded = daily_success_count >= daily_quota
    if quota_exceeded:
        _insert_failed_invocation_for_known_app(
            session,
            app_row,
            key_row,
            request,
            now,
            started_counter,
            "RAG_APP_QUOTA_EXCEEDED",
        )
        raise AppRuntimeQuotaExceededError("RAG_APP_QUOTA_EXCEEDED")


def _resolve_runtime_context(
    session: Session,
    api_key: str,
    request: AppRuntimeChatRequest,
    now: datetime,
    started_counter: float,
) -> _RuntimeContext:
    """完成鉴权、状态校验和 Revision/Actor 解析。"""
    key_row, app_row, kb_row = _read_key_context(session, api_key, now)
    if app_row["status"] != "active":
        _insert_failed_invocation_for_known_app(
            session,
            app_row,
            key_row,
            request,
            now,
            started_counter,
            "RAG_APP_DISABLED",
        )
        raise AppRuntimeConflictError("RAG_APP_DISABLED")
    if kb_row["status"] == "disabled":
        _insert_failed_invocation_for_known_app(session, app_row, key_row, request, now, started_counter, "KB_DISABLED")
        raise AppRuntimeConflictError("KB_DISABLED")
    _assert_runtime_quota(session, app_row, key_row, request, now, started_counter)
    try:
        revision_id = _read_revision_id(session, app_row, kb_row)
        actor = _read_runtime_actor(session, app_row, kb_row)
    except AppRuntimeConflictError as exc:
        error_code = str(exc) or "RAG_APP_RUNTIME_CONFLICT"
        _insert_failed_invocation_for_known_app(session, app_row, key_row, request, now, started_counter, error_code)
        raise
    return _RuntimeContext(app_row=app_row, key_row=key_row, kb_row=kb_row, revision_id=revision_id, actor=actor)


def _get_or_create_conversation(
    session: Session,
    app_id: UUID,
    request: AppRuntimeChatRequest,
    now: datetime,
) -> RowMapping:
    """获取当前 App 内会话；conversationId 不跨 App 复用。"""
    if request.conversationId is not None:
        row = session.execute(
            select(app_conversations)
            .where(
                app_conversations.c.conversation_id == request.conversationId,
                app_conversations.c.app_id == app_id,
                app_conversations.c.status == "active",
            )
            .limit(1)
        ).mappings().first()
        if row is None:
            raise AppRuntimeNotFoundError
        return row

    return session.execute(
        insert(app_conversations)
        .values(
            conversation_id=uuid4(),
            app_id=app_id,
            end_user_id=request.endUserId,
            status="active",
            metadata={"source": "app-runtime"},
            created_at=now,
            updated_at=now,
        )
        .returning(app_conversations)
    ).mappings().one()


def _insert_message(
    session: Session,
    conversation_id: UUID,
    role: str,
    content: str,
    status: str,
    now: datetime,
    qa_run_id: UUID | None = None,
    metadata: dict | None = None,
) -> RowMapping:
    """写入 App 对话消息，作为 Runtime 会话审计主线。"""
    return session.execute(
        insert(app_messages)
        .values(
            message_id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            qa_run_id=qa_run_id,
            status=status,
            metadata=metadata or {},
            created_at=now,
        )
        .returning(app_messages)
    ).mappings().one()


def _insert_invocation(
    session: Session,
    context: _RuntimeContext,
    request: AppRuntimeChatRequest,
    started_at: datetime,
    started_counter: float,
    status: str,
    error_code: str | None = None,
    conversation_id: UUID | None = None,
    message_id: UUID | None = None,
    qa_run_id: UUID | None = None,
    response_summary: dict | None = None,
) -> None:
    """记录 App Runtime 调用摘要；正文与密钥不进入审计摘要。"""
    latency_ms = int((perf_counter() - started_counter) * 1000)
    session.execute(
        insert(app_invocations).values(
            invocation_id=uuid4(),
            app_id=context.app_row["app_id"],
            api_key_id=context.key_row["api_key_id"],
            conversation_id=conversation_id,
            message_id=message_id,
            qa_run_id=qa_run_id,
            status=status,
            error_code=error_code,
            latency_ms=latency_ms,
            request_summary={
                "queryLength": len(request.query),
                "hasConversationId": request.conversationId is not None,
                "hasInputs": bool(request.inputs),
                "responseMode": request.responseMode,
            },
            response_summary=response_summary or {},
            created_at=started_at,
        )
    )


def _to_response_usage(metrics: dict) -> dict:
    """将 QARun metrics 收敛为外部调用可见的 usage。"""
    return {
        "latencyMs": metrics.get("latencyMs"),
        "tokenUsage": metrics.get("tokenUsage", {}),
        "hitCount": metrics.get("hitCount"),
        "evidenceCount": metrics.get("evidenceCount"),
        "citationCount": metrics.get("citationCount"),
    }


def chat_with_app_runtime(
    session: Session,
    api_key: str,
    request: AppRuntimeChatRequest,
) -> AppRuntimeChatResponse:
    """执行 App Runtime blocking 对话，并复用现有 QARun 检索与权限过滤链路。"""
    started_at = datetime.now(UTC)
    started_counter = perf_counter()
    context = _resolve_runtime_context(session, api_key, request, started_at, started_counter)
    conversation_row = _get_or_create_conversation(session, context.app_row["app_id"], request, started_at)
    _insert_message(
        session,
        conversation_row["conversation_id"],
        "user",
        request.query,
        "success",
        started_at,
        metadata={"hasInputs": bool(request.inputs)},
    )
    session.execute(
        update(rag_app_api_keys)
        .where(rag_app_api_keys.c.api_key_id == context.key_row["api_key_id"])
        .values(last_used_at=started_at)
    )

    try:
        qa_response = create_qa_run(
            session,
            context.actor,
            context.kb_row["kb_id"],
            QARunCreateRequest(
                query=request.query,
                configRevisionId=context.revision_id,
                overrideParams={
                    "appRuntime": {
                        "appId": str(context.app_row["app_id"]),
                        "conversationId": str(conversation_row["conversation_id"]),
                        "endUserId": request.endUserId,
                    }
                },
            ),
        )
    except QARunCreateConflict:
        session.rollback()
        _insert_invocation(session, context, request, started_at, started_counter, status="failed", error_code="QA_RUN_CONFLICT")
        session.commit()
        raise
    if qa_response is None:
        raise AppRuntimeConflictError("RAG_APP_KB_NOT_FOUND")

    detail = get_qa_run_detail(
        session,
        context.actor,
        context.kb_row["kb_id"],
        UUID(qa_response.runId),
        include_trace=False,
        include_candidates=False,
    )
    if detail is None:
        raise AppRuntimeConflictError("QA_RUN_NOT_FOUND")

    assistant_message_row = _insert_message(
        session,
        conversation_row["conversation_id"],
        "assistant",
        detail.answer or "",
        "success" if detail.status in {"success", "partial"} else "failed",
        datetime.now(UTC),
        qa_run_id=UUID(detail.runId),
        metadata={"runStatus": detail.status, "citationCount": len(detail.citations)},
    )
    session.execute(
        update(app_conversations)
        .where(app_conversations.c.conversation_id == conversation_row["conversation_id"])
        .values(updated_at=datetime.now(UTC))
    )

    usage = _to_response_usage(detail.metrics or {})
    _insert_invocation(
        session,
        context,
        request,
        started_at,
        started_counter,
        status="success",
        conversation_id=conversation_row["conversation_id"],
        message_id=assistant_message_row["message_id"],
        qa_run_id=UUID(detail.runId),
        response_summary={
            "runStatus": detail.status,
            "answerLength": len(detail.answer or ""),
            "citationCount": len(detail.citations),
        },
    )
    session.commit()

    return AppRuntimeChatResponse(
        answer=detail.answer or "",
        conversationId=str(conversation_row["conversation_id"]),
        messageId=str(assistant_message_row["message_id"]),
        runId=detail.runId,
        citations=[
            AppRuntimeCitationDTO(
                citationId=item.citationId,
                evidenceId=item.evidenceId,
                label=item.label,
                locationSnapshot=item.locationSnapshot,
            )
            for item in detail.citations
        ],
        usage=usage,
        metadata={
            "appId": str(context.app_row["app_id"]),
            "kbId": str(context.kb_row["kb_id"]),
            "configRevisionId": str(context.revision_id),
            "runStatus": detail.status,
            "responseMode": request.responseMode,
        },
    )


def iter_chat_sse_events(response: AppRuntimeChatResponse):
    """把已完成的 Runtime 响应转换为 SSE 事件，保持 blocking 执行事实不变。"""
    answer = response.answer or ""
    chunk_size = 120
    for start in range(0, len(answer), chunk_size):
        data = {"text": answer[start:start + chunk_size], "index": start // chunk_size}
        yield f"event: answer_delta\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    if not answer:
        yield f"event: answer_delta\ndata: {json.dumps({'text': '', 'index': 0}, ensure_ascii=False)}\n\n"
    for citation in response.citations:
        yield f"event: citation\ndata: {citation.model_dump_json()}\n\n"
    yield f"event: usage\ndata: {json.dumps(response.usage, ensure_ascii=False)}\n\n"
    done_payload = {
        "conversationId": response.conversationId,
        "messageId": response.messageId,
        "runId": response.runId,
        "metadata": response.metadata,
    }
    yield f"event: done\ndata: {json.dumps(done_payload, ensure_ascii=False)}\n\n"


def _normalize_feedback_status(value: str) -> str:
    """兼容外部 camelCase 和内部 snake_case 反馈枚举。"""
    normalized = FEEDBACK_STATUS_MAP.get(value)
    if normalized is None:
        raise AppRuntimeConflictError("INVALID_FEEDBACK_STATUS")
    return normalized


def _read_feedback_message(
    session: Session,
    app_id: UUID,
    message_id: UUID,
) -> tuple[RowMapping, RowMapping]:
    """读取当前 App 的助手消息及其会话，避免跨 App 反馈。"""
    row = session.execute(
        select(app_messages, app_conversations.c.app_id)
        .select_from(app_messages.join(app_conversations, app_messages.c.conversation_id == app_conversations.c.conversation_id))
        .where(
            app_messages.c.message_id == message_id,
            app_messages.c.role == "assistant",
            app_messages.c.qa_run_id.is_not(None),
            app_conversations.c.app_id == app_id,
        )
        .limit(1)
    ).mappings().first()
    if row is None:
        raise AppRuntimeNotFoundError
    run_row = session.execute(
        select(qa_runs)
        .where(qa_runs.c.run_id == row["qa_run_id"])
        .limit(1)
    ).mappings().first()
    if run_row is None:
        raise AppRuntimeNotFoundError
    return row, run_row


def _create_feedback_sample(
    session: Session,
    context: _RuntimeContext,
    message_id: UUID,
    run_row: RowMapping,
    request: AppRuntimeFeedbackRequest,
    now: datetime,
) -> UUID:
    """将外部负反馈沉淀为 EvaluationSample，并只保存来源摘要。"""
    evidence_rows = session.execute(
        select(qa_run_evidence.c.chunk_id)
        .where(qa_run_evidence.c.run_id == run_row["run_id"])
        .order_by(qa_run_evidence.c.evidence_order.asc())
    ).mappings()
    expected_evidence = request.expectedEvidence or {
        "chunkIds": [str(row["chunk_id"]) for row in evidence_rows if row["chunk_id"]],
        "source": "app_runtime_feedback",
    }
    sample_id = uuid4()
    actor_id = UUID(context.actor.user.userId)
    session.execute(
        insert(evaluation_samples).values(
            sample_id=sample_id,
            kb_id=context.kb_row["kb_id"],
            source_run_id=run_row["run_id"],
            query=run_row["query"],
            expected_answer=request.expectedAnswer if request.expectedAnswer is not None else run_row["answer"],
            expected_evidence=expected_evidence,
            status="active",
            metadata={
                "source": "app_runtime_feedback",
                "appId": str(context.app_row["app_id"]),
                "messageId": str(message_id),
                "feedbackStatus": _normalize_feedback_status(request.feedbackStatus),
                "failureType": request.failureType,
            },
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
    )
    return sample_id


def submit_app_runtime_feedback(
    session: Session,
    api_key: str,
    message_id: UUID,
    request: AppRuntimeFeedbackRequest,
) -> AppRuntimeFeedbackResponse:
    """回流外部反馈到 QARun，并按需生成 EvaluationSample。"""
    now = datetime.now(UTC)
    key_row, app_row, kb_row = _read_key_context(session, api_key, now)
    if app_row["status"] != "active":
        raise AppRuntimeConflictError("RAG_APP_DISABLED")
    actor = _read_runtime_actor(session, app_row, kb_row)
    context = _RuntimeContext(
        app_row=app_row,
        key_row=key_row,
        kb_row=kb_row,
        revision_id=app_row["default_config_revision_id"] or kb_row["active_config_revision_id"],
        actor=actor,
    )
    message_row, run_row = _read_feedback_message(session, app_row["app_id"], message_id)
    feedback_status = _normalize_feedback_status(request.feedbackStatus)
    metrics = dict(run_row["metrics"] or {})
    if request.failureType:
        metrics["failureType"] = request.failureType
    else:
        metrics.pop("failureType", None)

    actor_id = UUID(actor.user.userId)
    session.execute(
        update(qa_runs)
        .where(qa_runs.c.run_id == run_row["run_id"])
        .values(
            feedback_status=feedback_status,
            feedback_note=request.feedbackNote,
            metrics=metrics,
            updated_at=now,
            updated_by=actor_id,
        )
    )
    message_metadata = dict(message_row["metadata"] or {})
    message_metadata["feedback"] = {
        "feedbackStatus": feedback_status,
        "failureType": request.failureType,
        "createdAt": now.isoformat(),
        "createEvaluationSample": request.createEvaluationSample,
    }
    session.execute(
        update(app_messages)
        .where(app_messages.c.message_id == message_id)
        .values(metadata=message_metadata)
    )

    sample_id = None
    if request.createEvaluationSample:
        sample_id = _create_feedback_sample(session, context, message_id, run_row, request, now)
    session.commit()
    return AppRuntimeFeedbackResponse(
        messageId=str(message_id),
        runId=str(run_row["run_id"]),
        feedbackStatus=feedback_status,
        failureType=request.failureType,
        feedbackNote=request.feedbackNote,
        evaluationSampleId=str(sample_id) if sample_id else None,
        createdAt=now.isoformat(),
    )
