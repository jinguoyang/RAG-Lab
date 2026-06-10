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


def _serialize_documents(documents: list[Any] | None) -> list[dict[str, Any]]:
    """将嵌套文档 DTO 转成可写入 JSON 列的普通字典。"""
    return [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in (documents or [])
    ]


def _normalize_plan_name(plan_name: str) -> str:
    """统一计划名称判重口径：裁剪首尾空格并忽略英文大小写。"""
    return plan_name.strip().casefold()


def _assert_unique_plan_name(
    session: Session,
    plan_name: str,
    *,
    exclude_plan_id: str | None = None,
) -> str:
    """校验计划名称在本地计划和平台草稿中唯一，并返回裁剪后的名称。"""
    import httpx

    from app.core.config import get_settings
    from app.services.platform_client import PlatformClient

    stripped_name = plan_name.strip()
    normalized_name = _normalize_plan_name(stripped_name)
    rows = session.execute(
        select(training_plans)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().all()
    for row in rows:
        if str(row["plan_id"]) == exclude_plan_id:
            continue
        existing_name = (row["metadata"] or {}).get("planName") or row["job_title"]
        if _normalize_plan_name(str(existing_name)) == normalized_name:
            raise TrainingPlanConflictError("计划名称已存在")

    try:
        settings = get_settings()
        drafts = PlatformClient(
            settings.platform_base_url,
            settings.platform_api_key,
        ).list_plan_drafts()
    except (ValueError, httpx.HTTPError):
        drafts = []
    for draft in drafts:
        if str(draft.get("planId")) == exclude_plan_id:
            continue
        existing_name = draft.get("planName") or draft.get("jobTitle") or ""
        if _normalize_plan_name(str(existing_name)) == normalized_name:
            raise TrainingPlanConflictError("计划名称已存在")
    return stripped_name


def create_plan_draft(session: Session, user_id: str | None, request: Any) -> dict:
    """生成学习计划草稿（异步）。

    调用平台 API 创建后台任务，返回任务信息供前端订阅 SSE。
    """
    import httpx
    from app.core.config import get_settings
    from app.services.platform_client import PlatformClient

    settings = get_settings()
    client = PlatformClient(settings.platform_base_url, settings.platform_api_key)
    plan_name = _assert_unique_plan_name(session, request.planName)
    try:
        task_data = client.create_plan_draft(
            plan_name=plan_name,
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

    # 返回任务信息（id, type, title, status, createdAt 等）
    return task_data


def list_plans(session: Session, app_id: str | None = None) -> list[dict]:
    """列出本地最终计划，并合并平台侧尚未保存的草稿。"""
    import httpx

    from app.core.config import get_settings
    from app.schemas.training_plan import TrainingPlanDTO
    from app.services.platform_client import PlatformClient

    query = select(training_plans).where(training_plans.c.deleted_at.is_(None))
    if app_id:
        query = query.where(training_plans.c.app_id == app_id)
    rows = session.execute(query.order_by(training_plans.c.created_at.desc())).mappings().all()

    local_plans = [
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
            employeeIds=(r["metadata"] or {}).get("employeeIds") or [],
            version=r["version"],
            createdAt=r["created_at"].isoformat(),
            updatedAt=r["updated_at"].isoformat(),
        ).model_dump()
        for r in rows
    ]
    local_plan_ids = {item["planId"] for item in local_plans}

    try:
        settings = get_settings()
        platform_drafts = PlatformClient(
            settings.platform_base_url,
            settings.platform_api_key,
        ).list_plan_drafts()
    except (ValueError, httpx.HTTPError):
        # 平台暂不可用时仍返回 ex-app 本地业务真值，避免列表整体失败。
        platform_drafts = []

    for draft in platform_drafts:
        if draft.get("planId") in local_plan_ids:
            continue
        if app_id and draft.get("appId") != app_id:
            continue
        local_plans.append(TrainingPlanDTO(**draft).model_dump())
    return local_plans


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

    plan_name = _assert_unique_plan_name(session, request.planName, exclude_plan_id=plan_id)
    now = datetime.now(timezone.utc)
    serialized_documents = _serialize_documents(request.documents)
    if row is None:
        metadata = {
            "planName": plan_name,
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
                documents=serialized_documents,
                evidence_chunk_ids=request.evidenceChunkIds,
                recommend_reason=request.recommendReason,
                reading_order=[item["documentId"] for item in serialized_documents],
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
    metadata["planName"] = plan_name
    metadata["employeeIds"] = request.employeeIds
    metadata["savedBy"] = user_id
    metadata["savedAt"] = now.isoformat()
    session.execute(
        update(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .values(
            status="saved",
            documents=serialized_documents,
            reading_order=[item["documentId"] for item in serialized_documents],
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
        metadata["planName"] = _assert_unique_plan_name(
            session,
            request.planName,
            exclude_plan_id=plan_id,
        )
    if request.documents is not None:
        serialized_documents = _serialize_documents(request.documents)
        values["documents"] = serialized_documents
        values["reading_order"] = [item["documentId"] for item in serialized_documents]
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
    """软删除本地计划；本地不存在时代理删除平台草稿。"""
    row = session.execute(
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().first()
    if row is None:
        import httpx

        from app.core.config import get_settings
        from app.services.platform_client import PlatformClient

        settings = get_settings()
        try:
            return PlatformClient(
                settings.platform_base_url,
                settings.platform_api_key,
            ).delete_plan_draft(plan_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise TrainingPlanNotFoundError(f"学习计划 {plan_id} 不存在") from exc
            raise TrainingPlanConflictError(f"平台草稿删除失败: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise TrainingPlanConflictError("平台服务不可用，暂时无法删除草稿") from exc

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

        # 自动生成才执行全局去重；草稿和已发布题目都会阻止重复生成。
        existing = db.execute(
            select(training_questions.c.metadata)
            .where(training_questions.c.status.in_(("draft", "published")))
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
                if templates:
                    existing_doc_ids.add(doc_id)
                logger.info("为文档 %s 生成 %d 道题目", doc_id, len(templates))
            except Exception as exc:
                logger.error("为文档 %s 生成题目失败: %s", doc_id, exc)
                db.rollback()
    finally:
        db.close()


def get_plan(session: Session, plan_id: str) -> dict:
    """获取单个学习计划。"""
    from app.schemas.training_plan import TrainingPlanDTO
    from app.tables import training_classroom_sessions, training_post_quizzes

    row = session.execute(
        select(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .where(training_plans.c.deleted_at.is_(None))
    ).mappings().first()

    if row is None:
        raise TrainingPlanNotFoundError(f"学习计划 {plan_id} 不存在")

    # 查询已完成学习的文档列表
    completed_docs = session.execute(
        select(training_classroom_sessions.c.metadata)
        .where(training_classroom_sessions.c.plan_id == plan_id)
        .where(training_classroom_sessions.c.current_state == "COMPLETED")
        .where(training_classroom_sessions.c.deleted_at.is_(None))
    ).scalars().all()

    completed_document_ids = []
    for meta in completed_docs:
        if meta and meta.get("documentId"):
            completed_document_ids.append(meta["documentId"])

    # 任意一次课后测验通过后，文档保持通过状态；后续复习或重考失败不影响。
    passed_document_ids = session.execute(
        select(training_post_quizzes.c.document_id)
        .where(training_post_quizzes.c.plan_id == plan_id)
        .where(training_post_quizzes.c.passed.is_(True))
    ).scalars().all()

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
        employeeIds=(row["metadata"] or {}).get("employeeIds") or [],
        completedDocuments=list(set(completed_document_ids)),
        passedDocuments=list(set(passed_document_ids)),
        version=row["version"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    ).model_dump()
