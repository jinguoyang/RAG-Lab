"""员工培训学习计划平台侧服务。"""
from __future__ import annotations

import logging
import time
import json
from difflib import SequenceMatcher
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.schemas.training_plan import AbilityGroupDTO, DocumentDTO, LearningSectionDTO, PlanDraftDTO, TeachingScriptDTO
from app.services.app_llm_audit_service import begin_app_llm_invocation, finish_app_llm_invocation
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


def _is_low_value_plan_evidence(row: Mapping[str, Any]) -> bool:
    """过滤封面、目录、版本记录和空附录等不参与课程蓝图的内容。"""
    heading = "".join(str(row.get("heading") or "").lower().split())
    section = "".join(str(row.get("section") or "").lower().split())
    content = " ".join(str(row.get("content") or "").split())
    labels = {heading.strip("：:.-_"), section.strip("：:.-_")}
    if labels & {"封面", "目录", "目次", "版本记录", "修订记录", "变更记录", "更改记录"}:
        return True
    compact = "".join(content.split())
    if not compact:
        return True
    if any(label.startswith("附录") for label in labels if label) and len(compact) <= 100:
        return True
    if "目次" in compact and ("......" in compact or "规范性引用文件" in compact):
        return True
    if "版本" in compact and "更改内容" in compact and "更改单编号" in compact:
        return True
    return len(compact) <= 320 and "企业标准" in compact and "发布" in compact and "实施" in compact


def _build_document_content_map(rows: list[Mapping[str, Any]], max_chars: int = 48000) -> str:
    """按文档和章节恢复完整内容地图，供课程蓝图模型理解全篇结构。"""
    documents: dict[str, dict[str, list[str]]] = {}
    document_titles: dict[str, str] = {}
    for row in rows:
        if _is_low_value_plan_evidence(row):
            continue
        document_id = str(row.get("document_id") or "")
        if not document_id:
            continue
        document_titles.setdefault(document_id, evidence_title(row))
        section = str(row.get("section") or "").strip()
        heading = str(row.get("heading") or "").strip()
        location = " / ".join(item for item in (section, heading) if item)
        location = location or "正文"
        content = " ".join(str(row.get("content") or "").split())
        chunk_id = str(row.get("chunk_id") or "")
        entry = f"[chunkId={chunk_id}] {content}" if chunk_id else content
        section_entries = documents.setdefault(document_id, {}).setdefault(location, [])
        if entry not in section_entries:
            section_entries.append(entry)

    lines: list[str] = []
    for document_id, sections in documents.items():
        lines.append(f"文档：{document_titles.get(document_id, document_id)}（documentId={document_id}）")
        for location, contents in sections.items():
            lines.append(f"章节：{location}")
            lines.extend(contents)
        lines.append("")
    return "\n".join(lines)[:max_chars]


def _max_verbatim_overlap(script_text: str, evidence_texts: list[str]) -> float:
    """估算讲稿与单条证据的直接重合度，避免整段复制 Chunk。"""
    normalized_script = "".join(script_text.split())
    if not normalized_script:
        return 1.0
    overlaps = []
    for evidence in evidence_texts:
        normalized_evidence = "".join(str(evidence).split())
        if not normalized_evidence:
            continue
        if normalized_evidence in normalized_script and len(normalized_evidence) >= 18:
            overlaps.append(1.0)
        else:
            overlaps.append(SequenceMatcher(None, normalized_script, normalized_evidence).ratio())
    return max(overlaps, default=0.0)


