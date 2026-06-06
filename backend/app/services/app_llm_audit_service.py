"""三方 LLM 能力调用的统一审计服务。

该服务复用 App Runtime 的 conversation/message/invocation 三张表，
让非聊天类外部 LLM 接口也能进入 P13 调用记录和会话回放。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.tables import app_conversations, app_invocations, app_messages, rag_app_api_keys


@dataclass(frozen=True)
class AppLlmInvocationAudit:
    """一次外部 LLM 调用审计的运行态标识。"""

    invocation_id: UUID
    conversation_id: UUID
    user_message_id: UUID
    app_id: UUID
    api_key_id: UUID
    operation: str
    started_counter: float


def _json_content(value: Any) -> str:
    """将审计摘要序列化为可读 JSON，避免保存完整 Prompt 或证据正文。"""
    return json.dumps(value, ensure_ascii=False, default=str)


def begin_app_llm_invocation(
    session: Session,
    context: Any,
    *,
    endpoint: str,
    operation: str,
    skill_name: str,
    input_summary: dict[str, Any],
    user_content: dict[str, Any],
    conversation_id: UUID | None = None,
    user_message_id: UUID | None = None,
) -> AppLlmInvocationAudit:
    """写入外部 LLM 调用的会话、用户消息和 running invocation。"""
    now = datetime.now(UTC)
    should_insert_conversation = conversation_id is None
    should_insert_user_message = user_message_id is None
    conversation_id = conversation_id or new_id()
    user_message_id = user_message_id or new_id()
    invocation_id = new_id()
    started_counter = perf_counter()

    if should_insert_conversation:
        session.execute(
            insert(app_conversations).values(
                conversation_id=conversation_id,
                app_id=context.app_row["app_id"],
                end_user_id=None,
                status="active",
                metadata={
                    "source": "external_llm_api",
                    "operation": operation,
                    "skillName": skill_name,
                    "endpoint": endpoint,
                },
                created_at=now,
                updated_at=now,
            )
        )
    if should_insert_user_message:
        session.execute(
            insert(app_messages).values(
                message_id=user_message_id,
                conversation_id=conversation_id,
                role="user",
                content=_json_content(user_content),
                qa_run_id=None,
                status="success",
                metadata={
                    "source": "external_llm_api",
                    "operation": operation,
                    "skillName": skill_name,
                    "endpoint": endpoint,
                },
                created_at=now,
            )
        )
    session.execute(
        insert(app_invocations).values(
            invocation_id=invocation_id,
            app_id=context.app_row["app_id"],
            api_key_id=context.key_row["api_key_id"],
            conversation_id=conversation_id,
            message_id=None,
            qa_run_id=None,
            status="running",
            error_code=None,
            latency_ms=None,
            request_summary={
                "endpoint": endpoint,
                "operation": operation,
                "skillName": skill_name,
                **input_summary,
            },
            response_summary={},
            created_at=now,
        )
    )
    session.commit()
    return AppLlmInvocationAudit(
        invocation_id=invocation_id,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        app_id=context.app_row["app_id"],
        api_key_id=context.key_row["api_key_id"],
        operation=operation,
        started_counter=started_counter,
    )


def finish_app_llm_invocation(
    session: Session,
    audit: AppLlmInvocationAudit,
    *,
    status: str,
    assistant_content: dict[str, Any],
    response_summary: dict[str, Any],
    error_code: str | None = None,
    assistant_message_id: UUID | None = None,
) -> UUID:
    """收口外部 LLM 调用审计，写入助手消息并更新 invocation 最终状态。"""
    now = datetime.now(UTC)
    should_insert_assistant_message = assistant_message_id is None
    assistant_message_id = assistant_message_id or new_id()
    message_status = "success" if status == "success" else "failed"
    if should_insert_assistant_message:
        session.execute(
            insert(app_messages).values(
                message_id=assistant_message_id,
                conversation_id=audit.conversation_id,
                role="assistant",
                content=_json_content(assistant_content),
                qa_run_id=None,
                status=message_status,
                metadata={
                    "source": "external_llm_api",
                    "operation": audit.operation,
                },
                created_at=now,
            )
        )
    session.execute(
        update(app_invocations)
        .where(app_invocations.c.invocation_id == audit.invocation_id)
        .values(
            message_id=assistant_message_id,
            status=status,
            error_code=error_code,
            latency_ms=int((perf_counter() - audit.started_counter) * 1000),
            response_summary=response_summary,
        )
    )
    session.execute(
        update(app_conversations)
        .where(app_conversations.c.conversation_id == audit.conversation_id)
        .values(updated_at=now)
    )
    session.execute(
        update(rag_app_api_keys)
        .where(rag_app_api_keys.c.api_key_id == audit.api_key_id)
        .values(last_used_at=now)
    )
    session.commit()
    return assistant_message_id
