"""员工培训课堂 Agent 状态机和结构化输出服务。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.app_runtime import AppRuntimeChatRequest
from app.schemas.training_classroom import (
    ClassroomCitationDTO,
    ClassroomControlDTO,
    ClassroomEventResponse,
    ClassroomMessageDTO,
    ClassroomProgressUpdateDTO,
    ClassroomSessionDetailResponse,
    ClassroomSessionResponse,
    ClassroomUiActionDTO,
)
from app.services.app_runtime_service import chat_with_app_runtime
from app.services.training_agent_service import (
    TrainingAgentConflictError,
    TrainingAgentNotFoundError,
    evidence_preview,
    evidence_title,
    read_training_evidence,
    resolve_training_context,
)
from app.tables import (
    training_classroom_events,
    training_classroom_messages,
    training_classroom_sessions,
    training_questions,
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


class ClassroomSessionNotFoundError(TrainingAgentNotFoundError):
    """课堂会话不存在。"""


class ClassroomTransitionError(TrainingAgentConflictError):
    """课堂状态流转非法。"""


class ClassroomEventError(ValueError):
    """课堂事件载荷错误。"""


def validate_classroom_transition(current_state: str, next_state: str) -> bool:
    """判断课堂状态流转是否合法。"""
    return next_state in CLASSROOM_TRANSITIONS.get(current_state, [])


def create_classroom_session(session: Session, credential: str, request: Any) -> ClassroomSessionResponse:
    """创建平台侧课堂会话，后续上下文和状态以此为准。"""
    context = resolve_training_context(session, credential, request.appId)
    now = datetime.now(UTC)
    session_id = new_id()
    metadata = {"inputs": request.inputs or {}, "source": "employee_training_agent"}
    session.execute(
        insert(training_classroom_sessions).values(
            session_id=session_id,
            app_id=context.app_row["app_id"],
            plan_id=request.planId,
            end_user_id=request.endUserId,
            current_state="INIT",
            current_section_index=0,
            context_summary=None,
            metadata=metadata,
            status="active",
            created_at=now,
            created_by=request.endUserId,
            updated_at=now,
            updated_by=request.endUserId,
            deleted_at=None,
            deleted_by=None,
        )
    )
    session.commit()
    return ClassroomSessionResponse(
        sessionId=str(session_id),
        appId=str(context.app_row["app_id"]),
        planId=request.planId,
        endUserId=request.endUserId,
        currentState="INIT",
        currentSectionIndex=0,
        createdAt=now.isoformat(),
    )


def _read_session(session: Session, session_id: str):
    """读取课堂会话行，不存在时抛业务异常。"""
    row = session.execute(
        select(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .where(training_classroom_sessions.c.deleted_at.is_(None))
        .limit(1)
    ).mappings().first()
    if row is None:
        raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在")
    return row


def _to_message(row: Any) -> ClassroomMessageDTO:
    """将数据库消息行转换为 API DTO。"""
    return ClassroomMessageDTO(
        messageId=str(row["message_id"]),
        role=row["role"],
        content=row["content"],
        stateAtTime=row["state_at_time"],
        metadata=row["metadata"] or {},
        createdAt=row["created_at"].isoformat(),
    )


def get_classroom_session(session: Session, session_id: str, credential: str | None = None) -> ClassroomSessionDetailResponse:
    """获取课堂会话详情和历史消息。"""
    row = _read_session(session, session_id)
    if credential is not None:
        resolve_training_context(session, credential, str(row["app_id"]))
    messages = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .order_by(training_classroom_messages.c.created_at.asc())
    ).mappings().all()
    return ClassroomSessionDetailResponse(
        sessionId=str(row["session_id"]),
        appId=str(row["app_id"]),
        planId=str(row["plan_id"]) if row["plan_id"] else None,
        endUserId=row["end_user_id"],
        currentState=row["current_state"],
        currentSectionIndex=row["current_section_index"],
        messages=[_to_message(item) for item in messages],
        metadata=row["metadata"] or {},
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _insert_message(
    session: Session,
    session_id: str,
    role: str,
    content: str,
    state: str,
    created_by: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """写入课堂消息，并返回消息 ID。"""
    message_id = new_id()
    session.execute(
        insert(training_classroom_messages).values(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            state_at_time=state,
            metadata=metadata or {},
            status="active",
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
    )
    return str(message_id)


def _insert_event(
    session: Session,
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
    result_state: str,
    created_by: str | None,
) -> str:
    """写入课堂事件审计，并返回事件 ID。"""
    event_id = new_id()
    session.execute(
        insert(training_classroom_events).values(
            event_id=event_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
            result_state=result_state,
            status="processed",
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
    )
    return str(event_id)


def _update_state(session: Session, session_id: str, next_state: str, updated_by: str | None, section_index: int | None = None) -> None:
    """更新课堂会话状态，确保所有推进都经过服务层。"""
    values: dict[str, Any] = {"current_state": next_state, "updated_at": datetime.now(UTC), "updated_by": updated_by}
    if section_index is not None:
        values["current_section_index"] = section_index
    session.execute(update(training_classroom_sessions).where(training_classroom_sessions.c.session_id == session_id).values(**values))


def _button_group(*items: tuple[str, str, dict[str, Any]]) -> ClassroomUiActionDTO:
    """生成前端可直接渲染的按钮组动作。"""
    return ClassroomUiActionDTO(
        actionType="button_group",
        data={
            "buttons": [
                {"label": label, "eventType": event_type, "payload": payload}
                for label, event_type, payload in items
            ]
        },
    )


def _current_evidence(session: Session, app_id: str, kb_id: Any, state_row: Any, query: str = "") -> tuple[str, list[ClassroomCitationDTO]]:
    """读取当前章节证据，生成教学正文和引用。"""
    metadata = state_row["metadata"] or {}
    inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
    rows = read_training_evidence(session, kb_id, query or str(inputs.get("jobTitle", "")), limit=6)
    if not rows:
        return "当前知识库暂无可用于本课程的学习材料，请联系管理员补充文档。", []
    index = min(state_row["current_section_index"], len(rows) - 1)
    row = rows[index]
    title = evidence_title(row)
    preview = evidence_preview(row, 360)
    content = f"本节学习「{title}」。\n\n{preview}\n\n请先理解关键要求，随后可以继续进入测验，或直接追问不清楚的地方。"
    citations = [
        ClassroomCitationDTO(
            documentId=str(row["document_id"]),
            chunkId=str(row["chunk_id"]),
            content=evidence_preview(row, 180),
            score=1.0,
        )
    ]
    return content, citations


def _plan_content(session: Session, kb_id: Any, state_row: Any) -> tuple[str, list[ClassroomCitationDTO]]:
    """生成课程目标说明。"""
    rows = read_training_evidence(session, kb_id, str((state_row["metadata"] or {}).get("inputs", {})), limit=6)
    titles = [evidence_title(row) for row in rows]
    if not titles:
        return "已初始化课程，但当前知识库没有可展示的学习材料。", []
    lines = [f"{index}. {title}" for index, title in enumerate(titles, start=1)]
    content = "本课程将按以下材料展开：\n" + "\n".join(lines)
    citations = [
        ClassroomCitationDTO(documentId=str(row["document_id"]), chunkId=str(row["chunk_id"]), content=evidence_preview(row, 120), score=1.0)
        for row in rows[:3]
    ]
    return content, citations


def _quiz_payload(session: Session, state_row: Any, kb_id: Any) -> tuple[str, list[ClassroomUiActionDTO], list[ClassroomCitationDTO]]:
    """生成课堂测验动作，优先使用平台题库，缺省时基于证据给出即时题。"""
    question = session.execute(
        select(training_questions)
        .where(training_questions.c.app_id == state_row["app_id"])
        .where(training_questions.c.status.in_(["approved", "draft"]))
        .order_by(training_questions.c.created_at.asc())
        .limit(1)
    ).mappings().first()
    citations: list[ClassroomCitationDTO] = []
    if question is not None:
        visible = question["content"]
        action = ClassroomUiActionDTO(
            actionType=question["question_type"],
            data={
                "questionId": str(question["question_id"]),
                "content": question["content"],
                "options": question["options"] or [],
                "questionType": question["question_type"],
                "answerEventType": "submit_answer",
            },
        )
        return visible, [action], citations

    content, citations = _current_evidence(session, str(state_row["app_id"]), kb_id, state_row)
    action = ClassroomUiActionDTO(
        actionType="true_false",
        data={
            "questionId": "inline-true-false",
            "content": "判断题：本节内容中的要求需要作为后续作业依据。",
            "options": [{"label": "true", "text": "正确"}, {"label": "false", "text": "错误"}],
            "answerEventType": "submit_answer",
        },
    )
    return f"请完成本节测验。\n\n{content}", [action], citations


def _grade_subjective_answer(answer: str, rubric: dict[str, Any] | None) -> tuple[int, str]:
    """根据服务端 rubric 对主观题做保守初评分。"""
    if not answer:
        return 0, "未提交有效答案。"
    base_score = 60 if len(answer) >= 20 else 40
    criteria = rubric.get("criteria", []) if isinstance(rubric, dict) else []
    if criteria and len(answer) >= 50:
        base_score = 80
    return base_score, "主观题已按服务端 rubric 初评分，管理员可继续复核。"


def _grade_answer(session: Session, state_row: Any, payload: dict[str, Any]) -> tuple[int, str]:
    """从平台题库或内置题读取正确答案，避免信任客户端传入的答案。"""
    answer = str(payload.get("answer", "")).strip()
    question_id = str(payload.get("questionId") or "")
    if question_id == "inline-true-false" or not question_id:
        correct_answer = "true"
        is_correct = answer.lower() == correct_answer
        return (100 if is_correct else 0), ("回答正确。" if is_correct else "回答不正确，请回看本节材料。")

    question = session.execute(
        select(training_questions)
        .where(training_questions.c.question_id == question_id)
        .where(training_questions.c.app_id == state_row["app_id"])
        .limit(1)
    ).mappings().first()
    if question is None:
        return 0, "题目不存在或不属于当前课堂应用。"
    if question["question_type"] == "subjective":
        return _grade_subjective_answer(answer, question["rubric"])

    correct_answer = str(question["correct_answer"] or "").strip()
    is_correct = answer.lower() == correct_answer.lower()
    explanation = question["explanation"] or "请回看本节材料。"
    return (100 if is_correct else 0), ("回答正确。" if is_correct else f"回答不正确，{explanation}")


def _is_continue_intent(query: str) -> bool:
    """识别用户用文本表达的继续意图。"""
    normalized = query.strip().lower()
    return normalized in {"继续", "下一步", "听懂了", "已理解", "明白了", "开始测验"}


def _is_illegal_command(query: str) -> bool:
    """识别用户试图绕过流程的文本命令。"""
    normalized = query.replace(" ", "")
    illegal_terms = ("本节课结束", "结束课程", "直接完成", "完成课程", "跳过测验", "跳过考试", "退出课程")
    return any(term in normalized for term in illegal_terms)


def _is_off_topic(query: str, state_row: Any) -> bool:
    """用轻量规则识别明显偏题问题，避免非课程内容进入教学流程。"""
    normalized = query.lower()
    off_topic_terms = ("股票", "天气", "电影", "旅游", "游戏", "彩票", "娱乐新闻")
    if any(term in normalized for term in off_topic_terms):
        return True
    metadata = state_row["metadata"] or {}
    inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
    job_title = str(inputs.get("jobTitle", "")).lower() if isinstance(inputs, dict) else ""
    if len(query) >= 8 and job_title and job_title not in normalized and any(term in normalized for term in ("怎么样", "是什么", "怎么做")):
        return True
    return False


def _recent_context_messages(session: Session, session_id: str, limit: int = 6) -> list[dict[str, str]]:
    """读取最近课堂消息，作为追问时的短期记忆上下文。"""
    rows = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .where(training_classroom_messages.c.status == "active")
        .order_by(training_classroom_messages.c.created_at.desc())
        .limit(limit)
    ).mappings().all()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def _answer_query_with_agent(
    session: Session,
    credential: str,
    state_row: Any,
    kb_id: Any,
    query: str,
) -> tuple[str, list[ClassroomCitationDTO]]:
    """优先调用平台 App Runtime 生成追问回答，失败时回退到证据摘要。"""
    session_id = str(state_row["session_id"])
    history = _recent_context_messages(session, session_id)
    context_lines = "\n".join(f"{item['role']}: {item['content']}" for item in history[-4:])
    agent_query = f"当前是员工培训课堂，请基于课程材料回答追问。\n最近对话：\n{context_lines}\n用户追问：{query}"
    try:
        response = chat_with_app_runtime(
            session,
            credential,
            AppRuntimeChatRequest(
                query=agent_query,
                endUserId=state_row["end_user_id"],
                inputs={"classroomSessionId": session_id, "classroomState": state_row["current_state"]},
            ),
        )
        citations = [
            ClassroomCitationDTO(
                documentId=None,
                chunkId=str(item.locationSnapshot.get("chunkId")) if item.locationSnapshot.get("chunkId") else None,
                content=item.label,
                score=None,
            )
            for item in response.citations
        ]
        return response.answer, citations
    except Exception:
        content, citations = _current_evidence(session, str(state_row["app_id"]), kb_id, state_row, query)
        if history:
            content = f"{content}\n\n我已结合最近 {len(history)} 条课堂消息继续讲解。"
        return content, citations


def _event_to_response(
    session: Session,
    state_row: Any,
    event_type: str,
    next_state: str,
    content: str,
    ui_actions: list[ClassroomUiActionDTO],
    citations: list[ClassroomCitationDTO],
    payload: dict[str, Any],
    progress: ClassroomProgressUpdateDTO | None = None,
) -> ClassroomEventResponse:
    """持久化一次课堂事件和助手消息，并组装响应。"""
    session_id = str(state_row["session_id"])
    event_id = _insert_event(session, session_id, event_type, payload, next_state, state_row["end_user_id"])
    _insert_message(session, session_id, "assistant", content, next_state, None, {"uiActions": [a.model_dump() for a in ui_actions]})
    _update_state(session, session_id, next_state, state_row["end_user_id"], progress.sectionIndex if progress else None)
    session.commit()
    has_answer_action = any(action.actionType in {"single_choice", "true_false", "subjective"} for action in ui_actions)
    requires_input = bool(ui_actions)
    return ClassroomEventResponse(
        eventId=event_id,
        sessionId=session_id,
        eventType=event_type,
        resultState=next_state,
        visibleContent=content,
        classroomState=next_state,
        uiActions=ui_actions,
        citations=citations,
        control=ClassroomControlDTO(canProceed=not requires_input, requiresInput=requires_input, inputType="answer" if has_answer_action else ("action" if requires_input else None)),
        progressUpdate=progress,
        messages=[],
        createdAt=datetime.now(UTC).isoformat(),
    )


def submit_classroom_event(session: Session, credential: str, session_id: str, request: Any) -> ClassroomEventResponse:
    """提交课堂事件，由平台 Agent 状态机决定下一步输出。"""
    state_row = _read_session(session, session_id)
    context = resolve_training_context(session, credential, str(state_row["app_id"]))
    current_state = state_row["current_state"]
    event_type = request.eventType
    payload = request.payload or {}
    if current_state == "COMPLETED":
        raise ClassroomEventError("课堂已完成，不能继续推进")

    if (event_type == "query" or request.query) and event_type != "continue":
        query = (request.query or payload.get("query") or "").strip()
        if not query:
            raise ClassroomEventError("query is required")
        if _is_continue_intent(query):
            event_type = "continue"
            payload = {}
        elif _is_illegal_command(query):
            _insert_message(session, session_id, "user", query, current_state, state_row["end_user_id"])
            return _event_to_response(
                session,
                state_row,
                "invalid_command",
                current_state,
                "当前阶段不允许通过文本指令跳过或结束课程，请按页面按钮完成学习流程。",
                [_button_group(("继续学习", "continue", {}), ("继续追问", "query", {}))],
                [],
                {"query": query},
            )
        elif _is_off_topic(query, state_row) and current_state in {"TEACH", "CHECK_UNDERSTAND", "OFF_TOPIC"}:
            _insert_message(session, session_id, "user", query, current_state, state_row["end_user_id"])
            return _event_to_response(
                session,
                state_row,
                "off_topic",
                "OFF_TOPIC",
                "这个问题偏离了当前课程目标。请回到当前课程内容，或提出与本节材料相关的问题。",
                [_button_group(("回到课程", "continue", {}))],
                [],
                {"query": query},
            )
    if event_type == "query" or request.query:
        _insert_message(session, session_id, "user", query, current_state, state_row["end_user_id"])
        content, citations = _answer_query_with_agent(session, credential, state_row, context.kb_row["kb_id"], query)
        return _event_to_response(
            session,
            state_row,
            "query",
            "TEACH" if current_state in {"OFF_TOPIC", "CHECK_UNDERSTAND"} else current_state,
            content,
            [_button_group(("听懂了，继续", "continue", {}), ("继续追问", "query", {}))],
            citations,
            {"query": query},
        )

    if event_type == "start":
        if not validate_classroom_transition(current_state, "PLAN"):
            raise ClassroomTransitionError(f"不允许从 {current_state} 流转到 PLAN")
        content, citations = _plan_content(session, context.kb_row["kb_id"], state_row)
        return _event_to_response(
            session,
            state_row,
            event_type,
            "PLAN",
            content,
            [_button_group(("开始学习", "continue", {}))],
            citations,
            payload,
        )

    if event_type in {"continue", "start_plan"} and current_state == "PLAN":
        content, citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], state_row)
        return _event_to_response(
            session,
            state_row,
            event_type,
            "TEACH",
            content,
            [_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
            citations,
            payload,
        )

    if event_type == "continue" and current_state == "TEACH":
        return _event_to_response(
            session,
            state_row,
            event_type,
            "CHECK_UNDERSTAND",
            "你理解了本节内容吗？如果已经听懂，可以继续进入测验；如果还有疑问，可以继续追问。",
            [_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
            [],
            payload,
        )

    if event_type in {"continue", "start_quiz"} and current_state == "CHECK_UNDERSTAND":
        visible, actions, citations = _quiz_payload(session, state_row, context.kb_row["kb_id"])
        return _event_to_response(session, state_row, event_type, "QUIZ", visible, actions, citations, payload)

    if event_type in {"submit_answer", "submit_quiz"} and current_state == "QUIZ":
        score, explanation = _grade_answer(session, state_row, payload)
        content = f"本次测验得分：{score}。\n{explanation}"
        return _event_to_response(
            session,
            state_row,
            event_type,
            "GRADE",
            content,
            [_button_group(("查看复习建议", "continue", {}))],
            [],
            {**payload, "score": score},
        )

    if event_type == "continue" and current_state == "GRADE":
        content = "请复盘错题或不确定的知识点，确认后继续查看本节小结。"
        return _event_to_response(session, state_row, event_type, "REVIEW", content, [_button_group(("完成复习", "continue", {}))], [], payload)

    if event_type == "continue" and current_state == "REVIEW":
        content = "本节小结：请将关键流程、风险点和证据出处纳入实际作业。"
        return _event_to_response(
            session,
            state_row,
            event_type,
            "SUMMARY",
            content,
            [_button_group(("下一节", "next_section", {}), ("完成课程", "complete", {}))],
            [],
            payload,
        )

    if event_type == "next_section" and current_state == "SUMMARY":
        next_index = state_row["current_section_index"] + 1
        progress = ClassroomProgressUpdateDTO(sectionIndex=next_index, completedSections=next_index)
        next_state_row = dict(state_row)
        next_state_row["current_section_index"] = next_index
        content, citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], next_state_row)
        return _event_to_response(
            session,
            state_row,
            event_type,
            "TEACH",
            content,
            [_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
            citations,
            payload,
            progress,
        )

    if event_type == "complete" and current_state == "SUMMARY":
        return _event_to_response(session, state_row, event_type, "COMPLETED", "课程已完成。", [], [], payload)

    raise ClassroomTransitionError(f"不允许在 {current_state} 阶段执行 {event_type}")
