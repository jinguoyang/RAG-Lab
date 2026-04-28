from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import RowMapping, func, insert, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.config import (
    ConfigRevisionActivationResponse,
    ConfigRevisionCreateRequest,
    ConfigRevisionCreateResponse,
    ConfigRevisionDraftFromRevisionRequest,
    ConfigRevisionDTO,
    ConfigTemplateDTO,
    PipelineValidateRequest,
    PipelineValidationIssueDTO,
    PipelineValidationResultDTO,
)
from app.services.audit_service import write_audit_log
from app.tables import config_revisions, config_templates, knowledge_bases
from app.services.knowledge_base_service import KnowledgeBaseDisabledError

STAGE_ORDER = {
    "preprocess": 1,
    "retrieval": 2,
    "fusion": 3,
    "generation": 4,
    "diagnostics": 5,
}
RETRIEVAL_NODE_TYPES = {"denseRetrieval", "sparseRetrieval", "graphRetrieval"}
LOCKED_NODE_TYPES = {
    "input",
    "fusion",
    "permissionFilter",
    "contextBuilder",
    "generation",
    "citation",
    "output",
}


def _is_platform_admin(current_user: CurrentUserResponse) -> bool:
    """沿用开发期最小权限：平台管理员可管理全部知识库配置。"""
    return current_user.user.platformRole == "platform_admin"


def _read_visible_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping | None:
    """读取当前用户可见知识库；不可见资源不暴露存在性。"""
    condition = (knowledge_bases.c.deleted_at.is_(None)) & (knowledge_bases.c.kb_id == kb_id)
    if not _is_platform_admin(current_user):
        condition = condition & (knowledge_bases.c.owner_id == UUID(current_user.user.userId))
    return session.execute(select(knowledge_bases).where(condition).limit(1)).mappings().first()


def _now() -> datetime:
    """统一生成带时区时间，避免不同接口响应格式漂移。"""
    return datetime.now(UTC)


def _issue(code: str, message: str, field: str | None = None) -> PipelineValidationIssueDTO:
    """构造 Pipeline 校验问题。"""
    return PipelineValidationIssueDTO(code=code, message=message, field=field)


