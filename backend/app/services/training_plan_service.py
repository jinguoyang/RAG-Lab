"""员工培训学习计划平台侧服务。"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.training_plan import AbilityGroupDTO, DocumentDTO, PlanDraftDTO
from app.services.training_agent_service import evidence_title, read_training_evidence, resolve_training_context
from app.tables import training_plans


def _difficulty_for_index(index: int) -> str:
    """按学习顺序给出可编辑的默认难度分层。"""
    if index <= 1:
        return "basic"
    if index <= 3:
        return "normal"
    return "advanced"


def _ability_groups(job_title: str) -> list[AbilityGroupDTO]:
    """生成稳定的岗位能力分组，供管理员二次编辑。"""
    return [
        AbilityGroupDTO(name="基础认知", description=f"理解{job_title}岗位目标、边界和基础术语。"),
        AbilityGroupDTO(name="作业流程", description=f"掌握{job_title}的关键步骤、检查项和异常处理。"),
        AbilityGroupDTO(name="风险与复盘", description="识别高风险点，并能在测验和复盘中说明处理依据。"),
    ]


def create_plan_draft(session: Session, credential: str, request: Any) -> PlanDraftDTO:
    """基于当前员工培训 App 的知识库证据生成学习计划草稿。"""
    context = resolve_training_context(session, credential, request.appId)
    now = datetime.now(UTC)
    query = f"{request.jobTitle} {request.jobDescription or ''}".strip()
    rows = read_training_evidence(session, context.kb_row["kb_id"], query, limit=8)

    documents: list[DocumentDTO] = []
    seen_document_ids: set[str] = set()
    groups = _ability_groups(request.jobTitle)
    for index, row in enumerate(rows, start=1):
        document_id = str(row["document_id"])
        if document_id in seen_document_ids:
            continue
        seen_document_ids.add(document_id)
        group = groups[min(index - 1, len(groups) - 1)].name
        documents.append(
            DocumentDTO(
                documentId=document_id,
                title=evidence_title(row),
                relevance=max(0.1, round(1 - (index - 1) * 0.08, 2)),
                abilityGroup=group,
                difficulty=_difficulty_for_index(index),
            )
        )

    plan_id = new_id()
    evidence_chunk_ids = [str(row["chunk_id"]) for row in rows]
    reading_order = [doc.documentId for doc in documents]
    recommend_reason = (
        f"已根据「{request.jobTitle}」岗位描述，从当前知识库匹配到 {len(documents)} 份学习材料，"
        "并按基础认知、作业流程、风险与复盘组织学习顺序。"
    )

    session.execute(
        insert(training_plans).values(
            plan_id=plan_id,
            app_id=context.app_row["app_id"],
            job_title=request.jobTitle,
            job_description=request.jobDescription,
            status="draft",
            ability_groups=[item.model_dump() for item in groups],
            documents=[item.model_dump() for item in documents],
            evidence_chunk_ids=evidence_chunk_ids,
            recommend_reason=recommend_reason,
            reading_order=reading_order,
            version=1,
            metadata={"source": "employee_training_agent", "retrievalQuery": query},
            created_at=now,
            created_by=context.actor.user.userId,
            updated_at=now,
            updated_by=context.actor.user.userId,
            deleted_at=None,
            deleted_by=None,
        )
    )
    session.commit()

    return PlanDraftDTO(
        planId=str(plan_id),
        appId=str(context.app_row["app_id"]),
        jobTitle=request.jobTitle,
        jobDescription=request.jobDescription,
        status="draft",
        abilityGroups=groups,
        documents=documents,
        evidenceChunkIds=evidence_chunk_ids,
        recommendReason=recommend_reason,
        readingOrder=reading_order,
        version=1,
        createdAt=now.isoformat(),
        updatedAt=now.isoformat(),
    )
