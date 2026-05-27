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
    """生成题库草稿。首版使用模板数据。"""
    from app.schemas.training_question import TrainingQuestionDTO

    now = datetime.now(timezone.utc)
    templates = _generate_template_questions(request.planId, request.appId, request.count)

    results = []
    for tmpl in templates:
        qid = new_id()
        session.execute(
            training_questions.insert().values(
                question_id=qid,
                plan_id=request.planId,
                app_id=request.appId,
                question_type=tmpl["questionType"],
                category=tmpl["category"],
                content=tmpl["content"],
                options=tmpl.get("options"),
                correct_answer=tmpl.get("correctAnswer"),
                explanation=tmpl.get("explanation"),
                rubric=tmpl.get("rubric"),
                evidence_chunk_ids=tmpl.get("evidenceChunkIds", []),
                status="draft",
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
            appId=request.appId,
            questionType=tmpl["questionType"],
            category=tmpl["category"],
            content=tmpl["content"],
            options=tmpl.get("options"),
            correctAnswer=tmpl.get("correctAnswer"),
            explanation=tmpl.get("explanation"),
            rubric=tmpl.get("rubric"),
            evidenceChunkIds=tmpl.get("evidenceChunkIds", []),
            status="draft",
            createdAt=now.isoformat(),
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


def _generate_template_questions(plan_id: str, app_id: str, count: int) -> list[dict]:
    """首版模板题目生成。后续替换为 LLM 调用。"""
    templates = [
        {
            "questionType": "single_choice",
            "category": "practice",
            "content": "以下哪项是 RAG 系统的核心组件？",
            "options": [
                {"label": "A", "text": "向量数据库"},
                {"label": "B", "text": "关系型数据库"},
                {"label": "C", "text": "文件系统"},
                {"label": "D", "text": "消息队列"},
            ],
            "correctAnswer": "A",
            "explanation": "RAG 系统使用向量数据库存储和检索文档嵌入。",
            "evidenceChunkIds": ["chunk-001"],
        },
        {
            "questionType": "true_false",
            "category": "practice",
            "content": "RAG 系统可以完全替代传统的搜索引擎。",
            "options": [
                {"label": "true", "text": "正确"},
                {"label": "false", "text": "错误"},
            ],
            "correctAnswer": "false",
            "explanation": "RAG 和传统搜索引擎适用于不同场景，不能完全替代。",
            "evidenceChunkIds": ["chunk-002"],
        },
        {
            "questionType": "single_choice",
            "category": "certification",
            "content": "在 RAG 流程中，检索阶段的主要目标是什么？",
            "options": [
                {"label": "A", "text": "生成回答"},
                {"label": "B", "text": "找到与问题相关的文档片段"},
                {"label": "C", "text": "训练模型"},
                {"label": "D", "text": "存储数据"},
            ],
            "correctAnswer": "B",
            "explanation": "检索阶段的核心是找到与用户问题最相关的文档片段。",
            "evidenceChunkIds": ["chunk-001", "chunk-003"],
        },
        {
            "questionType": "subjective",
            "category": "certification",
            "content": "请描述 RAG 系统中检索增强生成的工作原理。",
            "rubric": {
                "criteria": [
                    {"name": "检索阶段描述", "weight": 0.3, "description": "正确描述向量检索过程"},
                    {"name": "生成阶段描述", "weight": 0.3, "description": "正确描述 LLM 生成过程"},
                    {"name": "整合描述", "weight": 0.2, "description": "描述检索结果如何增强生成"},
                    {"name": "示例", "weight": 0.2, "description": "提供具体示例"},
                ],
                "totalScore": 10,
            },
            "evidenceChunkIds": ["chunk-001", "chunk-002", "chunk-003"],
        },
    ]
    return templates[:count]
