"""员工培训题库平台侧服务。"""
from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db_types import new_id
from app.schemas.training_question import (
    QuestionAppealDTO,
    QuestionAppealRequest,
    QuestionAppealResolveRequest,
    QuestionDraftDTO,
    QuestionOptionDTO,
    QuestionReviewRequest,
    QuestionUpdateRequest,
)
from app.services.app_llm_audit_service import begin_app_llm_invocation, finish_app_llm_invocation
from app.services.training_agent_service import (
    TrainingAgentConflictError,
    TrainingAgentNotFoundError,
    evidence_preview,
    read_training_evidence,
    resolve_training_context,
)
from app.services.task_manager import task_manager
from app.services.training_llm_client import LLMCallError, call_llm
from app.services.training_llm_json_service import TrainingLLMOutputError, parse_training_json
from app.services.training_skill_registry_service import record_training_skill_call
from app.tables import training_question_appeals, training_questions

logger = logging.getLogger(__name__)

QUESTION_TYPES = ("single_choice", "true_false", "subjective")
QUESTION_TYPE_RATIO = {
    "single_choice": 4,
    "true_false": 4,
    "subjective": 2,
}


def _question_count_from_request(request: Any) -> int:
    """读取本次每个文档的出题数量；请求未传时使用启动环境变量。"""
    if request.count is not None:
        return request.count
    return get_settings().training_questions_per_document


def _question_type_sequence(count: int) -> list[str]:
    """按 4:4:2 生成题型序列，10 题时为选择 4、判断 4、主观 2。"""
    if count <= 0:
        return []
    total_weight = sum(QUESTION_TYPE_RATIO.values())
    quotas = {
        question_type: count * weight / total_weight
        for question_type, weight in QUESTION_TYPE_RATIO.items()
    }
    distribution = {question_type: int(quota) for question_type, quota in quotas.items()}
    remaining = count - sum(distribution.values())
    order = sorted(
        QUESTION_TYPE_RATIO,
        key=lambda question_type: quotas[question_type] - distribution[question_type],
        reverse=True,
    )
    for question_type in order[:remaining]:
        distribution[question_type] += 1

    sequence: list[str] = []
    for question_type in QUESTION_TYPES:
        sequence.extend([question_type] * distribution[question_type])
    return sequence


def _align_llm_questions_to_ratio(
    llm_questions: list[dict[str, Any]] | None,
    question_types: list[str],
) -> list[dict[str, Any] | None]:
    """按目标题型序列消费 LLM 题目，比例不匹配的缺口交给模板回退。"""
    if not llm_questions:
        return [None for _ in question_types]

    used_indexes: set[int] = set()
    aligned: list[dict[str, Any] | None] = []
    for question_type in question_types:
        match_index = next(
            (
                index
                for index, question in enumerate(llm_questions)
                if index not in used_indexes and question.get("questionType") == question_type
            ),
            None,
        )
        if match_index is None:
            aligned.append(None)
            continue
        used_indexes.add(match_index)
        aligned.append(llm_questions[match_index])
    return aligned


