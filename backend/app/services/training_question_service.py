"""员工培训题库平台侧服务。"""
from __future__ import annotations

from datetime import UTC, datetime
from itertools import cycle
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.training_question import QuestionDraftDTO, QuestionOptionDTO
from app.services.training_agent_service import evidence_preview, read_training_evidence, resolve_training_context
from app.tables import training_questions


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


def create_question_drafts(session: Session, credential: str, request: Any) -> list[QuestionDraftDTO]:
    """基于知识库证据生成判断、选择和主观题草稿。"""
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

    question_cycle = cycle(QUESTION_TYPES)
    responses: list[QuestionDraftDTO] = []
    for index in range(request.count):
        question_type = next(question_cycle)
        row = rows[index % len(rows)] if rows else None
        evidence = evidence_preview(row) if row is not None else ""
        evidence_chunk_ids = [str(row["chunk_id"])] if row is not None else []
        payload = _build_question_payload(question_type, request.jobTitle, evidence)
        question_id = new_id()
        session.execute(
            insert(training_questions).values(
                question_id=question_id,
                plan_id=request.planId,
                app_id=context.app_row["app_id"],
                question_type=question_type,
                category="practice",
                content=payload["content"],
                options=[option.model_dump() for option in payload["options"]],
                correct_answer=payload["correctAnswer"],
                explanation=payload["explanation"],
                rubric=payload["rubric"],
                evidence_chunk_ids=evidence_chunk_ids,
                status="draft",
                metadata={"source": "employee_training_agent", "evidence": evidence},
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
                content=payload["content"],
                options=payload["options"],
                correctAnswer=payload["correctAnswer"],
                explanation=payload["explanation"],
                rubric=payload["rubric"],
                evidenceChunkIds=evidence_chunk_ids,
                status="draft",
                createdAt=now.isoformat(),
            )
        )

    session.commit()
    return responses
