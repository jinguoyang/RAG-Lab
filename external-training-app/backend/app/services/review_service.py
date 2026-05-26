"""审核服务。"""
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.tables import training_review_tasks, platform_app_bindings
from app.services.platform_client import PlatformClient


def _get_platform_client(db: Session) -> PlatformClient:
    row = db.execute(platform_app_bindings.select().where(platform_app_bindings.c.status == "active")).fetchone()
    if row is None:
        raise ValueError("未配置平台绑定")
    return PlatformClient(row.platform_base_url, row.platform_api_key_ref)


def list_review_tasks(db: Session, review_type: str | None = None) -> list[dict]:
    query = training_review_tasks.select()
    if review_type:
        query = query.where(training_review_tasks.c.review_type == review_type)
    rows = db.execute(query.order_by(training_review_tasks.c.created_at.desc())).fetchall()
    return [{"id": r.id, "platformDraftId": r.platform_draft_id, "platformPlanId": r.platform_plan_id,
             "reviewType": r.review_type, "status": r.status,
             "submittedPayload": r.submitted_payload or {}, "createdAt": r.created_at.isoformat()} for r in rows]


def generate_plan_draft(db: Session, job_title: str, job_description: str) -> dict:
    client = _get_platform_client(db)
    binding = db.execute(platform_app_bindings.select().where(platform_app_bindings.c.status == "active")).fetchone()
    result = client.create_plan_draft(binding.platform_app_id, job_title, job_description)
    now = datetime.now(timezone.utc)
    task_id = str(uuid4())
    db.execute(training_review_tasks.insert().values(
        id=task_id, platform_draft_id=result.get("draftId", result.get("planId")),
        review_type="plan", status="pending", submitted_payload=result, created_at=now,
    ))
    db.commit()
    return {"taskId": task_id, "draft": result}


def submit_review(db: Session, task_id: str, decision: str, notes: str = "", adjustments: dict | None = None) -> dict:
    row = db.execute(training_review_tasks.select().where(training_review_tasks.c.id == task_id)).fetchone()
    if row is None:
        raise ValueError(f"审核任务 {task_id} 不存在")
    client = _get_platform_client(db)
    if row.platform_draft_id:
        client.review_plan_draft(row.platform_draft_id, decision, notes)
    now = datetime.now(timezone.utc)
    db.execute(training_review_tasks.update().where(training_review_tasks.c.id == task_id).values(status=decision, reviewed_at=now))
    db.commit()
    return {"taskId": task_id, "status": decision}
