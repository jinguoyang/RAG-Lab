from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import base64
from hashlib import sha256
import hmac
import json
from time import perf_counter
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.app_runtime import (
    AppRuntimeChatRequest,
    AppRuntimeChatResponse,
    AppRuntimeCitationDTO,
    AppRuntimeEmbedTokenRequest,
    AppRuntimeEmbedTokenResponse,
    AppRuntimeFeedbackRequest,
    AppRuntimeFeedbackResponse,
    AppRuntimeRetrievedEvidenceDTO,
    AppRuntimeRetrieveRequest,
    AppRuntimeRetrieveResponse,
    AppRuntimeStructuredRunRequest,
    AppRuntimeStructuredRunResponse,
    AppRuntimeTrainingQuestionResultDTO,
    AppRuntimeTrainingQuizSubmissionRequest,
    AppRuntimeTrainingQuizSubmissionResponse,
)
from app.schemas.auth import CurrentUserResponse, UserDTO
from app.schemas.qa_run import QARunCreateRequest
from app.services.dictionary_service import require_active_dict_item
from app.services.qa_run_service import QARunCreateConflict, create_qa_run, get_qa_run_detail
from app.tables import (
    app_conversations,
    app_invocations,
    app_messages,
    chunks,
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


class AppRuntimeConcurrencyExceededError(ValueError):
    """App Runtime 同时运行调用超过应用级并发上限。"""


class KnowledgeBaseDisabledError(Exception):
    """知识库已禁用。"""

    def __init__(self, kb_id: UUID):
        self.kb_id = kb_id
        super().__init__(f"Knowledge base {kb_id} is disabled")


class KnowledgeBaseNotFoundError(Exception):
    """知识库不存在。"""

    def __init__(self, kb_id: UUID):
        self.kb_id = kb_id
        super().__init__(f"Knowledge base {kb_id} not found")


def _check_kb_status(
    session: Session,
    kb_id: UUID,
) -> None:
    """检查知识库状态。

    Raises:
        KnowledgeBaseNotFoundError: 知识库不存在
        KnowledgeBaseDisabledError: 知识库已禁用
    """
    kb = session.execute(
        select(knowledge_bases).where(
            knowledge_bases.c.kb_id == kb_id,
            knowledge_bases.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()

    if not kb:
        raise KnowledgeBaseNotFoundError(kb_id)

    if kb.get("status") == "disabled":
        raise KnowledgeBaseDisabledError(kb_id)


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


EMBED_TOKEN_PREFIX = "rlet_"


def _hash_api_key(api_key: str) -> str:
    """按管理端相同规则计算 API Key 哈希。"""
    return sha256(api_key.encode("utf-8")).hexdigest()


def _b64url_encode(payload: bytes) -> str:
    """生成不带 padding 的 URL 安全 Base64，便于作为 Bearer Token 传递。"""
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    """解码不带 padding 的 URL 安全 Base64。"""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _embed_token_secret() -> bytes:
    """读取嵌入 Token 签名密钥，避免浏览器端暴露 App API Key。"""
    return get_settings().app_runtime_embed_token_secret.encode("utf-8")


def _sign_embed_payload(payload_part: str) -> str:
    """对 Token payload 签名，校验时使用常量时间比较防篡改。"""
    signature = hmac.new(_embed_token_secret(), payload_part.encode("ascii"), "sha256").digest()
    return _b64url_encode(signature)


def _encode_embed_token(payload: dict) -> str:
    """将短期 Token payload 编码为 rlet_ 前缀令牌。"""
    payload_part = _b64url_encode(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature_part = _sign_embed_payload(payload_part)
    return f"{EMBED_TOKEN_PREFIX}{payload_part}.{signature_part}"


def _decode_embed_token(token: str, now: datetime) -> dict:
    """校验并解析嵌入 Token；过期、篡改和格式错误统一视为鉴权失败。"""
    if not token.startswith(EMBED_TOKEN_PREFIX):
        raise AppRuntimeAuthError
    body = token[len(EMBED_TOKEN_PREFIX):]
    payload_part, separator, signature_part = body.partition(".")
    if not separator or not payload_part or not signature_part:
        raise AppRuntimeAuthError
    expected_signature = _sign_embed_payload(payload_part)
    if not hmac.compare_digest(expected_signature, signature_part):
        raise AppRuntimeAuthError
    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise AppRuntimeAuthError
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at <= int(now.timestamp()):
        raise AppRuntimeAuthError
    return payload


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


def _read_embed_token_context(session: Session, embed_token: str, now: datetime) -> tuple[RowMapping, RowMapping, RowMapping]:
    """读取短期 Embed Token 中绑定的 Key/App/KB，避免跨 App 或已撤销 Key 继续调用。"""
    payload = _decode_embed_token(embed_token, now)
    try:
        app_id = UUID(str(payload["appId"]))
        api_key_id = UUID(str(payload["apiKeyId"]))
    except (KeyError, TypeError, ValueError):
        raise AppRuntimeAuthError

    key_row = session.execute(
        select(rag_app_api_keys)
        .where(
            rag_app_api_keys.c.api_key_id == api_key_id,
            rag_app_api_keys.c.app_id == app_id,
        )
        .limit(1)
    ).mappings().first()
    if key_row is None or key_row["status"] != "active" or _is_expired(key_row["expires_at"], now):
        raise AppRuntimeAuthError

    app_row = session.execute(
        select(rag_apps)
        .where(
            rag_apps.c.app_id == app_id,
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


def _read_credential_context(session: Session, credential: str, now: datetime) -> tuple[RowMapping, RowMapping, RowMapping]:
    """兼容 App API Key 和短期 Embed Token 两种 Runtime 凭据。"""
    if credential.startswith(EMBED_TOKEN_PREFIX):
        return _read_embed_token_context(session, credential, now)
    return _read_key_context(session, credential, now)


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


def _runtime_limits(app_row: RowMapping) -> tuple[int | None, int | None, int | None]:
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
    max_concurrent = _positive_limit(limits.get("maxConcurrent"))
    return minute_limit, daily_quota, max_concurrent


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


def _count_running_invocations(session: Session, app_id: UUID) -> int:
    """统计当前应用仍处于 running 的调用，用于轻量并发保护。"""
    return session.execute(
        select(func.count())
        .select_from(app_invocations)
        .where(app_invocations.c.app_id == app_id, app_invocations.c.status == "running")
    ).scalar_one()


def _assert_runtime_quota(
    session: Session,
    app_row: RowMapping,
    key_row: RowMapping,
    request: AppRuntimeChatRequest,
    now: datetime,
    started_counter: float,
) -> None:
    """在创建 QARun 前执行应用级限流和日配额检查。"""
    minute_limit, daily_quota, _ = _runtime_limits(app_row)
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


def _assert_runtime_concurrency(
    session: Session,
    app_row: RowMapping,
    key_row: RowMapping,
    request: AppRuntimeChatRequest,
    now: datetime,
    started_counter: float,
) -> None:
    """在创建 running invocation 前检查应用级同时运行上限。"""
    _, _, max_concurrent = _runtime_limits(app_row)
    if max_concurrent is None:
        return
    if _count_running_invocations(session, app_row["app_id"]) < max_concurrent:
        return
    _insert_failed_invocation_for_known_app(
        session,
        app_row,
        key_row,
        request,
        now,
        started_counter,
        "RAG_APP_CONCURRENCY_EXCEEDED",
    )
    raise AppRuntimeConcurrencyExceededError("RAG_APP_CONCURRENCY_EXCEEDED")


def _resolve_runtime_context(
    session: Session,
    credential: str,
    request: AppRuntimeChatRequest,
    now: datetime,
    started_counter: float,
) -> _RuntimeContext:
    """完成鉴权、状态校验和 Revision/Actor 解析。"""
    key_row, app_row, kb_row = _read_credential_context(session, credential, now)
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
    _assert_runtime_concurrency(session, app_row, key_row, request, now, started_counter)
    try:
        revision_id = _read_revision_id(session, app_row, kb_row)
        actor = _read_runtime_actor(session, app_row, kb_row)
    except AppRuntimeConflictError as exc:
        error_code = str(exc) or "RAG_APP_RUNTIME_CONFLICT"
        _insert_failed_invocation_for_known_app(session, app_row, key_row, request, now, started_counter, error_code)
        raise
    return _RuntimeContext(app_row=app_row, key_row=key_row, kb_row=kb_row, revision_id=revision_id, actor=actor)


def _resolve_runtime_context_without_quota(
    session: Session,
    credential: str,
    now: datetime,
) -> _RuntimeContext:
    """为 Token 签发、反馈和 retrieve 解析上下文；这些操作不占用对话并发配额。"""
    key_row, app_row, kb_row = _read_credential_context(session, credential, now)
    if app_row["status"] != "active":
        raise AppRuntimeConflictError("RAG_APP_DISABLED")
    if kb_row["status"] == "disabled":
        raise AppRuntimeConflictError("KB_DISABLED")
    revision_id = _read_revision_id(session, app_row, kb_row)
    actor = _read_runtime_actor(session, app_row, kb_row)
    return _RuntimeContext(app_row=app_row, key_row=key_row, kb_row=kb_row, revision_id=revision_id, actor=actor)


def _build_provider_set():
    """构建 QA Run Provider 集合（延迟导入避免循环依赖）。"""
    from app.services.qa_providers import get_qa_run_providers
    return get_qa_run_providers()


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


def _insert_running_invocation(
    session: Session,
    context: _RuntimeContext,
    request: AppRuntimeChatRequest,
    started_at: datetime,
) -> UUID:
    """调用被接受后立即写入 running 审计记录，便于管理端监控进行中请求。"""
    invocation_id = uuid4()
    session.execute(
        insert(app_invocations).values(
            invocation_id=invocation_id,
            app_id=context.app_row["app_id"],
            api_key_id=context.key_row["api_key_id"],
            status="running",
            error_code=None,
            latency_ms=None,
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
    return invocation_id


def _finalize_invocation(
    session: Session,
    invocation_id: UUID,
    started_counter: float,
    status: str,
    error_code: str | None = None,
    conversation_id: UUID | None = None,
    message_id: UUID | None = None,
    qa_run_id: UUID | None = None,
    response_summary: dict | None = None,
) -> None:
    """将 running invocation 收口为最终状态，保留原始创建时间用于列表排序。"""
    latency_ms = int((perf_counter() - started_counter) * 1000)
    session.execute(
        update(app_invocations)
        .where(app_invocations.c.invocation_id == invocation_id)
        .values(
            conversation_id=conversation_id,
            message_id=message_id,
            qa_run_id=qa_run_id,
            status=status,
            error_code=error_code,
            latency_ms=latency_ms,
            response_summary=response_summary or {},
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
    credential: str,
    request: AppRuntimeChatRequest,
) -> AppRuntimeChatResponse:
    """执行 App Runtime blocking 对话，并复用现有 QARun 检索与权限过滤链路。"""
    started_at = datetime.now(UTC)
    started_counter = perf_counter()
    context = _resolve_runtime_context(session, credential, request, started_at, started_counter)
    invocation_id = _insert_running_invocation(session, context, request, started_at)
    try:
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
                    "scenarioType": (context.app_row["metadata"] or {}).get("scenario", {}).get("scenarioType"),
                }
            },
            ),
        )
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
        _finalize_invocation(
            session,
            invocation_id,
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
                "authType": "embedToken" if credential.startswith(EMBED_TOKEN_PREFIX) else "apiKey",
            },
        )
    except QARunCreateConflict:
        session.rollback()
        _finalize_invocation(session, invocation_id, started_counter, status="failed", error_code="QA_RUN_CONFLICT")
        session.commit()
        raise
    except AppRuntimeNotFoundError:
        session.rollback()
        _finalize_invocation(session, invocation_id, started_counter, status="failed", error_code="RESOURCE_NOT_FOUND")
        session.commit()
        raise
    except AppRuntimeConflictError as exc:
        session.rollback()
        _finalize_invocation(
            session,
            invocation_id,
            started_counter,
            status="failed",
            error_code=str(exc) or "APP_RUNTIME_CONFLICT",
        )
        session.commit()
        raise
    except Exception:
        session.rollback()
        _finalize_invocation(session, invocation_id, started_counter, status="failed", error_code="APP_RUNTIME_FAILED")
        session.commit()
        raise


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


def create_app_runtime_embed_token(
    session: Session,
    api_key: str,
    request: AppRuntimeEmbedTokenRequest,
) -> AppRuntimeEmbedTokenResponse:
    """通过长期 App API Key 签发短期 Embed Token，浏览器嵌入页只持有短期凭据。"""
    now = datetime.now(UTC)
    key_row, app_row, kb_row = _read_key_context(session, api_key, now)
    if app_row["status"] != "active":
        raise AppRuntimeConflictError("RAG_APP_DISABLED")
    if kb_row["status"] == "disabled":
        raise AppRuntimeConflictError("KB_DISABLED")
    expires_at = now + timedelta(seconds=request.ttlSeconds)
    payload = {
        "typ": "embed",
        "appId": str(app_row["app_id"]),
        "apiKeyId": str(key_row["api_key_id"]),
        "exp": int(expires_at.timestamp()),
    }
    if request.allowedOrigin:
        payload["origin"] = request.allowedOrigin
    if request.endUserId:
        payload["endUserId"] = request.endUserId
    session.execute(
        update(rag_app_api_keys)
        .where(rag_app_api_keys.c.api_key_id == key_row["api_key_id"])
        .values(last_used_at=now)
    )
    session.commit()
    return AppRuntimeEmbedTokenResponse(
        embedToken=_encode_embed_token(payload),
        appId=str(app_row["app_id"]),
        expiresAt=expires_at.isoformat(),
    )


def _summarize_evidence_content(content: str | None, max_length: int = 240) -> str:
    """返回安全证据摘要，避免 retrieve 暴露完整 Chunk 正文。"""
    normalized = " ".join((content or "").split())
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length].rstrip()}..."


def retrieve_app_runtime_evidence(
    session: Session,
    credential: str,
    request: AppRuntimeRetrieveRequest,
) -> AppRuntimeRetrieveResponse:
    """从当前 App 所属知识库读取授权证据摘要。优先使用向量语义检索，回退到 ILIKE。"""
    now = datetime.now(UTC)
    context = _resolve_runtime_context_without_quota(session, credential, now)

    settings = get_settings()
    q = request.query.strip()
    use_vector = settings.dense_retrieval_provider != "local" and bool(q)
    retrieval_mode = "vector"

    if use_vector:
        # 向量语义检索路径（失败时静默回退到 ILIKE）
        try:
            provider_set = _build_provider_set()
            embedding = provider_set.embedding.embed_query(q)
            candidates = provider_set.dense.retrieve(
                context.kb_row["kb_id"], q, embedding, request.topK,
            )
            chunk_ids = [c.chunk_id for c in candidates]
            if chunk_ids:
                rows = session.execute(
                    select(chunks.c.chunk_id, chunks.c.chunk_index, chunks.c.content, chunks.c.metadata)
                    .where(chunks.c.chunk_id.in_(chunk_ids), chunks.c.status == "active")
                ).mappings().all()
                row_map = {str(r["chunk_id"]): r for r in rows}
                ordered_rows = [row_map[cid] for cid in chunk_ids if cid in row_map]
            else:
                ordered_rows = []
        except Exception:
            use_vector = False

    if not use_vector:
        # ILIKE 回退路径
        retrieval_mode = "ilike"
        stmt = (
            select(chunks.c.chunk_id, chunks.c.chunk_index, chunks.c.content, chunks.c.metadata)
            .where(
                chunks.c.kb_id == context.kb_row["kb_id"],
                chunks.c.status == "active",
            )
        )
        if q:
            stmt = stmt.where(chunks.c.content.ilike(f"%{q}%"))
        stmt = stmt.order_by(chunks.c.chunk_index.asc()).limit(request.topK)
        ordered_rows = session.execute(stmt).mappings().all()

    evidences = [
        AppRuntimeRetrievedEvidenceDTO(
            evidenceId=str(uuid4()),
            chunkId=str(row["chunk_id"]),
            label=f"片段 {index}",
            summary=_summarize_evidence_content(row["content"]),
            locationSnapshot={
                "chunkId": str(row["chunk_id"]),
                "chunkIndex": row["chunk_index"],
                "source": "milvus" if use_vector else "postgres_chunks",
            },
        )
        for index, row in enumerate(ordered_rows, start=1)
    ]
    return AppRuntimeRetrieveResponse(
        appId=str(context.app_row["app_id"]),
        kbId=str(context.kb_row["kb_id"]),
        evidences=evidences,
        metadata={
            "queryLength": len(request.query),
            "topK": request.topK,
            "retrievalMode": retrieval_mode,
            "authType": "embedToken" if credential.startswith(EMBED_TOKEN_PREFIX) else "apiKey",
        },
    )


def _scenario_payload(app_row: RowMapping) -> dict:
    """读取应用场景元数据，缺失时返回空结构以兼容旧应用。"""
    metadata = app_row["metadata"] or {}
    scenario = metadata.get("scenario") if isinstance(metadata, dict) else None
    return scenario if isinstance(scenario, dict) else {}


def _require_employee_training_app(context: _RuntimeContext) -> dict:
    """限制培训结构化接口只服务员工培训助手，避免普通问答应用误用。"""
    scenario = _scenario_payload(context.app_row)
    if scenario.get("scenarioType") != "employee_training":
        raise AppRuntimeConflictError("RAG_APP_SCENARIO_NOT_EMPLOYEE_TRAINING")
    return scenario


def _training_question_count(request: AppRuntimeStructuredRunRequest, scenario: dict) -> int:
    """从请求或场景默认值解析题目数量，并限制在首版支持范围内。"""
    scenario_config = scenario.get("scenarioConfig") if isinstance(scenario.get("scenarioConfig"), dict) else {}
    value = request.questionCount if request.questionCount is not None else scenario_config.get("questionCount", 5)
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = 5
    return min(max(count, 1), 10)


def _training_passing_score(scenario: dict) -> int:
    """读取及格分，非法配置回落为 80 分。"""
    scenario_config = scenario.get("scenarioConfig") if isinstance(scenario.get("scenarioConfig"), dict) else {}
    try:
        score = int(scenario_config.get("passingScore", 80))
    except (TypeError, ValueError):
        score = 80
    return min(max(score, 0), 100)


def _build_training_quiz(topic: str, answer: str, question_count: int, difficulty: str | None) -> dict:
    """基于 QARun 讲解摘要生成可评分的结构化测验（当前为模板占位实现，题目为固定选项）。"""
    base_answer = "完成培训并通过测验"
    questions = []
    for index in range(1, question_count + 1):
        correct_answer = base_answer if index == 1 else f"{topic}要点 {index}"
        questions.append(
            {
                "questionId": f"q{index}",
                "type": "single_choice",
                "stem": f"{topic}培训测验 {index}：根据材料，以下哪项最符合要求？",
                "options": [
                    correct_answer,
                    "跳过学习直接上岗",
                    "仅口头确认无需记录",
                    "由他人代为完成",
                ],
                "correctAnswer": correct_answer,
                "explanation": f"依据培训材料，{answer[:80] or topic}",
            }
        )
    return {
        "topic": topic,
        "difficulty": difficulty or "normal",
        "questionCount": question_count,
        "questions": questions,
    }


def _build_structured_output(request: AppRuntimeStructuredRunRequest, scenario: dict, answer: str) -> dict:
    """将 QARun 回答转换为培训讲解或测验结构化输出。"""
    if request.action == "training_explain":
        return {
            "explanation": {
                "topic": request.topic,
                "summary": answer,
                "keyPoints": [item.strip() for item in answer.replace("。", "\n").splitlines() if item.strip()][:5],
            }
        }
    return {
        "quiz": _build_training_quiz(
            request.topic,
            answer,
            _training_question_count(request, scenario),
            request.difficulty,
        )
    }


def create_app_runtime_structured_run(
    session: Session,
    credential: str,
    request: AppRuntimeStructuredRunRequest,
) -> AppRuntimeStructuredRunResponse:
    """执行培训讲解或测验生成，并将结构化输出写入 AppMessage metadata。"""
    now = datetime.now(UTC)
    context = _resolve_runtime_context_without_quota(session, credential, now)
    scenario = _require_employee_training_app(context)
    conversation_row = _get_or_create_conversation(
        session,
        context.app_row["app_id"],
        AppRuntimeChatRequest(
            query=request.topic,
            conversationId=request.conversationId,
            endUserId=request.endUserId,
            inputs=request.inputs,
        ),
        now,
    )
    _insert_message(
        session,
        conversation_row["conversation_id"],
        "user",
        request.topic,
        "success",
        now,
        metadata={"structuredAction": request.action, "hasInputs": bool(request.inputs)},
    )
    qa_response = create_qa_run(
        session,
        context.actor,
        context.kb_row["kb_id"],
        QARunCreateRequest(
            query=f"{request.topic} 培训{('测验生成' if request.action == 'training_quiz_generate' else '讲解')}",
            configRevisionId=context.revision_id,
            overrideParams={
                "appRuntime": {
                    "appId": str(context.app_row["app_id"]),
                    "conversationId": str(conversation_row["conversation_id"]),
                    "scenarioType": "employee_training",
                    "structuredAction": request.action,
                }
            },
        ),
    )
    if qa_response is None:
        raise AppRuntimeConflictError("RAG_APP_KB_NOT_FOUND")
    detail = get_qa_run_detail(session, context.actor, context.kb_row["kb_id"], UUID(qa_response.runId), include_trace=False, include_candidates=False)
    if detail is None:
        raise AppRuntimeConflictError("QA_RUN_NOT_FOUND")

    output = _build_structured_output(request, scenario, detail.answer or "")
    message_row = _insert_message(
        session,
        conversation_row["conversation_id"],
        "assistant",
        json.dumps(output, ensure_ascii=False),
        "success" if detail.status in {"success", "partial"} else "failed",
        datetime.now(UTC),
        qa_run_id=UUID(detail.runId),
        metadata={
            "trainingStructuredRun": {
                "action": request.action,
                "topic": request.topic,
                "runStatus": detail.status,
                **output,
            }
        },
    )
    session.execute(
        update(app_conversations)
        .where(app_conversations.c.conversation_id == conversation_row["conversation_id"])
        .values(updated_at=datetime.now(UTC))
    )
    session.execute(
        update(rag_app_api_keys)
        .where(rag_app_api_keys.c.api_key_id == context.key_row["api_key_id"])
        .values(last_used_at=now)
    )
    session.commit()
    return AppRuntimeStructuredRunResponse(
        appId=str(context.app_row["app_id"]),
        conversationId=str(conversation_row["conversation_id"]),
        messageId=str(message_row["message_id"]),
        runId=detail.runId,
        action=request.action,
        output=output,
        metadata={"kbId": str(context.kb_row["kb_id"]), "configRevisionId": str(context.revision_id)},
    )


def _read_training_quiz_message(session: Session, context: _RuntimeContext, request: AppRuntimeTrainingQuizSubmissionRequest) -> RowMapping:
    """读取当前 App 内的测验消息，禁止跨应用或跨会话提交答案。"""
    row = session.execute(
        select(app_messages)
        .select_from(app_messages.join(app_conversations, app_messages.c.conversation_id == app_conversations.c.conversation_id))
        .where(
            app_messages.c.message_id == request.quizMessageId,
            app_messages.c.conversation_id == request.conversationId,
            app_messages.c.role == "assistant",
            app_conversations.c.app_id == context.app_row["app_id"],
        )
        .limit(1)
    ).mappings().first()
    if row is None:
        raise AppRuntimeNotFoundError
    metadata = row["metadata"] or {}
    structured_run = metadata.get("trainingStructuredRun") if isinstance(metadata, dict) else None
    if not isinstance(structured_run, dict) or structured_run.get("action") != "training_quiz_generate":
        raise AppRuntimeConflictError("TRAINING_QUIZ_NOT_FOUND")
    return row


def _score_training_answers(
    quiz: dict,
    request: AppRuntimeTrainingQuizSubmissionRequest,
) -> tuple[int, list[AppRuntimeTrainingQuestionResultDTO]]:
    """按测验 metadata 中的标准答案评分，首版采用精确匹配。"""
    questions = quiz.get("questions") if isinstance(quiz, dict) else []
    question_by_id = {str(item.get("questionId")): item for item in questions if isinstance(item, dict)}
    results: list[AppRuntimeTrainingQuestionResultDTO] = []
    answer_by_id = {item.questionId: item.answer for item in request.answers}
    for question_id, question in question_by_id.items():
        answer = answer_by_id.get(question_id, "")
        correct_answer = str(question.get("correctAnswer") or "")
        is_correct = answer.strip() == correct_answer.strip()
        results.append(
            AppRuntimeTrainingQuestionResultDTO(
                questionId=question_id,
                answer=answer,
                correctAnswer=correct_answer,
                isCorrect=is_correct,
                explanation=str(question.get("explanation") or "请回到培训材料复习相关要点。"),
            )
        )
    correct_count = sum(1 for item in results if item.isCorrect)
    score = int(round((correct_count / len(results)) * 100)) if results else 0
    return score, results


def submit_app_runtime_training_quiz(
    session: Session,
    credential: str,
    request: AppRuntimeTrainingQuizSubmissionRequest,
) -> AppRuntimeTrainingQuizSubmissionResponse:
    """提交培训测验答案、写入训练结果，并复用测验生成时的 QARun 作为追溯锚点。"""
    now = datetime.now(UTC)
    context = _resolve_runtime_context_without_quota(session, credential, now)
    scenario = _require_employee_training_app(context)
    quiz_message = _read_training_quiz_message(session, context, request)
    structured_run = (quiz_message["metadata"] or {})["trainingStructuredRun"]
    quiz = structured_run["quiz"]
    score, results = _score_training_answers(quiz, request)
    passing_score = _training_passing_score(scenario)
    passed = score >= passing_score

    _insert_message(
        session,
        request.conversationId,
        "user",
        json.dumps({"answers": [item.model_dump() for item in request.answers]}, ensure_ascii=False),
        "success",
        now,
        metadata={"trainingSubmission": {"quizMessageId": str(request.quizMessageId)}},
    )
    training_result = {
        "quizMessageId": str(request.quizMessageId),
        "score": score,
        "passed": passed,
        "passingScore": passing_score,
        "results": [item.model_dump() for item in results],
        "submittedAt": now.isoformat(),
    }
    message_row = _insert_message(
        session,
        request.conversationId,
        "assistant",
        f"训练得分 {score}，{'已通过' if passed else '未通过'}。",
        "success",
        now,
        qa_run_id=quiz_message["qa_run_id"],
        metadata={"trainingResult": training_result},
    )
    session.execute(update(app_conversations).where(app_conversations.c.conversation_id == request.conversationId).values(updated_at=now))
    session.execute(update(rag_app_api_keys).where(rag_app_api_keys.c.api_key_id == context.key_row["api_key_id"]).values(last_used_at=now))
    session.commit()
    return AppRuntimeTrainingQuizSubmissionResponse(
        conversationId=str(request.conversationId),
        messageId=str(message_row["message_id"]),
        quizMessageId=str(request.quizMessageId),
        runId=str(quiz_message["qa_run_id"]),
        score=score,
        passed=passed,
        passingScore=passing_score,
        results=results,
        metadata={"appId": str(context.app_row["app_id"]), "kbId": str(context.kb_row["kb_id"])},
    )


def _normalize_feedback_status(value: str) -> str:
    """兼容外部 camelCase 和内部 snake_case 反馈枚举。"""
    return FEEDBACK_STATUS_MAP.get(value, value)


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
    credential: str,
    message_id: UUID,
    request: AppRuntimeFeedbackRequest,
) -> AppRuntimeFeedbackResponse:
    """回流外部反馈到 QARun，并按需生成 EvaluationSample。"""
    now = datetime.now(UTC)
    context = _resolve_runtime_context_without_quota(session, credential, now)
    message_row, run_row = _read_feedback_message(session, context.app_row["app_id"], message_id)
    feedback_status = _normalize_feedback_status(request.feedbackStatus)
    try:
        require_active_dict_item(session, "feedback_status", feedback_status, "feedbackStatus")
    except ValueError as exc:
        raise AppRuntimeConflictError("INVALID_FEEDBACK_STATUS") from exc
    metrics = dict(run_row["metrics"] or {})
    if request.failureType:
        metrics["failureType"] = request.failureType
    else:
        metrics.pop("failureType", None)

    actor_id = UUID(context.actor.user.userId)
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
