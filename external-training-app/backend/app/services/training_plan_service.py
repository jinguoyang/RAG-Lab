"""学习计划服务。"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.database import new_id
from app.tables import training_plans


class TrainingPlanNotFoundError(Exception):
    pass


class TrainingPlanConflictError(ValueError):
    pass


def create_plan_draft(session: Session, user_id: str | None, request: Any) -> Any:
    """生成学习计划草稿。首版使用模板数据。"""
    from app.schemas.training_plan import TrainingPlanDTO

    now = datetime.now(timezone.utc)
    plan_id = new_id()

    template_data = _generate_template_plan(request.jobTitle, request.jobDescription)

    session.execute(
        training_plans.insert().values(
            plan_id=plan_id,
            app_id=request.appId,
            job_title=request.jobTitle,
            job_description=request.jobDescription,
            status="draft",
            ability_groups=template_data["abilityGroups"],
            documents=template_data["documents"],
            evidence_chunk_ids=template_data["evidenceChunkIds"],
            recommend_reason=template_data["recommendReason"],
            reading_order=template_data["readingOrder"],
            version=1,
            metadata={},
            created_at=now,
            created_by=user_id,
            updated_at=now,
            updated_by=user_id,
        )
    )
    session.commit()

    return TrainingPlanDTO(
        planId=plan_id,
        appId=request.appId,
        jobTitle=request.jobTitle,
        jobDescription=request.jobDescription,
        status="draft",
        abilityGroups=template_data["abilityGroups"],
        documents=template_data["documents"],
        evidenceChunkIds=template_data["evidenceChunkIds"],
        recommendReason=template_data["recommendReason"],
        readingOrder=template_data["readingOrder"],
        version=1,
        createdAt=now.isoformat(),
        updatedAt=now.isoformat(),
    )


def list_plans(session: Session, app_id: str | None = None) -> list[dict]:
    """列出学习计划。"""
    from app.schemas.training_plan import TrainingPlanDTO

    query = select(training_plans).where(training_plans.c.deleted_at.is_(None))
    if app_id:
        query = query.where(training_plans.c.app_id == app_id)
    rows = session.execute(query.order_by(training_plans.c.created_at.desc())).mappings().all()

    return [
        TrainingPlanDTO(
            planId=r["plan_id"],
            appId=r["app_id"],
            jobTitle=r["job_title"],
            jobDescription=r["job_description"],
            status=r["status"],
            abilityGroups=r["ability_groups"] or [],
            documents=r["documents"] or [],
            evidenceChunkIds=r["evidence_chunk_ids"] or [],
            recommendReason=r["recommend_reason"],
            readingOrder=r["reading_order"] or [],
            version=r["version"],
            createdAt=r["created_at"].isoformat(),
            updatedAt=r["updated_at"].isoformat(),
        ).model_dump()
        for r in rows
    ]


def review_plan(session: Session, user_id: str | None, plan_id: str, decision: str, notes: str = "") -> dict:
    """审核学习计划。"""
    row = session.execute(
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().first()

    if row is None:
        raise TrainingPlanNotFoundError(f"学习计划 {plan_id} 不存在")

    if row["status"] != "draft":
        raise TrainingPlanConflictError(f"计划状态为 {row['status']}，不能审核")

    now = datetime.now(timezone.utc)
    new_status = "approved" if decision == "approved" else "rejected"

    session.execute(
        update(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .values(status=new_status, updated_at=now, updated_by=user_id)
    )
    session.commit()

    return {"planId": plan_id, "status": new_status}


def get_plan(session: Session, plan_id: str) -> dict:
    """获取单个学习计划。"""
    from app.schemas.training_plan import TrainingPlanDTO

    row = session.execute(
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().first()

    if row is None:
        raise TrainingPlanNotFoundError(f"学习计划 {plan_id} 不存在")

    return TrainingPlanDTO(
        planId=row["plan_id"],
        appId=row["app_id"],
        jobTitle=row["job_title"],
        jobDescription=row["job_description"],
        status=row["status"],
        abilityGroups=row["ability_groups"] or [],
        documents=row["documents"] or [],
        evidenceChunkIds=row["evidence_chunk_ids"] or [],
        recommendReason=row["recommend_reason"],
        readingOrder=row["reading_order"] or [],
        version=row["version"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    ).model_dump()


def _generate_template_plan(job_title: str, job_description: str) -> dict:
    """首版模板学习计划生成。后续替换为 RAG + Agent 调用。"""
    return {
        "abilityGroups": [
            {"name": "基础能力", "description": f"{job_title}岗位基础知识"},
            {"name": "专业技能", "description": f"{job_title}核心专业技能"},
        ],
        "documents": [
            {"documentId": "doc-001", "title": f"{job_title}入门指南", "relevance": 0.95},
            {"documentId": "doc-002", "title": f"{job_title}最佳实践", "relevance": 0.88},
        ],
        "evidenceChunkIds": ["chunk-001", "chunk-002", "chunk-003"],
        "recommendReason": f"基于{job_title}岗位描述，推荐以上文档作为核心学习材料。",
        "readingOrder": ["doc-001", "doc-002"],
    }
