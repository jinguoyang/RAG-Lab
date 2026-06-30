"""课堂会话本地镜像服务。

平台侧员工培训 Agent 负责状态机、记忆上下文和结构化动作；应用端只调用平台 API，
并保存一份轻量本地镜像，供用户管理、审计和断线续接页面读取。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.database import new_id
from app.tables import (
    training_classroom_events,
    training_classroom_messages,
    training_classroom_sessions,
    training_plans,
)


CLASSROOM_STATES = (
    "INIT",
    "PLAN",
    "TEACH",
    "CHECK_UNDERSTAND",
    "QUIZ",
    "GRADE",
    "REVIEW",
    "SUMMARY",
    "NEXT_SECTION",
    "COMPLETED",
    "OFF_TOPIC",
)

CLASSROOM_TRANSITIONS: dict[str, list[str]] = {
    "INIT": ["PLAN"],
    "PLAN": ["TEACH"],
    "TEACH": ["CHECK_UNDERSTAND", "QUIZ", "OFF_TOPIC"],
    "CHECK_UNDERSTAND": ["QUIZ", "TEACH"],
    "QUIZ": ["GRADE"],
    "GRADE": ["REVIEW"],
    "REVIEW": ["SUMMARY", "TEACH"],
    "SUMMARY": ["NEXT_SECTION", "COMPLETED"],
    "NEXT_SECTION": ["TEACH"],
    "COMPLETED": [],
    "OFF_TOPIC": ["TEACH"],
}


class ClassroomSessionNotFoundError(Exception):
    """课堂会话不存在。"""


class ClassroomSessionConflictError(ValueError):
    """课堂会话冲突。"""


class ClassroomTransitionError(ValueError):
    """课堂状态流转冲突。"""


class ClassroomEventError(ValueError):
    """课堂事件错误。"""


def validate_classroom_transition(current_state: str, next_state: str) -> bool:
    """判断状态流转是否合法；应用端仅用于展示与测试，不作为权威控制器。"""
    return next_state in CLASSROOM_TRANSITIONS.get(current_state, [])


def _platform_client():
    """构造平台客户端，集中读取应用端配置。"""
    from app.core.config import get_settings
    from app.services.platform_client import PlatformClient

    settings = get_settings()
    return PlatformClient(settings.platform_base_url, settings.platform_api_key)


def _upsert_session_mirror(session: Session, data: dict[str, Any], user_id: str | None, metadata: dict[str, Any] | None = None) -> None:
    """把平台会话状态同步到本地镜像表。"""
    now = datetime.now(timezone.utc)
    session_id = data["sessionId"]
    row = session.execute(
        select(training_classroom_sessions.c.session_id).where(training_classroom_sessions.c.session_id == session_id)
    ).mappings().first()
    values = {
        "app_id": data["appId"],
        "plan_id": data.get("planId"),
        "end_user_id": data["endUserId"],
        "current_state": data.get("currentState") or data.get("classroomState") or "INIT",
        "current_section_index": data.get("currentSectionIndex", 0),
        "metadata": metadata or data.get("metadata") or {},
        "status": "active",
        "updated_at": now,
        "updated_by": user_id,
    }
    if row is None:
        session.execute(
            insert(training_classroom_sessions).values(
                session_id=session_id,
                context_summary=None,
                created_at=now,
                created_by=user_id,
                deleted_at=None,
                deleted_by=None,
                **values,
            )
        )
        return
    session.execute(update(training_classroom_sessions).where(training_classroom_sessions.c.session_id == session_id).values(**values))


def _insert_event_mirror(session: Session, session_id: str, user_id: str | None, data: dict[str, Any]) -> None:
    """保存平台事件响应摘要，便于应用侧审计。"""
    session.execute(
        insert(training_classroom_events).values(
            event_id=data.get("eventId") or new_id(),
            session_id=session_id,
            event_type=data.get("eventType", "unknown"),
            payload={
                "visibleContent": data.get("visibleContent"),
                "uiActions": data.get("uiActions", []),
                "citations": data.get("citations", []),
            },
            result_state=data.get("classroomState") or data.get("resultState"),
            status="processed",
            created_at=datetime.now(timezone.utc),
            created_by=user_id,
        )
    )


def _insert_assistant_message_mirror(session: Session, session_id: str, data: dict[str, Any]) -> None:
    """把平台可见输出写入本地消息镜像。"""
    content = data.get("visibleContent") or ""
    if not content:
        return
    session.execute(
        insert(training_classroom_messages).values(
            message_id=new_id(),
            session_id=session_id,
            role="assistant",
            content=content,
            state_at_time=data.get("classroomState") or data.get("resultState"),
            metadata={"uiActions": data.get("uiActions", []), "citations": data.get("citations", [])},
            status="active",
            created_at=datetime.now(timezone.utc),
            created_by=None,
        )
    )


def _to_session_response(data: dict[str, Any]) -> Any:
    """将平台会话响应转换为应用端 DTO。"""
    from app.schemas.training_classroom import ClassroomSessionResponse

    return ClassroomSessionResponse(
        sessionId=data["sessionId"],
        appId=data["appId"],
        planId=data.get("planId"),
        endUserId=data["endUserId"],
        currentState=data["currentState"],
        currentSectionIndex=data.get("currentSectionIndex", 0),
        createdAt=data["createdAt"],
    )


def _to_event_response(data: dict[str, Any]) -> Any:
    """将平台事件响应转换为应用端 DTO。"""
    from app.schemas.training_classroom import ClassroomEventResponse

    return ClassroomEventResponse.model_validate(data)


def create_classroom_session(session: Session, user_id: str | None, request: Any) -> Any:
    """创建课堂会话：调用平台 Agent，再保存本地镜像。"""
    import httpx

    # 构造 inputs，传递语言和文档约束给平台 Agent
    inputs = dict(request.inputs or {})
    inputs["language"] = "zh-CN"
    if request.documentId:
        inputs["documentId"] = request.documentId
    if request.planId:
        plan_row = session.execute(
            select(training_plans)
            .where(training_plans.c.plan_id == request.planId)
            .where(training_plans.c.deleted_at.is_(None))
            .limit(1)
        ).mappings().first()
        if plan_row is not None:
            plan_documents = plan_row["documents"] or []
            if request.documentId:
                plan_documents = [
                    document
                    for document in plan_documents
                    if isinstance(document, dict) and document.get("documentId") == request.documentId
                ]
                if not plan_documents:
                    raise ClassroomSessionConflictError(
                        f"学习计划中不存在文档 {request.documentId}"
                    )
            inputs["courseSnapshot"] = {
                "planId": str(plan_row["plan_id"]),
                "version": plan_row["version"],
                "documents": plan_documents,
            }

    # 构造平台 API 请求
    platform_payload = {
        "planId": request.planId,
        "endUserId": request.endUserId,
        "inputs": inputs,
    }

    try:
        data = _platform_client().create_classroom_session(platform_payload)
    except httpx.HTTPError as exc:
        raise ClassroomSessionConflictError(f"平台课堂会话创建失败: {exc}") from exc

    # 将 documentId 保存到本地 metadata
    metadata = dict(inputs)
    _upsert_session_mirror(session, data, user_id, metadata)
    session.commit()
    return _to_session_response(data)


def get_classroom_session(session: Session, session_id: str) -> Any:
    """读取课堂会话：优先从平台拉取最新状态并同步本地镜像。"""
    import httpx
    from app.schemas.training_classroom import ClassroomSessionDetailResponse

    try:
        data = _platform_client().get_classroom_session(session_id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在") from exc
        raise ClassroomSessionConflictError(f"平台课堂会话读取失败: {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise ClassroomSessionConflictError(f"平台课堂会话读取失败: {exc}") from exc

    _upsert_session_mirror(session, data, None, data.get("metadata") or {})
    session.commit()
    return ClassroomSessionDetailResponse.model_validate(data)


def submit_classroom_event(session: Session, user_id: str | None, session_id: str, request: Any) -> Any:
    """提交课堂事件：平台 Agent 返回结构化动作，应用端只做镜像保存。"""
    import httpx

    try:
        data = _platform_client().submit_classroom_event(session_id, request.model_dump())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在") from exc
        if exc.response.status_code == 409:
            raise ClassroomTransitionError(str(exc.response.text)) from exc
        raise ClassroomEventError(f"平台课堂事件提交失败: {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise ClassroomEventError(f"平台课堂事件提交失败: {exc}") from exc

    session_row = session.execute(
        select(training_classroom_sessions).where(training_classroom_sessions.c.session_id == session_id)
    ).mappings().first()
    if session_row is None:
        raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在")
    _upsert_session_mirror(
        session,
        {
            "sessionId": session_id,
            "appId": str(session_row["app_id"]),
            "planId": str(session_row["plan_id"]) if session_row["plan_id"] else None,
            "endUserId": session_row["end_user_id"],
            "currentState": data.get("classroomState") or data.get("resultState"),
            "currentSectionIndex": (data.get("progressUpdate") or {}).get("sectionIndex", session_row["current_section_index"]),
            "createdAt": session_row["created_at"].isoformat(),
            "metadata": session_row["metadata"] or {},
        },
        user_id,
        session_row["metadata"] or {},
    )
    _insert_event_mirror(session, session_id, user_id, data)
    _insert_assistant_message_mirror(session, session_id, data)
    session.commit()
    return _to_event_response(data)
