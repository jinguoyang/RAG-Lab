"""题库服务。"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from app.core.database import new_id
from app.tables import training_questions


class TrainingQuestionNotFoundError(Exception):
    pass


class TrainingQuestionConflictError(ValueError):
    pass


def create_question_drafts(session: Session, user_id: str | None, request: Any) -> list[dict]:
    """生成题库草稿。通过 PlatformClient 调用平台端点。"""
    import httpx
    from app.core.config import get_settings
    from app.schemas.training_question import TrainingQuestionDTO
    from app.services.platform_client import PlatformClient

    settings = get_settings()
    client = PlatformClient(settings.platform_base_url, settings.platform_api_key)
    try:
        templates = client.create_question_drafts(
            plan_id=request.planId,
            job_title=request.jobTitle,
            ability_groups=request.abilityGroups,
            count=request.count,
        )
    except httpx.TimeoutException:
        raise TrainingQuestionConflictError("平台服务超时，请稍后重试")
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200] if exc.response.text else ""
        raise TrainingQuestionConflictError(f"平台服务错误 {exc.response.status_code}: {detail}")
    except httpx.ConnectError:
        raise TrainingQuestionConflictError("无法连接平台服务，请检查配置")

    now = datetime.now(timezone.utc)

    # 验证平台返回的题目格式
    required_keys = {"questionType", "content"}
    for i, tmpl in enumerate(templates):
        missing = required_keys - set(tmpl.keys())
        if missing:
            raise TrainingQuestionConflictError(f"平台返回的第 {i+1} 题缺少字段: {missing}")

    results = []
    for tmpl in templates:
        qid = tmpl.get("questionId") or new_id()
        app_id = tmpl["appId"]
        created_at_text = tmpl.get("createdAt") or now.isoformat()
        session.execute(
            training_questions.insert().values(
                question_id=qid,
                plan_id=request.planId,
                app_id=app_id,
                question_type=tmpl["questionType"],
                category=tmpl["category"],
                content=tmpl["content"],
                options=tmpl.get("options"),
                correct_answer=tmpl.get("correctAnswer"),
                explanation=tmpl.get("explanation"),
                rubric=tmpl.get("rubric"),
                evidence_chunk_ids=tmpl.get("evidenceChunkIds", []),
                status=tmpl.get("status", "draft"),
                metadata={},
                created_at=now,
                created_by=user_id,
                updated_at=now,
                updated_by=user_id,
            )
        )
        results.append(TrainingQuestionDTO(
            questionId=qid,
            planId=request.planId,
            appId=app_id,
            questionType=tmpl["questionType"],
            category=tmpl["category"],
            content=tmpl["content"],
            options=tmpl.get("options"),
            correctAnswer=tmpl.get("correctAnswer"),
            explanation=tmpl.get("explanation"),
            rubric=tmpl.get("rubric"),
            evidenceChunkIds=tmpl.get("evidenceChunkIds", []),
            status=tmpl.get("status", "draft"),
            createdAt=created_at_text,
        ).model_dump())

    session.commit()
    return results


def list_questions(session: Session, plan_id: str | None = None) -> list[dict]:
    """列出题目。"""
    from app.schemas.training_question import TrainingQuestionDTO

    query = select(training_questions)
    if plan_id:
        query = query.where(training_questions.c.plan_id == plan_id)
    rows = session.execute(query.order_by(training_questions.c.created_at.desc())).mappings().all()

    return [
        TrainingQuestionDTO(
            questionId=r["question_id"],
            planId=r["plan_id"],
            appId=r["app_id"],
            questionType=r["question_type"],
            category=r["category"],
            content=r["content"],
            options=r["options"],
            correctAnswer=r["correct_answer"],
            explanation=r["explanation"],
            rubric=r["rubric"],
            evidenceChunkIds=r["evidence_chunk_ids"] or [],
            status=r["status"],
            createdAt=r["created_at"].isoformat(),
        ).model_dump()
        for r in rows
    ]


def review_question(session: Session, user_id: str | None, question_id: str, decision: str) -> dict:
    """审核题目。"""
    row = session.execute(
        select(training_questions).where(training_questions.c.question_id == question_id)
    ).mappings().first()

    if row is None:
        raise TrainingQuestionNotFoundError(f"题目 {question_id} 不存在")

    if row["status"] != "draft":
        raise TrainingQuestionConflictError(f"题目状态为 {row['status']}，不能审核")

    now = datetime.now(timezone.utc)
    new_status = "approved" if decision == "approved" else "rejected"

    session.execute(
        sa_update(training_questions)
        .where(training_questions.c.question_id == question_id)
        .values(status=new_status, updated_at=now, updated_by=user_id)
    )
    session.commit()

    return {"questionId": question_id, "status": new_status}
