"""审核路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.review import ReviewSubmitRequest
from app.services.review_service import list_review_tasks, generate_plan_draft, submit_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def list_reviews(reviewType: str | None = None, db: Session = Depends(get_db)):
    return list_review_tasks(db, reviewType)


@router.post("/plans/drafts", status_code=201)
def create_plan_draft(jobTitle: str = "", jobDescription: str = "", db: Session = Depends(get_db)):
    if not jobTitle:
        raise HTTPException(400, "jobTitle 不能为空")
    return generate_plan_draft(db, jobTitle, jobDescription)


@router.post("/{task_id}/submit")
def submit_review_result(task_id: str, request: ReviewSubmitRequest, db: Session = Depends(get_db)):
    try:
        return submit_review(db, task_id, request.decision, request.notes, request.adjustments)
    except ValueError as e:
        raise HTTPException(404, str(e))
