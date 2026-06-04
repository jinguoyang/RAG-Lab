"""审核服务。"""
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.tables import training_review_tasks
from app.services.training_plan_service import create_plan_draft


def list_review_tasks(db: Session, review_type: str | None = None) -> list[dict]:
    query = training_review_tasks.select()
    if review_type:
        query = query.where(training_review_tasks.c.review_type == review_type)
    rows = db.execute(query.order_by(training_review_tasks.c.created_at.desc())).fetchall()
    return [{"id": r.id, "platformDraftId": r.platform_draft_id, "platformPlanId": r.platform_plan_id,
             "reviewType": r.review_type, "status": r.status,
             "submittedPayload": r.submitted_payload or {}, "createdAt": r.created_at.isoformat()} for r in rows]


def generate_plan_draft(db: Session, job_title: str, job_description: str) -> dict:
    """调用本地 plan service 生成草稿，并记录审核任务。"""
    from app.core.config import get_settings
    from app.schemas.training_plan import TrainingPlanDraftRequest
    from app.services.training_plan_service import TrainingPlanConflictError

    settings = get_settings()
    if not settings.platform_app_id:
        raise TrainingPlanConflictError(
            "platform_app_id 未配置，请在 .env 中设置 EXT_TRAINING_PLATFORM_APP_ID"
        )

    request = TrainingPlanDraftRequest(
        appId=settings.platform_app_id,
        jobTitle=job_title,
        jobDescription=job_description,
    )
    result = create_plan_draft(db, None, request)
    result_dict = result.model_dump() if hasattr(result, "model_dump") else result

    now = datetime.now(timezone.utc)
    task_id = str(uuid4())
    db.execute(training_review_tasks.insert().values(
        id=task_id, platform_draft_id=result_dict.get("planId"),
        review_type="plan", status="pending", submitted_payload=result_dict, created_at=now,
    ))
    db.commit()
    return {"taskId": task_id, "draft": result_dict}


def submit_review(db: Session, task_id: str, decision: str, notes: str = "", adjustments: dict | None = None) -> dict:
    row = db.execute(training_review_tasks.select().where(training_review_tasks.c.id == task_id)).fetchone()
    if row is None:
        raise ValueError(f"审核任务 {task_id} 不存在")

    if row.platform_draft_id:
        from app.services.training_plan_service import review_plan
        try:
            review_plan(db, None, row.platform_draft_id, decision, notes)
        except Exception:
            pass

    now = datetime.now(timezone.utc)
    db.execute(training_review_tasks.update().where(training_review_tasks.c.id == task_id).values(status=decision, reviewed_at=now))
    db.commit()
    return {"taskId": task_id, "status": decision}
