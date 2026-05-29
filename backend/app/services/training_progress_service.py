"""员工学习进度与答题记录服务。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.training_progress import AnswerRecordDTO, ProgressDTO
from app.tables import training_answer_records, training_progress_records


def record_answer(
    session: Session,
    *,
    session_id: str,
    app_id: str,
    end_user_id: str,
    question_id: str,
    question_type: str,
    answer: str,
    score: int | None = None,
    is_correct: bool | None = None,
    explanation: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """记录一次答题，返回 answer_id。"""
    answer_id = new_id()
    now = datetime.now(UTC)
    session.execute(
        insert(training_answer_records).values(
            answer_id=answer_id,
            session_id=session_id,
            app_id=app_id,
            end_user_id=end_user_id,
            question_id=question_id,
            question_type=question_type,
            answer=answer,
            score=score,
            is_correct=is_correct,
            explanation=explanation,
            metadata=metadata or {},
            created_at=now,
        )
    )
    return answer_id


def update_progress(
    session: Session,
    *,
    session_id: str,
    app_id: str,
    end_user_id: str,
    plan_id: str | None = None,
    current_section_index: int = 0,
    completed_sections: int = 0,
    total_sections: int = 0,
    last_score: int | None = None,
    status: str = "in_progress",
) -> None:
    """创建或更新学习进度记录。

    按 session_id + app_id + end_user_id 唯一定位。
    """
    now = datetime.now(UTC)
    existing = session.execute(
        select(training_progress_records.c.progress_id)
        .where(training_progress_records.c.session_id == session_id)
        .where(training_progress_records.c.app_id == app_id)
        .where(training_progress_records.c.end_user_id == end_user_id)
        .limit(1)
    ).scalar()

    if existing is not None:
        session.execute(
            update(training_progress_records)
            .where(training_progress_records.c.progress_id == existing)
            .values(
                plan_id=plan_id,
                current_section_index=current_section_index,
                completed_sections=completed_sections,
                total_sections=total_sections,
                last_score=last_score,
                status=status,
                updated_at=now,
            )
        )
    else:
        session.execute(
            insert(training_progress_records).values(
                progress_id=new_id(),
                session_id=session_id,
                app_id=app_id,
                end_user_id=end_user_id,
                plan_id=plan_id,
                current_section_index=current_section_index,
                completed_sections=completed_sections,
                total_sections=total_sections,
                last_score=last_score,
                status=status,
                metadata={},
                created_at=now,
                updated_at=now,
            )
        )


def get_progress(
    session: Session,
    session_id: str,
    app_id: str,
    end_user_id: str,
) -> ProgressDTO | None:
    """按 sessionId + appId + endUserId 查询进度，不存在返回 None。"""
    row = session.execute(
        select(training_progress_records)
        .where(training_progress_records.c.session_id == session_id)
        .where(training_progress_records.c.app_id == app_id)
        .where(training_progress_records.c.end_user_id == end_user_id)
        .limit(1)
    ).mappings().first()

    if row is None:
        return None

    return ProgressDTO(
        sessionId=str(row["session_id"]),
        appId=str(row["app_id"]),
        endUserId=row["end_user_id"],
        currentSectionIndex=row["current_section_index"],
        completedSections=row["completed_sections"],
        totalSections=row["total_sections"],
        lastScore=row["last_score"],
        status=row["status"],
        updatedAt=row["updated_at"].isoformat(),
    )


def get_answer_records(
    session: Session,
    session_id: str,
    app_id: str,
) -> list[AnswerRecordDTO]:
    """查询指定 session + app 的所有答题记录。"""
    rows = session.execute(
        select(training_answer_records)
        .where(training_answer_records.c.session_id == session_id)
        .where(training_answer_records.c.app_id == app_id)
        .order_by(training_answer_records.c.created_at.asc())
    ).mappings().all()

    return [
        AnswerRecordDTO(
            answerId=str(row["answer_id"]),
            sessionId=str(row["session_id"]),
            questionId=str(row["question_id"]),
            questionType=row["question_type"],
            answer=row["answer"],
            score=row["score"],
            isCorrect=row["is_correct"],
            explanation=row["explanation"],
            createdAt=row["created_at"].isoformat(),
        )
        for row in rows
    ]