def _score_teaching_script(
    script: Mapping[str, Any],
    *,
    learning_objective: str,
    key_points: list[str],
    checkpoint_criteria: list[str],
    evidence_texts: list[str],
) -> float:
    """按教学结构、目标一致性、条理、案例和非 Chunk 化计算初版质量分。"""
    opening = str(script.get("opening") or "").strip()
    explanation = str(script.get("explanation") or "").strip()
    scenario = str(script.get("scenario") or "").strip()
    questions = [str(item).strip() for item in (script.get("interactionQuestions") or []) if str(item).strip()]
    summary = str(script.get("summary") or "").strip()
    combined = "\n".join([opening, explanation, scenario, *questions, summary])

    structure_count = sum(bool(item) for item in (opening, explanation, scenario, questions, summary))
    structure_score = 0.25 * structure_count / 5
    alignment_score = 0.2 if learning_objective and key_points and checkpoint_criteria and explanation and summary else 0.0
    relation_markers = ("先", "再", "然后", "最后", "因此", "但是", "不等于", "由", "之后", "同时")
    coherence_score = 0.2 if len(explanation) >= 45 and sum(marker in explanation for marker in relation_markers) >= 2 else 0.1 if len(explanation) >= 30 else 0.0
    action_markers = ("判断", "核对", "提报", "复核", "评审", "处理", "记录", "停止", "确认", "审批")
    scenario_score = 0.15 if len(scenario) >= 30 and any(marker in scenario for marker in action_markers) else 0.0
    banned_markers = ("chunkid", "chunk id", "参考证据", "证据包", "以下片段")
    overlap = _max_verbatim_overlap(combined, evidence_texts)
    non_chunk_score = 0.2 if not any(marker in combined.lower() for marker in banned_markers) and overlap < 0.72 else 0.0
    return round(min(1.0, structure_score + alignment_score + coherence_score + scenario_score + non_chunk_score), 2)


