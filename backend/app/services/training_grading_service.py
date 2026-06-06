"""员工培训主观题 AI 批改服务。"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tables import training_questions
from app.services.training_agent_service import evidence_preview
from app.services.training_llm_client import LLMCallError, call_llm
from app.services.training_llm_json_service import TrainingLLMOutputError, parse_training_json
from app.services.training_skill_registry_service import record_training_skill_call

logger = logging.getLogger(__name__)

SKILL_NAME = "gradeSubjectiveAnswer"

DEFAULT_RUBRIC: dict[str, Any] = {
    "totalScore": 100,
    "criteria": [
        {"name": "内容相关性", "score": 40, "description": "回答与题目要求相关，不偏题。"},
        {"name": "知识准确性", "score": 40, "description": "回答中的知识点准确，无明显错误。"},
        {"name": "表达清晰度", "score": 20, "description": "表述清晰、有条理。"},
    ],
}


class SubjectiveGradeResult(BaseModel):
    """主观题评分结果 DTO。"""

    score: int = Field(ge=0, le=100)
    reason: str
    matchedCriteria: list[str] = Field(default_factory=list)
    needsManualReview: bool = False


def grade_subjective_answer(
    session: Session,
    question_id: str,
    answer: str,
    app_id: str,
) -> SubjectiveGradeResult:
    """对主观题进行 AI 辅助评分。

    从数据库读取题目 rubric，不信任客户端传入的评分标准。
    LLM 失败时回退到保守规则评分。
    """
    started_at = datetime.now(UTC)
    started_ms = perf_counter() * 1000

    question_row = session.execute(
        select(training_questions)
        .where(training_questions.c.question_id == question_id)
        .where(training_questions.c.app_id == app_id)
        .limit(1)
    ).mappings().first()

    if question_row is None:
        raise ValueError(f"题目 {question_id} 不存在或不属于当前应用。")

    if question_row["question_type"] != "subjective":
        raise ValueError(f"题目 {question_id} 类型为 {question_row['question_type']}，不是主观题。")

    rubric = question_row["rubric"] if isinstance(question_row["rubric"], dict) else None
    if not rubric or not rubric.get("criteria"):
        rubric = DEFAULT_RUBRIC

    question_content = question_row["content"] or ""
    evidence_chunk_ids = question_row["evidence_chunk_ids"] or []

    result: SubjectiveGradeResult | None = None
    llm_error: str | None = None

    try:
        result = _llm_grade(session, app_id, question_content, rubric, answer, evidence_chunk_ids)
    except Exception as exc:
        llm_error = str(exc)
        logger.warning("LLM 主观题评分失败，回退到规则评分: %s", exc)

    if result is None:
        result = _fallback_grade(answer, rubric)
        result.needsManualReview = True

    if result.score < 60:
        result.needsManualReview = True

    latency_ms = int(perf_counter() * 1000 - started_ms)
    _record_audit(session, app_id, question_id, result, llm_error, latency_ms)

    return result


def grade_subjective_answer_payload(
    session: Session,
    app_id: str,
    content: str,
    answer: str,
    rubric: dict[str, Any] | None,
    evidence_chunk_ids: list[str],
) -> SubjectiveGradeResult:
    """按 ex-app 传入的题目内容评分，不依赖平台题库 questionId。"""
    started_ms = perf_counter() * 1000
    normalized_rubric = rubric if isinstance(rubric, dict) and rubric.get("criteria") else DEFAULT_RUBRIC
    result: SubjectiveGradeResult | None = None
    llm_error: str | None = None

    try:
        result = _llm_grade(session, app_id, content, normalized_rubric, answer, evidence_chunk_ids)
    except Exception as exc:
        llm_error = str(exc)
        logger.warning("LLM 主观题评分失败，回退到规则评分: %s", exc)

    if result is None:
        result = _fallback_grade(answer, normalized_rubric)
        result.needsManualReview = True

    if result.score < 60:
        result.needsManualReview = True

    latency_ms = int(perf_counter() * 1000 - started_ms)
    _record_audit(session, app_id, "external-question-payload", result, llm_error, latency_ms)
    return result


def _llm_grade(
    session: Session,
    app_id: str,
    question_content: str,
    rubric: dict[str, Any],
    answer: str,
    evidence_chunk_ids: list[str],
) -> SubjectiveGradeResult:
    """调用 LLM 进行主观题评分。"""
    evidence_text = _build_evidence_text(session, app_id, question_content, evidence_chunk_ids)
    criteria_text = _format_criteria(rubric)
    prompt = _build_prompt(question_content, criteria_text, answer, evidence_text)

    raw_response = call_llm(prompt, temperature=0.1, max_tokens=1024)
    data = parse_training_json(
        raw_response,
        required_keys={"score", "reason"},
    )

    score = _clamp_score(data.get("score", 0))
    reason = str(data.get("reason", "LLM 评分完成。"))
    matched_criteria = [
        str(item) for item in data.get("matchedCriteria", []) if item
    ]

    return SubjectiveGradeResult(
        score=score,
        reason=reason,
        matchedCriteria=matched_criteria,
    )


def _build_evidence_text(
    session: Session,
    app_id: str,
    question_content: str,
    evidence_chunk_ids: list[str],
) -> str:
    """构建证据摘要文本。"""
    if not evidence_chunk_ids:
        return ""

    from app.tables import chunks

    rows = session.execute(
        select(chunks.c.content, chunks.c.heading, chunks.c.section)
        .where(chunks.c.chunk_id.in_(evidence_chunk_ids))
        .where(chunks.c.status == "active")
        .limit(6)
    ).mappings().all()

    if not rows:
        return ""

    parts = []
    for i, row in enumerate(rows, 1):
        title = row["heading"] or row["section"] or f"证据{i}"
        preview = evidence_preview(row, limit=300)
        parts.append(f"[{i}] {title}: {preview}")
    return "\n".join(parts)


def _format_criteria(rubric: dict[str, Any]) -> str:
    """将 rubric criteria 格式化为可读文本。"""
    criteria = rubric.get("criteria", [])
    if not criteria:
        return "无具体评分标准，请根据题目要求和知识库证据进行综合评判。"

    lines = []
    for item in criteria:
        name = item.get("name", "未命名")
        score = item.get("score", 0)
        desc = item.get("description", "")
        lines.append(f"- {name}（{score}分）：{desc}")
    return "\n".join(lines)


def _build_prompt(
    question_content: str,
    criteria_text: str,
    answer: str,
    evidence_text: str,
) -> list[dict[str, str]]:
    """构建 LLM 评分 prompt。"""
    system = (
        "你是一位专业的培训考核评分员。"
        "请根据题目、评分标准和知识库证据，对学员的主观题答案进行评分。"
        "返回严格 JSON 格式，包含以下字段：\n"
        "- score: 整数，0-100 分\n"
        "- reason: 字符串，评分理由\n"
        "- matchedCriteria: 字符串数组，学员满足的评分标准名称\n"
        "不要包含 markdown 标记或其他文本。"
    )

    user_parts = [f"## 题目\n{question_content}"]
    user_parts.append(f"## 评分标准\n{criteria_text}")
    if evidence_text:
        user_parts.append(f"## 知识库证据\n{evidence_text}")
    user_parts.append(f"## 学员答案\n{answer}")
    user_parts.append("请根据以上信息评分，返回 JSON。")

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def _clamp_score(score: Any) -> int:
    """将分数限制在 0-100 范围内。"""
    try:
        value = int(float(score))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, value))


def _fallback_grade(answer: str, rubric: dict[str, Any] | None) -> SubjectiveGradeResult:
    """保守规则评分，LLM 失败时使用。"""
    if not answer:
        return SubjectiveGradeResult(
            score=0,
            reason="未提交有效答案。",
            needsManualReview=True,
        )

    criteria = rubric.get("criteria", []) if isinstance(rubric, dict) else []
    base_score = 40 if len(answer) >= 20 else 20
    if criteria and len(answer) >= 50:
        base_score = 50

    return SubjectiveGradeResult(
        score=base_score,
        reason="LLM 评分不可用，已按保守规则初评分，建议管理员复核。",
        matchedCriteria=[],
        needsManualReview=True,
    )


def _record_audit(
    session: Session,
    app_id: str,
    question_id: str,
    result: SubjectiveGradeResult,
    llm_error: str | None,
    latency_ms: int,
) -> None:
    """记录评分 Skill 调用到审计表。"""
    status = "fallback" if llm_error else "success"
    error_code = None
    if llm_error:
        error_code = "LLM_ERROR"

    input_summary = json.dumps(
        {"questionId": question_id},
        ensure_ascii=False,
    )
    output_summary = json.dumps(
        {
            "score": result.score,
            "needsManualReview": result.needsManualReview,
        },
        ensure_ascii=False,
    )

    record_training_skill_call(
        session,
        skill_name=SKILL_NAME,
        status=status,
        app_id=app_id,
        input_summary=input_summary,
        output_summary=output_summary,
        error_code=error_code,
        latency_ms=latency_ms,
    )