def _build_question_payload(question_type: str, job_title: str, evidence: str) -> dict[str, Any]:
    """根据证据片段生成可审核的题目草稿。"""
    topic = job_title or "当前岗位"
    if question_type == "single_choice":
        return {
            "content": f"关于「{topic}」培训内容，下列哪项最符合知识库要求？",
            "options": [
                QuestionOptionDTO(label="A", text=evidence or "按照知识库要求执行关键流程。"),
                QuestionOptionDTO(label="B", text="可以跳过记录，凭经验处理。"),
                QuestionOptionDTO(label="C", text="遇到异常无需上报。"),
                QuestionOptionDTO(label="D", text="培训测验与上岗资格无关。"),
            ],
            "correctAnswer": "A",
            "explanation": "选项 A 与知识库证据一致，其余选项弱化了流程、记录或异常处理要求。",
            "rubric": None,
        }
    if question_type == "true_false":
        return {
            "content": f"判断题：{topic}学习时应以知识库中的流程和风险要求作为回答依据。",
            "options": [
                QuestionOptionDTO(label="true", text="正确"),
                QuestionOptionDTO(label="false", text="错误"),
            ],
            "correctAnswer": "true",
            "explanation": "员工培训测验需要可追溯到知识库证据。",
            "rubric": None,
        }
    return {
        "content": f"请结合材料说明「{topic}」在实际作业中应如何处理关键风险。",
        "options": [],
        "correctAnswer": None,
        "explanation": "主观题按要点覆盖度评分。",
        "rubric": {
            "totalScore": 5,
            "criteria": [
                {"name": "依据准确", "score": 2, "description": "回答能引用或复述知识库关键要求。"},
                {"name": "流程完整", "score": 2, "description": "覆盖准备、执行、异常处理或复盘等步骤。"},
                {"name": "表达清晰", "score": 1, "description": "表述具体、可执行。"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# LLM 辅助出题
# ---------------------------------------------------------------------------

_DEFAULT_SUBJECTIVE_RUBRIC: dict[str, Any] = {
    "totalScore": 5,
    "criteria": [
        {"name": "依据准确", "score": 2, "description": "能引用或复述关键要求。"},
        {"name": "流程完整", "score": 2, "description": "覆盖主要处理步骤。"},
        {"name": "表达清晰", "score": 1, "description": "表述具体、可执行。"},
    ],
}


def _build_llm_prompt(job_title: str, count: int, evidence_summaries: list[str]) -> list[dict[str, str]]:
    """构建 LLM 题库生成的消息列表。"""
    evidence_block = "\n".join(f"[{i + 1}] {text}" for i, text in enumerate(evidence_summaries)) if evidence_summaries else "（无可用证据）"
    system_msg = (
        "你是一位企业培训出题专家。根据提供的知识库证据，为指定岗位生成培训考核题目。\n"
        "要求：\n"
        "1. 题型比例为 single_choice:true_false:subjective = 4:4:2。\n"
        f"2. 共生成 {count} 道题。\n"
        "3. single_choice 题目必须有 4 个选项（label: A/B/C/D），correctAnswer 为正确选项 label。\n"
        "4. true_false 题目必须有 2 个选项（label: true/false），correctAnswer 为 true 或 false。\n"
        "5. subjective 题目 options 为空列表，correctAnswer 为 null，rubric.totalScore 必须为 5。\n"
        "6. subjective rubric.criteria 不超过 5 个，每个 name 尽量不超过 20 个汉字，description 简要说明评分标准。\n"
        "7. 每道题必须包含 explanation 字段，作为答案解读和参考资料。\n"
        "8. 输出严格 JSON 数组，不要包含任何额外文字。每项字段：questionType, content, options, correctAnswer, explanation, rubric。\n"
        "9. 严格按以下格式输出（options 不可省略）：\n"
        '   single_choice: {"questionType":"single_choice","content":"...","options":[{"label":"A","text":"..."},{"label":"B","text":"..."},{"label":"C","text":"..."},{"label":"D","text":"..."}],"correctAnswer":"A","explanation":"...","rubric":null}\n'
        '   true_false: {"questionType":"true_false","content":"...","options":[{"label":"true","text":"正确"},{"label":"false","text":"错误"}],"correctAnswer":"true","explanation":"...","rubric":null}\n'
        '   subjective: {"questionType":"subjective","content":"...","options":[],"correctAnswer":null,"explanation":"...","rubric":{"totalScore":5,"criteria":[{"name":"考点名称","score":1,"description":"评分说明"}]}}\n'
    )
    user_msg = (
        f"岗位名称：{job_title or '当前岗位'}\n\n"
        f"知识库证据：\n{evidence_block}\n\n"
        f"请生成 {count} 道题目，以 JSON 数组格式输出。"
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _validate_and_normalize_question(raw: dict[str, Any]) -> dict[str, Any] | None:
    """校验并规范化单道 LLM 生成的题目，不合法返回 None。"""
    question_type = str(raw.get("questionType") or "").strip()
    if question_type not in QUESTION_TYPES:
        return None
    content = str(raw.get("content") or "").strip()
    if not content:
        return None

    raw_options = raw.get("options") or []
    options: list[QuestionOptionDTO] = []
    for opt in raw_options:
        if isinstance(opt, dict) and "label" in opt and "text" in opt:
            options.append(QuestionOptionDTO(label=str(opt["label"]), text=str(opt["text"])))

    # 题型级别的 options 校验：选项数量不合规的题目直接丢弃，走模板兜底
    if question_type == "single_choice" and len(options) != 4:
        return None
    if question_type == "true_false" and len(options) != 2:
        return None

    correct_answer = raw.get("correctAnswer")
    if correct_answer is not None:
        correct_answer = str(correct_answer)
    explanation = raw.get("explanation")
    if explanation is not None:
        explanation = str(explanation)

    rubric = raw.get("rubric")
    if question_type == "subjective":
        if not isinstance(rubric, dict) or not rubric.get("criteria"):
            rubric = _DEFAULT_SUBJECTIVE_RUBRIC
        else:
            rubric = _normalize_subjective_rubric(rubric)
    else:
        rubric = None

    return {
        "questionType": question_type,
        "content": content,
        "options": options,
        "correctAnswer": correct_answer,
        "explanation": explanation,
        "rubric": rubric,
    }


def _normalize_subjective_rubric(rubric: dict[str, Any]) -> dict[str, Any]:
    """将主观题 rubric 规范为 5 分制，最多保留 5 个考点。"""
    criteria = rubric.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return _DEFAULT_SUBJECTIVE_RUBRIC

    total_score = 5
    normalized: list[dict[str, Any]] = []
    raw_total = rubric.get("totalScore") or sum(
        item.get("score", 0) for item in criteria if isinstance(item, dict)
    )
    try:
        raw_total_value = float(raw_total)
    except (TypeError, ValueError):
        raw_total_value = 0.0

    for index, item in enumerate(criteria[:5]):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or f"考点{index + 1}")[:20]
        description = str(item.get("description") or "按该考点给分。")
        try:
            raw_score = float(item.get("score", 0))
        except (TypeError, ValueError):
            raw_score = 0.0
        score = round(raw_score / raw_total_value * total_score, 2) if raw_total_value > 0 else 1
        normalized.append({"name": name, "score": score, "description": description})

    if not normalized:
        return _DEFAULT_SUBJECTIVE_RUBRIC

    score_sum = sum(float(item["score"]) for item in normalized)
    if score_sum != total_score:
        normalized[-1]["score"] = round(float(normalized[-1]["score"]) + total_score - score_sum, 2)
    return {"totalScore": total_score, "criteria": normalized}


def _generate_questions_with_llm(
    session: Session,
    *,
    job_title: str,
    count: int,
    evidence_summaries: list[str],
    app_id: str | None = None,
) -> list[dict[str, Any]] | None:
    """调用 LLM 生成题目列表，失败返回 None。"""
    messages = _build_llm_prompt(job_title, count, evidence_summaries)

    start = time.monotonic()
    try:
        raw_content = call_llm(messages, temperature=0.3, timeout=90)
    except (LLMCallError, Exception) as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.warning("LLM question generation failed: %s", exc)
        record_training_skill_call(
            session,
            skill_name="generateQuestionDrafts",
            status="error",
            app_id=app_id,
            input_summary=json.dumps({"jobTitle": job_title, "count": count}, ensure_ascii=False),
            error_code="LLM_ERROR",
            latency_ms=latency_ms,
        )
        session.flush()
        return None

    latency_ms = int((time.monotonic() - start) * 1000)

    # 解析 JSON
    try:
        data = parse_training_json(raw_content)
        if not isinstance(data, list):
            data = [data]
    except TrainingLLMOutputError as exc:
        logger.warning("LLM output parse failed: %s", exc)
        record_training_skill_call(
            session,
            skill_name="generateQuestionDrafts",
            status="error",
            app_id=app_id,
            input_summary=json.dumps({"jobTitle": job_title, "count": count}, ensure_ascii=False),
            error_code="LLM_PARSE_ERROR",
            latency_ms=latency_ms,
        )
        session.flush()
        return None

    # 校验并规范化每道题
    questions: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized = _validate_and_normalize_question(item)
        if normalized is not None:
            questions.append(normalized)

    if not questions:
        record_training_skill_call(
            session,
            skill_name="generateQuestionDrafts",
            status="error",
            app_id=app_id,
            input_summary=json.dumps({"jobTitle": job_title, "count": count}, ensure_ascii=False),
            error_code="LLM_VALIDATION_ERROR",
            latency_ms=latency_ms,
        )
        session.flush()
        return None

    record_training_skill_call(
        session,
        skill_name="generateQuestionDrafts",
        status="success",
        app_id=app_id,
        input_summary=json.dumps({"jobTitle": job_title, "count": count}, ensure_ascii=False),
        output_summary=json.dumps({"questionCount": len(questions)}, ensure_ascii=False),
        latency_ms=latency_ms,
    )
    session.flush()
    return questions


def create_question_drafts(session: Session, credential: str, request: Any, *, task_id: str | None = None) -> list[QuestionDraftDTO]:
    """基于知识库证据生成判断、选择和主观题草稿。

    优先使用 LLM 辅助出题，LLM 失败时静默回退到模板生成。
    """
    def _log(level: str, message: str) -> None:
        if task_id:
            task_manager.append_log(task_id, level, message)

    context = resolve_training_context(session, credential)
    _log("info", "正在初始化题目生成上下文...")
    audit = begin_app_llm_invocation(
        session,
        context,
        endpoint="/api/v1/training/questions/drafts",
        operation="generateQuestionDrafts",
        skill_name="generateQuestionDrafts",
        input_summary={
            "planId": request.planId,
            "jobTitle": request.jobTitle or "",
            "questionCount": _question_count_from_request(request),
            "abilityGroupCount": len(getattr(request, "abilityGroups", []) or []),
        },
        user_content={
            "planId": request.planId,
            "jobTitle": request.jobTitle or "",
            "abilityGroups": getattr(request, "abilityGroups", []) or [],
            "count": _question_count_from_request(request),
        },
    )
    try:
        now = datetime.now(UTC)
        question_count = _question_count_from_request(request)
        requested_document_ids = getattr(request, "documentIds", None) or []
        query = " ".join([request.jobTitle or "", *getattr(request, "abilityGroups", [])]).strip()

        responses: list[QuestionDraftDTO] = []
        fallback = False
        document_batches = requested_document_ids or [None]
        for batch_idx, document_id in enumerate(document_batches, 1):
            _log("info", f"正在读取知识库证据（批次 {batch_idx}/{len(document_batches)}）...")
            rows = read_training_evidence(
                session,
                context.kb_row["kb_id"],
                query,
                limit=max(1, question_count),
                document_ids=[document_id] if document_id else None,
            )
            if not rows:
                rows = []
            _log("info", f"读取到 {len(rows)} 条证据")

            _log("info", "正在调用 LLM 生成题目...")
            evidence_summaries = [evidence_preview(row) for row in rows]
            llm_questions = _generate_questions_with_llm(
                session,
                job_title=request.jobTitle or "",
                count=question_count,
                evidence_summaries=evidence_summaries,
                app_id=str(context.app_row["app_id"]),
            )
            fallback = fallback or not llm_questions
            if llm_questions:
                _log("info", f"LLM 生成了 {len(llm_questions)} 道题目")
            else:
                _log("warning", "LLM 生成失败，回退到模板生成")
            question_types = _question_type_sequence(question_count)
            aligned_llm_questions = _align_llm_questions_to_ratio(llm_questions, question_types)

            for index in range(question_count):
                responses.append(
                    _insert_question_draft(
                        session,
                        context,
                        request,
                        now,
                        rows,
                        aligned_llm_questions,
                        question_types,
                        index,
                        document_id,
                    )
                )

        _log("info", "正在保存题目草稿...")
        session.commit()
        question_ids = [item.questionId for item in responses]
        _log("info", f"题目草稿生成完成，共 {len(responses)} 道")
        finish_app_llm_invocation(
            session,
            audit,
            status="success",
            assistant_content={
                "planId": request.planId,
                "questionCount": len(responses),
                "questionIds": question_ids,
                "fallback": fallback,
            },
            response_summary={
                "planId": request.planId,
                "questionCount": len(responses),
                "questionIds": question_ids,
                "fallback": fallback,
                "llmErrorCode": "LLM_FALLBACK" if fallback else None,
            },
        )
        return responses
    except Exception as exc:
        session.rollback()
        _log("error", f"生成失败: {exc}")
        finish_app_llm_invocation(
            session,
            audit,
            status="failed",
            assistant_content={"error": str(exc)[:200]},
            response_summary={"error": str(exc)[:200]},
            error_code=exc.__class__.__name__,
        )
        raise


def _insert_question_draft(
    session: Session,
    context: Any,
    request: Any,
    now: datetime,
    rows: list,
    aligned_llm_questions: list[dict[str, Any] | None],
    question_types: list[str],
    index: int,
    requested_document_id: str | None,
) -> QuestionDraftDTO:
    """插入单道题目草稿，并保留所属文档 ID 以支持后续按文档抽题。"""
    row = rows[index % len(rows)] if rows else None
    evidence = evidence_preview(row) if row is not None else ""
    evidence_chunk_ids = [str(row["chunk_id"])] if row is not None else []
    document_id = str(row["document_id"]) if row is not None else requested_document_id

    if index < len(aligned_llm_questions) and aligned_llm_questions[index] is not None:
        q = aligned_llm_questions[index]
        question_type = q["questionType"]
        content = q["content"]
        options = q["options"]
        correct_answer = q["correctAnswer"]
        explanation = q["explanation"]
        rubric = q["rubric"]
        source = "llm"
    else:
        question_type = question_types[index]
        payload = _build_question_payload(question_type, request.jobTitle, evidence)
        content = payload["content"]
        options = payload["options"]
        correct_answer = payload["correctAnswer"]
        explanation = payload["explanation"]
        rubric = payload["rubric"]
        source = "template"

    question_id = new_id()
    session.execute(
        insert(training_questions).values(
            question_id=question_id,
            plan_id=request.planId,
            app_id=context.app_row["app_id"],
            question_type=question_type,
            category="practice",
            content=content,
            options=[option.model_dump() for option in options] if options else [],
            correct_answer=correct_answer,
            explanation=explanation,
            rubric=rubric,
            evidence_chunk_ids=evidence_chunk_ids,
            status="draft",
            metadata={"source": source, "evidence": evidence, "documentId": document_id},
            created_at=now,
            created_by=context.actor.user.userId,
            updated_at=now,
            updated_by=context.actor.user.userId,
        )
    )
    return QuestionDraftDTO(
        questionId=str(question_id),
        planId=request.planId,
        appId=str(context.app_row["app_id"]),
        documentId=document_id,
        questionType=question_type,
        category="practice",
        content=content,
        options=options,
        correctAnswer=correct_answer,
        explanation=explanation,
        rubric=rubric,
        evidenceChunkIds=evidence_chunk_ids,
        status="draft",
        createdAt=now.isoformat(),
    )


def _review_question(session: Session, question_id: str, user_id: str, new_status: str) -> QuestionDraftDTO:
    """通用审核逻辑：将 draft 题目改为 published/approved 或 rejected。"""
    row = session.execute(
        select(training_questions).where(training_questions.c.question_id == question_id)
    ).mappings().first()
    if row is None:
        raise TrainingAgentNotFoundError(f"Question {question_id} not found.")
    if row["status"] != "draft":
        raise TrainingAgentConflictError(
            f"Question {question_id} is '{row['status']}', only 'draft' questions can be reviewed."
        )

    now = datetime.now(UTC)
    existing_meta = dict(row["metadata"] or {})
    existing_meta["reviewedBy"] = user_id
    existing_meta["reviewedAt"] = now.isoformat()

    session.execute(
        update(training_questions)
        .where(training_questions.c.question_id == question_id)
        .values(
            status=new_status,
            updated_at=now,
            updated_by=user_id,
            metadata=existing_meta,
        )
    )
    session.commit()

    options = [QuestionOptionDTO(**o) for o in (row["options"] or [])]
    return QuestionDraftDTO(
        questionId=str(row["question_id"]),
        planId=str(row["plan_id"]),
        appId=str(row["app_id"]),
        documentId=(row["metadata"] or {}).get("documentId"),
        questionType=row["question_type"],
        category=row["category"],
        content=row["content"],
        options=options,
        correctAnswer=row["correct_answer"],
        explanation=row["explanation"],
        rubric=row["rubric"],
        evidenceChunkIds=row["evidence_chunk_ids"] or [],
        status=new_status,
        createdAt=row["created_at"].isoformat(),
        updatedAt=now.isoformat(),
    )


def review_question_with_credential(
    session: Session,
    credential: str,
    question_id: str,
    request: QuestionReviewRequest,
) -> QuestionDraftDTO:
    """ex-app 通过 App API Key 审核题目，平台校验题目归属后发布或拒绝。"""
    context = resolve_training_context(session, credential)
    row = session.execute(
        select(training_questions.c.app_id)
        .where(training_questions.c.question_id == question_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        raise TrainingAgentNotFoundError(f"Question {question_id} not found.")
    if str(row["app_id"]) != str(context.app_row["app_id"]):
        raise TrainingAgentConflictError("QUESTION_NOT_BELONG_TO_APP")
    reviewer_id = context.actor.user.userId
    if request.decision == "approved":
        return _review_question(session, question_id, reviewer_id, "published")
    return _review_question(session, question_id, reviewer_id, "rejected")


def update_question(
    session: Session,
    question_id: str,
    request: QuestionUpdateRequest,
    user_id: str,
) -> QuestionDraftDTO:
    """管理员修改题目内容、答案、解析、rubric 和证据引用。"""
    row = session.execute(
        select(training_questions).where(training_questions.c.question_id == question_id)
    ).mappings().first()
    if row is None:
        raise TrainingAgentNotFoundError(f"Question {question_id} not found.")
    if row["status"] not in {"draft", "published"}:
        raise TrainingAgentConflictError(f"Question {question_id} is '{row['status']}', cannot be updated.")

    values = _question_update_values(row, request)
    if not values:
        return _question_row_to_dto(row)

    now = datetime.now(UTC)
    values.update(updated_at=now, updated_by=user_id)
    session.execute(
        update(training_questions)
        .where(training_questions.c.question_id == question_id)
        .values(**values)
    )
    session.commit()
    updated_row = dict(row)
    updated_row.update(values)
    return _question_row_to_dto(updated_row)


def create_question_appeal(
    session: Session,
    credential: str,
    question_id: str,
    request: QuestionAppealRequest,
) -> QuestionAppealDTO:
    """学员上报题目异议，供管理员后续处理。"""
    context = resolve_training_context(session, credential)
    app_id = str(context.app_row["app_id"])
    question = session.execute(
        select(training_questions.c.question_id)
        .where(training_questions.c.question_id == question_id)
        .where(training_questions.c.app_id == app_id)
        .limit(1)
    ).scalar()
    if question is None:
        raise TrainingAgentNotFoundError(f"Question {question_id} not found.")

    now = datetime.now(UTC)
    appeal_id = new_id()
    metadata = {}
    if request.answerRecordId:
        metadata["answerRecordId"] = request.answerRecordId
    session.execute(
        training_question_appeals.insert().values(
            appeal_id=appeal_id,
            app_id=app_id,
            question_id=question_id,
            end_user_id=request.endUserId,
            reason=request.reason,
            status="open",
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    return QuestionAppealDTO(
        appealId=str(appeal_id),
        questionId=question_id,
        appId=app_id,
        endUserId=request.endUserId,
        reason=request.reason,
        status="open",
        createdAt=now.isoformat(),
    )


def resolve_question_appeal(
    session: Session,
    appeal_id: str,
    request: QuestionAppealResolveRequest,
    user_id: str,
) -> QuestionAppealDTO:
    """管理员处理题目异议。"""
    row = session.execute(
        select(training_question_appeals)
        .where(training_question_appeals.c.appeal_id == appeal_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        raise TrainingAgentNotFoundError(f"Question appeal {appeal_id} not found.")
    if row["status"] != "open":
        raise TrainingAgentConflictError("QUESTION_APPEAL_ALREADY_PROCESSED")

    now = datetime.now(UTC)
    metadata = dict(row["metadata"] or {})
    metadata.update({"processedBy": user_id, "processedAt": now.isoformat(), "notes": request.notes})
    session.execute(
        update(training_question_appeals)
        .where(training_question_appeals.c.appeal_id == appeal_id)
        .values(status=request.status, metadata=metadata, updated_at=now)
    )
    session.commit()
    return QuestionAppealDTO(
        appealId=str(row["appeal_id"]),
        questionId=str(row["question_id"]),
        appId=str(row["app_id"]),
        endUserId=row["end_user_id"],
        reason=row["reason"],
        status=request.status,
        createdAt=row["created_at"].isoformat(),
    )


def _question_update_values(row: Any, request: QuestionUpdateRequest) -> dict[str, Any]:
    """把 PATCH 请求转换成数据库更新字段。"""
    values: dict[str, Any] = {}
    if request.content is not None:
        values["content"] = request.content
    if request.options is not None:
        values["options"] = [item.model_dump() for item in request.options]
    if request.correctAnswer is not None:
        values["correct_answer"] = request.correctAnswer
    if request.explanation is not None:
        values["explanation"] = request.explanation
    if request.rubric is not None:
        if row["question_type"] != "subjective":
            raise TrainingAgentConflictError("ONLY_SUBJECTIVE_QUESTION_CAN_HAVE_RUBRIC")
        values["rubric"] = _normalize_subjective_rubric(request.rubric)
    if request.evidenceChunkIds is not None:
        values["evidence_chunk_ids"] = request.evidenceChunkIds
    if request.category is not None:
        values["category"] = request.category
    return values


def _question_row_to_dto(row: Any) -> QuestionDraftDTO:
    """将 training_questions 行转换为 DTO。"""
    options = [QuestionOptionDTO(**o) for o in (row["options"] or [])]
    updated_at = row.get("updated_at") if isinstance(row, dict) else row["updated_at"]
    created_at = row.get("created_at") if isinstance(row, dict) else row["created_at"]
    metadata = row.get("metadata") if isinstance(row, dict) else row["metadata"]
    return QuestionDraftDTO(
        questionId=str(row["question_id"]),
        planId=str(row["plan_id"]),
        appId=str(row["app_id"]),
        documentId=(metadata or {}).get("documentId"),
        questionType=row["question_type"],
        category=row["category"],
        content=row["content"],
        options=options,
        correctAnswer=row["correct_answer"],
        explanation=row["explanation"],
        rubric=row["rubric"],
        evidenceChunkIds=row["evidence_chunk_ids"] or [],
        status=row["status"],
        createdAt=created_at.isoformat(),
        updatedAt=updated_at.isoformat() if updated_at else None,
    )


def publish_question(session: Session, question_id: str, user_id: str) -> QuestionDraftDTO:
    """将 draft 题目发布为 published。"""
    return _review_question(session, question_id, user_id, "published")


def reject_question(session: Session, question_id: str, user_id: str) -> QuestionDraftDTO:
    """将 draft 题目拒绝为 rejected。"""
    return _review_question(session, question_id, user_id, "rejected")
