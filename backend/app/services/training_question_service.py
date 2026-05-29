"""员工培训题库平台侧服务。"""
from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from itertools import cycle, islice
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.training_question import QuestionDraftDTO, QuestionOptionDTO
from app.services.training_agent_service import (
    TrainingAgentConflictError,
    TrainingAgentNotFoundError,
    evidence_preview,
    read_training_evidence,
    resolve_training_context,
)
from app.services.training_llm_client import LLMCallError, call_llm
from app.services.training_llm_json_service import TrainingLLMOutputError, parse_training_json
from app.services.training_skill_registry_service import record_training_skill_call
from app.tables import training_questions

logger = logging.getLogger(__name__)

QUESTION_TYPES = ("single_choice", "true_false", "subjective")


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
            "totalScore": 100,
            "criteria": [
                {"name": "依据准确", "score": 40, "description": "回答能引用或复述知识库关键要求。"},
                {"name": "流程完整", "score": 40, "description": "覆盖准备、执行、异常处理或复盘等步骤。"},
                {"name": "表达清晰", "score": 20, "description": "表述具体、可执行。"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# LLM 辅助出题
# ---------------------------------------------------------------------------

_DEFAULT_SUBJECTIVE_RUBRIC: dict[str, Any] = {
    "totalScore": 100,
    "criteria": [
        {"name": "依据准确", "score": 40, "description": "回答能引用或复述知识库关键要求。"},
        {"name": "流程完整", "score": 40, "description": "覆盖准备、执行、异常处理或复盘等步骤。"},
        {"name": "表达清晰", "score": 20, "description": "表述具体、可执行。"},
    ],
}


def _build_llm_prompt(job_title: str, count: int, evidence_summaries: list[str]) -> list[dict[str, str]]:
    """构建 LLM 题库生成的消息列表。"""
    evidence_block = "\n".join(f"[{i + 1}] {text}" for i, text in enumerate(evidence_summaries)) if evidence_summaries else "（无可用证据）"
    system_msg = (
        "你是一位企业培训出题专家。根据提供的知识库证据，为指定岗位生成培训考核题目。\n"
        "要求：\n"
        f"1. 共生成 {count} 道题，题型在 single_choice、true_false、subjective 中均匀分配。\n"
        "2. single_choice 题目必须有 4 个选项（label: A/B/C/D），correctAnswer 为正确选项 label。\n"
        "3. true_false 题目必须有 2 个选项（label: true/false），correctAnswer 为 true 或 false。\n"
        "4. subjective 题目 options 为空列表，correctAnswer 为 null，必须包含 rubric（totalScore: 100，criteria 数组每项含 name/score/description）。\n"
        "5. 每道题必须包含 explanation 字段。\n"
        "6. 输出严格 JSON 数组，不要包含任何额外文字。每项字段：questionType, content, options, correctAnswer, explanation, rubric。\n"
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
        rubric = None

    return {
        "questionType": question_type,
        "content": content,
        "options": options,
        "correctAnswer": correct_answer,
        "explanation": explanation,
        "rubric": rubric,
    }


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


def create_question_drafts(session: Session, credential: str, request: Any) -> list[QuestionDraftDTO]:
    """基于知识库证据生成判断、选择和主观题草稿。

    优先使用 LLM 辅助出题，LLM 失败时静默回退到模板生成。
    """
    context = resolve_training_context(session, credential, request.appId)
    now = datetime.now(UTC)
    query = " ".join([request.jobTitle or "", *getattr(request, "abilityGroups", [])]).strip()
    rows = read_training_evidence(
        session,
        context.kb_row["kb_id"],
        query,
        limit=max(1, request.count),
        document_ids=getattr(request, "documentIds", None) or None,
    )
    if not rows:
        rows = []

    evidence_summaries = [evidence_preview(row) for row in rows]
    llm_questions = _generate_questions_with_llm(
        session,
        job_title=request.jobTitle or "",
        count=request.count,
        evidence_summaries=evidence_summaries,
        app_id=str(context.app_row["app_id"]),
    )

    responses: list[QuestionDraftDTO] = []
    for index in range(request.count):
        row = rows[index % len(rows)] if rows else None
        evidence = evidence_preview(row) if row is not None else ""
        evidence_chunk_ids = [str(row["chunk_id"])] if row is not None else []

        if llm_questions and index < len(llm_questions):
            q = llm_questions[index]
            question_type = q["questionType"]
            content = q["content"]
            options = q["options"]
            correct_answer = q["correctAnswer"]
            explanation = q["explanation"]
            rubric = q["rubric"]
            source = "llm"
        else:
            question_cycle = cycle(QUESTION_TYPES)
            question_type = next(islice(question_cycle, index % len(QUESTION_TYPES), None))
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
                metadata={"source": source, "evidence": evidence},
                created_at=now,
                created_by=context.actor.user.userId,
                updated_at=now,
                updated_by=context.actor.user.userId,
            )
        )
        responses.append(
            QuestionDraftDTO(
                questionId=str(question_id),
                planId=request.planId,
                appId=str(context.app_row["app_id"]),
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
        )

    session.commit()
    return responses


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


def publish_question(session: Session, question_id: str, user_id: str) -> QuestionDraftDTO:
    """将 draft 题目发布为 published。"""
    return _review_question(session, question_id, user_id, "published")


def reject_question(session: Session, question_id: str, user_id: str) -> QuestionDraftDTO:
    """将 draft 题目拒绝为 rejected。"""
    return _review_question(session, question_id, user_id, "rejected")