def _build_llm_prompt(job_title: str, job_description: str, evidence_summary: str) -> list[dict[str, str]]:
    """构建 LLM chat messages。"""
    system = (
        "你是一个企业培训计划规划助手。根据岗位信息和知识库文档，先识别可验证学习目标，再生成结构化学习计划。\n"
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
        "4. 按学习难度从低到高排列 readingOrder。\n"
        "5. abilityGroups 必须表示可独立验证的学习目标；同一目标可关联多个文档，短课程允许只有一个目标。"
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


def _build_section_prompt(
    job_title: str,
    job_description: str,
    documents: list[DocumentDTO],
    content_map: str,
) -> list[dict[str, str]]:
    """构建课程蓝图 Prompt，要求模型基于全文结构输出章节级讲稿。"""
    valid_documents = "\n".join(f"- {item.documentId}: {item.title}" for item in documents)
    system = (
        "你是企业一对一培训课程设计师。你要先理解完整制度结构，再按业务逻辑和可验证学习目标设计课程，"
        "不能按 Chunk 数量机械分节，也不能把 Chunk 原文直接当讲稿。\n"
        "严格返回 JSON，不要输出其他文字。格式为：\n"
        '{"sections":[{"sectionId":"section-001","title":"string","learningObjective":"string",'
        '"sourceDocumentIds":["documentId"],"evidenceChunkIds":["chunkId"],"keyPoints":["string"],'
        '"checkpointCriteria":["string"],"opening":"string","explanation":"string",'
        '"scenario":"string","interactionQuestions":["string"],"summary":"string",'
        '"estimatedMinutes":8,"required":true}]}\n'
        "规则：\n"
        "1. 先围绕为什么、是什么、如何判断、谁负责、流程如何走、风险与改进等语义组织课程；不是每个标题都必须单独成节。\n"
        "2. 短文档允许一节，长制度通常按 4 至 8 个真实学习目标组织，不设置固定数量。\n"
        "3. opening、explanation、scenario、interactionQuestions、summary 必须直接位于 section 对象中，禁止再嵌套对象。"
        " explanation 必须像教师讲稿一样解释概念关系、职责边界或流程顺序，不得列出 Chunk 标签或复制大段原文。\n"
        "4. opening 使用岗位情境提问；scenario 必须包含具体条件、判断过程和正确动作；interactionQuestions 为 1 至 3 个。\n"
        "5. sourceDocumentIds 和 evidenceChunkIds 只能使用输入中真实存在的 ID。\n"
        "6. Checkpoint 标准必须可观察、可判断，不能写成泛泛的“理解本节”。"
    )
    user = (
        f"岗位名称：{job_title}\n岗位描述：{job_description}\n\n"
        f"可用文档：\n{valid_documents}\n\n"
        f"完整文档内容地图：\n{content_map}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_generated_sections(
    data: Mapping[str, Any],
    documents: list[DocumentDTO],
    rows: list[Mapping[str, Any]],
) -> list[LearningSectionDTO]:
    """校验模型章节来源并计算教学质量分。"""
    valid_document_ids = {item.documentId for item in documents}
    valid_chunk_ids = {str(row.get("chunk_id") or "") for row in rows}
    evidence_by_chunk = {
        str(row.get("chunk_id") or ""): str(row.get("content") or "")
        for row in rows
        if row.get("chunk_id")
    }
    sections: list[LearningSectionDTO] = []
    for index, raw in enumerate(data.get("sections") or [], start=1):
        if not isinstance(raw, Mapping):
            continue
        source_document_ids = [
            str(item) for item in (raw.get("sourceDocumentIds") or [])
            if str(item) in valid_document_ids
        ]
        evidence_chunk_ids = [
            str(item) for item in (raw.get("evidenceChunkIds") or [])
            if str(item) in valid_chunk_ids
        ]
        if not source_document_ids or not evidence_chunk_ids:
            continue
        script_raw = raw.get("teachingScript")
        if not isinstance(script_raw, Mapping):
            script_raw = {
                "opening": raw.get("opening"),
                "explanation": raw.get("explanation"),
                "scenario": raw.get("scenario"),
                "interactionQuestions": raw.get("interactionQuestions"),
                "summary": raw.get("summary"),
            }
        script = TeachingScriptDTO(**script_raw)
        key_points = [str(item) for item in (raw.get("keyPoints") or []) if item]
        criteria = [str(item) for item in (raw.get("checkpointCriteria") or []) if item]
        objective = str(raw.get("learningObjective") or "").strip()
        quality_score = _score_teaching_script(
            script.model_dump(),
            learning_objective=objective,
            key_points=key_points,
            checkpoint_criteria=criteria,
            evidence_texts=[evidence_by_chunk[item] for item in evidence_chunk_ids if item in evidence_by_chunk],
        )
        sections.append(
            LearningSectionDTO(
                sectionId=str(raw.get("sectionId") or f"section-{index:03d}"),
                title=str(raw.get("title") or f"第 {index} 节"),
                learningObjective=objective,
                sourceDocumentIds=source_document_ids,
                evidenceChunkIds=evidence_chunk_ids,
                keyPoints=key_points,
                checkpointCriteria=criteria,
                teachingScript=script,
                teachingQualityScore=quality_score,
                estimatedMinutes=int(raw.get("estimatedMinutes") or 8),
                required=bool(raw.get("required", True)),
            )
        )
    return sections


def _generate_sections_with_llm(
    session: Session,
    job_title: str,
    job_description: str,
    documents: list[DocumentDTO],
    rows: list[Mapping[str, Any]],
    app_id: str,
) -> list[LearningSectionDTO] | None:
    """基于入选文档全文生成章节课程蓝图，失败时由调用方回退。"""
    content_map = _build_document_content_map(rows)
    if not content_map:
        return None
    started_at = time.monotonic()
    try:
        messages = _build_section_prompt(job_title, job_description, documents, content_map)
        data = None
        last_parse_error: Exception | None = None
        for attempt in range(2):
            retry_messages = messages if attempt == 0 else [
                messages[0],
                {
                    "role": "user",
                    "content": (
                        f"{messages[1]['content']}\n\n"
                        "上一轮输出未形成有效 JSON。请重新生成，尤其检查每个 section 的大括号和逗号；"
                        "五个讲稿字段必须直接放在 section 内，最终只返回一个可被 JSON.parse 解析的对象。"
                    ),
                },
            ]
            try:
                raw_text = call_llm(
                    retry_messages,
                    temperature=0.1,
                    max_tokens=7000,
                    timeout=120,
                    disable_thinking=True,
                )
                data = parse_training_json(raw_text, required_keys={"sections"})
                break
            except TrainingLLMOutputError as exc:
                last_parse_error = exc
        if data is None:
            raise last_parse_error or TrainingLLMOutputError("课程蓝图输出无法解析。")
        sections = _parse_generated_sections(data, documents, rows)
        if sections and any(section.teachingQualityScore < 0.7 for section in sections):
            scores = ", ".join(
                f"{section.sectionId}={section.teachingQualityScore:.2f}"
                for section in sections
            )
            repair_messages = [
                messages[0],
                {
                    "role": "user",
                    "content": (
                        f"{messages[1]['content']}\n\n"
                        "上一版课程蓝图如下：\n"
                        f"{json.dumps(data, ensure_ascii=False)}\n\n"
                        f"程序质量评分：{scores}。请只重写低于 0.70 的五个讲稿字段，"
                        "补足情境导入、概念关系或流程顺序、具体工作案例、互动问题和行动小结；"
                        "禁止复制 Chunk 原文，章节来源 ID 和课程顺序保持不变。返回完整 JSON。"
                    ),
                },
            ]
            repaired_text = call_llm(
                repair_messages,
                temperature=0.2,
                max_tokens=7000,
                timeout=120,
                disable_thinking=True,
            )
            repaired_data = parse_training_json(repaired_text, required_keys={"sections"})
            repaired_sections = _parse_generated_sections(repaired_data, documents, rows)
            if repaired_sections:
                old_average = sum(item.teachingQualityScore for item in sections) / len(sections)
                new_average = sum(item.teachingQualityScore for item in repaired_sections) / len(repaired_sections)
                if new_average >= old_average:
                    sections = repaired_sections
    except (LLMCallError, TrainingLLMOutputError, ValueError, TypeError) as exc:
        logger.warning("课程蓝图生成失败，将回退到规则化小节: %s", exc)
        sections = []
    latency_ms = int((time.monotonic() - started_at) * 1000)
    record_training_skill_call(
        session,
        skill_name="buildTrainingCourseBlueprint",
        status="success" if sections else "error",
        app_id=app_id,
        input_summary=f"jobTitle={job_title}, documents={len(documents)}",
        output_summary=f"sections={len(sections)}",
        error_code=None if sections else "COURSE_BLUEPRINT_FAILED",
        latency_ms=latency_ms,
    )
    session.flush()
    return sections or None


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
        raw_text = call_llm(
            messages,
            max_tokens=2000,
            timeout=120,
            disable_thinking=True,
        )
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
        session.flush()
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
        session.flush()
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
                title=_find_evidence_title(rows, doc_id),
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
        session.flush()
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
    session.flush()

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


def _build_sections(
    groups: list[AbilityGroupDTO],
    documents: list[DocumentDTO],
    rows: list,
) -> list[LearningSectionDTO]:
    """按能力目标组织课程小节，允许一个小节引用多个文档和多个证据。"""
    chunks_by_document: dict[str, list[str]] = {}
    for row in rows:
        document_id = str(row["document_id"])
        chunk_id = str(row["chunk_id"])
        chunks_by_document.setdefault(document_id, [])
        if chunk_id not in chunks_by_document[document_id]:
            chunks_by_document[document_id].append(chunk_id)

    group_descriptions = {group.name: group.description for group in groups}
    grouped_documents: dict[str, list[DocumentDTO]] = {}
    for document in documents:
        group_name = document.abilityGroup or (groups[0].name if groups else "课程目标")
        grouped_documents.setdefault(group_name, []).append(document)

    sections: list[LearningSectionDTO] = []
    for index, (group_name, group_documents) in enumerate(grouped_documents.items(), start=1):
        source_document_ids = [document.documentId for document in group_documents]
        evidence_chunk_ids = [
            chunk_id
            for document_id in source_document_ids
            for chunk_id in chunks_by_document.get(document_id, [])
        ]
        key_points = [document.title for document in group_documents]
        objective = group_descriptions.get(group_name) or f"理解并应用{group_name}相关要求。"
        teaching_script = TeachingScriptDTO(
            opening=f"在实际工作中遇到与「{group_name}」相关的问题时，你会先检查什么？",
            explanation=f"本节围绕{objective}展开。先建立整体判断，再结合关键材料理解执行顺序和风险边界。",
            scenario=f"员工执行{group_name}相关工作时，先核对适用条件，再按要求处理并保留必要记录。",
            interactionQuestions=[f"你认为{group_name}最容易被忽略的环节是什么？"],
            summary=f"掌握{group_name}的判断依据、执行顺序和异常处理要求。",
        )
        evidence_texts = [
            str(row.get("content") or "")
            for row in rows
            if str(row.get("document_id") or "") in source_document_ids
        ]
        criteria = [f"能够说明{group_name}的关键要求", f"能够在实际场景中应用{group_name}要求"]
        sections.append(
            LearningSectionDTO(
                sectionId=f"section-{index:03d}",
                title=group_name,
                learningObjective=objective,
                sourceDocumentIds=source_document_ids,
                evidenceChunkIds=evidence_chunk_ids,
                keyPoints=key_points,
                checkpointCriteria=criteria,
                teachingScript=teaching_script,
                teachingQualityScore=_score_teaching_script(
                    teaching_script.model_dump(),
                    learning_objective=objective,
                    key_points=key_points,
                    checkpoint_criteria=criteria,
                    evidence_texts=evidence_texts,
                ),
                estimatedMinutes=max(5, min(30, len(evidence_chunk_ids) * 3)),
                required=True,
            )
        )
    return sections


def create_plan_draft(
    session: Session,
    credential: str,
    request: Any,
    task_id: str | None = None,
) -> PlanDraftDTO:
    """基于当前员工培训 App 的知识库证据生成学习计划草稿。

    优先使用 LLM 生成，失败时静默回退到规则化逻辑。
    """
    from app.services.task_manager import task_manager as _tm

    context = resolve_training_context(session, credential)
    audit = begin_app_llm_invocation(
        session,
        context,
        endpoint="/api/v1/training/plans/drafts",
        operation="buildLearningPlanDraft",
        skill_name="buildLearningPlanDraft",
        input_summary={
            "jobTitle": request.jobTitle,
            "jobDescriptionLength": len(request.jobDescription or ""),
        },
        user_content={
            "jobTitle": request.jobTitle,
            "jobDescription": request.jobDescription or "",
        },
    )
    try:
        now = datetime.now(UTC)
        query = f"{request.jobTitle} {request.jobDescription or ''}".strip()

        if task_id:
            _tm.append_log(task_id, "info", "正在检索知识库证据...")

        rows = read_training_evidence(session, context.kb_row["kb_id"], query, limit=8)

        if task_id:
            _tm.append_log(task_id, "info", f"检索到 {len(rows)} 条证据")

        # 尝试 LLM 生成
        if task_id:
            _tm.append_log(task_id, "info", "正在调用 LLM 生成学习计划...")

        llm_result = _generate_plan_with_llm(
            session,
            request.jobTitle,
            request.jobDescription or "",
            rows,
            str(context.app_row["app_id"]),
        )

        fallback = llm_result is None
        if llm_result is not None:
            groups, documents, reading_order, recommend_reason, evidence_chunk_ids = llm_result
            if task_id:
                _tm.append_log(task_id, "info", "LLM 生成学习计划成功")
        else:
            if task_id:
                _tm.append_log(task_id, "warning", "LLM 生成失败，回退到规则化逻辑")
            groups, documents, reading_order, recommend_reason, evidence_chunk_ids = _rule_based_plan(
                request.jobTitle, rows,
            )

        if task_id:
            _tm.append_log(task_id, "info", "正在获取文档详细内容...")

        full_rows = read_training_evidence(
            session,
            context.kb_row["kb_id"],
            "",
            limit=200,
            document_ids=[item.documentId for item in documents],
        )
        if not full_rows:
            full_rows = rows

        if task_id:
            _tm.append_log(task_id, "info", "正在生成课程章节...")

        sections = _generate_sections_with_llm(
            session,
            request.jobTitle,
            request.jobDescription or "",
            documents,
            full_rows,
            str(context.app_row["app_id"]),
        ) or _build_sections(groups, documents, full_rows)

        if task_id:
            _tm.append_log(task_id, "info", f"生成了 {len(sections)} 个课程章节")
        evidence_chunk_ids = [str(row["chunk_id"]) for row in full_rows]

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
                metadata={
                    "source": "employee_training_agent",
                    "retrievalQuery": query,
                    "sections": [item.model_dump() for item in sections],
                },
                created_at=now,
                created_by=context.actor.user.userId,
                updated_at=now,
                updated_by=context.actor.user.userId,
                deleted_at=None,
                deleted_by=None,
            )
        )
        session.commit()

        if task_id:
            _tm.append_log(task_id, "info", "学习计划已保存到数据库")

        response = PlanDraftDTO(
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
            sections=sections,
            version=1,
            createdAt=now.isoformat(),
            updatedAt=now.isoformat(),
        )
        finish_app_llm_invocation(
            session,
            audit,
            status="success",
            assistant_content={
                "planId": response.planId,
                "abilityGroupCount": len(response.abilityGroups),
                "documentCount": len(response.documents),
                "fallback": fallback,
            },
            response_summary={
                "planId": response.planId,
                "abilityGroupCount": len(response.abilityGroups),
                "documentCount": len(response.documents),
                "fallback": fallback,
                "llmErrorCode": "LLM_FALLBACK" if fallback else None,
            },
        )
        return response
    except Exception as exc:
        session.rollback()
        finish_app_llm_invocation(
            session,
            audit,
            status="failed",
            assistant_content={"error": str(exc)[:200]},
            response_summary={"error": str(exc)[:200]},
            error_code=exc.__class__.__name__,
        )
        raise


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
    metadata = row["metadata"] or {}
    sections = [LearningSectionDTO(**item) for item in metadata.get("sections", []) if isinstance(item, dict)]
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
        sections=sections,
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
