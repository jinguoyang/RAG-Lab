"""员工培训课堂 Agent 状态机和结构化输出服务。"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.app_runtime import AppRuntimeChatRequest
from app.schemas.training_classroom import (
    ClassroomCitationDTO,
    ClassroomControlDTO,
    ClassroomDomainResult,
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
    rag_apps,
    training_classroom_events,
    training_classroom_messages,
    training_classroom_sessions,
    training_questions,
)

logger = logging.getLogger(__name__)

try:
    from app.services.training_grading_service import grade_subjective_answer
    HAS_GRADING_SERVICE = True
except ImportError:
    HAS_GRADING_SERVICE = False

try:
    from app.services.training_progress_service import record_answer, update_progress
    HAS_PROGRESS_SERVICE = True
except ImportError:
    HAS_PROGRESS_SERVICE = False

try:
    from app.services.training_skill_registry_service import record_training_skill_call
    HAS_SKILL_REGISTRY = True
except ImportError:
    HAS_SKILL_REGISTRY = False


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
    "GRADE": ["REVIEW", "QUIZ"],
    "REVIEW": ["SUMMARY", "TEACH", "QUIZ"],
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
    from app.services.agent_runtime.runtime_facade import resolve_runtime_version

    context = resolve_training_context(session, credential, request.appId)
    now = datetime.now(UTC)
    session_id = new_id()
    runtime_version = resolve_runtime_version(getattr(request, "runtimeVersion", None))
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
            runtime_version=runtime_version.value,
        )
    )
    session.commit()
    if HAS_PROGRESS_SERVICE:
        try:
            update_progress(
                session,
                session_id=str(session_id),
                app_id=str(context.app_row["app_id"]),
                end_user_id=request.endUserId,
                plan_id=request.planId,
                current_section_index=0,
                completed_sections=0,
                total_sections=0,
                status="init",
            )
            session.commit()
        except Exception as exc:
            logger.debug("非关键操作失败，已忽略: %s", exc)
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


def _resolve_kb_id(session: Session, app_id: str) -> Any | None:
    """从 rag_apps 表解析 app_id 对应的 kb_id。"""
    row = session.execute(
        select(rag_apps.c.kb_id)
        .where(rag_apps.c.app_id == app_id)
        .where(rag_apps.c.deleted_at.is_(None))
        .limit(1)
    ).scalar()
    return row


def _get_pending_actions(current_state: str, state_row: Any, is_last_section: bool = False) -> list[dict[str, Any]]:
    """根据当前状态返回可执行的动作列表。"""
    if current_state == "INIT":
        return [{"label": "开始学习", "eventType": "start"}]
    if current_state == "PLAN":
        return [{"label": "开始学习", "eventType": "continue"}]
    if current_state == "TEACH":
        return [
            {"label": "听懂了，继续", "eventType": "continue"},
            {"label": "我还不清楚", "eventType": "query"},
        ]
    if current_state == "CHECK_UNDERSTAND":
        return [
            {"label": "听懂了，继续", "eventType": "continue"},
            {"label": "我还不清楚", "eventType": "query"},
        ]
    if current_state == "QUIZ":
        return [{"label": "提交答案", "eventType": "submit_answer"}]
    if current_state == "GRADE":
        return [{"label": "查看复习建议", "eventType": "continue"}]
    if current_state == "REVIEW":
        metadata = state_row["metadata"] or {}
        last_passed = metadata.get("lastPassed", True) if isinstance(metadata, dict) else True
        if last_passed:
            return [{"label": "完成复习", "eventType": "continue"}]
        return [
            {"label": "重新学习", "eventType": "retry_teach"},
            {"label": "重新测验", "eventType": "retry_quiz"},
            {"label": "完成复习", "eventType": "continue"},
        ]
    if current_state == "SUMMARY":
        if is_last_section:
            return [{"label": "完成课程", "eventType": "complete"}]
        return [
            {"label": "下一节", "eventType": "next_section"},
            {"label": "完成课程", "eventType": "complete"},
        ]
    if current_state == "COMPLETED":
        return []
    if current_state == "OFF_TOPIC":
        return [{"label": "回到课程", "eventType": "continue"}]
    return []


def _get_context_summary(session: Session, session_id: str) -> str | None:
    """读取最近消息，生成简短摘要记忆。"""
    rows = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .where(training_classroom_messages.c.status == "active")
        .order_by(training_classroom_messages.c.created_at.desc())
        .limit(10)
    ).mappings().all()
    if not rows:
        return None
    assistant_msgs = [r for r in rows if r["role"] == "assistant"][:3]
    if not assistant_msgs:
        return None
    parts = []
    for msg in reversed(assistant_msgs):
        text = str(msg["content"] or "")
        parts.append(text[:100])
    return " | ".join(parts)


def _get_current_document(session: Session, state_row: Any, kb_id: Any) -> str | None:
    """读取当前 section 对应的文档标题。"""
    if kb_id is None:
        return None
    metadata = state_row["metadata"] or {}
    inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
    query = str(inputs.get("jobTitle", "")) if isinstance(inputs, dict) else ""
    rows = read_training_evidence(session, kb_id, query, limit=6)
    if not rows:
        return None
    index = min(state_row["current_section_index"], len(rows) - 1)
    return evidence_title(rows[index])


def get_classroom_session(
    session: Session,
    session_id: str,
    credential: str | None = None,
    expected_end_user_id: str | None = None,
) -> ClassroomSessionDetailResponse:
    """获取课堂会话详情和历史消息。

    安全规则：
    - credential 的 app_id 必须与 session 的 app_id 匹配
    - expected_end_user_id 与 session 的 end_user_id 不匹配时返回 404（不泄漏存在性）
    """
    row = _read_session(session, session_id)
    if credential is not None:
        context = resolve_training_context(session, credential, str(row["app_id"]))
        # 检查 endUserId 隔离：普通员工只能访问自己的会话
        if expected_end_user_id is not None and str(row["end_user_id"]) != str(expected_end_user_id):
            raise ClassroomSessionNotFoundError("课堂会话不存在")
    messages = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .order_by(training_classroom_messages.c.created_at.asc())
    ).mappings().all()

    # 构造恢复用 metadata
    base_metadata: dict[str, Any] = dict(row["metadata"]) if isinstance(row["metadata"], dict) else {}
    kb_id = _resolve_kb_id(session, str(row["app_id"]))
    current_state = row["current_state"]

    is_last = False
    if current_state == "SUMMARY" and kb_id is not None:
        meta_inputs = base_metadata.get("inputs") if isinstance(base_metadata, dict) else {}
        query_str = str(meta_inputs.get("jobTitle", "")) if isinstance(meta_inputs, dict) else ""
        total_sections = _count_sections(session, kb_id, query_str, session_id=session_id)
        is_last = row["current_section_index"] >= total_sections - 1

    base_metadata["pendingActions"] = _get_pending_actions(current_state, row, is_last)
    base_metadata["contextSummary"] = _get_context_summary(session, session_id)
    base_metadata["currentDocument"] = _get_current_document(session, row, kb_id)
    base_metadata["currentSectionIndex"] = row["current_section_index"]

    return ClassroomSessionDetailResponse(
        sessionId=str(row["session_id"]),
        appId=str(row["app_id"]),
        planId=str(row["plan_id"]) if row["plan_id"] else None,
        endUserId=row["end_user_id"],
        currentState=row["current_state"],
        currentSectionIndex=row["current_section_index"],
        messages=[_to_message(item) for item in messages],
        metadata=base_metadata,
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
    request_id: str | None = None,
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
            request_id=request_id,
        )
    )
    return str(event_id)


def read_classroom_event_by_request_id(
    session: Session,
    session_id: str,
    request_id: str,
) -> Any | None:
    """查询同一会话中已有的 requestId 事件，用于幂等保护。"""
    return session.execute(
        select(training_classroom_events)
        .where(training_classroom_events.c.session_id == session_id)
        .where(training_classroom_events.c.request_id == request_id)
        .limit(1)
    ).mappings().first()


def _update_state(session: Session, session_id: str, next_state: str, updated_by: str | None, section_index: int | None = None) -> None:
    """更新课堂会话状态，确保所有推进都经过服务层。"""
    values: dict[str, Any] = {"current_state": next_state, "updated_at": datetime.now(UTC), "updated_by": updated_by}
    if section_index is not None:
        values["current_section_index"] = section_index
    session.execute(update(training_classroom_sessions).where(training_classroom_sessions.c.session_id == session_id).values(**values))


def _merge_session_metadata(session: Session, session_id: str, extra: dict[str, Any]) -> None:
    """将额外字段合并到会话 metadata 中，供下游状态读取。使用 SELECT FOR UPDATE 防止并发丢失更新。"""
    row = session.execute(
        select(training_classroom_sessions.c.metadata)
        .where(training_classroom_sessions.c.session_id == session_id)
        .limit(1)
        .with_for_update()
    ).scalar()
    current = dict(row) if isinstance(row, dict) else {}
    current.update(extra)
    session.execute(
        update(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .values(metadata=current, updated_at=datetime.now(UTC))
    )


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
    _meta = state_row["metadata"] or {}
    _inputs = _meta.get("inputs") if isinstance(_meta, dict) else {}
    _query = _inputs.get("jobTitle", "") if isinstance(_inputs, dict) else ""
    rows = read_training_evidence(session, kb_id, _query, limit=6)
    titles = [evidence_title(row) for row in rows]
    if not titles:
        return "已初始化课程，但当前知识库没有可展示的学习材料。", []
    lines = [f"{index}. {title}" for index, title in enumerate(titles, start=1)]
    content = "本课程将按以下材料展开：\n" + "\n".join(lines)
    citations = [
        ClassroomCitationDTO(documentId=str(row["document_id"]), chunkId=str(row["chunk_id"]), content=evidence_preview(row, 120), score=1.0)
        for row in rows[:3]
    ]
    if HAS_SKILL_REGISTRY:
        try:
            record_training_skill_call(
                session,
                skill_name="buildLearningPlanDraft",
                status="success",
                app_id=str(state_row["app_id"]),
                input_summary=f"jobTitle={((state_row['metadata'] or {}).get('inputs', {}) or {}).get('jobTitle', '')}",
                output_summary=f"sections={len(titles)}",
            )
        except Exception as exc:
            logger.debug("非关键操作失败，已忽略: %s", exc)
    return content, citations


def _quiz_payload(session: Session, state_row: Any, kb_id: Any) -> tuple[str, list[ClassroomUiActionDTO], list[ClassroomCitationDTO]]:
    """生成课堂测验动作，优先使用平台题库，缺省时基于证据给出即时题。"""
    question = session.execute(
        select(training_questions)
        .where(training_questions.c.app_id == state_row["app_id"])
        .where(training_questions.c.status.in_(["approved", "published"]))
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


def _get_passing_score(state_row) -> int:
    """从会话 metadata 中读取通过分数线，默认 80。"""
    metadata = state_row["metadata"] or {}
    inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
    scenario_config = inputs.get("scenarioConfig") if isinstance(inputs, dict) else {}
    return int(scenario_config.get("passingScore", 80)) if isinstance(scenario_config, dict) else 80


def _count_sections(session: Session, kb_id: Any, query: str, session_id: str | None = None) -> int:
    """读取当前知识库证据总数，作为课程章节数。结果缓存到会话 metadata 中。"""
    # 尝试从缓存读取
    if session_id:
        row = session.execute(
            select(training_classroom_sessions.c.metadata)
            .where(training_classroom_sessions.c.session_id == session_id)
            .limit(1)
        ).scalar()
        meta = row if isinstance(row, dict) else {}
        cached = meta.get("_cached_section_count") if isinstance(meta, dict) else None
        if isinstance(cached, int) and cached > 0:
            return cached

    rows = read_training_evidence(session, kb_id, query, limit=50)
    count = len(rows)

    # 写入缓存
    if session_id and count > 0:
        _merge_session_metadata(session, session_id, {"_cached_section_count": count})

    return count


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
        if HAS_GRADING_SERVICE:
            try:
                result = grade_subjective_answer(
                    session,
                    question_id,
                    answer,
                    str(state_row["app_id"]),
                )
                return result.score, result.reason
            except Exception as exc:
                logger.debug("主观题 AI 批改失败，回退到规则评分: %s", exc)
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
        if HAS_SKILL_REGISTRY:
            try:
                record_training_skill_call(
                    session,
                    skill_name="classifyIntent",
                    status="success",
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    input_summary=query[:120],
                    output_summary=f"answer_len={len(response.answer)}",
                )
            except Exception as exc:
                logger.debug("Skill 审计记录失败: %s", exc)
        return response.answer, citations
    except Exception as exc:
        logger.debug("App Runtime 调用失败，回退到证据摘要: %s", exc)
        content, citations = _current_evidence(session, str(state_row["app_id"]), kb_id, state_row, query)
        if history:
            content = f"{content}\n\n我已结合最近 {len(history)} 条课堂消息继续讲解。"
        if HAS_SKILL_REGISTRY:
            try:
                record_training_skill_call(
                    session,
                    skill_name="classifyIntent",
                    status="fallback",
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    input_summary=query[:120],
                    output_summary=f"fallback_answer_len={len(content)}",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
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


def resolve_classroom_response_mode(
    *,
    event_type: str,
    result_state: str,
    response_context: dict[str, Any] | None = None,
) -> str:
    """确定性策略：根据事件类型和结果状态选择响应模式。"""
    ctx = response_context or {}
    if event_type in {"start_plan", "retry_teach", "next_section"} and result_state == "TEACH":
        return "teaching_narration"
    if event_type in {"submit_answer", "submit_quiz"} and result_state == "GRADE" and not ctx.get("passed", False):
        return "rag_explain"
    return "template"


def apply_classroom_domain_event(
    session: Session,
    credential: str,
    session_id: str,
    request: Any,
) -> ClassroomDomainResult:
    """执行课堂领域事件，返回结果（不含消息/事件持久化）。

    Graph Primary 路径调用此函数获取领域结果，
    再由 persist_classroom_domain_response 负责持久化。
    """
    state_row = _read_session(session, session_id)
    context = resolve_training_context(session, credential, str(state_row["app_id"]))
    current_state = state_row["current_state"]
    event_type = request.eventType
    payload = request.payload or {}

    if current_state == "COMPLETED":
        raise ClassroomEventError("课堂已完成，不能继续推进")

    # --- query 预处理 ---
    user_message: str | None = None
    if (event_type == "query" or request.query) and event_type != "continue":
        query = (request.query or payload.get("query") or "").strip()
        if not query:
            raise ClassroomEventError("query is required")
        user_message = query
        if _is_continue_intent(query):
            event_type = "continue"
            payload = {}
        elif _is_illegal_command(query):
            return ClassroomDomainResult(
                eventType="invalid_command",
                resultState=current_state,
                responseMode="template",
                visibleContent="当前阶段不允许通过文本指令跳过或结束课程，请按页面按钮完成学习流程。",
                uiActions=[_button_group(("继续学习", "continue", {}), ("继续追问", "query", {}))],
                userMessage=user_message,
                auditType="invalid_command",
            )
        elif _is_off_topic(query, state_row) and current_state in {"TEACH", "CHECK_UNDERSTAND", "OFF_TOPIC"}:
            return ClassroomDomainResult(
                eventType="off_topic",
                resultState="OFF_TOPIC",
                responseMode="template",
                visibleContent="这个问题偏离了当前课程目标。请回到当前课程内容，或提出与本节材料相关的问题。",
                uiActions=[_button_group(("回到课程", "continue", {}))],
                userMessage=user_message,
                auditType="off_topic",
            )

    # --- query 追问 ---
    if event_type == "query" or request.query:
        query_str = (request.query or payload.get("query") or "").strip()
        content, citations = _answer_query_with_agent(session, credential, state_row, context.kb_row["kb_id"], query_str)
        return ClassroomDomainResult(
            eventType="query",
            resultState="TEACH" if current_state in {"OFF_TOPIC", "CHECK_UNDERSTAND"} else current_state,
            responseMode="agent_task",
            visibleContent=content,
            uiActions=[_button_group(("听懂了，继续", "continue", {}), ("继续追问", "query", {}))],
            citations=citations,
            userMessage=user_message,
        )

    # --- start ---
    if event_type == "start":
        if not validate_classroom_transition(current_state, "PLAN"):
            raise ClassroomTransitionError(f"不允许从 {current_state} 流转到 PLAN")
        content, citations = _plan_content(session, context.kb_row["kb_id"], state_row)
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="PLAN",
            responseMode="template",
            visibleContent=content,
            uiActions=[_button_group(("开始学习", "continue", {}))],
            citations=citations,
            userMessage=user_message,
        )

    # --- continue/start_plan from PLAN ---
    if event_type in {"continue", "start_plan"} and current_state == "PLAN":
        content, citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], state_row)
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="TEACH",
            responseMode="teaching_narration",
            visibleContent=content,
            uiActions=[_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
            citations=citations,
            userMessage=user_message,
        )

    # --- continue from TEACH ---
    if event_type == "continue" and current_state == "TEACH":
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="CHECK_UNDERSTAND",
            responseMode="template",
            visibleContent="你理解了本节内容吗？如果已经听懂，可以继续进入测验；如果还有疑问，可以继续追问。",
            uiActions=[_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
            userMessage=user_message,
        )

    # --- continue/start_quiz from CHECK_UNDERSTAND ---
    if event_type in {"continue", "start_quiz"} and current_state == "CHECK_UNDERSTAND":
        visible, actions, citations = _quiz_payload(session, state_row, context.kb_row["kb_id"])
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="QUIZ",
            responseMode="template",
            visibleContent=visible,
            uiActions=actions,
            citations=citations,
            userMessage=user_message,
        )

    # --- submit_answer/submit_quiz from QUIZ ---
    if event_type in {"submit_answer", "submit_quiz"} and current_state == "QUIZ":
        score, explanation = _grade_answer(session, state_row, payload)
        passing_score = _get_passing_score(state_row)
        passed = score >= passing_score
        _merge_session_metadata(session, session_id, {"lastScore": score, "lastPassed": passed, "lastPassingScore": passing_score})
        if HAS_SKILL_REGISTRY:
            try:
                record_training_skill_call(
                    session,
                    skill_name="gradeSubjectiveAnswer",
                    status="success",
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    input_summary=f"questionId={payload.get('questionId', '')}",
                    output_summary=f"score={score},passed={passed}",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        if HAS_PROGRESS_SERVICE:
            try:
                q_id = str(payload.get("questionId") or "")
                if q_id and q_id != "inline-true-false":
                    q_row = session.execute(
                        select(training_questions.c.question_type)
                        .where(training_questions.c.question_id == q_id)
                        .limit(1)
                    ).scalar()
                    actual_question_type = q_row or "single_choice"
                    record_answer(
                        session,
                        session_id=session_id,
                        app_id=str(state_row["app_id"]),
                        end_user_id=str(state_row["end_user_id"]),
                        question_id=q_id,
                        question_type=actual_question_type,
                        answer=str(payload.get("answer", "")),
                        score=score,
                        is_correct=passed,
                        explanation=explanation,
                    )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        response_ctx = {"score": score, "passed": passed, "passingScore": passing_score}
        if passed:
            content = f"本次测验得分：{score}，达到通过线 {passing_score}。\n{explanation}"
            actions = [_button_group(("查看复习建议", "continue", {}))]
        else:
            content = f"本次测验得分：{score}，未达到通过线 {passing_score}。\n{explanation}"
            actions = [_button_group(("进入复习", "continue", {}))]
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="GRADE",
            responseMode=resolve_classroom_response_mode(event_type=event_type, result_state="GRADE", response_context=response_ctx),
            responseContext=response_ctx,
            visibleContent=content,
            uiActions=actions,
            userMessage=user_message,
        )

    # --- continue from GRADE ---
    if event_type == "continue" and current_state == "GRADE":
        metadata = state_row["metadata"] or {}
        last_passed = metadata.get("lastPassed", True) if isinstance(metadata, dict) else True
        if last_passed:
            content = "测验通过，以下是本节复习建议：请回顾关键知识点，巩固学习成果。"
            actions = [_button_group(("完成复习", "continue", {}))]
            return ClassroomDomainResult(
                eventType=event_type,
                resultState="REVIEW",
                responseMode="template",
                visibleContent=content,
                uiActions=actions,
                userMessage=user_message,
            )
        last_score = metadata.get("lastScore", 0) if isinstance(metadata, dict) else 0
        content, review_citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], state_row)
        content = f"测验未通过（得分 {last_score}），请回顾以下错题和相关材料：\n\n{content}"
        actions = [
            _button_group(
                ("重新学习", "retry_teach", {}),
                ("重新测验", "retry_quiz", {}),
                ("完成复习", "continue", {}),
            )
        ]
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="REVIEW",
            responseMode="rag_explain",
            visibleContent=content,
            uiActions=actions,
            citations=review_citations,
            userMessage=user_message,
        )

    # --- retry_teach/retry_quiz from REVIEW ---
    if event_type in {"retry_teach", "retry_quiz"} and current_state == "REVIEW":
        if event_type == "retry_teach":
            content, citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], state_row)
            return ClassroomDomainResult(
                eventType=event_type,
                resultState="TEACH",
                responseMode="teaching_narration",
                visibleContent=f"让我们重新学习本节内容。\n\n{content}",
                uiActions=[_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
                citations=citations,
                userMessage=user_message,
            )
        visible, actions, citations = _quiz_payload(session, state_row, context.kb_row["kb_id"])
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="QUIZ",
            responseMode="template",
            visibleContent=visible,
            uiActions=actions,
            citations=citations,
            userMessage=user_message,
        )

    # --- continue from REVIEW ---
    if event_type == "continue" and current_state == "REVIEW":
        metadata = state_row["metadata"] or {}
        last_passed = metadata.get("lastPassed", True) if isinstance(metadata, dict) else True
        if last_passed:
            content = "本节小结：请将关键流程、风险点和证据出处纳入实际作业。"
        else:
            content = "本节小结：你未通过测验，建议后续继续复习。请将关键流程、风险点和证据出处纳入实际作业。"
        _inputs = (state_row["metadata"] or {}).get("inputs", {})
        _query_str = _inputs.get("jobTitle", "") if isinstance(_inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], _query_str, session_id=session_id)
        current_index = state_row["current_section_index"]
        if current_index < total_sections - 1:
            actions = [_button_group(("下一节", "next_section", {}), ("完成课程", "complete", {}))]
        else:
            content += "\n\n所有章节已完成，你可以结束课程。"
            actions = [_button_group(("完成课程", "complete", {}))]
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="SUMMARY",
            responseMode="template",
            visibleContent=content,
            uiActions=actions,
            userMessage=user_message,
        )

    # --- next_section from SUMMARY ---
    if event_type == "next_section" and current_state == "SUMMARY":
        next_index = state_row["current_section_index"] + 1
        metadata = state_row["metadata"] or {}
        inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
        query_str = str(inputs.get("jobTitle", "")) if isinstance(inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], query_str, session_id=session_id)
        if next_index >= total_sections:
            raise ClassroomTransitionError(
                f"当前已是最后一节（index={state_row['current_section_index']}，共 {total_sections} 节），不能再进入下一节"
            )
        progress = ClassroomProgressUpdateDTO(sectionIndex=next_index, completedSections=next_index)
        next_state_row = dict(state_row)
        next_state_row["current_section_index"] = next_index
        content, citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], next_state_row)
        if HAS_PROGRESS_SERVICE:
            try:
                update_progress(
                    session,
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    end_user_id=str(state_row["end_user_id"]),
                    plan_id=str(state_row["plan_id"]) if state_row["plan_id"] else None,
                    current_section_index=next_index,
                    completed_sections=next_index,
                    total_sections=total_sections,
                    status="in_progress",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="TEACH",
            responseMode="teaching_narration",
            visibleContent=content,
            uiActions=[_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
            citations=citations,
            progressUpdate=progress,
            userMessage=user_message,
        )

    # --- complete from SUMMARY ---
    if event_type == "complete" and current_state == "SUMMARY":
        metadata = state_row["metadata"] or {}
        inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
        query_str = str(inputs.get("jobTitle", "")) if isinstance(inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], query_str, session_id=session_id)
        current_index = state_row["current_section_index"]
        if current_index < total_sections - 1:
            raise ClassroomTransitionError(
                f"当前在第 {current_index + 1} 节（共 {total_sections} 节），还有未完成的章节，请继续学习"
            )
        last_score_val = metadata.get("lastScore") if isinstance(metadata, dict) else None
        if HAS_PROGRESS_SERVICE:
            try:
                update_progress(
                    session,
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    end_user_id=str(state_row["end_user_id"]),
                    plan_id=str(state_row["plan_id"]) if state_row["plan_id"] else None,
                    current_section_index=current_index,
                    completed_sections=total_sections,
                    total_sections=total_sections,
                    last_score=int(last_score_val) if last_score_val is not None else None,
                    status="completed",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="COMPLETED",
            responseMode="template",
            visibleContent="课程已完成。",
            userMessage=user_message,
        )

    raise ClassroomTransitionError(f"不允许在 {current_state} 阶段执行 {event_type}")


def persist_classroom_domain_response(
    session: Session,
    session_id: str,
    state_row: Any,
    domain_result: ClassroomDomainResult,
    end_user_id: str,
    request_id: str | None = None,
) -> ClassroomEventResponse:
    """持久化课堂领域事件结果：写入消息、事件审计、更新状态。"""
    if domain_result.userMessage:
        _insert_message(session, session_id, "user", domain_result.userMessage, state_row["current_state"], end_user_id)

    event_payload: dict[str, Any] = {"eventType": domain_result.eventType}
    if domain_result.responseContext:
        event_payload["responseContext"] = domain_result.responseContext

    # 幂等快照：首次处理时保存完整响应快照
    if request_id:
        snapshot = {
            "eventType": domain_result.eventType,
            "resultState": domain_result.resultState,
            "visibleContent": domain_result.visibleContent,
            "responseMode": domain_result.responseMode,
            "uiActions": [a.model_dump() for a in domain_result.uiActions],
            "citations": [c.model_dump() for c in domain_result.citations],
            "progressUpdate": domain_result.progressUpdate.model_dump() if domain_result.progressUpdate else None,
        }
        event_payload["_runtime"] = {"requestId": request_id, "responseSnapshot": snapshot}

    event_id = _insert_event(
        session, session_id, domain_result.eventType,
        event_payload, domain_result.resultState, end_user_id,
        request_id=request_id,
    )
    _insert_message(
        session, session_id, "assistant", domain_result.visibleContent,
        domain_result.resultState, None,
        {"uiActions": [a.model_dump() for a in domain_result.uiActions]},
    )
    _update_state(
        session, session_id, domain_result.resultState, end_user_id,
        domain_result.progressUpdate.sectionIndex if domain_result.progressUpdate else None,
    )
    session.commit()

    has_answer_action = any(a.actionType in {"single_choice", "true_false", "subjective"} for a in domain_result.uiActions)
    requires_input = bool(domain_result.uiActions)
    return ClassroomEventResponse(
        eventId=event_id,
        sessionId=session_id,
        eventType=domain_result.eventType,
        resultState=domain_result.resultState,
        visibleContent=domain_result.visibleContent,
        classroomState=domain_result.resultState,
        uiActions=domain_result.uiActions,
        citations=domain_result.citations,
        control=ClassroomControlDTO(
            canProceed=not requires_input,
            requiresInput=requires_input,
            inputType="answer" if has_answer_action else ("action" if requires_input else None),
        ),
        progressUpdate=domain_result.progressUpdate,
        messages=[],
        createdAt=datetime.now(UTC).isoformat(),
    )


def submit_classroom_event(session: Session, credential: str, session_id: str, request: Any) -> ClassroomEventResponse:
    """提交课堂事件，由平台 Agent 状态机决定下一步输出。"""
    state_row = _read_session(session, session_id)
    request_id = getattr(request, "requestId", None)

    # 幂等保护：相同 sessionId + requestId 返回首次快照
    if request_id:
        existing = read_classroom_event_by_request_id(session, session_id, request_id)
        if existing is not None:
            payload = existing.get("payload", {}) if hasattr(existing, "keys") else {}
            runtime = payload.get("_runtime", {}) if isinstance(payload, dict) else {}
            snapshot = runtime.get("responseSnapshot", {})
            if snapshot:
                from app.schemas.training_classroom import ClassroomUiActionDTO, ClassroomCitationDTO, ClassroomProgressUpdateDTO
                ui_actions = [ClassroomUiActionDTO(**a) for a in snapshot.get("uiActions", [])]
                citations = [ClassroomCitationDTO(**c) for c in snapshot.get("citations", [])]
                progress_data = snapshot.get("progressUpdate")
                progress = ClassroomProgressUpdateDTO(**progress_data) if progress_data else None
                result_state = snapshot.get("resultState", state_row["current_state"])
                has_answer = any(a.actionType in {"single_choice", "true_false", "subjective"} for a in ui_actions)
                requires_input = bool(ui_actions)
                return ClassroomEventResponse(
                    eventId=str(existing["event_id"]) if "event_id" in existing else "",
                    sessionId=session_id,
                    eventType=snapshot.get("eventType", ""),
                    resultState=result_state,
                    visibleContent=snapshot.get("visibleContent", ""),
                    classroomState=result_state,
                    uiActions=ui_actions,
                    citations=citations,
                    control=ClassroomControlDTO(
                        canProceed=not requires_input,
                        requiresInput=requires_input,
                        inputType="answer" if has_answer else ("action" if requires_input else None),
                    ),
                    progressUpdate=progress,
                    createdAt=datetime.now(UTC).isoformat(),
                )

    domain_result = apply_classroom_domain_event(session, credential, session_id, request)
    return persist_classroom_domain_response(
        session, session_id, state_row, domain_result, state_row["end_user_id"],
        request_id=request_id,
    )
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
        passing_score = _get_passing_score(state_row)
        passed = score >= passing_score
        _merge_session_metadata(session, session_id, {"lastScore": score, "lastPassed": passed, "lastPassingScore": passing_score})
        if HAS_SKILL_REGISTRY:
            try:
                record_training_skill_call(
                    session,
                    skill_name="gradeSubjectiveAnswer",
                    status="success",
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    input_summary=f"questionId={payload.get('questionId', '')}",
                    output_summary=f"score={score},passed={passed}",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        if HAS_PROGRESS_SERVICE:
            try:
                q_id = str(payload.get("questionId") or "")
                if q_id and q_id != "inline-true-false":
                    # 查询实际题型，避免硬编码
                    q_row = session.execute(
                        select(training_questions.c.question_type)
                        .where(training_questions.c.question_id == q_id)
                        .limit(1)
                    ).scalar()
                    actual_question_type = q_row or "single_choice"
                    record_answer(
                        session,
                        session_id=session_id,
                        app_id=str(state_row["app_id"]),
                        end_user_id=str(state_row["end_user_id"]),
                        question_id=q_id,
                        question_type=actual_question_type,
                        answer=str(payload.get("answer", "")),
                        score=score,
                        is_correct=passed,
                        explanation=explanation,
                    )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        if passed:
            content = f"本次测验得分：{score}，达到通过线 {passing_score}。\n{explanation}"
            actions = [_button_group(("查看复习建议", "continue", {}))]
        else:
            content = f"本次测验得分：{score}，未达到通过线 {passing_score}。\n{explanation}"
            actions = [_button_group(("进入复习", "continue", {}))]
        return _event_to_response(
            session,
            state_row,
            event_type,
            "GRADE",
            content,
            actions,
            [],
            {**payload, "score": score, "passed": passed, "passingScore": passing_score},
        )

    if event_type == "continue" and current_state == "GRADE":
        metadata = state_row["metadata"] or {}
        last_passed = metadata.get("lastPassed", True) if isinstance(metadata, dict) else True
        if last_passed:
            content = "测验通过，以下是本节复习建议：请回顾关键知识点，巩固学习成果。"
            actions = [_button_group(("完成复习", "continue", {}))]
        else:
            last_score = metadata.get("lastScore", 0) if isinstance(metadata, dict) else 0
            content, review_citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], state_row)
            content = f"测验未通过（得分 {last_score}），请回顾以下错题和相关材料：\n\n{content}"
            actions = [
                _button_group(
                    ("重新学习", "retry_teach", {}),
                    ("重新测验", "retry_quiz", {}),
                    ("完成复习", "continue", {}),
                )
            ]
            return _event_to_response(session, state_row, event_type, "REVIEW", content, actions, review_citations, payload)
        return _event_to_response(session, state_row, event_type, "REVIEW", content, actions, [], payload)

    if event_type in {"retry_teach", "retry_quiz"} and current_state == "REVIEW":
        if event_type == "retry_teach":
            content, citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], state_row)
            return _event_to_response(
                session,
                state_row,
                event_type,
                "TEACH",
                f"让我们重新学习本节内容。\n\n{content}",
                [_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {}))],
                citations,
                payload,
            )
        # retry_quiz
        visible, actions, citations = _quiz_payload(session, state_row, context.kb_row["kb_id"])
        return _event_to_response(session, state_row, event_type, "QUIZ", visible, actions, citations, payload)

    if event_type == "continue" and current_state == "REVIEW":
        metadata = state_row["metadata"] or {}
        last_passed = metadata.get("lastPassed", True) if isinstance(metadata, dict) else True
        if last_passed:
            content = "本节小结：请将关键流程、风险点和证据出处纳入实际作业。"
        else:
            content = "本节小结：你未通过测验，建议后续继续复习。请将关键流程、风险点和证据出处纳入实际作业。"
        _inputs = (state_row["metadata"] or {}).get("inputs", {})
        _query_str = _inputs.get("jobTitle", "") if isinstance(_inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], _query_str, session_id=session_id)
        current_index = state_row["current_section_index"]
        if current_index < total_sections - 1:
            actions = [_button_group(("下一节", "next_section", {}), ("完成课程", "complete", {}))]
        else:
            content += "\n\n所有章节已完成，你可以结束课程。"
            actions = [_button_group(("完成课程", "complete", {}))]
        return _event_to_response(
            session,
            state_row,
            event_type,
            "SUMMARY",
            content,
            actions,
            [],
            payload,
        )

    if event_type == "next_section" and current_state == "SUMMARY":
        next_index = state_row["current_section_index"] + 1
        metadata = state_row["metadata"] or {}
        inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
        query_str = str(inputs.get("jobTitle", "")) if isinstance(inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], query_str, session_id=session_id)
        if next_index >= total_sections:
            raise ClassroomTransitionError(
                f"当前已是最后一节（index={state_row['current_section_index']}，共 {total_sections} 节），不能再进入下一节"
            )
        progress = ClassroomProgressUpdateDTO(sectionIndex=next_index, completedSections=next_index)
        next_state_row = dict(state_row)
        next_state_row["current_section_index"] = next_index
        content, citations = _current_evidence(session, str(state_row["app_id"]), context.kb_row["kb_id"], next_state_row)
        if HAS_PROGRESS_SERVICE:
            try:
                update_progress(
                    session,
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    end_user_id=str(state_row["end_user_id"]),
                    plan_id=str(state_row["plan_id"]) if state_row["plan_id"] else None,
                    current_section_index=next_index,
                    completed_sections=next_index,
                    total_sections=total_sections,
                    status="in_progress",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
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
        metadata = state_row["metadata"] or {}
        inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
        query_str = str(inputs.get("jobTitle", "")) if isinstance(inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], query_str, session_id=session_id)
        current_index = state_row["current_section_index"]
        if current_index < total_sections - 1:
            raise ClassroomTransitionError(
                f"当前在第 {current_index + 1} 节（共 {total_sections} 节），还有未完成的章节，请继续学习"
            )
        last_score_val = metadata.get("lastScore") if isinstance(metadata, dict) else None
        if HAS_PROGRESS_SERVICE:
            try:
                update_progress(
                    session,
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    end_user_id=str(state_row["end_user_id"]),
                    plan_id=str(state_row["plan_id"]) if state_row["plan_id"] else None,
                    current_section_index=current_index,
                    completed_sections=total_sections,
                    total_sections=total_sections,
                    last_score=int(last_score_val) if last_score_val is not None else None,
                    status="completed",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        return _event_to_response(session, state_row, event_type, "COMPLETED", "课程已完成。", [], [], payload)

    raise ClassroomTransitionError(f"不允许在 {current_state} 阶段执行 {event_type}")
