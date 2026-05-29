"""培训报表与薄弱点统计服务。"""
from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.schemas.training_report import TrainingReportDTO, WeaknessItemDTO
from app.tables import training_answer_records, training_progress_records, training_questions


def get_training_report(session: Session, app_id: str) -> TrainingReportDTO:
    """聚合培训进度和答题记录，返回报表。无数据时返回空报表。"""
    # 1. 完成率、平均分、通过数
    progress_row = session.execute(
        select(
            func.count().label("total_count"),
            func.sum(
                case(
                    (training_progress_records.c.status == "completed", 1),
                    else_=0,
                )
            ).label("passed_count"),
            func.avg(training_progress_records.c.last_score).label("avg_score"),
        ).where(training_progress_records.c.app_id == app_id)
    ).one()

    total_count = progress_row.total_count or 0
    passed_count = progress_row.passed_count or 0
    avg_score = progress_row.avg_score or 0.0
    completion_rate = (passed_count / total_count) if total_count > 0 else 0.0

    # 2. 薄弱点：按 question_id 聚合错题
    weakness_rows = session.execute(
        select(
            training_answer_records.c.question_id,
            training_questions.c.content,
            func.count().label("total_attempts"),
            func.sum(
                case(
                    (training_answer_records.c.is_correct == 0, 1),
                    else_=0,
                )
            ).label("fail_count"),
        )
        .join(
            training_questions,
            training_answer_records.c.question_id == training_questions.c.question_id,
        )
        .where(training_answer_records.c.app_id == app_id)
        .group_by(
            training_answer_records.c.question_id,
            training_questions.c.content,
        )
        .having(
            func.sum(
                case(
                    (training_answer_records.c.is_correct == 0, 1),
                    else_=0,
                )
            )
            > 0
        )
        .order_by(
            func.sum(
                case(
                    (training_answer_records.c.is_correct == 0, 1),
                    else_=0,
                )
            ).desc()
        )
    ).all()

    weaknesses: list[WeaknessItemDTO] = []
    for row in weakness_rows:
        fail_count = row.fail_count or 0
        total_attempts = row.total_attempts or 1
        weaknesses.append(
            WeaknessItemDTO(
                questionId=str(row.question_id),
                content=str(row.content),
                failCount=fail_count,
                failRate=round(fail_count / total_attempts, 4),
            )
        )

    failed_question_count = len(weaknesses)

    return TrainingReportDTO(
        appId=app_id,
        completionRate=round(completion_rate, 4),
        averageScore=round(float(avg_score), 1),
        passedCount=passed_count,
        totalCount=total_count,
        failedQuestionCount=failed_question_count,
        weaknesses=weaknesses,
    )
