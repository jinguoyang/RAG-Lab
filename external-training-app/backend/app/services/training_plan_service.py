"""学习计划服务。"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.tables import training_plans


class TrainingPlanNotFoundError(Exception):
    pass


class TrainingPlanConflictError(ValueError):
    pass


def create_plan_draft(session: Session, user_id: str | None, request: Any) -> Any:
    """生成学习计划草稿。

    草稿只作为页面编辑的临时数据返回，不在 ex-app 本地落库；最终计划由
    save_plan 统一保存，避免本地长期维护 draft 状态。
    """
    import httpx
    from app.core.config import get_settings
    from app.schemas.training_plan import TrainingPlanDTO
    from app.services.platform_client import PlatformClient

    settings = get_settings()
    client = PlatformClient(settings.platform_base_url, settings.platform_api_key)
    try:
        plan_data = client.create_plan_draft(
            job_title=request.jobTitle,
            job_description=request.jobDescription,
        )
    except httpx.TimeoutException:
        raise TrainingPlanConflictError("平台服务超时，请稍后重试")
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200] if exc.response.text else ""
        raise TrainingPlanConflictError(f"平台服务错误 {exc.response.status_code}: {detail}")
    except httpx.ConnectError:
        raise TrainingPlanConflictError("无法连接平台服务，请检查配置")

    return TrainingPlanDTO(
        planId=plan_data["planId"],
        appId=plan_data["appId"],
        planName=request.planName or plan_data["jobTitle"],
        jobTitle=plan_data["jobTitle"],
        jobDescription=plan_data["jobDescription"],
        status=plan_data["status"],
        abilityGroups=plan_data["abilityGroups"],
        documents=plan_data["documents"],
        evidenceChunkIds=plan_data["evidenceChunkIds"],
        recommendReason=plan_data["recommendReason"],
        readingOrder=plan_data["readingOrder"],
        employeeIds=[],
        version=plan_data["version"],
        createdAt=plan_data["createdAt"],
        updatedAt=plan_data["updatedAt"],
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
            planName=(r["metadata"] or {}).get("planName"),
            jobTitle=r["job_title"],
            jobDescription=r["job_description"],
            status=r["status"],
            abilityGroups=r["ability_groups"] or [],
            documents=r["documents"] or [],
            evidenceChunkIds=r["evidence_chunk_ids"] or [],
            recommendReason=r["recommend_reason"],
            readingOrder=r["reading_order"] or [],
            employeeIds=(r["metadata"] or {}).get("employeeIds") or [],
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


def save_plan(session: Session, user_id: str | None, plan_id: str, request: Any) -> dict:
    """保存 ex-app 侧最终学习计划和员工绑定。

    本地不保存草稿，因此新建计划保存时可能没有既有记录；此时直接插入
    saved 计划。已有 saved 计划则只做局部更新。
    """
    row = session.execute(
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().first()

    now = datetime.now(timezone.utc)
    if row is None:
        metadata = {
            "planName": request.planName,
            "employeeIds": request.employeeIds,
            "savedBy": user_id,
            "savedAt": now.isoformat(),
        }
        session.execute(
            training_plans.insert().values(
                plan_id=plan_id,
                app_id=request.appId,
                job_title=request.jobTitle,
                job_description=request.jobDescription,
                status="saved",
                ability_groups=request.abilityGroups,
                documents=request.documents,
                evidence_chunk_ids=request.evidenceChunkIds,
                recommend_reason=request.recommendReason,
                reading_order=request.readingOrder,
                version=request.version,
                metadata=metadata,
                created_at=now,
                created_by=user_id,
                updated_at=now,
                updated_by=user_id,
            )
        )
        session.commit()
        return {"planId": plan_id, "status": "saved"}

    metadata = dict(row["metadata"] or {})
    metadata["planName"] = request.planName
    metadata["employeeIds"] = request.employeeIds
    metadata["savedBy"] = user_id
    metadata["savedAt"] = now.isoformat()
    session.execute(
        update(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .values(
            status="saved",
            documents=request.documents,
            reading_order=request.readingOrder,
            metadata=metadata,
            updated_at=now,
            updated_by=user_id,
        )
    )
    session.commit()
    return {"planId": plan_id, "status": "saved"}


def list_training_documents(query: str = "", category: str | None = None, difficulty: str | None = None) -> list[dict]:
    """代理平台知识库文档查询。"""
    import httpx
    from app.core.config import get_settings
    from app.services.platform_client import PlatformClient

    settings = get_settings()
    client = PlatformClient(settings.platform_base_url, settings.platform_api_key)
    try:
        return client.list_training_documents(query=query, category=category, difficulty=difficulty)
    except httpx.TimeoutException:
        raise TrainingPlanConflictError("平台服务超时，请稍后重试")
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200] if exc.response.text else ""
        raise TrainingPlanConflictError(f"平台服务错误 {exc.response.status_code}: {detail}")
    except httpx.ConnectError:
        raise TrainingPlanConflictError("无法连接平台服务，请检查配置")


def update_plan(session: Session, user_id: str | None, plan_id: str, request: Any) -> dict:
    """更新学习计划（本地数据）。"""
    row = session.execute(
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().first()
    if row is None:
        raise TrainingPlanNotFoundError(f"学习计划 {plan_id} 不存在")

    now = datetime.now(timezone.utc)
    metadata = dict(row["metadata"] or {})

    values: dict[str, Any] = {"updated_at": now, "updated_by": user_id}
    if request.planName is not None:
        metadata["planName"] = request.planName
    if request.documents is not None:
        values["documents"] = request.documents
    if request.readingOrder is not None:
        values["reading_order"] = request.readingOrder
    if request.employeeIds is not None:
        metadata["employeeIds"] = request.employeeIds
    values["metadata"] = metadata

    session.execute(
        update(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .values(**values)
    )
    session.commit()
    return {"planId": plan_id, "status": row["status"]}


def delete_plan(session: Session, user_id: str | None, plan_id: str) -> dict:
    """软删除学习计划。"""
    row = session.execute(
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().first()
    if row is None:
        raise TrainingPlanNotFoundError(f"学习计划 {plan_id} 不存在")

    now = datetime.now(timezone.utc)
    session.execute(
        update(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .values(deleted_at=now, deleted_by=user_id)
    )
    session.commit()
    return {"planId": plan_id, "status": "deleted"}


def generate_questions_for_plan(plan_id: str) -> None:
    """后台任务：为计划中的每个文档生成题目。"""
    import logging
    from app.core.database import SessionLocal
    from app.core.config import get_settings
    from app.core.database import new_id
    from app.services.platform_client import PlatformClient
    from app.tables import training_questions

    logger = logging.getLogger(__name__)
    settings = get_settings()
    db = SessionLocal()
    try:
        row = db.execute(
            select(training_plans)
            .where(training_plans.c.plan_id == plan_id)
            .where(training_plans.c.deleted_at.is_(None))
        ).mappings().first()
        if row is None:
            logger.warning("计划 %s 不存在，跳过题目生成", plan_id)
            return

        documents = row["documents"] or []
        if not documents:
            return

        # 按文档全局去重：同一文档在其他计划已有题目时不重复生成。
        existing = db.execute(
            select(training_questions.c.metadata)
        ).fetchall()
        existing_doc_ids = set()
        for r in existing:
            meta = r[0] or {}
            if meta.get("documentId"):
                existing_doc_ids.add(meta["documentId"])

        client = PlatformClient(settings.platform_base_url, settings.platform_api_key)
        now = datetime.now(timezone.utc)

        for doc in documents:
            doc_id = doc.get("documentId") if isinstance(doc, dict) else None
            if not doc_id or doc_id in existing_doc_ids:
                continue
            try:
                templates = client.create_question_drafts(
                    plan_id=plan_id,
                    job_title=row["job_title"],
                    ability_groups=row["ability_groups"] or [],
                    count=10,
                    document_ids=[doc_id],
                )
                for tmpl in templates:
                    qid = new_id()
                    db.execute(
                        training_questions.insert().values(
                            question_id=qid,
                            plan_id=plan_id,
                            app_id=tmpl.get("appId", row["app_id"]),
                            question_type=tmpl["questionType"],
                            category=tmpl.get("category", "practice"),
                            content=tmpl["content"],
                            options=tmpl.get("options"),
                            correct_answer=tmpl.get("correctAnswer"),
                            explanation=tmpl.get("explanation"),
                            rubric=tmpl.get("rubric"),
                            evidence_chunk_ids=tmpl.get("evidenceChunkIds", []),
                            status="draft",
                            metadata={
                                "documentId": doc_id,
                                "platformDraftQuestionId": tmpl.get("questionId"),
                            },
                            created_at=now,
                            created_by="system",
                            updated_at=now,
                            updated_by="system",
                        )
                    )
                db.commit()
                logger.info("为文档 %s 生成 %d 道题目", doc_id, len(templates))
            except Exception as exc:
                logger.error("为文档 %s 生成题目失败: %s", doc_id, exc)
                db.rollback()
    finally:
        db.close()


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
        planName=(row["metadata"] or {}).get("planName"),
        jobTitle=row["job_title"],
        jobDescription=row["job_description"],
        status=row["status"],
        abilityGroups=row["ability_groups"] or [],
        documents=row["documents"] or [],
        evidenceChunkIds=row["evidence_chunk_ids"] or [],
        recommendReason=row["recommend_reason"],
        readingOrder=row["reading_order"] or [],
        employeeIds=(row["metadata"] or {}).get("employeeIds") or [],
        version=row["version"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    ).model_dump()
