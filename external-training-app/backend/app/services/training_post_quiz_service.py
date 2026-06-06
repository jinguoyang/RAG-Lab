"""课后测验本地服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from app.core.database import new_id
from app.tables import training_classroom_sessions, training_post_quizzes, training_questions


class TrainingPostQuizConflictError(ValueError):
    """课后测验调用冲突。"""


class TrainingPostQuizNotFoundError(Exception):
    """课后测验不存在。"""


def _platform_client():
    """创建平台客户端，用于主观题评分能力。"""
    from app.core.config import get_settings
    from app.services.platform_client import PlatformClient

    settings = get_settings()
    return PlatformClient(settings.platform_base_url, settings.platform_api_key)


def create_post_quiz(session: Session, request: Any) -> dict:
    """从 ex-app 本地已发布题库创建课后测验。"""
    session_row = session.execute(
        select(training_classroom_sessions).where(training_classroom_sessions.c.session_id == request.sessionId)
    ).mappings().first()
    if session_row is None:
        raise TrainingPostQuizConflictError(f"课堂会话 {request.sessionId} 不存在")
    if session_row["end_user_id"] != request.endUserId:
        raise TrainingPostQuizConflictError("课堂会话与学员不匹配")
    if session_row["current_state"] != "COMPLETED":
        raise TrainingPostQuizConflictError("文档尚未完成学习，不能开始课后测验")

    rows = session.execute(
        select(training_questions)
        .where(training_questions.c.status == "published")
        .where(training_questions.c.app_id == session_row["app_id"])
        .order_by(training_questions.c.created_at.asc())
    ).mappings().all()
    document_questions = [
        row for row in rows
        if str((row["metadata"] or {}).get("documentId") or "") == request.documentId
    ]
    selected = _select_questions(document_questions, request.count or 5)
    if not selected:
        raise TrainingPostQuizConflictError("当前文档没有可用的已审核题目")

    now = datetime.now(timezone.utc)
    quiz_id = new_id()
    question_snapshot = [_question_snapshot(row) for row in selected]
    session.execute(
        training_post_quizzes.insert().values(
            quiz_id=quiz_id,
            session_id=request.sessionId,
            plan_id=request.planId or session_row["plan_id"],
            app_id=session_row["app_id"],
            end_user_id=request.endUserId,
            document_id=request.documentId,
            questions=question_snapshot,
            status="started",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    return {
        "quizId": quiz_id,
        "sessionId": request.sessionId,
        "appId": session_row["app_id"],
        "endUserId": request.endUserId,
        "documentId": request.documentId,
        "questions": [_public_question(item) for item in question_snapshot],
        "status": "started",
        "createdAt": now.isoformat(),
    }


def submit_post_quiz(session: Session, quiz_id: str, request: Any) -> dict:
    """提交并评分 ex-app 本地课后测验。"""
    import httpx

    quiz = session.execute(
        select(training_post_quizzes).where(training_post_quizzes.c.quiz_id == quiz_id)
    ).mappings().first()
    if quiz is None:
        raise TrainingPostQuizNotFoundError(f"课后测验 {quiz_id} 不存在")
    if quiz["end_user_id"] != request.endUserId:
        raise TrainingPostQuizConflictError("课后测验与学员不匹配")
    if quiz["status"] == "submitted":
        raise TrainingPostQuizConflictError("课后测验已提交")

    answer_by_id = {item["questionId"]: item["answer"] for item in request.answers}
    results = []
    total_score = 0.0
    for question in quiz["questions"]:
        answer = answer_by_id.get(question["questionId"], "")
        if question["questionType"] == "subjective":
            try:
                graded = _platform_client().grade_subjective_answer({
                    "content": question["content"],
                    "answer": answer,
                    "rubric": question.get("rubric"),
                    "evidenceChunkIds": question.get("evidenceChunkIds") or [],
                })
                score = float(graded.get("score", 0))
                passed = bool(graded.get("passed", score > 4))
                explanation = graded.get("reason")
            except httpx.HTTPError as exc:
                raise TrainingPostQuizConflictError(f"平台主观题评分失败: {exc}") from exc
            is_correct = None
        else:
            is_correct = str(answer).strip() == str(question.get("correctAnswer") or "").strip()
            score = 5.0 if is_correct else 0.0
            passed = is_correct
            explanation = question.get("explanation")
        total_score += score
        results.append({
            "questionId": question["questionId"],
            "questionType": question["questionType"],
            "score": score,
            "passed": passed,
            "isCorrect": is_correct,
            "explanation": explanation,
        })

    passed_all = all(item["passed"] for item in results)
    submitted_at = datetime.now(timezone.utc)
    if passed_all:
        _mark_document_completed(session, quiz, submitted_at)
    session.execute(
        sa_update(training_post_quizzes)
        .where(training_post_quizzes.c.quiz_id == quiz_id)
        .values(
            answers=request.answers,
            results=results,
            score=total_score,
            passed=passed_all,
            status="submitted",
            submitted_at=submitted_at,
            updated_at=submitted_at,
        )
    )
    session.commit()
    return {
        "quizId": quiz_id,
        "score": total_score,
        "passed": passed_all,
        "results": results,
        "submittedAt": submitted_at.isoformat(),
    }


def _mark_document_completed(session: Session, quiz: Any, now: datetime) -> None:
    """课后测验通过后，在 ex-app 本地课堂会话标记文档完成。"""
    session_row = session.execute(
        select(training_classroom_sessions).where(training_classroom_sessions.c.session_id == quiz["session_id"])
    ).mappings().first()
    if session_row is None:
        return
    metadata = dict(session_row["metadata"] or {})
    completed = list(metadata.get("completedDocumentIds") or [])
    if quiz["document_id"] not in completed:
        completed.append(quiz["document_id"])
    metadata["completedDocumentIds"] = completed
    session.execute(
        sa_update(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == quiz["session_id"])
        .values(metadata=metadata, updated_at=now)
    )


def _select_questions(rows: list[Any], count: int) -> list[Any]:
    """按 4:4:2 近似比例从本地题库抽题。"""
    buckets = {"single_choice": [], "true_false": [], "subjective": []}
    for row in rows:
        buckets.setdefault(row["question_type"], []).append(row)

    if count == 5:
        targets = {"single_choice": 2, "true_false": 2, "subjective": 1}
    else:
        targets = {
            "single_choice": round(count * 0.4),
            "true_false": round(count * 0.4),
            "subjective": max(0, count - round(count * 0.4) * 2),
        }

    selected = []
    for question_type, target in targets.items():
        selected.extend(buckets.get(question_type, [])[:target])
    if len(selected) < count:
        selected_ids = {row["question_id"] for row in selected}
        for row in rows:
            if row["question_id"] not in selected_ids:
                selected.append(row)
            if len(selected) >= count:
                break
    return selected[:count]


def _question_snapshot(row: Any) -> dict:
    """冻结测验题目快照，保证提交时评分依据不漂移。"""
    return {
        "questionId": row["question_id"],
        "questionType": row["question_type"],
        "content": row["content"],
        "options": row["options"] or [],
        "correctAnswer": row["correct_answer"],
        "explanation": row["explanation"],
        "rubric": row["rubric"],
        "evidenceChunkIds": row["evidence_chunk_ids"] or [],
    }


def _public_question(question: dict) -> dict:
    """返回给学员的题目不包含标准答案。"""
    return {
        "questionId": question["questionId"],
        "questionType": question["questionType"],
        "content": question["content"],
        "options": question.get("options") or [],
        "rubric": question.get("rubric"),
    }
