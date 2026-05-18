from datetime import UTC, datetime
from hashlib import sha256
import secrets
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, delete, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.rag_app import (
    AppConversationDetailDTO,
    AppInvocationDTO,
    AppInvocationStatsDTO,
    AppMessageDTO,
    RagAppApiKeyCreateRequest,
    RagAppApiKeyCreateResponse,
    RagAppApiKeyDTO,
    RagAppCreateRequest,
    RagAppDTO,
    RagAppUpdateRequest,
)
from app.services.audit_service import write_audit_log
from app.services.permission_service import has_kb_permission, kb_visibility_condition
from app.tables import (
    app_conversations,
    app_invocations,
    app_messages,
    config_revisions,
    knowledge_bases,
    rag_app_api_keys,
    rag_apps,
)


class RagAppPermissionError(Exception):
    """当前用户缺少 RAG App 管理权限。"""


class RagAppNotFoundError(Exception):
    """RAG App 不存在或当前用户不可见。"""


class RagAppApiKeyNotFoundError(Exception):
    """App API Key 不存在或不属于当前应用。"""


class RagAppConflictError(ValueError):
    """RAG App 管理操作遇到业务状态冲突。"""


def _to_app_dto(row: RowMapping) -> RagAppDTO:
    """将 RAG App 数据库行转换为管理端 DTO。"""
    return RagAppDTO(
        appId=str(row["app_id"]),
        kbId=str(row["kb_id"]),
        defaultConfigRevisionId=(
            str(row["default_config_revision_id"]) if row["default_config_revision_id"] else None
        ),
        name=row["name"],
        description=row["description"],
        status=row["status"],
        outputPolicy=row["output_policy"] or {},
        metadata=row["metadata"] or {},
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_api_key_dto(row: RowMapping) -> RagAppApiKeyDTO:
    """转换 API Key 摘要；不会包含明文 key。"""
    return RagAppApiKeyDTO(
        apiKeyId=str(row["api_key_id"]),
        appId=str(row["app_id"]),
        keyPrefix=row["key_prefix"],
        status=row["status"],
        expiresAt=row["expires_at"].isoformat() if row["expires_at"] else None,
        lastUsedAt=row["last_used_at"].isoformat() if row["last_used_at"] else None,
        createdAt=row["created_at"].isoformat(),
        revokedAt=row["revoked_at"].isoformat() if row["revoked_at"] else None,
    )


def _to_invocation_dto(row: RowMapping) -> AppInvocationDTO:
    """转换 App Runtime 调用审计摘要。"""
    return AppInvocationDTO(
        invocationId=str(row["invocation_id"]),
        appId=str(row["app_id"]),
        apiKeyId=str(row["api_key_id"]) if row["api_key_id"] else None,
        conversationId=str(row["conversation_id"]) if row["conversation_id"] else None,
        messageId=str(row["message_id"]) if row["message_id"] else None,
        qaRunId=str(row["qa_run_id"]) if row["qa_run_id"] else None,
        status=row["status"],
        errorCode=row["error_code"],
        latencyMs=row["latency_ms"],
        requestSummary=row["request_summary"] or {},
        responseSummary=row["response_summary"] or {},
        createdAt=row["created_at"].isoformat(),
    )


def _to_message_dto(row: RowMapping) -> AppMessageDTO:
    """转换 App 会话消息，保留 message 与 QARun 的追溯关系。"""
    return AppMessageDTO(
        messageId=str(row["message_id"]),
        conversationId=str(row["conversation_id"]),
        role=row["role"],
        content=row["content"],
        qaRunId=str(row["qa_run_id"]) if row["qa_run_id"] else None,
        status=row["status"],
        metadata=row["metadata"] or {},
        createdAt=row["created_at"].isoformat(),
    )


def _to_conversation_detail_dto(
    conversation_row: RowMapping,
    message_rows: list[RowMapping],
) -> AppConversationDetailDTO:
    """组合会话与消息详情，供 P13 只读展示。"""
    return AppConversationDetailDTO(
        conversationId=str(conversation_row["conversation_id"]),
        appId=str(conversation_row["app_id"]),
        endUserId=conversation_row["end_user_id"],
        status=conversation_row["status"],
        metadata=conversation_row["metadata"] or {},
        createdAt=conversation_row["created_at"].isoformat(),
        updatedAt=conversation_row["updated_at"].isoformat(),
        messages=[_to_message_dto(row) for row in message_rows],
    )


def _visible_app_condition(current_user: CurrentUserResponse):
    """RAG App 可见性跟随绑定知识库可见性。"""
    return (
        rag_apps.c.deleted_at.is_(None)
        & (rag_apps.c.kb_id == knowledge_bases.c.kb_id)
        & kb_visibility_condition(current_user)
    )


def _read_visible_app_row(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
) -> RowMapping:
    """读取当前用户可见的 RAG App；不可见按不存在处理。"""
    row = session.execute(
        select(rag_apps)
        .select_from(rag_apps.join(knowledge_bases, rag_apps.c.kb_id == knowledge_bases.c.kb_id))
        .where(_visible_app_condition(current_user), rag_apps.c.app_id == app_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        raise RagAppNotFoundError
    return row


def _ensure_app_manage_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> None:
    """确认当前用户可管理 KB 下的 RAG App；当前兼容 kb.manage。"""
    if current_user.user.platformRole == "platform_admin":
        return
    if has_kb_permission(session, current_user, kb_id, "kb.app.manage"):
        return
    if has_kb_permission(session, current_user, kb_id, "kb.manage"):
        return
    raise RagAppPermissionError


def _read_writable_kb_row(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping:
    """读取可见且可写的知识库行，供创建和配置绑定校验复用。"""
    row = session.execute(
        select(knowledge_bases)
        .where(kb_visibility_condition(current_user), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        raise RagAppNotFoundError
    if row["status"] == "disabled":
        raise RagAppConflictError("KB_DISABLED")
    _ensure_app_manage_permission(session, current_user, kb_id)
    return row


def _read_manageable_kb_row(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping:
    """读取可见且当前用户可管理的知识库；允许停用 KB 下的收口动作。"""
    row = session.execute(
        select(knowledge_bases)
        .where(kb_visibility_condition(current_user), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        raise RagAppNotFoundError
    _ensure_app_manage_permission(session, current_user, kb_id)
    return row


def _ensure_kb_allows_app_update(
    kb_row: RowMapping,
    requested_fields: set[str],
    request: RagAppUpdateRequest,
) -> None:
    """停用 KB 下只允许停用或归档应用，避免无法收口的状态死锁。"""
    if kb_row["status"] != "disabled":
        return
    if requested_fields == {"status"} and request.status in {"disabled", "archived"}:
        return
    raise RagAppConflictError("KB_DISABLED")


def _ensure_runnable_revision(
    session: Session,
    kb_id: UUID,
    config_revision_id: UUID | None,
) -> None:
    """确认指定 Revision 属于当前知识库且可运行。"""
    if config_revision_id is None:
        return
    row = session.execute(
        select(config_revisions.c.config_revision_id, config_revisions.c.status)
        .where(
            config_revisions.c.kb_id == kb_id,
            config_revisions.c.config_revision_id == config_revision_id,
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if row is None or row["status"] in {"draft", "invalid"}:
        raise RagAppConflictError("RAG_APP_NO_RUNNABLE_REVISION")


def list_rag_apps(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int,
    page_size: int,
    keyword: str | None = None,
    kb_id: UUID | None = None,
    status_filter: str | None = None,
) -> PageResponse[RagAppDTO]:
    """分页查询当前用户可见的 RAG App。"""
    condition = _visible_app_condition(current_user)
    if kb_id is not None:
        condition = condition & (rag_apps.c.kb_id == kb_id)
    if status_filter:
        condition = condition & (rag_apps.c.status == status_filter)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            rag_apps.c.name.ilike(keyword_pattern),
            rag_apps.c.description.ilike(keyword_pattern),
        )

    base_from = rag_apps.join(knowledge_bases, rag_apps.c.kb_id == knowledge_bases.c.kb_id)
    total = session.execute(select(func.count()).select_from(base_from).where(condition)).scalar_one()
    rows = session.execute(
        select(rag_apps)
        .select_from(base_from)
        .where(condition)
        .order_by(rag_apps.c.updated_at.desc(), rag_apps.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_app_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_rag_app(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
) -> RagAppDTO:
    """读取单个 RAG App 详情。"""
    return _to_app_dto(_read_visible_app_row(session, current_user, app_id))


def create_rag_app(
    session: Session,
    current_user: CurrentUserResponse,
    request: RagAppCreateRequest,
) -> RagAppDTO:
    """创建 RAG App，只保存应用与 KB/Revision 的绑定关系。"""
    _read_writable_kb_row(session, current_user, request.kbId)
    _ensure_runnable_revision(session, request.kbId, request.defaultConfigRevisionId)

    app_id = uuid4()
    actor_id = UUID(current_user.user.userId)
    now = datetime.now(UTC)
    row = session.execute(
        insert(rag_apps)
        .values(
            app_id=app_id,
            kb_id=request.kbId,
            default_config_revision_id=request.defaultConfigRevisionId,
            name=request.name,
            description=request.description,
            status="active",
            output_policy=request.outputPolicy or {},
            metadata=request.metadata or {},
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
        .returning(rag_apps)
    ).mappings().one()
    write_audit_log(
        session,
        current_user,
        "rag_app.create",
        "rag_app",
        app_id,
        kb_id=request.kbId,
        detail={"name": request.name},
    )
    session.commit()
    return _to_app_dto(row)


def update_rag_app(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
    request: RagAppUpdateRequest,
) -> RagAppDTO:
    """更新 RAG App 基础信息和默认配置绑定。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    requested_fields = request.model_fields_set
    kb_row = _read_manageable_kb_row(session, current_user, app_row["kb_id"])
    _ensure_kb_allows_app_update(kb_row, requested_fields, request)
    if "defaultConfigRevisionId" in requested_fields:
        _ensure_runnable_revision(session, app_row["kb_id"], request.defaultConfigRevisionId)

    update_values: dict[str, object] = {
        "updated_at": func.now(),
        "updated_by": UUID(current_user.user.userId),
    }
    if "name" in requested_fields and request.name is not None:
        update_values["name"] = request.name
    if "description" in requested_fields:
        update_values["description"] = request.description
    if "defaultConfigRevisionId" in requested_fields:
        update_values["default_config_revision_id"] = request.defaultConfigRevisionId
    if "outputPolicy" in requested_fields and request.outputPolicy is not None:
        update_values["output_policy"] = request.outputPolicy
    if "metadata" in requested_fields and request.metadata is not None:
        update_values["metadata"] = request.metadata
    if "status" in requested_fields and request.status is not None:
        update_values["status"] = request.status

    row = session.execute(
        update(rag_apps)
        .where(rag_apps.c.app_id == app_id)
        .values(**update_values)
        .returning(rag_apps)
    ).mappings().one()
    write_audit_log(
        session,
        current_user,
        "rag_app.update",
        "rag_app",
        app_id,
        kb_id=app_row["kb_id"],
        detail={"updatedFields": sorted(requested_fields)},
    )
    session.commit()
    return _to_app_dto(row)


def delete_rag_app(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
) -> None:
    """逻辑删除 RAG App，使其从管理列表和 Runtime 鉴权中消失。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    _ensure_app_manage_permission(session, current_user, app_row["kb_id"])
    actor_id = UUID(current_user.user.userId)
    now = datetime.now(UTC)
    session.execute(
        update(rag_apps)
        .where(rag_apps.c.app_id == app_id, rag_apps.c.deleted_at.is_(None))
        .values(
            status="archived",
            deleted_at=now,
            deleted_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
    )
    write_audit_log(
        session,
        current_user,
        "rag_app.delete",
        "rag_app",
        app_id,
        kb_id=app_row["kb_id"],
        detail={"name": app_row["name"]},
    )
    session.commit()


def list_rag_app_api_keys(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
) -> list[RagAppApiKeyDTO]:
    """列出应用 API Key 摘要。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    _ensure_app_manage_permission(session, current_user, app_row["kb_id"])
    rows = session.execute(
        select(rag_app_api_keys)
        .where(rag_app_api_keys.c.app_id == app_id, rag_app_api_keys.c.status == "active")
        .order_by(rag_app_api_keys.c.created_at.desc())
    ).mappings()
    return [_to_api_key_dto(row) for row in rows]


def _generate_plain_api_key() -> str:
    """生成带固定前缀的 App API Key 明文。"""
    return f"rlak_{secrets.token_urlsafe(32)}"


def create_rag_app_api_key(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
    request: RagAppApiKeyCreateRequest,
) -> RagAppApiKeyCreateResponse:
    """生成应用级 API Key；明文只通过本响应返回一次。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    _ensure_app_manage_permission(session, current_user, app_row["kb_id"])

    plain_key = _generate_plain_api_key()
    key_hash = sha256(plain_key.encode("utf-8")).hexdigest()
    key_prefix = plain_key[:16]
    api_key_id = uuid4()
    actor_id = UUID(current_user.user.userId)
    row = session.execute(
        insert(rag_app_api_keys)
        .values(
            api_key_id=api_key_id,
            app_id=app_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            status="active",
            expires_at=request.expiresAt,
            created_by=actor_id,
        )
        .returning(rag_app_api_keys)
    ).mappings().one()
    write_audit_log(
        session,
        current_user,
        "rag_app_api_key.create",
        "rag_app_api_key",
        api_key_id,
        kb_id=app_row["kb_id"],
        detail={"appId": str(app_id), "keyPrefix": key_prefix},
    )
    session.commit()
    return RagAppApiKeyCreateResponse(apiKey=plain_key, item=_to_api_key_dto(row))


def delete_rag_app_api_key(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
    api_key_id: UUID,
) -> None:
    """物理删除应用 API Key，并解除调用审计中的 Key 外键引用。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    _ensure_app_manage_permission(session, current_user, app_row["kb_id"])
    key_row = session.execute(
        select(rag_app_api_keys)
        .where(
            rag_app_api_keys.c.app_id == app_id,
            rag_app_api_keys.c.api_key_id == api_key_id,
        )
    ).mappings().first()
    if key_row is None:
        session.rollback()
        raise RagAppApiKeyNotFoundError
    session.execute(
        update(app_invocations)
        .where(app_invocations.c.api_key_id == api_key_id)
        .values(api_key_id=None)
    )
    session.execute(
        delete(rag_app_api_keys).where(
            rag_app_api_keys.c.app_id == app_id,
            rag_app_api_keys.c.api_key_id == api_key_id,
        )
    )
    write_audit_log(
        session,
        current_user,
        "rag_app_api_key.delete",
        "rag_app_api_key",
        api_key_id,
        kb_id=app_row["kb_id"],
        detail={"appId": str(app_id), "keyPrefix": key_row["key_prefix"]},
    )
    session.commit()


def list_rag_app_invocations(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
    page_no: int,
    page_size: int,
    status_filter: str | None = None,
) -> PageResponse[AppInvocationDTO]:
    """分页查看应用调用审计摘要。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    _ensure_app_manage_permission(session, current_user, app_row["kb_id"])
    condition = app_invocations.c.app_id == app_id
    if status_filter:
        condition = condition & (app_invocations.c.status == status_filter)

    total = session.execute(select(func.count()).select_from(app_invocations).where(condition)).scalar_one()
    rows = session.execute(
        select(app_invocations)
        .where(condition)
        .order_by(app_invocations.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_invocation_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_rag_app_invocation_stats(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
) -> AppInvocationStatsDTO:
    """按应用聚合 Runtime 调用量、失败率、延迟和无证据率。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    _ensure_app_manage_permission(session, current_user, app_row["kb_id"])
    rows = list(session.execute(select(app_invocations).where(app_invocations.c.app_id == app_id)).mappings())
    total = len(rows)
    running_count = sum(1 for row in rows if row["status"] == "running")
    success_count = sum(1 for row in rows if row["status"] == "success")
    failed_count = sum(1 for row in rows if row["status"] == "failed")
    quota_count = sum(1 for row in rows if row["error_code"] == "RAG_APP_QUOTA_EXCEEDED")
    concurrency_count = sum(1 for row in rows if row["error_code"] == "RAG_APP_CONCURRENCY_EXCEEDED")
    latencies = [row["latency_ms"] for row in rows if row["latency_ms"] is not None]
    no_evidence_count = 0
    for row in rows:
        response_summary = row["response_summary"] or {}
        if row["status"] == "success" and response_summary.get("citationCount") == 0:
            no_evidence_count += 1
    return AppInvocationStatsDTO(
        appId=str(app_id),
        totalInvocations=total,
        runningInvocations=running_count,
        successInvocations=success_count,
        failedInvocations=failed_count,
        quotaExceededInvocations=quota_count,
        concurrencyExceededInvocations=concurrency_count,
        noEvidenceInvocations=no_evidence_count,
        averageLatencyMs=int(sum(latencies) / len(latencies)) if latencies else None,
        failureRate=round(failed_count / total, 4) if total else 0,
        noEvidenceRate=round(no_evidence_count / success_count, 4) if success_count else 0,
    )


def get_rag_app_conversation_detail(
    session: Session,
    current_user: CurrentUserResponse,
    app_id: UUID,
    conversation_id: UUID,
) -> AppConversationDetailDTO:
    """读取单个 App 会话和消息时间线；会话必须属于指定应用。"""
    app_row = _read_visible_app_row(session, current_user, app_id)
    _ensure_app_manage_permission(session, current_user, app_row["kb_id"])
    conversation_row = session.execute(
        select(app_conversations)
        .where(
            app_conversations.c.app_id == app_id,
            app_conversations.c.conversation_id == conversation_id,
        )
        .limit(1)
    ).mappings().first()
    if conversation_row is None:
        raise RagAppNotFoundError
    message_rows = list(
        session.execute(
            select(app_messages)
            .where(app_messages.c.conversation_id == conversation_id)
            .order_by(app_messages.c.created_at.asc(), app_messages.c.message_id.asc())
        ).mappings()
    )
    return _to_conversation_detail_dto(conversation_row, message_rows)
