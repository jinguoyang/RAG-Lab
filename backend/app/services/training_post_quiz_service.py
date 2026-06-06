"""员工培训课后测验服务。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db_types import new_id
from app.schemas.training_post_quiz import (
    PostQuizDTO,
    PostQuizQuestionDTO,
    PostQuizStartRequest,
    PostQuizSubmissionDTO,
    PostQuizSubmitRequest,
    PostQuizResultItemDTO,
)
from app.schemas.training_question import QuestionOptionDTO
from app.services.training_agent_service import TrainingAgentConflictError, TrainingAgentNotFoundError, resolve_training_context
from app.services.training_grading_service import grade_subjective_answer
from app.services.training_progress_service import record_answer
from app.services.training_question_service import _question_type_sequence
from app.tables import training_post_quizzes, training_progress_records, training_questions


def start_post_quiz(session: Session, credential: str, request: PostQuizStartRequest) -> PostQuizDTO:
    """在文档学习完成后创建课后测验快照。"""
    context = resolve_training_context(session, credential)
    app_id = str(context.app_row["app_id"])
    _assert_document_learning_completed(session, app_id, request.sessionId, request.endUserId, request.documentId)

    question_count = request.count or get_settings().training_post_quiz_question_count
    question_rows = _select_quiz_questions(session, app_id, request.documentId, question_count)
    now = datetime.now(UTC)
    quiz_id = new_id()
    question_ids = [str(row["question_id"]) for row in question_rows]
    session.execute(
        training_post_quizzes.insert().values(
            quiz_id=quiz_id,
            app_id=app_id,
            session_id=request.sessionId,
            end_user_id=request.endUserId,
            plan_id=request.planId,
            document_id=request.documentId,
            question_ids=question_ids,
            status="started",
            score=None,
            passed=None,
            metadata={},
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    return _quiz_dto(quiz_id, app_id, request, question_rows, now)


def submit_post_quiz(
    session: Session,
    credential: str,
    quiz_id: str,
    request: PostQuizSubmitRequest,
) -> PostQuizSubmissionDTO:
    """提交课后测验答案并写入答题记录。"""
    context = resolve_training_context(session, credential)
    app_id = str(context.app_row["app_id"])
    quiz_row = session.execute(
        select(training_post_quizzes)
        .where(training_post_quizzes.c.quiz_id == quiz_id)
        .where(training_post_quizzes.c.app_id == app_id)
        .limit(1)
    ).mappings().first()
    if quiz_row is None:
        raise TrainingAgentNotFoundError(f"Post quiz {quiz_id} not found.")
    if quiz_row["status"] == "submitted":
        raise TrainingAgentConflictError("POST_QUIZ_ALREADY_SUBMITTED")
    if quiz_row["end_user_id"] != request.endUserId:
        raise TrainingAgentConflictError("END_USER_NOT_MATCHED")

    question_ids = [str(item) for item in (quiz_row["question_ids"] or [])]
    question_rows = _read_questions_by_ids(session, app_id, question_ids)
    question_by_id = {str(row["question_id"]): row for row in question_rows}
    answer_by_id = {item.questionId: item.answer for item in request.answers}
    missing = [question_id for question_id in question_ids if question_id not in answer_by_id]
    if missing:
        raise TrainingAgentConflictError("POST_QUIZ_ANSWERS_INCOMPLETE")

    results: list[PostQuizResultItemDTO] = []
    for question_id in question_ids:
        question = question_by_id[question_id]
        answer = answer_by_id[question_id]
        result = _score_question(session, app_id, question, answer)
        results.append(result)
        record_answer(
            session,
            session_id=str(quiz_row["session_id"]),
            app_id=app_id,
            end_user_id=request.endUserId,
            question_id=question_id,
            question_type=question["question_type"],
            answer=answer,
            score=int(round(result.score * 20)),
            is_correct=result.passed,
            explanation=result.explanation,
            metadata={"postQuizId": quiz_id, "score5": result.score},
        )

    average_score = round(sum(item.score for item in results) / len(results), 2) if results else 0.0
    passed = all(item.passed for item in results)
    now = datetime.now(UTC)
    session.execute(
        update(training_post_quizzes)
        .where(training_post_quizzes.c.quiz_id == quiz_id)
        .values(status="submitted", score=average_score, passed=passed, updated_at=now)
    )
    if passed:
        _mark_document_completed(
            session,
            app_id,
            str(quiz_row["session_id"]),
            request.endUserId,
            str(quiz_row["document_id"]),
        )
    session.commit()
    return PostQuizSubmissionDTO(
        quizId=quiz_id,
        score=average_score,
        passed=passed,
        results=results,
        submittedAt=now.isoformat(),
    )


def _assert_document_learning_completed(
    session: Session,
    app_id: str,
    session_id: str,
    end_user_id: str,
    document_id: str,
) -> None:
    """确认课堂会话已完成，未完成不得进入课后测验。"""
    row = session.execute(
        select(training_progress_records.c.status, training_progress_records.c.metadata)
        .where(training_progress_records.c.session_id == session_id)
        .where(training_progress_records.c.app_id == app_id)
        .where(training_progress_records.c.end_user_id == end_user_id)
        .limit(1)
    ).mappings().first()
    if row is None or row["status"] != "completed":
        raise TrainingAgentConflictError("DOCUMENT_LEARNING_NOT_COMPLETED")
    metadata = row["metadata"] or {}
    learned_document_ids = metadata.get("learnedDocumentIds") or metadata.get("completedLearningDocumentIds")
    if learned_document_ids and str(document_id) not in [str(item) for item in learned_document_ids]:
        # 兼容没有文档级元数据的旧进度；一旦调用方写入文档列表，就严格按文档校验。
        raise TrainingAgentConflictError("DOCUMENT_LEARNING_NOT_COMPLETED")


def _mark_document_completed(
    session: Session,
    app_id: str,
    session_id: str,
    end_user_id: str,
    document_id: str,
) -> None:
    """课后测验通过后，把文档写入进度 metadata 的 completedDocumentIds。"""
    row = session.execute(
        select(training_progress_records)
        .where(training_progress_records.c.session_id == session_id)
        .where(training_progress_records.c.app_id == app_id)
        .where(training_progress_records.c.end_user_id == end_user_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return
    metadata = dict(row["metadata"] or {})
    completed = set(str(item) for item in metadata.get("completedDocumentIds", []))
    completed.add(document_id)
    metadata["completedDocumentIds"] = sorted(completed)
    session.execute(
        update(training_progress_records)
        .where(training_progress_records.c.progress_id == row["progress_id"])
        .values(metadata=metadata, updated_at=datetime.now(UTC))
    )


def _select_quiz_questions(session: Session, app_id: str, document_id: str, count: int) -> list[Any]:
    """按题型比例从已发布题库抽取课后测验题。"""
    rows = session.execute(
        select(training_questions)
        .where(training_questions.c.app_id == app_id)
        .where(training_questions.c.status == "published")
        .order_by(training_questions.c.created_at.asc())
    ).mappings().all()
    document_rows = [
        row for row in rows
        if str((row["metadata"] or {}).get("documentId") or "") == str(document_id)
    ]
    selected: list[Any] = []
    used_ids: set[str] = set()
    for question_type in _question_type_sequence(count):
        match = next(
            (
                row for row in document_rows
                if row["question_type"] == question_type and str(row["question_id"]) not in used_ids
            ),
            None,
        )
        if match is None:
            raise TrainingAgentConflictError("POST_QUIZ_QUESTION_POOL_INSUFFICIENT")
        used_ids.add(str(match["question_id"]))
        selected.append(match)
    return selected


def _read_questions_by_ids(session: Session, app_id: str, question_ids: list[str]) -> list[Any]:
    rows = session.execute(
        select(training_questions)
        .where(training_questions.c.app_id == app_id)
        .where(training_questions.c.question_id.in_(question_ids))
    ).mappings().all()
    if len(rows) != len(question_ids):
        raise TrainingAgentConflictError("POST_QUIZ_QUESTION_NOT_FOUND")
    return rows


def _quiz_dto(
    quiz_id: str,
    app_id: str,
    request: PostQuizStartRequest,
    question_rows: list[Any],
    now: datetime,
) -> PostQuizDTO:
    return PostQuizDTO(
        quizId=str(quiz_id),
        sessionId=request.sessionId,
        appId=app_id,
        endUserId=request.endUserId,
        documentId=request.documentId,
        questions=[_question_dto(row) for row in question_rows],
        status="started",
        createdAt=now.isoformat(),
    )


def _question_dto(row: Any) -> PostQuizQuestionDTO:
    return PostQuizQuestionDTO(
        questionId=str(row["question_id"]),
        questionType=row["question_type"],
        content=row["content"],
        options=[QuestionOptionDTO(**item) for item in (row["options"] or [])],
        rubric=row["rubric"],
    )


def _score_question(session: Session, app_id: str, question: Any, answer: str) -> PostQuizResultItemDTO:
    """按 5 分制评分单题。"""
    question_type = question["question_type"]
    if question_type == "subjective":
        graded = grade_subjective_answer(session, str(question["question_id"]), answer, app_id)
        score = round(graded.score / 20, 2)
        return PostQuizResultItemDTO(
            questionId=str(question["question_id"]),
            questionType=question_type,
            score=score,
            passed=score > 4,
            isCorrect=None,
            explanation=graded.reason,
        )

    expected = str(question["correct_answer"] or "").strip()
    actual = answer.strip()
    is_correct = actual == expected
    return PostQuizResultItemDTO(
        questionId=str(question["question_id"]),
        questionType=question_type,
        score=5.0 if is_correct else 0.0,
        passed=is_correct,
        isCorrect=is_correct,
        explanation=question["explanation"],
    )