def _nodes_by_type(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按节点类型索引节点；同类型重复时保留首个，重复问题由校验结果说明。"""
    result: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_type = node.get("type")
        if isinstance(node_type, str) and node_type not in result:
            result[node_type] = node
    return result


def _normalize_pipeline_definition(pipeline_definition: dict[str, Any]) -> dict[str, Any]:
    """补齐受约束 Pipeline 的基础字段，不改变节点启用状态和参数。"""
    normalized = dict(pipeline_definition)
    normalized.setdefault("version", "1.0")
    normalized.setdefault("constraintsVersion", "1.0")
    normalized.setdefault("mode", "constrained-stage-pipeline")
    normalized.setdefault("stages", list(STAGE_ORDER.keys()))
    normalized.setdefault("nodes", [])
    return normalized


def validate_pipeline_definition(
    request: PipelineValidateRequest,
) -> PipelineValidationResultDTO:
    """基于后端执行契约校验 Pipeline，前端护栏不能替代这里的安全规则。"""
    normalized = _normalize_pipeline_definition(request.pipelineDefinition)
    errors: list[PipelineValidationIssueDTO] = []
    warnings: list[PipelineValidationIssueDTO] = []

    if normalized.get("mode") != "constrained-stage-pipeline":
        errors.append(
            _issue(
                "PIPELINE_MODE_INVALID",
                "pipelineDefinition.mode 必须为 constrained-stage-pipeline。",
                "pipelineDefinition.mode",
            )
        )

    raw_nodes = normalized.get("nodes")
    if not isinstance(raw_nodes, list):
        errors.append(_issue("PIPELINE_NODES_INVALID", "pipelineDefinition.nodes 必须是数组。", "pipelineDefinition.nodes"))
        raw_nodes = []

    nodes = [node for node in raw_nodes if isinstance(node, dict)]
    if len(nodes) != len(raw_nodes):
        errors.append(_issue("PIPELINE_NODE_INVALID", "节点定义必须是对象。", "pipelineDefinition.nodes"))

    nodes_by_type = _nodes_by_type(nodes)
    seen_types: set[str] = set()
    for index, node in enumerate(nodes):
        node_type = node.get("type")
        stage = node.get("stage")
        if not isinstance(node_type, str):
            errors.append(_issue("PIPELINE_NODE_TYPE_REQUIRED", "节点必须声明 type。", f"pipelineDefinition.nodes[{index}].type"))
            continue
        if node_type in seen_types:
            errors.append(_issue("PIPELINE_NODE_DUPLICATED", f"节点类型 {node_type} 重复。", f"pipelineDefinition.nodes[{index}].type"))
        seen_types.add(node_type)
        if stage not in STAGE_ORDER:
            errors.append(_issue("PIPELINE_STAGE_INVALID", f"节点 {node_type} 的阶段无效。", f"pipelineDefinition.nodes[{index}].stage"))
        if node_type in LOCKED_NODE_TYPES and node.get("enabled") is False:
            errors.append(_issue("PIPELINE_LOCKED_NODE_DISABLED", f"锁定节点 {node_type} 不允许禁用。", f"pipelineDefinition.nodes[{index}].enabled"))

    enabled_retrieval_nodes = [
        node for node in nodes if node.get("type") in RETRIEVAL_NODE_TYPES and node.get("enabled") is not False
    ]
    if not enabled_retrieval_nodes:
        errors.append(
            _issue(
                "PIPELINE_NO_RETRIEVAL_ENABLED",
                "Dense、Sparse、Graph 至少需要启用一路。",
                "pipelineDefinition.nodes",
            )
        )

    permission_filter = nodes_by_type.get("permissionFilter")
    generation = nodes_by_type.get("generation")
    if permission_filter is None or permission_filter.get("enabled") is False:
        errors.append(
            _issue(
                "PIPELINE_PERMISSION_FILTER_REQUIRED",
                "Permission Filter 必须存在且启用。",
                "pipelineDefinition.nodes",
            )
        )
    elif generation is not None:
        permission_stage = STAGE_ORDER.get(str(permission_filter.get("stage")), 99)
        generation_stage = STAGE_ORDER.get(str(generation.get("stage")), 99)
        if permission_stage >= generation_stage:
            errors.append(
                _issue(
                    "PIPELINE_STAGE_ORDER_INVALID",
                    "Permission Filter 必须位于 Generation 之前。",
                    "pipelineDefinition.nodes",
                )
            )

    query_rewrite = nodes_by_type.get("queryRewrite")
    if query_rewrite and query_rewrite.get("enabled") is not False:
        query_stage = STAGE_ORDER.get(str(query_rewrite.get("stage")), 99)
        retrieval_stage = STAGE_ORDER["retrieval"]
        if query_stage >= retrieval_stage:
            errors.append(
                _issue(
                    "PIPELINE_STAGE_ORDER_INVALID",
                    "Query Rewrite 如果启用，必须位于 Retrieval 之前。",
                    "pipelineDefinition.nodes",
                )
            )

    graph_node = nodes_by_type.get("graphRetrieval")
    graph_params = graph_node.get("params", {}) if graph_node else {}
    if graph_node and graph_node.get("enabled") is not False and isinstance(graph_params, dict):
        if graph_params.get("mustFallbackToChunk") is False:
            errors.append(
                _issue(
                    "PIPELINE_GRAPH_CHUNK_FALLBACK_REQUIRED",
                    "Graph Retrieval 输出必须回落到授权 Chunk / Evidence。",
                    "pipelineDefinition.nodes.graphRetrieval.params.mustFallbackToChunk",
                )
            )

    citation = nodes_by_type.get("citation")
    if citation is None or citation.get("enabled") is False:
        errors.append(_issue("PIPELINE_CITATION_INVALID", "Citation 节点必须存在且启用。", "pipelineDefinition.nodes"))

    if not errors and not normalized.get("validationSnapshot"):
        warnings.append(
            _issue(
                "PIPELINE_VALIDATION_SNAPSHOT_MISSING",
                "保存时后端会写入本次校验快照。",
                "pipelineDefinition.validationSnapshot",
            )
        )

    return PipelineValidationResultDTO(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        normalizedPipelineDefinition=normalized,
    )


def validate_pipeline_for_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: PipelineValidateRequest,
) -> PipelineValidationResultDTO | None:
    """校验指定知识库的 Pipeline；先确认知识库对当前用户可见。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    return validate_pipeline_definition(request)


def _to_template_dto(row: RowMapping) -> ConfigTemplateDTO:
    """将配置模板行转换为接口 DTO。"""
    return ConfigTemplateDTO(
        templateId=str(row["template_id"]),
        name=row["name"],
        description=row["description"],
        pipelineDefinition=row["pipeline_definition"],
        defaultParams=row["default_params"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _to_revision_dto(row: RowMapping) -> ConfigRevisionDTO:
    """将配置版本行转换为接口 DTO。"""
    return ConfigRevisionDTO(
        configRevisionId=str(row["config_revision_id"]),
        kbId=str(row["kb_id"]),
        revisionNo=row["revision_no"],
        sourceTemplateId=str(row["source_template_id"]) if row["source_template_id"] else None,
        status=row["status"],
        pipelineDefinition=row["pipeline_definition"],
        validationSnapshot=row["validation_snapshot"],
        remark=row["remark"],
        activatedAt=row["activated_at"].isoformat() if row["activated_at"] else None,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def list_config_templates(session: Session) -> list[ConfigTemplateDTO]:
    """查询可用配置模板；当前 Sprint 不提供模板创建后台。"""
    rows = session.execute(
        select(config_templates)
        .where(config_templates.c.deleted_at.is_(None), config_templates.c.status == "active")
        .order_by(config_templates.c.updated_at.desc(), config_templates.c.created_at.desc())
    ).mappings()
    return [_to_template_dto(row) for row in rows]


def list_config_revisions(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
) -> PageResponse[ConfigRevisionDTO] | None:
    """分页查询知识库配置版本列表。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = (config_revisions.c.kb_id == kb_id) & (config_revisions.c.deleted_at.is_(None))
    total = session.execute(select(func.count()).select_from(config_revisions).where(condition)).scalar_one()
    rows = session.execute(
        select(config_revisions)
        .where(condition)
        .order_by(config_revisions.c.revision_no.desc(), config_revisions.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()
    return PageResponse(
        items=[_to_revision_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_config_revision(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    revision_id: UUID,
) -> ConfigRevisionDTO | None:
    """读取单个配置版本，不可见知识库和不存在版本统一返回 None。"""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    row = session.execute(
        select(config_revisions)
        .where(
            config_revisions.c.kb_id == kb_id,
            config_revisions.c.config_revision_id == revision_id,
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    return _to_revision_dto(row) if row else None


def create_config_revision(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: ConfigRevisionCreateRequest,
) -> tuple[ConfigRevisionCreateResponse | None, PipelineValidationResultDTO]:
    """保存新的 ConfigRevision；保存前必须通过后端 Pipeline 校验。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None, validate_pipeline_definition(PipelineValidateRequest(pipelineDefinition=request.pipelineDefinition))
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError

    validation = validate_pipeline_definition(PipelineValidateRequest(pipelineDefinition=request.pipelineDefinition))
    if not validation.valid:
        return None, validation

    actor_id = UUID(current_user.user.userId)
    revision_no = (
        session.execute(
            select(func.coalesce(func.max(config_revisions.c.revision_no), 0)).where(
                config_revisions.c.kb_id == kb_id
            )
        ).scalar_one()
        + 1
    )
    validation_snapshot = {
        "valid": True,
        "errors": [],
        "warnings": [warning.model_dump() for warning in validation.warnings],
        "validatedAt": _now().isoformat(),
    }

    try:
        revision_id = uuid4()
        row = session.execute(
            insert(config_revisions)
            .values(
                config_revision_id=revision_id,
                kb_id=kb_id,
                revision_no=revision_no,
                source_template_id=request.sourceTemplateId,
                status="saved",
                pipeline_definition={
                    **validation.normalizedPipelineDefinition,
                    "validationSnapshot": validation_snapshot,
                },
                validation_snapshot=validation_snapshot,
                remark=request.remark,
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(config_revisions)
        ).mappings().one()
        write_audit_log(
            session,
            current_user,
            "config_revision.create",
            "config_revision",
            revision_id,
            kb_id=kb_id,
            detail={"revisionNo": revision_no, "status": "saved"},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return (
        ConfigRevisionCreateResponse(
            configRevisionId=str(row["config_revision_id"]),
            revisionNo=row["revision_no"],
            status=row["status"],
            validationSnapshot=row["validation_snapshot"],
        ),
        validation,
    )


def create_revision_draft_from_revision(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: ConfigRevisionDraftFromRevisionRequest,
) -> ConfigRevisionDTO | None:
    """复制历史 Revision 为新草稿，不修改源 Revision 的状态和审计字段。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError

    source_row = session.execute(
        select(config_revisions)
        .where(
            config_revisions.c.kb_id == kb_id,
            config_revisions.c.config_revision_id == request.sourceRevisionId,
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if source_row is None:
        return None

    actor_id = UUID(current_user.user.userId)
    revision_no = (
        session.execute(
            select(func.coalesce(func.max(config_revisions.c.revision_no), 0)).where(
                config_revisions.c.kb_id == kb_id
            )
        ).scalar_one()
        + 1
    )
    copied_at = _now()
    validation_snapshot = {
        **source_row["validation_snapshot"],
        "copiedFromRevisionId": str(request.sourceRevisionId),
        "copiedAt": copied_at.isoformat(),
    }
    remark = request.remark or f"从 rev_{source_row['revision_no']:03d} 复制为草稿"

    try:
        new_revision_id = uuid4()
        row = session.execute(
            insert(config_revisions)
            .values(
                config_revision_id=new_revision_id,
                kb_id=kb_id,
                revision_no=revision_no,
                source_template_id=source_row["source_template_id"],
                status="draft",
                pipeline_definition=source_row["pipeline_definition"],
                validation_snapshot=validation_snapshot,
                remark=remark,
                created_by=actor_id,
                updated_by=actor_id,
            )
            .returning(config_revisions)
        ).mappings().one()
        write_audit_log(
            session,
            current_user,
            "config_revision.create_draft",
            "config_revision",
            new_revision_id,
            kb_id=kb_id,
            detail={
                "sourceRevisionId": str(request.sourceRevisionId),
                "revisionNo": revision_no,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return _to_revision_dto(row)


def activate_config_revision(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    revision_id: UUID,
    confirm_impact: bool,
) -> ConfigRevisionActivationResponse | None:
    """同事务切换 active Revision，避免知识库指针和版本状态不一致。"""
    kb_row = _read_visible_knowledge_base(session, current_user, kb_id)
    if kb_row is None:
        return None
    if kb_row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    if not confirm_impact:
        raise ValueError("confirmImpact must be true.")

    target_row = session.execute(
        select(config_revisions)
        .where(
            config_revisions.c.kb_id == kb_id,
            config_revisions.c.config_revision_id == revision_id,
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()
    if target_row is None or target_row["status"] not in {"saved", "active"}:
        raise ValueError("Revision is not activatable.")

    actor_id = UUID(current_user.user.userId)
    activated_at = _now()
    previous_active_id = kb_row["active_config_revision_id"]

    try:
        session.execute(
            update(config_revisions)
            .where(
                config_revisions.c.kb_id == kb_id,
                config_revisions.c.config_revision_id != revision_id,
                config_revisions.c.status == "active",
            )
            .values(
                status="archived",
                deactivated_at=activated_at,
                deactivated_by=actor_id,
                updated_at=activated_at,
                updated_by=actor_id,
            )
        )
        session.execute(
            update(config_revisions)
            .where(config_revisions.c.config_revision_id == revision_id)
            .values(
                status="active",
                activated_at=activated_at,
                activated_by=actor_id,
                deactivated_at=None,
                deactivated_by=None,
                updated_at=activated_at,
                updated_by=actor_id,
            )
        )
        session.execute(
            update(knowledge_bases)
            .where(knowledge_bases.c.kb_id == kb_id)
            .values(
                active_config_revision_id=revision_id,
                updated_at=activated_at,
                updated_by=actor_id,
            )
        )
        audit_log_id = write_audit_log(
            session,
            current_user,
            "config_revision.activate",
            "config_revision",
            revision_id,
            kb_id=kb_id,
            detail={
                "previousActiveConfigRevisionId": str(previous_active_id) if previous_active_id else None,
                "activatedAt": activated_at.isoformat(),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return ConfigRevisionActivationResponse(
        activeConfigRevisionId=str(revision_id),
        previousActiveConfigRevisionId=str(previous_active_id) if previous_active_id else None,
        activatedAt=activated_at.isoformat(),
        auditLogId=str(audit_log_id),
    )
