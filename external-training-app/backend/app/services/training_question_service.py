"""题库服务。"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete as sa_delete, select, update as sa_update
from sqlalchemy.orm import Session

from app.core.database import new_id
from app.tables import training_question_appeals, training_questions


class TrainingQuestionNotFoundError(Exception):
    pass


class TrainingQuestionConflictError(ValueError):
    pass


def create_question_drafts(session: Session, user_id: str | None, request: Any) -> list[dict]:
    """手动生成题库草稿；每次请求都调用平台，不执行重复生成控制。"""
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
            document_ids=request.documentIds,
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
        qid = new_id()
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
                status="draft",
                metadata={
                    "documentId": tmpl.get("documentId"),
                    "platformDraftQuestionId": tmpl.get("questionId"),
                },
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
            documentId=tmpl.get("documentId"),
            questionType=tmpl["questionType"],
            category=tmpl["category"],
            content=tmpl["content"],
            options=tmpl.get("options"),
            correctAnswer=tmpl.get("correctAnswer"),
            explanation=tmpl.get("explanation"),
            rubric=tmpl.get("rubric"),
            evidenceChunkIds=tmpl.get("evidenceChunkIds", []),
            status="draft",
            createdAt=created_at_text,
            updatedAt=tmpl.get("updatedAt"),
        ).model_dump())

    session.commit()
    return results


def list_questions(session: Session, plan_id: str | None = None, question_status: str | None = None) -> list[dict]:
    """列出题目。

    指定计划时，返回当前计划题目以及该计划文档在其他计划中已生成的题目。
    """
    from app.schemas.training_question import TrainingQuestionDTO
    from app.tables import training_plans

    query = select(training_questions)
    if question_status:
        query = query.where(training_questions.c.status == question_status)
    rows = session.execute(query.order_by(training_questions.c.created_at.desc())).mappings().all()
    if plan_id:
        plan_row = session.execute(
            select(training_plans.c.documents).where(training_plans.c.plan_id == plan_id)
        ).first()
        plan_doc_ids = {
            item.get("documentId")
            for item in ((plan_row[0] if plan_row else []) or [])
            if isinstance(item, dict) and item.get("documentId")
        }
        rows = [
            row for row in rows
            if row["plan_id"] == plan_id or (row["metadata"] or {}).get("documentId") in plan_doc_ids
        ]

    return [
        TrainingQuestionDTO(
            questionId=r["question_id"],
            planId=r["plan_id"],
            appId=r["app_id"],
            documentId=(r["metadata"] or {}).get("documentId"),
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
            updatedAt=r["updated_at"].isoformat(),
        ).model_dump()
        for r in rows
    ]


def review_question(session: Session, user_id: str | None, question_id: str, decision: str) -> dict:
    """审核题目；通过后直接发布，未通过则物理删除草稿。"""
    row = session.execute(
        select(training_questions).where(training_questions.c.question_id == question_id)
    ).mappings().first()

    if row is None:
        raise TrainingQuestionNotFoundError(f"题目 {question_id} 不存在")

    if row["status"] != "draft":
        raise TrainingQuestionConflictError(f"题目状态为 {row['status']}，不能审核")

    if decision == "rejected":
        session.execute(sa_delete(training_questions).where(training_questions.c.question_id == question_id))
        session.commit()
        return {"questionId": question_id, "status": "deleted"}

    now = datetime.now(timezone.utc)
    session.execute(
        sa_update(training_questions)
        .where(training_questions.c.question_id == question_id)
        .values(status="published", updated_at=now, updated_by=user_id)
    )
    session.commit()
    return {"questionId": question_id, "status": "published"}


def update_question(session: Session, user_id: str | None, question_id: str, request: Any) -> dict:
    """在 ex-app 本地修改题目。"""
    row = session.execute(
        select(training_questions).where(training_questions.c.question_id == question_id)
    ).mappings().first()
    if row is None:
        raise TrainingQuestionNotFoundError(f"题目 {question_id} 不存在")
    payload = request.model_dump(exclude_none=True)

    now = datetime.now(timezone.utc)
    values = {}
    if "content" in payload:
        values["content"] = payload["content"]
    if "options" in payload:
        values["options"] = payload["options"]
    if "correctAnswer" in payload:
        values["correct_answer"] = payload["correctAnswer"]
    if "explanation" in payload:
        values["explanation"] = payload["explanation"]
    if "rubric" in payload:
        values["rubric"] = payload["rubric"]
    if "evidenceChunkIds" in payload:
        values["evidence_chunk_ids"] = payload["evidenceChunkIds"]
    values.update(updated_at=now, updated_by=user_id)
    session.execute(sa_update(training_questions).where(training_questions.c.question_id == question_id).values(**values))
    session.commit()
    return {"questionId": question_id, "status": row["status"]}


def delete_question(session: Session, question_id: str) -> dict:
    """物理删除本地题目；用于题库维护和审核不通过场景。"""
    row = session.execute(
        select(training_questions.c.question_id).where(training_questions.c.question_id == question_id)
    ).first()
    if row is None:
        raise TrainingQuestionNotFoundError(f"题目 {question_id} 不存在")

    session.execute(sa_delete(training_questions).where(training_questions.c.question_id == question_id))
    session.commit()
    return {"questionId": question_id, "status": "deleted"}


def create_question(session: Session, user_id: str | None, request: Any) -> dict:
    """管理员手动录入题目。"""
    from app.schemas.training_question import TrainingQuestionDTO
    from app.core.config import get_settings

    now = datetime.now(timezone.utc)
    qid = new_id()

    # 从计划获取 app_id，校验计划存在且未删除
    from app.tables import training_plans
    settings = get_settings()
    app_id = settings.platform_app_id or "local"

    plan_row = session.execute(
        select(training_plans.c.app_id)
        .where(training_plans.c.plan_id == request.planId)
        .where(training_plans.c.deleted_at.is_(None))
    ).first()
    if plan_row is None:
        raise TrainingQuestionNotFoundError(f"学习计划 {request.planId} 不存在或已删除")
    app_id = plan_row[0]

    metadata: dict[str, Any] = {}
    if request.documentId:
        metadata["documentId"] = request.documentId

    session.execute(
        training_questions.insert().values(
            question_id=qid,
            plan_id=request.planId,
            app_id=app_id,
            question_type=request.questionType,
            category="practice",
            content=request.content,
            options=request.options,
            correct_answer=request.correctAnswer,
            explanation=request.explanation,
            rubric=request.rubric,
            evidence_chunk_ids=[],
            status="draft",
            metadata=metadata,
            created_at=now,
            created_by=user_id,
            updated_at=now,
            updated_by=user_id,
        )
    )
    session.commit()

    return TrainingQuestionDTO(
        questionId=qid,
        planId=request.planId,
        appId=app_id,
        documentId=request.documentId,
        questionType=request.questionType,
        category="practice",
        content=request.content,
        options=request.options,
        correctAnswer=request.correctAnswer,
        explanation=request.explanation,
        rubric=request.rubric,
        evidenceChunkIds=[],
        status="draft",
        createdAt=now.isoformat(),
        updatedAt=now.isoformat(),
    ).model_dump()


def count_questions_by_document(session: Session, plan_id: str) -> dict[str, int]:
    """统计计划文档在本地题库中已发布的题目数量。

    仅 status='published' 的题目计入统计。
    """
    from app.tables import training_plans

    plan_row = session.execute(
        select(training_plans.c.documents).where(training_plans.c.plan_id == plan_id)
    ).first()
    plan_doc_ids = {
        item.get("documentId")
        for item in ((plan_row[0] if plan_row else []) or [])
        if isinstance(item, dict) and item.get("documentId")
    }
    rows = session.execute(
        select(training_questions.c.metadata, training_questions.c.plan_id)
        .where(training_questions.c.status == "published")
    ).fetchall()

    counts: dict[str, int] = {}
    for r in rows:
        meta = r[0] or {}
        doc_id = meta.get("documentId")
        if doc_id and (not plan_doc_ids or doc_id in plan_doc_ids or r[1] == plan_id):
            counts[doc_id] = counts.get(doc_id, 0) + 1
    return counts


def create_question_appeal(session: Session, question_id: str, request: Any) -> dict:
    """在 ex-app 本地记录学员题目异议。"""
    from app.schemas.training_question import TrainingQuestionAppealDTO

    row = session.execute(
        select(training_questions.c.question_id).where(training_questions.c.question_id == question_id)
    ).mappings().first()
    if row is None:
        raise TrainingQuestionNotFoundError(f"题目 {question_id} 不存在")

    now = datetime.now(timezone.utc)
    appeal_id = new_id()
    session.execute(
        training_question_appeals.insert().values(
            appeal_id=appeal_id,
            question_id=question_id,
            end_user_id=request.endUserId,
            reason=request.reason,
            answer_record_id=request.answerRecordId,
            status="open",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    return TrainingQuestionAppealDTO(
        appealId=appeal_id,
        questionId=question_id,
        endUserId=request.endUserId,
        reason=request.reason,
        answerRecordId=request.answerRecordId,
        status="open",
        createdAt=now.isoformat(),
    ).model_dump()


def resolve_question_appeal(session: Session, user_id: str | None, appeal_id: str, request: Any) -> dict:
    """在 ex-app 本地处理题目异议。"""
    from app.schemas.training_question import TrainingQuestionAppealDTO

    row = session.execute(
        select(training_question_appeals).where(training_question_appeals.c.appeal_id == appeal_id)
    ).mappings().first()
    if row is None:
        raise TrainingQuestionNotFoundError(f"题目异议 {appeal_id} 不存在")

    if row["status"] != "open":
        raise TrainingQuestionConflictError(f"该异议状态为 {row['status']}，不能重复处理")

    now = datetime.now(timezone.utc)
    session.execute(
        sa_update(training_question_appeals)
        .where(training_question_appeals.c.appeal_id == appeal_id)
        .values(
            status=request.status,
            resolution=request.resolution,
            resolved_at=now,
            resolved_by=user_id,
            updated_at=now,
        )
    )
    session.commit()
    return TrainingQuestionAppealDTO(
        appealId=appeal_id,
        questionId=row["question_id"],
        endUserId=row["end_user_id"],
        reason=row["reason"],
        answerRecordId=row["answer_record_id"],
        status=request.status,
        resolution=request.resolution,
        createdAt=row["created_at"].isoformat(),
        resolvedAt=now.isoformat(),
    ).model_dump()
