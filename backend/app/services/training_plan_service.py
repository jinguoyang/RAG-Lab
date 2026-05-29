"""员工培训学习计划平台侧服务。"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.training_plan import AbilityGroupDTO, DocumentDTO, PlanDraftDTO
from app.services.training_agent_service import (
    TrainingAgentConflictError,
    TrainingAgentNotFoundError,
    evidence_preview,
    evidence_title,
    read_training_evidence,
    resolve_training_context,
)
from app.services.training_llm_client import LLMCallError, call_llm
from app.services.training_llm_json_service import TrainingLLMOutputError, parse_training_json
from app.services.training_skill_registry_service import record_training_skill_call
from app.tables import training_plans

logger = logging.getLogger(__name__)


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


def _build_evidence_summary(rows: list) -> str:
    """构建知识库证据摘要，用于 LLM prompt。"""
    lines: list[str] = []
    for i, row in enumerate(rows, start=1):
        doc_id = str(row["document_id"])
        title = evidence_title(row)
        preview = evidence_preview(row, limit=300)
        lines.append(f"[{i}] documentId={doc_id} title={title}\n内容摘要: {preview}")
    return "\n\n".join(lines)


def _build_llm_prompt(job_title: str, job_description: str, evidence_summary: str) -> list[dict[str, str]]:
    """构建 LLM chat messages。"""
    system = (
        "你是一个企业培训计划规划助手。根据岗位信息和知识库文档，生成结构化的学习计划。\n"
        "你必须严格返回 JSON 格式，不要包含任何其他文字。\n"
        "JSON schema:\n"
        "{\n"
        '  "abilityGroups": [\n'
        '    {"name": "string", "description": "string"}\n'
        "  ],\n"
        '  "documents": [\n'
        '    {"documentId": "string", "title": "string", "relevance": 0.0-1.0, "abilityGroup": "string", "difficulty": "basic|normal|advanced"}\n'
        "  ],\n"
        '  "readingOrder": ["documentId1", "documentId2"],\n'
        '  "recommendReason": "string"\n'
        "}\n\n"
        "规则:\n"
        "1. documentId 必须是证据中提供的真实 documentId，不得编造。\n"
        "2. abilityGroup 的 name 必须与 abilityGroups 中的 name 一致。\n"
        "3. readingOrder 中的 documentId 必须来自 documents 列表。\n"
        "4. 按学习难度从低到高排列 readingOrder。"
    )
    user = (
        f"岗位名称: {job_title}\n"
        f"岗位描述: {job_description}\n\n"
        f"知识库证据:\n{evidence_summary}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _generate_plan_with_llm(
    session: Session,
    job_title: str,
    job_description: str,
    rows: list,
    app_id: str,
) -> tuple[list[AbilityGroupDTO], list[DocumentDTO], list[str], str, list[str]] | None:
    """尝试用 LLM 生成学习计划，成功返回 (groups, documents, reading_order, reason, chunk_ids)，失败返回 None。"""
    evidence_chunk_ids = [str(row["chunk_id"]) for row in rows]
    valid_document_ids = {str(row["document_id"]) for row in rows}

    evidence_summary = _build_evidence_summary(rows)
    messages = _build_llm_prompt(job_title, job_description, evidence_summary)

    start = time.monotonic()
    try:
        raw_text = _call_llm(messages)
        latency_ms = int((time.monotonic() - start) * 1000)
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.warning("LLM 调用失败，将回退到规则生成: %s", exc)
        record_training_skill_call(
            session,
            skill_name="buildLearningPlanDraft",
            status="error",
            app_id=app_id,
            input_summary=f"jobTitle={job_title}",
            error_code="LLM_CALL_FAILED",
            latency_ms=latency_ms,
        )
        session.commit()
        return None

    try:
        required_keys = {"abilityGroups", "documents", "readingOrder", "recommendReason"}
        data = parse_training_json(raw_text, required_keys=required_keys)
    except TrainingLLMOutputError as exc:
        logger.warning("LLM 输出解析失败，将回退到规则生成: %s", exc)
        record_training_skill_call(
            session,
            skill_name="buildLearningPlanDraft",
            status="error",
            app_id=app_id,
            input_summary=f"jobTitle={job_title}",
            error_code="LLM_PARSE_FAILED",
            latency_ms=latency_ms,
        )
        session.commit()
        return None

    # 解析 abilityGroups
    raw_groups = data.get("abilityGroups", [])
    groups: list[AbilityGroupDTO] = []
    for g in raw_groups:
        if isinstance(g, dict) and g.get("name") and g.get("description"):
            groups.append(AbilityGroupDTO(name=str(g["name"]), description=str(g["description"])))
    if not groups:
        groups = _ability_groups(job_title)

    # 解析 documents，验证 documentId 必须在证据中
    raw_documents = data.get("documents", [])
    documents: list[DocumentDTO] = []
    seen_ids: set[str] = set()
    for d in raw_documents:
        if not isinstance(d, dict):
            continue
        doc_id = str(d.get("documentId", ""))
        if not doc_id or doc_id not in valid_document_ids:
            logger.warning("LLM 返回的 documentId=%s 不在证据中，已跳过", doc_id)
            continue
        if doc_id in seen_ids:
            continue
        seen_ids.add(doc_id)
        group_name = str(d.get("abilityGroup", "")) or (groups[0].name if groups else "")
        # 确保 abilityGroup 在 groups 中
        group_names = {g.name for g in groups}
        if group_name not in group_names:
            group_name = groups[0].name if groups else ""
        documents.append(
            DocumentDTO(
                documentId=doc_id,
                title=str(d.get("title", "")) or _find_evidence_title(rows, doc_id),
                relevance=_clamp(float(d.get("relevance", 0.5)), 0.0, 1.0),
                abilityGroup=group_name,
                difficulty=_validate_difficulty(str(d.get("difficulty", "normal"))),
            )
        )

    # 如果 LLM 返回的文档全部无效，回退
    if not documents:
        logger.warning("LLM 返回的 documentId 全部无效，将回退到规则生成")
        record_training_skill_call(
            session,
            skill_name="buildLearningPlanDraft",
            status="error",
            app_id=app_id,
            input_summary=f"jobTitle={job_title}",
            error_code="LLM_NO_VALID_DOCUMENTS",
            latency_ms=latency_ms,
        )
        session.commit()
        return None

    # 解析 readingOrder，只保留有效的 documentId
    valid_doc_ids = {doc.documentId for doc in documents}
    raw_order = data.get("readingOrder", [])
    reading_order = [str(oid) for oid in raw_order if str(oid) in valid_doc_ids]
    # 补充 LLM 遗漏的文档
    for doc in documents:
        if doc.documentId not in reading_order:
            reading_order.append(doc.documentId)

    recommend_reason = str(data.get("recommendReason", ""))
    if not recommend_reason:
        recommend_reason = (
            f"已根据「{job_title}」岗位描述，从当前知识库匹配到 {len(documents)} 份学习材料，"
            "并按 AI 推荐的学习顺序组织。"
        )

    # 审计成功
    record_training_skill_call(
        session,
        skill_name="buildLearningPlanDraft",
        status="success",
        app_id=app_id,
        input_summary=f"jobTitle={job_title}",
        output_summary=f"groups={len(groups)}, documents={len(documents)}",
        latency_ms=latency_ms,
    )
    session.commit()

    return groups, documents, reading_order, recommend_reason, evidence_chunk_ids


def _find_evidence_title(rows: list, document_id: str) -> str:
    """从证据行中查找指定 document_id 的标题。"""
    for row in rows:
        if str(row["document_id"]) == document_id:
            return evidence_title(row)
    return f"文档 {document_id[:8]}"


def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def _validate_difficulty(value: str) -> str:
    if value in ("basic", "normal", "advanced"):
        return value
    return "normal"


def _rule_based_plan(
    job_title: str,
    rows: list,
) -> tuple[list[AbilityGroupDTO], list[DocumentDTO], list[str], str, list[str]]:
    """规则化生成学习计划（原有逻辑）。"""
    groups = _ability_groups(job_title)
    documents: list[DocumentDTO] = []
    seen_document_ids: set[str] = set()
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
    evidence_chunk_ids = [str(row["chunk_id"]) for row in rows]
    reading_order = [doc.documentId for doc in documents]
    recommend_reason = (
        f"已根据「{job_title}」岗位描述，从当前知识库匹配到 {len(documents)} 份学习材料，"
        "并按基础认知、作业流程、风险与复盘组织学习顺序。"
    )
    return groups, documents, reading_order, recommend_reason, evidence_chunk_ids


def create_plan_draft(session: Session, credential: str, request: Any) -> PlanDraftDTO:
    """基于当前员工培训 App 的知识库证据生成学习计划草稿。

    优先使用 LLM 生成，失败时静默回退到规则化逻辑。
    """
    context = resolve_training_context(session, credential, request.appId)
    now = datetime.now(UTC)
    query = f"{request.jobTitle} {request.jobDescription or ''}".strip()
    rows = read_training_evidence(session, context.kb_row["kb_id"], query, limit=8)

    # 尝试 LLM 生成
    llm_result = _generate_plan_with_llm(
        session,
        request.jobTitle,
        request.jobDescription or "",
        rows,
        str(context.app_row["app_id"]),
    )

    if llm_result is not None:
        groups, documents, reading_order, recommend_reason, evidence_chunk_ids = llm_result
    else:
        # 回退到规则化逻辑
        groups, documents, reading_order, recommend_reason, evidence_chunk_ids = _rule_based_plan(
            request.jobTitle, rows,
        )

    plan_id = new_id()

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


def _review_plan(session: Session, plan_id: str, user_id: str, new_status: str) -> PlanDraftDTO:
    """通用审核逻辑：将 draft 计划改为 published 或 rejected。"""
    row = session.execute(
        select(training_plans).where(training_plans.c.plan_id == plan_id)
    ).mappings().first()
    if row is None:
        raise TrainingAgentNotFoundError(f"Plan {plan_id} not found.")
    if row["status"] != "draft":
        raise TrainingAgentConflictError(
            f"Plan {plan_id} is '{row['status']}', only 'draft' plans can be reviewed."
        )

    now = datetime.now(UTC)
    existing_meta = dict(row["metadata"] or {})
    existing_meta["reviewedBy"] = user_id
    existing_meta["reviewedAt"] = now.isoformat()

    session.execute(
        update(training_plans)
        .where(training_plans.c.plan_id == plan_id)
        .values(
            status=new_status,
            updated_at=now,
            updated_by=user_id,
            metadata=existing_meta,
        )
    )
    session.commit()

    ability_groups = [AbilityGroupDTO(**g) for g in (row["ability_groups"] or [])]
    documents = [DocumentDTO(**d) for d in (row["documents"] or [])]
    return PlanDraftDTO(
        planId=str(row["plan_id"]),
        appId=str(row["app_id"]),
        jobTitle=row["job_title"],
        jobDescription=row["job_description"] or "",
        status=new_status,
        abilityGroups=ability_groups,
        documents=documents,
        evidenceChunkIds=row["evidence_chunk_ids"] or [],
        recommendReason=row["recommend_reason"] or "",
        readingOrder=row["reading_order"] or [],
        version=row["version"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=now.isoformat(),
    )


def publish_plan(session: Session, plan_id: str, user_id: str) -> PlanDraftDTO:
    """将 draft 学习计划发布为 published。"""
    return _review_plan(session, plan_id, user_id, "published")


def reject_plan(session: Session, plan_id: str, user_id: str) -> PlanDraftDTO:
    """将 draft 学习计划拒绝为 rejected。"""
    return _review_plan(session, plan_id, user_id, "rejected")
