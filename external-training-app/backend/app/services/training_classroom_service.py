"""课堂会话、状态机、事件处理和受控答疑服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.core.database import new_id
from app.tables import (
    training_classroom_events,
    training_classroom_messages,
    training_classroom_sessions,
)


# ── 课堂状态机 ────────────────────────────────────────────────────────

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


def validate_classroom_transition(current_state: str, next_state: str) -> bool:
    """判断状态流转是否合法。"""
    allowed = CLASSROOM_TRANSITIONS.get(current_state, [])
    return next_state in allowed


# ── 异常定义 ──────────────────────────────────────────────────────────

class ClassroomSessionNotFoundError(Exception):
    """课堂会话不存在。"""


class ClassroomSessionConflictError(ValueError):
    """课堂会话冲突。"""


class ClassroomTransitionError(ValueError):
    """非法状态流转。"""


class ClassroomEventError(ValueError):
    """课堂事件处理错误。"""


# ── 会话 CRUD ─────────────────────────────────────────────────────────

def create_classroom_session(
    session: Session,
    user_id: str | None,
    request: Any,
) -> Any:
    """创建课堂会话。"""
    from app.schemas.training_classroom import ClassroomSessionResponse

    now = datetime.now(timezone.utc)
    session_id = new_id()

    session.execute(
        insert(training_classroom_sessions).values(
            session_id=session_id,
            app_id=request.appId,
            plan_id=request.planId,
            end_user_id=request.endUserId,
            current_state="INIT",
            current_section_index=0,
            metadata=request.inputs or {},
            status="active",
            created_at=now,
            created_by=user_id,
            updated_at=now,
            updated_by=user_id,
        )
    )
    session.commit()

    return ClassroomSessionResponse(
        sessionId=session_id,
        appId=request.appId,
        planId=request.planId,
        endUserId=request.endUserId,
        currentState="INIT",
        currentSectionIndex=0,
        createdAt=now.isoformat(),
    )


def get_classroom_session(
    session: Session,
    session_id: str,
) -> Any:
    """获取课堂会话详情。"""
    from app.schemas.training_classroom import (
        ClassroomMessageDTO,
        ClassroomSessionDetailResponse,
    )

    row = session.execute(
        select(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .where(training_classroom_sessions.c.deleted_at.is_(None))
    ).mappings().first()

    if row is None:
        raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在")

    msg_rows = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .order_by(training_classroom_messages.c.created_at)
    ).mappings().all()

    messages = [
        ClassroomMessageDTO(
            messageId=r["message_id"],
            role=r["role"],
            content=r["content"],
            stateAtTime=r["state_at_time"],
            metadata=r["metadata"] or {},
            createdAt=r["created_at"].isoformat(),
        )
        for r in msg_rows
    ]

    return ClassroomSessionDetailResponse(
        sessionId=row["session_id"],
        appId=row["app_id"],
        planId=row["plan_id"],
        endUserId=row["end_user_id"],
        currentState=row["current_state"],
        currentSectionIndex=row["current_section_index"],
        messages=messages,
        metadata=row["metadata"] or {},
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _get_session_row(session: Session, session_id: str) -> Any:
    """内部获取会话行，不存在则抛异常。"""
    row = session.execute(
        select(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .where(training_classroom_sessions.c.deleted_at.is_(None))
    ).mappings().first()

    if row is None:
        raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在")
    return row


def _insert_classroom_message(
    session: Session,
    session_id: str,
    role: str,
    content: str,
    state_at_time: str | None,
    created_by: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """插入课堂消息，返回 message_id。"""
    now = datetime.now(timezone.utc)
    message_id = new_id()

    session.execute(
        insert(training_classroom_messages).values(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            state_at_time=state_at_time,
            metadata=metadata or {},
            status="active",
            created_at=now,
            created_by=created_by,
        )
    )
    return message_id


def _insert_classroom_event(
    session: Session,
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
    result_state: str | None,
    created_by: str | None,
) -> str:
    """插入课堂事件，返回 event_id。"""
    now = datetime.now(timezone.utc)
    event_id = new_id()

    session.execute(
        insert(training_classroom_events).values(
            event_id=event_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
            result_state=result_state,
            status="processed",
            created_at=now,
            created_by=created_by,
        )
    )
    return event_id


def _update_session_state(
    session: Session,
    session_id: str,
    new_state: str,
    updated_by: str | None,
    section_index: int | None = None,
) -> None:
    """更新会话状态。"""
    now = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "current_state": new_state,
        "updated_at": now,
        "updated_by": updated_by,
    }
    if section_index is not None:
        values["current_section_index"] = section_index

    session.execute(
        update(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .values(**values)
    )


# ── 受控答疑 ──────────────────────────────────────────────────────────

def _build_classroom_context_messages(
    session: Session,
    session_id: str,
    max_turns: int = 10,
) -> list[dict[str, str]]:
    """构建课堂历史上下文。"""
    rows = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .where(training_classroom_messages.c.status == "active")
        .order_by(training_classroom_messages.c.created_at.desc())
        .limit(max_turns)
    ).mappings().all()

    rows = list(reversed(rows))

    return [
        {"role": r["role"], "content": r["content"]}
        for r in rows
    ]


def _is_query_relevant(
    query: str,
    plan_context: dict[str, Any] | None,
) -> bool:
    """简单偏题检测。首版始终返回 True，由 Agent 提示词约束。"""
    return True


_OFF_TOPIC_RESPONSE = (
    "这个问题偏离了当前课程目标。请回到当前学习内容，"
    "或者提出与课程相关的问题。"
)


def handle_classroom_query(
    session: Session,
    user_id: str | None,
    session_id: str,
    query: str,
    plan_context: dict[str, Any] | None = None,
) -> Any:
    """处理课堂提问：偏题检测 + 上下文注入 + Agent 调用。"""
    from app.schemas.training_classroom import (
        ClassroomControlDTO,
        ClassroomEventResponse,
        ClassroomMessageDTO,
    )

    session_row = _get_session_row(session, session_id)
    current_state = session_row["current_state"]

    if current_state == "COMPLETED":
        raise ClassroomEventError("课堂已结束，不能继续提问")

    if not _is_query_relevant(query, plan_context):
        if validate_classroom_transition(current_state, "OFF_TOPIC"):
            _update_session_state(session, session_id, "OFF_TOPIC", user_id)
            _insert_classroom_message(session, session_id, "user", query, current_state, user_id)
            _insert_classroom_message(session, session_id, "assistant", _OFF_TOPIC_RESPONSE, "OFF_TOPIC", None)
            _insert_classroom_event(session, session_id, "off_topic", {"query": query}, "OFF_TOPIC", user_id)
            session.commit()

            return ClassroomEventResponse(
                eventId=new_id(),
                sessionId=session_id,
                eventType="off_topic",
                resultState="OFF_TOPIC",
                visibleContent=_OFF_TOPIC_RESPONSE,
                classroomState="OFF_TOPIC",
                uiActions=[],
                citations=[],
                control=ClassroomControlDTO(canProceed=True, requiresInput=False),
                messages=[],
                createdAt=datetime.now(timezone.utc).isoformat(),
            )

    _insert_classroom_message(session, session_id, "user", query, current_state, user_id)

    context_messages = _build_classroom_context_messages(session, session_id)

    answer_text, citations = _generate_classroom_answer(
        session, session_row, query, context_messages
    )

    _insert_classroom_message(session, session_id, "assistant", answer_text, current_state, None)

    ui_actions = _extract_ui_actions(answer_text)

    requires_input = len(ui_actions) > 0 and any(
        a.actionType in ("single_choice", "true_false", "subjective")
        for a in ui_actions
    )

    result_state = current_state
    if current_state == "OFF_TOPIC" and validate_classroom_transition("OFF_TOPIC", "TEACH"):
        result_state = "TEACH"
        _update_session_state(session, session_id, "TEACH", user_id)

    _insert_classroom_event(
        session, session_id, "query",
        {"query": query, "answer": answer_text},
        result_state, user_id,
    )
    session.commit()

    return ClassroomEventResponse(
        eventId=new_id(),
        sessionId=session_id,
        eventType="query",
        resultState=result_state,
        visibleContent=answer_text,
        classroomState=result_state,
        uiActions=ui_actions,
        citations=citations,
        control=ClassroomControlDTO(
            canProceed=True,
            requiresInput=requires_input,
            inputType="choice" if requires_input else None,
        ),
        messages=[],
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


def _generate_classroom_answer(
    session: Session,
    session_row: Any,
    query: str,
    context_messages: list[dict[str, str]],
) -> tuple[str, list[Any]]:
    """调用平台 Agent 生成课堂回答。首版使用模板。"""
    from app.schemas.training_classroom import ClassroomCitationDTO

    state = session_row["current_state"]

    if state == "INIT":
        answer = "课堂尚未开始，请先开始学习计划。"
    elif state == "PLAN":
        answer = "正在为您准备学习计划，请稍候。"
    elif state == "TEACH":
        answer = f"关于您的问题「{query}」：这是基于当前课程内容的回答。"
    elif state == "CHECK_UNDERSTAND":
        answer = "请确认您是否理解了当前内容，我们可以继续或复习。"
    elif state == "QUIZ":
        answer = "当前处于测验阶段，请回答展示的题目。"
    else:
        answer = f"收到您的问题。当前课堂状态：{state}。"

    citations: list[ClassroomCitationDTO] = []

    return answer, citations


def _extract_ui_actions(answer_text: str) -> list[Any]:
    """从回答中提取 UI 动作。首版返回空列表。"""
    from app.schemas.training_classroom import ClassroomUiActionDTO
    return []


# ── 事件提交 ──────────────────────────────────────────────────────────

def submit_classroom_event(
    session: Session,
    user_id: str | None,
    session_id: str,
    request: Any,
) -> Any:
    """提交课堂事件，返回结构化课堂输出。"""
    from app.schemas.training_classroom import (
        ClassroomControlDTO,
        ClassroomEventResponse,
        ClassroomMessageDTO,
        ClassroomProgressUpdateDTO,
    )

    session_row = _get_session_row(session, session_id)
    current_state = session_row["current_state"]
    event_type = request.eventType

    if event_type == "query" and request.query:
        return handle_classroom_query(session, user_id, session_id, request.query)

    next_state = request.payload.get("nextState") if request.payload else None

    if next_state:
        if not validate_classroom_transition(current_state, next_state):
            raise ClassroomTransitionError(
                f"不允许从 {current_state} 流转到 {next_state}"
            )
        _update_session_state(session, session_id, next_state, user_id)
        result_state = next_state
    else:
        result_state = current_state

    event_id = _insert_classroom_event(
        session, session_id, event_type,
        request.payload or {}, result_state, user_id,
    )

    visible_content = _generate_event_response(event_type, current_state, result_state)

    progress = None
    if result_state == "NEXT_SECTION":
        new_index = session_row["current_section_index"] + 1
        _update_session_state(session, session_id, "TEACH", user_id, new_index)
        result_state = "TEACH"
        progress = ClassroomProgressUpdateDTO(
            sectionIndex=new_index,
            sectionTotal=None,
            completedSections=new_index,
        )

    session.commit()

    return ClassroomEventResponse(
        eventId=event_id,
        sessionId=session_id,
        eventType=event_type,
        resultState=result_state,
        visibleContent=visible_content,
        classroomState=result_state,
        uiActions=[],
        citations=[],
        control=ClassroomControlDTO(canProceed=True, requiresInput=False),
        progressUpdate=progress,
        messages=[],
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


def _generate_event_response(
    event_type: str,
    from_state: str,
    to_state: str,
) -> str:
    """根据事件类型和状态流转生成响应内容。"""
    responses = {
        ("start", "INIT", "PLAN"): "正在为您准备学习计划...",
        ("start_plan", "PLAN", "TEACH"): "学习计划已就绪，开始上课！",
        ("check_understand", "TEACH", "CHECK_UNDERSTAND"): "您理解了当前内容吗？",
        ("understood", "CHECK_UNDERSTAND", "QUIZ"): "很好，进入测验环节。",
        ("need_review", "CHECK_UNDERSTAND", "TEACH"): "让我们再复习一下。",
        ("start_quiz", "TEACH", "QUIZ"): "开始测验。",
        ("submit_quiz", "QUIZ", "GRADE"): "正在评分...",
        ("show_review", "GRADE", "REVIEW"): "查看测验结果。",
        ("finish_review", "REVIEW", "SUMMARY"): "课程总结如下。",
        ("next_section", "SUMMARY", "NEXT_SECTION"): "进入下一个章节。",
        ("complete", "SUMMARY", "COMPLETED"): "课程已完成！恭喜您！",
    }

    key = (event_type, from_state, to_state)
    return responses.get(key, f"事件 {event_type} 已处理，当前状态：{to_state}")
