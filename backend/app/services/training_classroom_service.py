"""员工培训课堂 Agent 状态机和结构化输出服务。"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
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
from app.services.app_llm_audit_service import begin_app_llm_invocation, finish_app_llm_invocation
from app.services.training_agent_service import (
    TrainingAgentConflictError,
    TrainingAgentNotFoundError,
    evidence_preview,
    evidence_title,
    read_training_evidence,
    resolve_training_context,
)
from app.services.training_llm_client import call_llm
from app.tables import (
    rag_apps,
    training_classroom_events,
    training_classroom_messages,
    training_classroom_sessions,
    training_plans,
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


def _validate_course_snapshot(snapshot: Mapping[str, Any]) -> None:
    """校验文档内小节快照，防止旧顶层结构继续进入课堂。"""
    if "sections" in snapshot:
        raise ClassroomEventError("courseSnapshot 不允许顶层 sections")
    documents = snapshot.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ClassroomEventError("courseSnapshot.documents 不能为空")
    seen_section_ids: set[str] = set()
    for document in documents:
        if not isinstance(document, Mapping) or not document.get("documentId"):
            raise ClassroomEventError("courseSnapshot.documents contains invalid document")
        sections = document.get("sections")
        if not isinstance(sections, list) or not sections:
            raise ClassroomEventError("courseSnapshot document requires sections")
        for section in sections:
            if not isinstance(section, Mapping) or not section.get("sectionId") or not section.get("title"):
                raise ClassroomEventError("courseSnapshot document contains invalid section")
            section_id = str(section["sectionId"])
            if section_id in seen_section_ids:
                raise ClassroomEventError("courseSnapshot contains duplicate sectionId")
            seen_section_ids.add(section_id)


def create_classroom_session(session: Session, credential: str, request: Any) -> ClassroomSessionResponse:
    """创建平台侧课堂会话，后续上下文和状态以此为准。"""
    from app.services.agent_runtime.runtime_facade import resolve_runtime_version

    context = resolve_training_context(session, credential)
    now = datetime.now(UTC)
    session_id = new_id()
    runtime_version = resolve_runtime_version(getattr(request, "runtimeVersion", None))
    inputs = dict(request.inputs or {})
    snapshot = inputs.get("courseSnapshot")
    if isinstance(snapshot, dict):
        _validate_course_snapshot(snapshot)
    metadata = {"inputs": inputs, "source": "employee_training_agent"}
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
            {"label": "进入本节 Checkpoint", "eventType": "continue"},
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
        ]
    if current_state == "SUMMARY":
        if is_last_section:
            return [{"label": "完成课程", "eventType": "complete"}]
        return [{"label": "下一节", "eventType": "next_section"}]
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


def _mapping_get(row: Any, key: str, default: Any = None) -> Any:
    """兼容 dict 和 SQLAlchemy RowMapping，避免测试 mock 被误判为真实行。"""
    if isinstance(row, Mapping):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError):
        return default


def _read_learning_plan(session: Session, state_row: Any) -> Mapping[str, Any] | None:
    """读取课堂绑定的学习计划；未绑定或计划不可用时返回 None。"""
    plan_id = _mapping_get(state_row, "plan_id")
    app_id = _mapping_get(state_row, "app_id")
    if not isinstance(plan_id, str) or not plan_id:
        return None
    stmt = (
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    )
    if isinstance(app_id, str) and app_id:
        stmt = stmt.where(training_plans.c.app_id == app_id)
    row = session.execute(stmt.limit(1)).mappings().first()
    if not isinstance(row, Mapping) or row.get("status") == "rejected":
        return None
    return row


def _ordered_plan_documents(plan_row: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """按文档数组顺序返回计划文档。"""
    if plan_row is None:
        return []
    raw_documents = plan_row.get("documents") or []
    if not isinstance(raw_documents, list):
        return []
    documents = [item for item in raw_documents if isinstance(item, dict) and item.get("documentId")]
    return documents


def _ordered_course_sections(state_row: Any, plan_row: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """按文档顺序和文档内小节顺序展开课堂执行序列。"""
    metadata = _mapping_get(state_row, "metadata", {}) or {}
    inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
    snapshot = inputs.get("courseSnapshot") if isinstance(inputs, dict) else {}
    documents = snapshot.get("documents") if isinstance(snapshot, dict) else None
    if not isinstance(documents, list) and plan_row is not None:
        documents = plan_row.get("documents")
    sections: list[dict[str, Any]] = []
    if isinstance(documents, list):
        for document in documents:
            if not isinstance(document, Mapping) or not document.get("documentId"):
                continue
            document_id = str(document["documentId"])
            document_title = str(document.get("title") or document_id)
            for section in document.get("sections") or []:
                if not isinstance(section, Mapping) or not section.get("sectionId") or not section.get("title"):
                    continue
                sections.append({
                    **dict(section),
                    "documentId": document_id,
                    "documentTitle": document_title,
                })
    if sections:
        return sections

    # 仅用于恢复已经存在的旧课堂会话；新课堂快照入口会拒绝顶层 sections。
    raw_snapshot_sections = snapshot.get("sections") if isinstance(snapshot, dict) else None
    if isinstance(raw_snapshot_sections, list):
        legacy_sections = []
        for section in raw_snapshot_sections:
            source_ids = section.get("sourceDocumentIds") if isinstance(section, dict) else None
            if isinstance(source_ids, list) and len(source_ids) == 1:
                legacy_sections.append({**section, "documentId": str(source_ids[0])})
        if legacy_sections:
            return legacy_sections

    # 仅用于读取已经存在的旧计划。
    if plan_row is not None:
        plan_metadata = plan_row.get("metadata") or {}
        raw_sections = plan_metadata.get("sections") if isinstance(plan_metadata, dict) else None
        if isinstance(raw_sections, list):
            legacy_sections = []
            for section in raw_sections:
                source_ids = section.get("sourceDocumentIds") if isinstance(section, dict) else None
                if isinstance(source_ids, list) and len(source_ids) == 1:
                    legacy_sections.append({
                        **section,
                        "documentId": str(source_ids[0]),
                    })
            return legacy_sections
    return []


def _current_course_section(state_row: Any, plan_row: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """读取课堂当前结构化小节；旧课程没有 sections 时返回 None。"""
    sections = _ordered_course_sections(state_row, plan_row)
    if not sections:
        return None
    index = min(int(_mapping_get(state_row, "current_section_index", 0) or 0), len(sections) - 1)
    return sections[index]


def _plan_document_ids(plan_documents: list[dict[str, Any]]) -> list[str]:
    """提取计划文档 ID，供证据读取限定在学习计划范围内。"""
    return [str(item["documentId"]) for item in plan_documents if item.get("documentId")]


def _find_evidence_for_document(rows: list[Any], document_id: str) -> Any | None:
    """从召回证据中找到计划章节对应的文档片段。"""
    for row in rows:
        if str(_mapping_get(row, "document_id", "")) == document_id:
            return row
    return None


def _is_low_value_teaching_evidence(row: Any) -> bool:
    """识别不适合直接进入教学讲解的封面、目录等低价值证据。"""
    heading = "".join(str(_mapping_get(row, "heading", "") or "").lower().split())
    section = "".join(str(_mapping_get(row, "section", "") or "").lower().split())
    content = " ".join(str(_mapping_get(row, "content", "") or "").split())
    labels = {heading.strip("：:.-_"), section.strip("：:.-_")}
    low_value_labels = {
        "封面",
        "目录",
        "目次",
        "版本记录",
        "修订记录",
        "变更记录",
        "更改记录",
        "tableofcontents",
        "revisionhistory",
    }
    if labels & low_value_labels:
        return True
    if not content:
        return True
    if any(label.startswith(("附录", "appendix")) for label in labels if label) and len(content) <= 20:
        return True
    compact_content = "".join(content.split())
    if "目次" in compact_content and ("......" in compact_content or "规范性引用文件" in compact_content):
        return True
    if "......" in compact_content and ("记录表单" in compact_content or "参考文献" in compact_content):
        return True
    if "版本" in compact_content and "更改内容" in compact_content and "更改单编号" in compact_content:
        return True
    if "前言" in compact_content and "本标准" in compact_content and ("起草" in compact_content or "首次发布" in compact_content):
        return True
    if len(compact_content) <= 100 and "附录" in compact_content and "规范性附录" in compact_content:
        return True
    return (
        len(compact_content) <= 320
        and "企业标准" in compact_content
        and "发布" in compact_content
        and "实施" in compact_content
    )


def _filter_teaching_evidence(rows: list[Any]) -> list[Any]:
    """过滤不应进入教学讲解的低价值证据。"""
    return [row for row in rows if not _is_low_value_teaching_evidence(row)]


def _teaching_evidence_label(row: Any) -> str:
    """生成多证据教学包中的证据标签。"""
    metadata = _mapping_get(row, "metadata", {}) or {}
    metadata_title = metadata.get("title") if isinstance(metadata, dict) else None
    source = str(
        _mapping_get(row, "document_name")
        or metadata_title
        or f"文档 {str(_mapping_get(row, 'document_id', ''))[:8]}"
    )
    location = str(_mapping_get(row, "heading") or _mapping_get(row, "section") or "")
    return f"{source} / {location}" if location and location != source else source


def _build_teaching_evidence_packet(
    title: str,
    section: Mapping[str, Any] | None,
    rows: list[Any],
) -> tuple[str, list[ClassroomCitationDTO]]:
    """把当前小节的多个正文片段整理为供教学模型使用的结构化证据包。"""
    selected_rows = _filter_teaching_evidence(rows)[:4]
    if not selected_rows:
        return f"本节学习「{title}」。\n\n当前小节仅召回低教学价值片段，暂无可用于讲解的正文证据，请联系管理员复核课程材料。", []
    lines = [f"本节学习「{title}」。"]
    learning_objective = str(section.get("learningObjective") or "理解本节关键要求并能用于实际作业") if section is not None else "理解本节关键要求并能用于实际作业"
    lines.append(f"学习目标：{learning_objective}")
    key_points = [str(item) for item in (section.get("keyPoints") or []) if item] if section is not None else []
    criteria = section.get("checkpointCriteria") if section is not None else None
    core_explanation = "；".join(key_points) if key_points else "把多份证据中的前置条件、执行要求和异常处置串成完整作业流程"
    lines.extend([
        f"核心解释：本节重点不是记忆孤立条文，而是掌握「{core_explanation}」。",
        f"适用条件：当执行与「{title}」相关的现场作业、检查或异常处置时，应对照下方证据确认条件。",
        "风险点：跳过前置确认、异常处置或记录要求，会造成作业失控，也无法证明执行符合规范。",
        f"具体作业案例：开始「{title}」相关作业前先核对关键条件；发现条件不符合时暂停作业，按证据要求完成调整、确认和记录后再继续。",
    ])
    if isinstance(criteria, list) and criteria:
        lines.append("小节验收标准：" + "；".join(str(item) for item in criteria if item))
    lines.append("\n参考证据：")
    for index, row in enumerate(selected_rows, start=1):
        lines.append(f"{index}. [{_teaching_evidence_label(row)}] {evidence_preview(row, 420)}")
    lines.append("\n请基于以上证据理解关键要求；不清楚的地方可以继续追问。")
    citations = [
        ClassroomCitationDTO(
            documentId=str(_mapping_get(row, "document_id", "")),
            chunkId=str(_mapping_get(row, "chunk_id", "")) or None,
            content=evidence_preview(row, 180),
            score=1.0,
        )
        for row in selected_rows
    ]
    return "\n".join(lines), citations


def _render_teaching_script(title: str, section: Mapping[str, Any]) -> str | None:
    """将冻结的章节讲稿渲染为面向学员的课堂内容，不暴露 Chunk 原文。"""
    script = section.get("teachingScript")
    if not isinstance(script, Mapping):
        return None
    opening = str(script.get("opening") or "").strip()
    explanation = str(script.get("explanation") or "").strip()
    scenario = str(script.get("scenario") or "").strip()
    questions = [str(item).strip() for item in (script.get("interactionQuestions") or []) if str(item).strip()]
    summary = str(script.get("summary") or "").strip()
    if not all((opening, explanation, scenario, summary)):
        return None
    objective = str(section.get("learningObjective") or "理解本节要求并能应用到实际工作。")
    question_text = "\n".join(f"- {item}" for item in questions) if questions else "- 你会如何把本节要求应用到自己的岗位？"
    return (
        f"{title}\n\n"
        f"学习目标\n{objective}\n\n"
        f"情境导入\n{opening}\n\n"
        f"教师讲解\n{explanation}\n\n"
        f"工作案例\n{scenario}\n\n"
        f"想一想\n{question_text}\n\n"
        f"本节小结\n{summary}"
    )


def _has_prepared_teaching_script(state_row: Any, plan_row: Mapping[str, Any] | None = None) -> bool:
    """判断当前小节是否已有冻结讲稿，避免 Graph 再次改写。"""
    section = _current_course_section(state_row, plan_row)
    return bool(section and isinstance(section.get("teachingScript"), Mapping))


def _current_evidence(session: Session, app_id: str, kb_id: Any, state_row: Any, query: str = "") -> tuple[str, list[ClassroomCitationDTO]]:
    """读取当前章节证据，生成教学正文和引用。"""
    metadata = state_row["metadata"] or {}
    inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
    plan_row = _read_learning_plan(session, state_row)
    plan_documents = _ordered_plan_documents(plan_row)
    course_sections = _ordered_course_sections(state_row, plan_row)
    section = None
    if course_sections:
        section = course_sections[min(state_row["current_section_index"], len(course_sections) - 1)]
    document_ids = [str(section["documentId"])] if section is not None else _plan_document_ids(plan_documents)
    evidence_chunk_ids = section.get("evidenceChunkIds") if section is not None else None
    pinned_rows = []
    if isinstance(evidence_chunk_ids, list) and evidence_chunk_ids:
        pinned_rows = read_training_evidence(
            session,
            kb_id,
            "",
            limit=len(evidence_chunk_ids),
            document_ids=document_ids or None,
            chunk_ids=[str(chunk_id) for chunk_id in evidence_chunk_ids],
        )
    rows = read_training_evidence(
        session,
        kb_id,
        query or str(inputs.get("jobTitle", "")),
        limit=max(6, len(document_ids) * 3) if document_ids else 6,
        document_ids=document_ids or None,
    )
    if pinned_rows:
        seen_chunk_ids: set[str] = set()
        merged_rows = []
        for row in [*pinned_rows, *rows]:
            chunk_id = str(_mapping_get(row, "chunk_id", ""))
            if chunk_id in seen_chunk_ids:
                continue
            seen_chunk_ids.add(chunk_id)
            merged_rows.append(row)
        rows = merged_rows
    if not rows:
        if section is not None:
            return f"本节学习「{section['title']}」。\n\n当前小节暂无可引用的正文片段，请联系管理员复核课程证据。", []
        if plan_documents:
            index = min(state_row["current_section_index"], len(plan_documents) - 1)
            title = str(plan_documents[index].get("title") or "当前章节")
            return f"本节学习「{title}」。\n\n当前章节已来自学习计划，但知识库暂无可引用的正文片段，请联系管理员复核文档入库状态。", []
        return "当前知识库暂无可用于本课程的学习材料，请联系管理员补充文档。", []
    if section is not None:
        title = str(section["title"])
        if isinstance(evidence_chunk_ids, list) and evidence_chunk_ids:
            evidence_order = {str(chunk_id): index for index, chunk_id in enumerate(evidence_chunk_ids)}
            rows = sorted(
                rows,
                key=lambda row: evidence_order.get(str(_mapping_get(row, "chunk_id", "")), len(evidence_order)),
            )
    elif plan_documents:
        index = min(state_row["current_section_index"], len(plan_documents) - 1)
        plan_doc = plan_documents[index]
        document_id = str(plan_doc["documentId"])
        document_rows = [row for row in rows if str(_mapping_get(row, "document_id", "")) == document_id]
        rows = document_rows or [rows[min(index, len(rows) - 1)]]
        title = str(plan_doc.get("title") or evidence_title(rows[0]))
    else:
        index = min(state_row["current_section_index"], len(rows) - 1)
        rows = [rows[index]]
        title = evidence_title(rows[0])
    if section is not None:
        prepared_content = _render_teaching_script(title, section)
        if prepared_content is not None:
            selected_rows = _filter_teaching_evidence(rows)
            citations = [
                ClassroomCitationDTO(
                    documentId=str(_mapping_get(row, "document_id", "")),
                    chunkId=str(_mapping_get(row, "chunk_id", "")) or None,
                    content=evidence_preview(row, 180),
                    score=1.0,
                )
                for row in selected_rows
            ]
            return prepared_content, citations
    return _build_teaching_evidence_packet(title, section, rows)


def _plan_content(session: Session, kb_id: Any, state_row: Any) -> tuple[str, list[ClassroomCitationDTO]]:
    """生成课程目标说明。"""
    _meta = state_row["metadata"] or {}
    _inputs = _meta.get("inputs") if isinstance(_meta, dict) else {}
    _query = _inputs.get("jobTitle", "") if isinstance(_inputs, dict) else ""
    plan_row = _read_learning_plan(session, state_row)
    plan_documents = _ordered_plan_documents(plan_row)
    course_sections = _ordered_course_sections(state_row, plan_row)
    rows = read_training_evidence(
        session,
        kb_id,
        _query,
        limit=max(6, len(plan_documents) * 3) if plan_documents else 6,
        document_ids=_plan_document_ids(plan_documents) or None,
    )
    if course_sections:
        titles = [str(item["title"]) for item in course_sections]
        reason = str(plan_row.get("recommend_reason") or "").strip() if plan_row is not None else ""
        if not reason:
            reason = "已按可验证学习目标组织课程小节。"
        lines = [
            f"{index}. {section['title']}：{section.get('learningObjective', '')}"
            for index, section in enumerate(course_sections, start=1)
        ]
        content = f"本课程已按学习目标组织为 {len(course_sections)} 个小节。\n课程摘要：{reason}\n\n学习小节：\n" + "\n".join(lines)
        citations = []
    elif plan_documents:
        titles = [str(item.get("title") or item["documentId"]) for item in plan_documents]
        reason = str(plan_row.get("recommend_reason") or "").strip() if plan_row is not None else ""
        if not reason:
            reason = "已根据岗位目标和知识库材料生成学习计划。"
        lines = [f"{index}. {title}" for index, title in enumerate(titles, start=1)]
        content = f"本课程已关联学习计划。\n课程摘要：{reason}\n\n学习章节：\n" + "\n".join(lines)
        citations = []
        for doc in plan_documents[:3]:
            row = _find_evidence_for_document(rows, str(doc["documentId"]))
            citations.append(
                ClassroomCitationDTO(
                    documentId=str(doc["documentId"]),
                    chunkId=str(row["chunk_id"]) if row is not None else None,
                    content=evidence_preview(row, 120) if row is not None else str(doc.get("title") or ""),
                    score=1.0,
                )
            )
    else:
        titles = [evidence_title(row) for row in rows]
        if not titles:
            return "已初始化课程，但当前知识库没有可展示的学习材料。", []
        lines = [f"{index}. {title}" for index, title in enumerate(titles, start=1)]
        content = "本课程将按以下材料展开：\n" + "\n".join(lines)
        citations = [
            ClassroomCitationDTO(documentId=str(row["document_id"]), chunkId=str(row["chunk_id"]), content=evidence_preview(row, 120), score=1.0)
            for row in rows[:3]
        ]
    if not titles:
        return "已初始化课程，但当前知识库没有可展示的学习材料。", []
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


def _quiz_payload(session: Session, state_row: Any, kb_id: Any, session_id: str) -> tuple[str, list[ClassroomUiActionDTO], list[ClassroomCitationDTO]]:
    """基于当前小节讲稿调用 LLM 现场生成一道 Checkpoint 测验题。"""
    section = _current_course_section(state_row, _read_learning_plan(session, state_row))
    section_id = str(section["sectionId"]) if section is not None else "default"
    question_id = f"llm-quiz-{section_id}"

    # 从冻结讲稿提取教学内容作为出题上下文
    section_content = _render_teaching_script(str(section.get("title", "本节内容")), section) if section is not None else ""
    if not section_content:
        section_title = str(section.get("title", "本节内容")) if section is not None else "本节内容"
        section_content = section_title

    checkpoint_criteria = list(section.get("checkpointCriteria") or []) if section is not None else []
    criteria_hint = "验收标准：" + "；".join(checkpoint_criteria) if checkpoint_criteria else ""

    prompt = (
        "你是一个培训测验出题专家。根据以下教学内容，生成 1 道单选题（4 个选项，1 个正确答案）。\n"
        "题目应测试对内容的理解，而非简单记忆；干扰选项应基于材料内容，不能明显错误。\n\n"
        f"教学内容：\n{section_content[:3000]}\n\n"
        f"{criteria_hint}\n\n"
        '返回 JSON 格式：\n'
        '{"stem": "题目内容", '
        '"options": [{"label": "A", "text": "选项文本"}, {"label": "B", "text": "选项文本"}, '
        '{"label": "C", "text": "选项文本"}, {"label": "D", "text": "选项文本"}], '
        '"correctAnswer": "A", "explanation": "解析"}'
    )

    citations: list[ClassroomCitationDTO] = []
    try:
        audit = begin_app_llm_invocation(
            session,
            {"session_id": session_id, "app_id": str(state_row["app_id"])},
            endpoint="/api/v1/training/classroom/sessions/events",
            operation="generateCheckpointQuiz",
            skill_name="generateCheckpointQuiz",
            input_summary={"sectionId": section_id, "sectionContentLength": len(section_content)},
            user_content={"sectionId": section_id},
        )
    except Exception:
        audit = None

    try:
        raw = call_llm(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000,
            timeout=30,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)

        stem = str(parsed.get("stem", "")).strip()
        options = parsed.get("options", [])
        correct_answer = str(parsed.get("correctAnswer", "")).strip()
        explanation = str(parsed.get("explanation", "")).strip()

        if not stem or not options or not correct_answer:
            raise ValueError("LLM 返回的题目字段不完整")

        # 标准化：确保 correctAnswer 是选项标签（A/B/C/D）而非完整文本
        option_labels = [str(opt.get("label", "")) if isinstance(opt, dict) else "" for opt in options]
        option_texts = [str(opt.get("text", "")) if isinstance(opt, dict) else str(opt) for opt in options]
        if correct_answer not in option_labels:
            # LLM 可能返回了完整文本而非标签，尝试匹配
            for label, text in zip(option_labels, option_texts):
                if text and (correct_answer == text or correct_answer in text or text in correct_answer):
                    correct_answer = label
                    break

        if audit is not None:
            finish_app_llm_invocation(
                session, audit, status="success",
                assistant_content={"stem": stem, "optionCount": len(options)},
                response_summary={"sectionId": section_id, "questionId": question_id},
            )

        # 将正确答案存入会话 metadata，供评分时读取
        _merge_session_metadata(session, session_id, {
            "current_llm_quiz": {
                "questionId": question_id,
                "correctAnswer": correct_answer,
                "explanation": explanation or "请回看本节材料。",
                "options": options,
            },
        })

        action = ClassroomUiActionDTO(
            actionType="single_choice",
            data={
                "questionId": question_id,
                "content": stem,
                "options": options,
                "questionType": "single_choice",
                "sectionId": section_id,
                "checkpointCriteria": checkpoint_criteria,
                "evidenceChunkIds": [],
                "answerEventType": "submit_answer",
            },
        )
        return stem, [action], citations

    except Exception as exc:
        if audit is not None:
            try:
                finish_app_llm_invocation(
                    session, audit, status="error",
                    assistant_content={"error": str(exc)},
                    response_summary={"sectionId": section_id, "fallback": True},
                )
            except Exception:
                pass
        logger.warning("LLM 随堂测验生成失败，回退到判断题: %s", exc)
        # 回退：生成一道简单的判断题
        fallback_answer = "A"
        _merge_session_metadata(session, session_id, {
            "current_llm_quiz": {
                "questionId": question_id,
                "correctAnswer": fallback_answer,
                "explanation": "请回看本节材料。",
                "options": [{"label": "A", "text": "正确"}, {"label": "B", "text": "错误"}],
            },
        })
        fallback_content = f"请判断：根据本节内容，你是否理解了{section.get('title', '本节内容') if section is not None else '本节内容'}的核心要求？"
        action = ClassroomUiActionDTO(
            actionType="true_false",
            data={
                "questionId": question_id,
                "content": fallback_content,
                "options": [{"label": "A", "text": "正确"}, {"label": "B", "text": "错误"}],
                "questionType": "true_false",
                "sectionId": section_id,
                "checkpointCriteria": checkpoint_criteria,
                "evidenceChunkIds": [],
                "answerEventType": "submit_answer",
            },
        )
        return fallback_content, [action], citations


def _question_matches_section(question: Any, section: Mapping[str, Any] | None) -> bool:
    """判断题目证据是否属于当前结构化小节；旧课程继续兼容首道发布题目。"""
    if section is None:
        return True
    question_chunk_ids = {str(item) for item in (_mapping_get(question, "evidence_chunk_ids", []) or []) if item}
    section_chunk_ids = {str(item) for item in (section.get("evidenceChunkIds") or []) if item}
    if section_chunk_ids:
        return bool(question_chunk_ids & section_chunk_ids)
    metadata = _mapping_get(question, "metadata", {}) or {}
    document_id = str(metadata.get("documentId") or "") if isinstance(metadata, dict) else ""
    return bool(document_id and document_id == str(section.get("documentId") or ""))


def _checkpoint_feedback(section: Mapping[str, Any] | None, explanation: str, passed: bool) -> str:
    """把评分说明对齐到当前小节验收标准，形成可执行的通过或补强反馈。"""
    criteria = [str(item) for item in (section.get("checkpointCriteria") or []) if item] if section is not None else []
    if not criteria:
        return explanation
    label = "已验证的验收标准" if passed else "需要补强的验收标准"
    return f"{label}：{'；'.join(criteria)}。\n答题反馈：{explanation}"


def _passed_section_summary(
    section: Mapping[str, Any] | None,
    checkpoint_feedback: str = "",
) -> str:
    """使用本节讲稿生成通过小结，避免显示脱离课程上下文的通用复习话术。"""
    section = section or {}
    teaching_script = section.get("teachingScript") or {}
    summary = str(teaching_script.get("summary") or "").strip()
    if not summary:
        title = str(section.get("title") or "本节内容").strip()
        summary = f"你已完成“{title}”的学习，请把本节判断方法用于后续工作场景。"

    content = f"Checkpoint 已通过。\n\n本节复习建议：{summary}"
    if checkpoint_feedback:
        content += f"\n\n{checkpoint_feedback}"
    return content


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
        session_row = session.execute(
            select(training_classroom_sessions)
            .where(training_classroom_sessions.c.session_id == session_id)
            .limit(1)
        ).mappings().first()
        meta = session_row.get("metadata") if isinstance(session_row, Mapping) else {}
        course_sections = _ordered_course_sections(session_row) if isinstance(session_row, Mapping) else []
        if course_sections:
            count = len(course_sections)
            _merge_session_metadata(session, session_id, {"_cached_section_count": count})
            return count
        cached = meta.get("_cached_section_count") if isinstance(meta, dict) else None
        if isinstance(cached, int) and cached > 0:
            return cached
        plan_documents = _ordered_plan_documents(_read_learning_plan(session, session_row)) if isinstance(session_row, Mapping) else []
        if plan_documents:
            count = len(plan_documents)
            _merge_session_metadata(session, session_id, {"_cached_section_count": count})
            return count

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


def _grade_answer(session: Session, state_row: Any, payload: dict[str, Any], context: Any | None = None) -> tuple[int, str]:
    """从平台题库或内置题读取正确答案，避免信任客户端传入的答案。"""
    answer = str(payload.get("answer", "")).strip()
    question_id = str(payload.get("questionId") or "")
    if question_id == "inline-true-false" or not question_id:
        correct_answer = "true"
        is_correct = answer.lower() == correct_answer
        return (100 if is_correct else 0), ("回答正确。" if is_correct else "回答不正确，请回看本节材料。")

    # LLM 现场出题：从会话 metadata 读取正确答案
    if question_id.startswith("llm-quiz-"):
        metadata = state_row["metadata"] or {}
        quiz_meta = (metadata.get("current_llm_quiz") or {}) if isinstance(metadata, dict) else {}
        if str(quiz_meta.get("questionId", "")) != question_id:
            return 0, "测验题目已过期，请重新开始。"
        correct_answer = str(quiz_meta.get("correctAnswer", "")).strip()
        explanation = str(quiz_meta.get("explanation", "")).strip() or "请回看本节材料。"
        is_correct = answer.lower() == correct_answer.lower()
        return (100 if is_correct else 0), ("回答正确。" if is_correct else f"回答不正确，{explanation}")

    question = session.execute(
        select(training_questions)
        .where(training_questions.c.question_id == question_id)
        .where(training_questions.c.app_id == state_row["app_id"])
        .limit(1)
    ).mappings().first()
    if question is None:
        return 0, "题目不存在或不属于当前课堂应用。"
    section = _current_course_section(state_row, _read_learning_plan(session, state_row))
    if section is not None and not _question_matches_section(question, section):
        raise ClassroomEventError("提交的题目不属于当前小节 Checkpoint")
    if question["question_type"] == "subjective":
        if HAS_GRADING_SERVICE:
            audit = None
            if context is not None:
                audit = begin_app_llm_invocation(
                    session,
                    context,
                    endpoint="/api/v1/training/classroom/sessions/events",
                    operation="gradeSubjectiveAnswer",
                    skill_name="gradeSubjectiveAnswer",
                    input_summary={
                        "questionId": question_id,
                        "answerLength": len(answer),
                        "classroomSessionId": str(state_row["session_id"]),
                    },
                    user_content={
                        "questionId": question_id,
                        "answer": answer,
                    },
                )
            try:
                result = grade_subjective_answer(
                    session,
                    question_id,
                    answer,
                    str(state_row["app_id"]),
                )
                if audit is not None:
                    finish_app_llm_invocation(
                        session,
                        audit,
                        status="success",
                        assistant_content={
                            "questionId": question_id,
                            "score": result.score,
                            "needsManualReview": result.needsManualReview,
                            "fallback": False,
                        },
                        response_summary={
                            "questionId": question_id,
                            "score": result.score,
                            "needsManualReview": result.needsManualReview,
                            "fallback": False,
                        },
                    )
                return result.score, result.reason
            except Exception as exc:
                if audit is not None:
                    fallback_score, fallback_reason = _grade_subjective_answer(answer, question["rubric"])
                    finish_app_llm_invocation(
                        session,
                        audit,
                        status="success",
                        assistant_content={
                            "questionId": question_id,
                            "score": fallback_score,
                            "reason": fallback_reason,
                            "fallback": True,
                        },
                        response_summary={
                            "questionId": question_id,
                            "score": fallback_score,
                            "fallback": True,
                            "llmErrorCode": exc.__class__.__name__,
                        },
                    )
                    return fallback_score, fallback_reason
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


def _is_runtime_evidence_refusal(answer: str) -> bool:
    """识别 Runtime 因检索不到授权证据而返回的固定拒答。"""
    normalized = " ".join(answer.split())
    return any(
        phrase in normalized
        for phrase in (
            "当前用户没有可用于回答的授权证据",
            "资料不足，无法基于当前授权证据回答",
            "现有资料不足以回答",
        )
    )


def _answer_query_from_section_script(session: Session, state_row: Any, query: str) -> str | None:
    """以当前冻结讲稿为受控上下文回答课堂追问，不重新拼接或展示 Chunk。"""
    section = _current_course_section(state_row, _read_learning_plan(session, state_row))
    if section is None:
        return None
    title = str(section.get("title") or "当前小节").strip()
    script = _render_teaching_script(title, section)
    if not script:
        return None
    messages = [
        {
            "role": "system",
            "content": (
                "你是员工培训课堂教师。只能依据给定的当前小节讲稿回答，"
                "先直接回应问题，再用一个工作场景解释；不要提及 Chunk、检索或内部证据编号，"
                "不要照抄整段讲稿。若讲稿确实无法支持回答，请明确说本节材料未覆盖。"
            ),
        },
        {
            "role": "user",
            "content": f"当前小节讲稿：\n{script}\n\n学员追问：{query}",
        },
    ]
    try:
        return call_llm(messages, temperature=0.1, max_tokens=600, timeout=60).strip()
    except Exception as exc:
        logger.debug("章节讲稿追问生成失败: %s", exc)
        explanation = str((section.get("teachingScript") or {}).get("explanation") or "").strip()
        return f"结合本节内容：{explanation}" if explanation else None


def _answer_query_with_agent(
    session: Session,
    credential: str,
    state_row: Any,
    kb_id: Any,
    query: str,
) -> tuple[str, list[ClassroomCitationDTO]]:
    """新课程优先基于冻结章节讲稿回答，旧课程再使用 App Runtime 和证据摘要。"""
    from app.services.app_runtime_service import chat_with_app_runtime

    session_id = str(state_row["session_id"])
    history = _recent_context_messages(session, session_id)
    section_answer = _answer_query_from_section_script(session, state_row, query)
    if section_answer:
        return section_answer, []

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
        if _is_runtime_evidence_refusal(response.answer):
            section_answer = _answer_query_from_section_script(session, state_row, query)
            if section_answer:
                return section_answer, []
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
            uiActions=[_button_group(("进入本节 Checkpoint", "continue", {}), ("继续追问", "query", {}))],
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
        response_mode = "template" if _has_prepared_teaching_script(state_row, _read_learning_plan(session, state_row)) else "teaching_narration"
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="TEACH",
            responseMode=response_mode,
            visibleContent=content,
            uiActions=[_button_group(("进入本节 Checkpoint", "continue", {}), ("我还不清楚", "query", {}))],
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
        visible, actions, citations = _quiz_payload(session, state_row, context.kb_row["kb_id"], session_id)
        if not actions:
            raise ClassroomTransitionError(visible)
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
        score, explanation = _grade_answer(session, state_row, payload, context)
        passing_score = _get_passing_score(state_row)
        passed = score >= passing_score
        current_section = _current_course_section(state_row, _read_learning_plan(session, state_row))
        feedback = _checkpoint_feedback(current_section, explanation, passed)
        checkpoint_criteria = list(current_section.get("checkpointCriteria") or []) if current_section is not None else []
        _merge_session_metadata(
            session,
            session_id,
            {
                "lastScore": score,
                "lastPassed": passed,
                "lastPassingScore": passing_score,
                "lastQuestionId": str(payload.get("questionId") or ""),
                "lastSectionId": str(current_section["sectionId"]) if current_section is not None else None,
                "lastCheckpointCriteria": checkpoint_criteria,
                "lastCheckpointFeedback": feedback,
            },
        )
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
                        metadata={
                            "sectionId": str(current_section["sectionId"]) if current_section is not None else None,
                            "checkpointCriteria": checkpoint_criteria,
                        },
                    )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        response_ctx = {
            "score": score,
            "passed": passed,
            "passingScore": passing_score,
            "sectionId": str(current_section["sectionId"]) if current_section is not None else None,
            "checkpointCriteria": checkpoint_criteria,
        }
        if passed:
            content = f"本次测验得分：{score}，达到通过线 {passing_score}。\n{feedback}"
            actions = [_button_group(("查看复习建议", "continue", {}))]
        else:
            content = f"本次测验得分：{score}，未达到通过线 {passing_score}。\n{feedback}"
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
        checkpoint_feedback = str(metadata.get("lastCheckpointFeedback") or "") if isinstance(metadata, dict) else ""
        if last_passed:
            learning_plan = _read_learning_plan(session, state_row)
            current_section = _current_course_section(state_row, learning_plan)
            content = _passed_section_summary(current_section, checkpoint_feedback)
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
        feedback = checkpoint_feedback or "请根据本节验收标准重新梳理遗漏点。"
        content = f"测验未通过（得分 {last_score}）。\n{feedback}\n\n请回顾以下相关材料：\n\n{content}"
        actions = [
            _button_group(
                ("重新学习", "retry_teach", {}),
                ("重新测验", "retry_quiz", {}),
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
            response_mode = "template" if _has_prepared_teaching_script(state_row, _read_learning_plan(session, state_row)) else "teaching_narration"
            return ClassroomDomainResult(
                eventType=event_type,
                resultState="TEACH",
                responseMode=response_mode,
                visibleContent=f"让我们重新学习本节内容。\n\n{content}",
                uiActions=[_button_group(("进入本节 Checkpoint", "continue", {}), ("我还不清楚", "query", {}))],
                citations=citations,
                userMessage=user_message,
            )
        visible, actions, citations = _quiz_payload(session, state_row, context.kb_row["kb_id"], session_id)
        if not actions:
            raise ClassroomTransitionError(visible)
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
            learning_plan = _read_learning_plan(session, state_row)
            current_section = _current_course_section(state_row, learning_plan)
            content = _passed_section_summary(current_section)
        else:
            raise ClassroomTransitionError("当前小节尚未通过随堂测验，请重新学习或重新测验")
        _inputs = (state_row["metadata"] or {}).get("inputs", {})
        _query_str = _inputs.get("jobTitle", "") if isinstance(_inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], _query_str, session_id=session_id)
        current_index = state_row["current_section_index"]
        course_sections = _ordered_course_sections(state_row, _read_learning_plan(session, state_row))
        completed_section_ids = [
            str(item)
            for item in (metadata.get("completedSectionIds") or [])
            if item
        ] if isinstance(metadata, dict) else []
        if course_sections:
            current_section_id = str(course_sections[min(current_index, len(course_sections) - 1)]["sectionId"])
            if current_section_id not in completed_section_ids:
                completed_section_ids.append(current_section_id)
            _merge_session_metadata(session, session_id, {"completedSectionIds": completed_section_ids})
        completed_count = len(completed_section_ids) if course_sections else current_index + 1
        if HAS_PROGRESS_SERVICE:
            try:
                update_progress(
                    session,
                    session_id=session_id,
                    app_id=str(state_row["app_id"]),
                    end_user_id=str(state_row["end_user_id"]),
                    plan_id=str(state_row["plan_id"]) if state_row["plan_id"] else None,
                    current_section_index=current_index,
                    completed_sections=completed_count,
                    total_sections=total_sections,
                    last_score=int(metadata.get("lastScore")) if isinstance(metadata, dict) and metadata.get("lastScore") is not None else None,
                    status="in_progress",
                )
            except Exception as exc:
                logger.debug("非关键操作失败，已忽略: %s", exc)
        if current_index < total_sections - 1:
            actions = [_button_group(("下一节", "next_section", {}))]
        else:
            content += "\n\n所有章节已完成，你可以结束课程。"
            actions = [_button_group(("完成课程", "complete", {}))]
        return ClassroomDomainResult(
            eventType=event_type,
            resultState="SUMMARY",
            responseMode="template",
            visibleContent=content,
            uiActions=actions,
            progressUpdate=ClassroomProgressUpdateDTO(
                sectionIndex=current_index,
                sectionTotal=total_sections,
                completedSections=completed_count,
            ),
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
        response_mode = "template" if _has_prepared_teaching_script(next_state_row, _read_learning_plan(session, state_row)) else "teaching_narration"
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
            responseMode=response_mode,
            visibleContent=content,
            uiActions=[_button_group(("进入本节 Checkpoint", "continue", {}), ("我还不清楚", "query", {}))],
            citations=citations,
            progressUpdate=progress,
            userMessage=user_message,
        )

    # --- complete from SUMMARY ---
    if event_type == "complete" and current_state == "SUMMARY":
        metadata = state_row["metadata"] or {}
        if isinstance(metadata, dict) and "lastPassed" in metadata and not metadata.get("lastPassed"):
            raise ClassroomTransitionError("当前小节尚未通过 Checkpoint，不能完成课程")
        inputs = metadata.get("inputs") if isinstance(metadata, dict) else {}
        query_str = str(inputs.get("jobTitle", "")) if isinstance(inputs, dict) else ""
        total_sections = _count_sections(session, context.kb_row["kb_id"], query_str, session_id=session_id)
        current_index = state_row["current_section_index"]
        if current_index < total_sections - 1:
            raise ClassroomTransitionError(
                f"当前在第 {current_index + 1} 节（共 {total_sections} 节），还有未完成的章节，请继续学习"
            )
        course_sections = _ordered_course_sections(state_row, _read_learning_plan(session, state_row))
        if course_sections:
            required_section_ids = {str(item["sectionId"]) for item in course_sections}
            completed_section_ids = {str(item) for item in (metadata.get("completedSectionIds") or []) if item}
            missing_section_ids = required_section_ids - completed_section_ids
            if missing_section_ids:
                raise ClassroomTransitionError("仍有小节尚未通过 Checkpoint，不能完成课程")
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
