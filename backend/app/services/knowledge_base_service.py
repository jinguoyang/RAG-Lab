from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, and_, case, func, insert, or_, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.knowledge_base import (
    KbDeleteImpactCascadeDTO,
    KbDeleteImpactDTO,
    KbDeleteImpactBlockerDTO,
    KbDeleteImpactUnaffectedDTO,
    KbMemberBindingDTO,
    KbMemberCreateRequest,
    KbMemberSubjectOptionDTO,
    KbMemberUpdateRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDTO,
    KnowledgeBaseUpdateRequest,
    RequiredForActivationDTO,
)
from app.services.dictionary_service import require_active_dict_item
from app.services.audit_service import write_audit_log
from app.services.default_pipeline import build_default_pipeline_definition
from app.services.permission_service import has_kb_permission, kb_visibility_condition
from app.tables import chunks, config_revisions, document_kb_bindings, documents, ingest_jobs, kb_member_bindings, knowledge_bases, rag_apps, user_groups, users


class KnowledgeBasePermissionError(Exception):
    """当前用户缺少执行知识库成员管理动作的权限。"""


class KnowledgeBaseNotFoundError(Exception):
    """知识库不存在或当前用户不可见。"""


class KnowledgeBaseDisabledError(Exception):
    """知识库已停用，当前写操作不允许继续。"""


class KnowledgeBaseIndexCapabilityLockedError(Exception):
    """知识库已有文档后，索引能力开关不允许通过普通编辑变更。"""


class KnowledgeBaseActiveRagAppsError(Exception):
    """知识库仍绑定启用中的 RAG App，不能直接停用。"""


class KnowledgeBaseConfirmNameMismatchError(Exception):
    """删除确认名称不匹配。"""


class KnowledgeBaseRunningJobsError(Exception):
    """存在运行中的摄入任务，无法删除。"""


class KbMemberBindingNotFoundError(Exception):
    """成员绑定不存在、已失效或不属于当前知识库。"""


class KbMemberBindingConflictError(Exception):
    """同一主体在当前知识库下已经存在有效成员绑定。"""


class KbMemberSubjectNotFoundError(Exception):
    """成员绑定的用户或用户组不存在、已删除或已禁用。"""


def _to_dto(row: RowMapping) -> KnowledgeBaseDTO:
    """将数据库 snake_case 行转换为前端接口使用的 camelCase DTO。"""
    return KnowledgeBaseDTO(
        kbId=str(row["kb_id"]),
        name=row["name"],
        description=row["description"],
        ownerId=str(row["owner_id"]),
        defaultSecurityLevel=row["default_security_level"],
        sparseIndexEnabled=row["sparse_index_enabled"],
        graphIndexEnabled=row["graph_index_enabled"],
        requiredForActivation=RequiredForActivationDTO(
            dense=True,
            sparse=row["sparse_required_for_activation"],
            graph=row["graph_required_for_activation"],
        ),
        status=row["status"],
        activeConfigRevisionId=(
            str(row["active_config_revision_id"]) if row["active_config_revision_id"] else None
        ),
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _visible_condition(current_user: CurrentUserResponse):
    """知识库可见性以后端权限解析为准，成员绑定后立即影响列表。"""
    return kb_visibility_condition(current_user)


def _ensure_kb_visible(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> None:
    """确认当前用户可见知识库；不可见资源按不存在处理。"""
    exists = session.execute(
        select(knowledge_bases.c.kb_id)
        .where(_visible_condition(current_user), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).scalar_one_or_none()
    if exists is None:
        raise KnowledgeBaseNotFoundError


def _read_visible_kb_row(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping:
    """读取当前用户可见知识库行，供状态校验和更新复用。"""
    row = session.execute(
        select(knowledge_bases)
        .where(_visible_condition(current_user), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        raise KnowledgeBaseNotFoundError
    return row


def ensure_knowledge_base_writable(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> RowMapping:
    """确认知识库可见且未停用；写入口统一用它收口停用态保护。"""
    row = _read_visible_kb_row(session, current_user, kb_id)
    if row["status"] == "disabled":
        raise KnowledgeBaseDisabledError
    return row


def _ensure_member_manage_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> None:
    """成员变更是权限边界操作，必须先确认知识库可见并具备管理权限。"""
    _ensure_kb_visible(session, current_user, kb_id)
    if not has_kb_permission(session, current_user, kb_id, "kb.member.manage"):
        raise KnowledgeBasePermissionError


def _ensure_kb_manage_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> None:
    """确认当前用户可管理知识库基础信息。"""
    _ensure_kb_visible(session, current_user, kb_id)
    if not has_kb_permission(session, current_user, kb_id, "kb.manage"):
        raise KnowledgeBasePermissionError


def _ensure_index_capabilities_mutable(
    session: Session,
    kb_id: UUID,
    kb_row: RowMapping,
    request: KnowledgeBaseUpdateRequest,
) -> None:
    """已有文档时锁定 OpenSearch/Neo4j 能力，避免历史版本副本状态被普通编辑改写。"""
    requested_fields = request.model_fields_set
    sparse_changed = (
        "sparseIndexEnabled" in requested_fields
        and request.sparseIndexEnabled is not None
        and request.sparseIndexEnabled != kb_row["sparse_index_enabled"]
    )
    graph_changed = (
        "graphIndexEnabled" in requested_fields
        and request.graphIndexEnabled is not None
        and request.graphIndexEnabled != kb_row["graph_index_enabled"]
    )
    if not sparse_changed and not graph_changed:
        return

    has_documents = session.execute(
        select(documents.c.document_id)
        .where(documents.c.kb_id == kb_id, documents.c.deleted_at.is_(None))
        .limit(1)
    ).scalar_one_or_none()
    if has_documents is not None:
        raise KnowledgeBaseIndexCapabilityLockedError


def _member_subject_name_expression():
    """生成成员主体展示名表达式，避免 API 层理解用户/用户组表结构。"""
    return case(
        (kb_member_bindings.c.subject_type == "user", users.c.display_name),
        else_=user_groups.c.name,
    ).label("subject_name")


def _member_subject_status_expression():
    """生成成员主体状态表达式，供前端展示禁用主体的只读提示。"""
    return case(
        (kb_member_bindings.c.subject_type == "user", users.c.status),
        else_=user_groups.c.status,
    ).label("subject_status")


def _member_base_select():
    """构造成员绑定查询，统一处理 user/group 两类主体的展示字段。"""
    return (
        select(
            kb_member_bindings,
            _member_subject_name_expression(),
            _member_subject_status_expression(),
        )
        .select_from(
            kb_member_bindings.outerjoin(
                users,
                and_(
                    kb_member_bindings.c.subject_type == "user",
                    kb_member_bindings.c.subject_id == users.c.user_id,
                ),
            ).outerjoin(
                user_groups,
                and_(
                    kb_member_bindings.c.subject_type == "group",
                    kb_member_bindings.c.subject_id == user_groups.c.group_id,
                ),
            )
        )
        .where(kb_member_bindings.c.status == "active")
    )


def _member_to_dto(row: RowMapping) -> KbMemberBindingDTO:
    """将成员绑定行转换为 P12 页面消费的 DTO。"""
    return KbMemberBindingDTO(
        bindingId=str(row["binding_id"]),
        kbId=str(row["kb_id"]),
        subjectType=row["subject_type"],
        subjectId=str(row["subject_id"]),
        subjectName=row["subject_name"] or str(row["subject_id"]),
        subjectStatus=row["subject_status"] or "unknown",
        kbRole=row["kb_role"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _ensure_subject_exists(session: Session, request: KbMemberCreateRequest) -> None:
    """绑定前校验主体存在且处于 active，避免产生不可解释的授权记录。"""
    if request.subjectType == "user":
        subject_table = users
        subject_id_column = users.c.user_id
    else:
        subject_table = user_groups
        subject_id_column = user_groups.c.group_id

    subject_id = session.execute(
        select(subject_id_column)
        .where(
            subject_id_column == request.subjectId,
            subject_table.c.status == "active",
            subject_table.c.deleted_at.is_(None),
        )
        .limit(1)
    ).scalar_one_or_none()
    if subject_id is None:
        raise KbMemberSubjectNotFoundError


def list_knowledge_bases(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int,
    page_size: int,
    keyword: str | None,
) -> PageResponse[KnowledgeBaseDTO]:
    """分页查询当前用户可见知识库，支撑平台工作台入口。"""
    condition = _visible_condition(current_user)
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            knowledge_bases.c.name.ilike(keyword_pattern),
            knowledge_bases.c.description.ilike(keyword_pattern),
        )

    total = session.execute(
        select(func.count()).select_from(knowledge_bases).where(condition)
    ).scalar_one()
    rows = session.execute(
        select(knowledge_bases)
        .where(condition)
        .order_by(knowledge_bases.c.updated_at.desc(), knowledge_bases.c.created_at.desc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return PageResponse(
        items=[_to_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def get_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> KnowledgeBaseDTO | None:
    """读取单个可见知识库；不可见与不存在统一返回 None。"""
    row = session.execute(
        select(knowledge_bases)
        .where(_visible_condition(current_user), knowledge_bases.c.kb_id == kb_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    return _to_dto(row)


def update_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: KnowledgeBaseUpdateRequest,
) -> KnowledgeBaseDTO:
    """更新知识库基础信息；停用知识库只允许读，不允许继续变更。"""
    _ensure_kb_manage_permission(session, current_user, kb_id)
    kb_row = ensure_knowledge_base_writable(session, current_user, kb_id)
    _ensure_index_capabilities_mutable(session, kb_id, kb_row, request)
    if request.defaultSecurityLevel is not None:
        require_active_dict_item(session, "security_level", request.defaultSecurityLevel, "defaultSecurityLevel")

    update_values = {"updated_by": UUID(current_user.user.userId), "updated_at": func.now()}
    requested_fields = request.model_fields_set
    if "name" in requested_fields and request.name is not None:
        update_values["name"] = request.name
    if "description" in requested_fields:
        update_values["description"] = request.description
    if "ownerId" in requested_fields and request.ownerId is not None:
        update_values["owner_id"] = request.ownerId
    if "defaultSecurityLevel" in requested_fields and request.defaultSecurityLevel is not None:
        update_values["default_security_level"] = request.defaultSecurityLevel
    if "sparseIndexEnabled" in requested_fields and request.sparseIndexEnabled is not None:
        update_values["sparse_index_enabled"] = request.sparseIndexEnabled
    if "graphIndexEnabled" in requested_fields and request.graphIndexEnabled is not None:
        update_values["graph_index_enabled"] = request.graphIndexEnabled
    if request.requiredForActivation is not None:
        update_values["sparse_required_for_activation"] = request.requiredForActivation.sparse
        update_values["graph_required_for_activation"] = request.requiredForActivation.graph

    row = session.execute(
        update(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id)
        .values(**update_values)
        .returning(knowledge_bases)
    ).mappings().one()
    write_audit_log(
        session,
        current_user,
        "knowledge_base.update",
        "knowledge_base",
        kb_id,
        kb_id=kb_id,
        detail={"updatedFields": sorted(requested_fields)},
    )
    session.commit()
    return _to_dto(row)


def disable_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> KnowledgeBaseDTO:
    """停用知识库时仅更新状态，保留文档、配置和 QA 历史用于追溯。"""
    _ensure_kb_manage_permission(session, current_user, kb_id)
    ensure_knowledge_base_writable(session, current_user, kb_id)
    active_app_count = session.execute(
        select(func.count())
        .select_from(rag_apps)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status == "active",
            rag_apps.c.deleted_at.is_(None),
        )
    ).scalar_one()
    if active_app_count > 0:
        raise KnowledgeBaseActiveRagAppsError

    row = session.execute(
        update(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id)
        .values(
            status="disabled",
            updated_by=UUID(current_user.user.userId),
            updated_at=func.now(),
        )
        .returning(knowledge_bases)
    ).mappings().one()
    write_audit_log(
        session,
        current_user,
        "knowledge_base.disable",
        "knowledge_base",
        kb_id,
        kb_id=kb_id,
        detail={},
    )
    session.commit()
    return _to_dto(row)


def enable_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> KnowledgeBaseDTO:
    """恢复停用知识库，只改变主状态并保留原有文档、配置和历史记录。"""
    _ensure_kb_manage_permission(session, current_user, kb_id)
    _read_visible_kb_row(session, current_user, kb_id)

    row = session.execute(
        update(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id)
        .values(
            status="active",
            updated_by=UUID(current_user.user.userId),
            updated_at=func.now(),
        )
        .returning(knowledge_bases)
    ).mappings().one()
    write_audit_log(
        session,
        current_user,
        "knowledge_base.enable",
        "knowledge_base",
        kb_id,
        kb_id=kb_id,
        detail={},
    )
    session.commit()
    return _to_dto(row)


def get_kb_delete_impact(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> KbDeleteImpactDTO:
    """查询删除知识库会影响的数据范围。"""
    kb_row = _read_visible_kb_row(session, current_user, kb_id)

    # 阻断条件：活跃 RAG 应用
    active_apps = session.execute(
        select(rag_apps.c.app_id, rag_apps.c.name)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status == "active",
            rag_apps.c.deleted_at.is_(None),
        )
    ).mappings().all()

    # 阻断条件：运行中的 ingest_job
    running_jobs = session.execute(
        select(ingest_jobs.c.job_id, ingest_jobs.c.status)
        .where(
            ingest_jobs.c.kb_id == kb_id,
            ingest_jobs.c.status.in_(["pending", "processing"]),
        )
    ).mappings().all()

    # 级联数据统计
    binding_count = session.execute(
        select(func.count())
        .select_from(document_kb_bindings)
        .where(
            document_kb_bindings.c.kb_id == kb_id,
            document_kb_bindings.c.status.in_(["active", "processing", "pending", "failed"]),
        )
    ).scalar_one()

    kb_doc_count = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    chunk_count = session.execute(
        select(func.count())
        .select_from(chunks)
        .where(
            chunks.c.kb_id == kb_id,
        )
    ).scalar_one()

    config_count = session.execute(
        select(func.count())
        .select_from(config_revisions)
        .where(config_revisions.c.kb_id == kb_id)
    ).scalar_one()

    inactive_apps = session.execute(
        select(rag_apps.c.app_id, rag_apps.c.name, rag_apps.c.status)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status.in_(["disabled", "archived"]),
            rag_apps.c.deleted_at.is_(None),
        )
    ).mappings().all()

    member_count = session.execute(
        select(func.count())
        .select_from(kb_member_bindings)
        .where(kb_member_bindings.c.kb_id == kb_id)
    ).scalar_one()

    # 不受影响的数据
    library_doc_count = session.execute(
        select(func.count())
        .select_from(documents)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.library_id.is_not(None),
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()

    return KbDeleteImpactDTO(
        kbName=kb_row["name"],
        blockers=KbDeleteImpactBlockerDTO(
            activeRagApps=[{"appId": str(r["app_id"]), "name": r["name"]} for r in active_apps],
            runningJobs=[{"jobId": str(r["job_id"]), "status": r["status"]} for r in running_jobs],
        ),
        cascadeData=KbDeleteImpactCascadeDTO(
            bindings=binding_count,
            kbDocuments=kb_doc_count,
            chunks=chunk_count,
            configRevisions=config_count,
            inactiveRagApps=[{"appId": str(r["app_id"]), "name": r["name"], "status": r["status"]} for r in inactive_apps],
            kbMembers=member_count,
        ),
        unaffected=KbDeleteImpactUnaffectedDTO(
            libraryDocuments=library_doc_count,
            description="文件库中的源文档不会被删除",
        ),
    )


def delete_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    confirm_name: str,
) -> None:
    """删除知识库及级联数据。采用软删除，外部索引异步清理。"""
    _ensure_kb_manage_permission(session, current_user, kb_id)
    kb_row = _read_visible_kb_row(session, current_user, kb_id)

    # 名称确认
    if confirm_name != kb_row["name"]:
        raise KnowledgeBaseConfirmNameMismatchError

    # 阻断条件：活跃 RAG 应用
    active_app_count = session.execute(
        select(func.count())
        .select_from(rag_apps)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status == "active",
            rag_apps.c.deleted_at.is_(None),
        )
    ).scalar_one()
    if active_app_count > 0:
        raise KnowledgeBaseActiveRagAppsError

    # 阻断条件：运行中的 ingest_job
    running_job_count = session.execute(
        select(func.count())
        .select_from(ingest_jobs)
        .where(
            ingest_jobs.c.kb_id == kb_id,
            ingest_jobs.c.status.in_(["pending", "processing"]),
        )
    ).scalar_one()
    if running_job_count > 0:
        raise KnowledgeBaseRunningJobsError

    now = datetime.now(UTC)
    deleted_by = UUID(current_user.user.userId)

    # 1. 软删除知识库本身
    session.execute(
        update(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id)
        .values(
            status="archived",
            deleted_at=now,
            deleted_by=deleted_by,
            updated_at=now,
            updated_by=deleted_by,
        )
    )

    # 2. 禁用所有 document_kb_bindings
    session.execute(
        update(document_kb_bindings)
        .where(
            document_kb_bindings.c.kb_id == kb_id,
            document_kb_bindings.c.status.in_(["active", "processing", "pending", "failed"]),
        )
        .values(status="disabled")
    )

    # 3. 收集 chunk_ids 用于外部索引清理（在标记删除前）
    kb_doc_ids = session.execute(
        select(documents.c.document_id)
        .where(
            documents.c.kb_id == kb_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalars().all()

    chunk_ids = []
    if kb_doc_ids:
        chunk_rows = session.execute(
            select(chunks.c.chunk_id)
            .where(chunks.c.document_id.in_(kb_doc_ids))
        ).scalars().all()
        chunk_ids = list(chunk_rows)

    # 4. 软删除 KB 侧文档副本
    if kb_doc_ids:
        session.execute(
            update(documents)
            .where(documents.c.document_id.in_(kb_doc_ids))
            .values(
                status="archived",
                deleted_at=now,
                deleted_by=deleted_by,
            )
        )

    # 5. 取消运行中的 ingest_jobs（防御性处理）
    session.execute(
        update(ingest_jobs)
        .where(
            ingest_jobs.c.kb_id == kb_id,
            ingest_jobs.c.status.in_(["pending", "processing"]),
        )
        .values(status="cancelled")
    )

    # 6. 软删除 config_revisions
    session.execute(
        update(config_revisions)
        .where(config_revisions.c.kb_id == kb_id)
        .values(
            deleted_at=now,
            deleted_by=deleted_by,
        )
    )

    # 7. 删除 kb_member_bindings
    session.execute(
        kb_member_bindings.delete().where(kb_member_bindings.c.kb_id == kb_id)
    )

    # 8. 软删除停用/归档的 rag_apps
    session.execute(
        update(rag_apps)
        .where(
            rag_apps.c.kb_id == kb_id,
            rag_apps.c.status.in_(["disabled", "archived"]),
            rag_apps.c.deleted_at.is_(None),
        )
        .values(
            status="archived",
            deleted_at=now,
            deleted_by=deleted_by,
        )
    )

    # 9. 记录 KB 配置用于外部清理
    kb_config_row = session.execute(
        select(
            knowledge_bases.c.sparse_index_enabled,
            knowledge_bases.c.graph_index_enabled,
        )
        .where(knowledge_bases.c.kb_id == kb_id)
    ).mappings().first()

    # 10. 审计日志
    write_audit_log(
        session,
        current_user,
        "knowledge_base.delete",
        "knowledge_base",
        kb_id,
        kb_id=kb_id,
        detail={"confirm_name": confirm_name},
    )

    session.commit()

    # 11. 异步清理外部索引（best-effort）
    from app.services.document_service import _create_index_sync_job

    if chunk_ids:
        targets = ["milvus"]
        if kb_config_row and kb_config_row["sparse_index_enabled"]:
            targets.append("opensearch")
        if kb_config_row and kb_config_row["graph_index_enabled"]:
            targets.append("neo4j")
        for target_store in targets:
            try:
                _create_index_sync_job(
                    session,
                    kb_config_row,
                    current_user,
                    target_store,
                    None,
                    chunk_ids,
                    False,
                    sync_type="delete",
                )
                session.commit()
            except Exception:
                session.rollback()


def create_knowledge_base(
    session: Session,
    current_user: CurrentUserResponse,
    request: KnowledgeBaseCreateRequest,
) -> KnowledgeBaseDTO:
    """创建知识库基础记录，并生成默认 active Revision 供 QA 直接运行。"""
    require_active_dict_item(session, "security_level", request.defaultSecurityLevel, "defaultSecurityLevel")
    owner_id = request.ownerId or UUID(current_user.user.userId)
    activation = request.requiredForActivation or RequiredForActivationDTO(
        sparse=request.sparseIndexEnabled,
        graph=False,
    )
    kb_id = uuid4()
    default_revision_id = uuid4()
    actor_id = UUID(current_user.user.userId)
    created_at = datetime.now(UTC)
    default_pipeline = build_default_pipeline_definition(
        sparse_index_enabled=request.sparseIndexEnabled,
        graph_index_enabled=request.graphIndexEnabled,
    )
    validation_snapshot = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "source": "system_default",
        "validatedAt": created_at.isoformat(),
    }

    row = session.execute(
        insert(knowledge_bases)
        .values(
            kb_id=kb_id,
            name=request.name,
            description=request.description,
            owner_id=owner_id,
            default_security_level=request.defaultSecurityLevel,
            sparse_index_enabled=request.sparseIndexEnabled,
            graph_index_enabled=request.graphIndexEnabled,
            sparse_required_for_activation=activation.sparse,
            graph_required_for_activation=activation.graph,
            status="active",
            metadata={},
            created_by=actor_id,
            updated_by=actor_id,
        )
        .returning(knowledge_bases)
    ).mappings().one()
    session.execute(
        insert(config_revisions).values(
            config_revision_id=default_revision_id,
            kb_id=kb_id,
            revision_no=1,
            source_template_id=None,
            status="active",
            pipeline_definition=default_pipeline,
            validation_snapshot=validation_snapshot,
            remark="system_default",
            activated_at=created_at,
            activated_by=actor_id,
            created_at=created_at,
            created_by=actor_id,
            updated_at=created_at,
            updated_by=actor_id,
        )
    )
    row = session.execute(
        update(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id)
        .values(
            active_config_revision_id=default_revision_id,
            updated_at=created_at,
            updated_by=actor_id,
        )
        .returning(knowledge_bases)
    ).mappings().one()
    session.execute(
        insert(kb_member_bindings).values(
            binding_id=uuid4(),
            kb_id=kb_id,
            subject_type="user",
            subject_id=owner_id,
            kb_role="kb_owner",
            status="active",
            created_by=actor_id,
            updated_by=actor_id,
        )
    )
    write_audit_log(
        session,
        current_user,
        "knowledge_base.create",
        "knowledge_base",
        kb_id,
        kb_id=kb_id,
        detail={"ownerId": str(owner_id), "name": request.name},
    )
    write_audit_log(
        session,
        current_user,
        "config_revision.create_default",
        "config_revision",
        default_revision_id,
        kb_id=kb_id,
        detail={
            "revisionNo": 1,
            "source": "system_default",
            "activeConfigRevisionId": str(default_revision_id),
        },
    )
    session.commit()
    return _to_dto(row)


def count_visible_knowledge_bases(session: Session, current_user: CurrentUserResponse) -> int:
    """计算当前用户可见知识库数量，用于 `/auth/me` 能力摘要。"""
    return session.execute(
        select(func.count()).select_from(knowledge_bases).where(_visible_condition(current_user))
    ).scalar_one()


def list_kb_members(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    page_no: int,
    page_size: int,
    keyword: str | None,
    kb_role: str | None = None,
) -> PageResponse[KbMemberBindingDTO]:
    """分页返回知识库成员绑定；列表可读仍受知识库可见性约束。"""
    _ensure_kb_visible(session, current_user, kb_id)

    condition = kb_member_bindings.c.kb_id == kb_id
    if keyword:
        keyword_pattern = f"%{keyword.strip()}%"
        condition = condition & or_(
            users.c.display_name.ilike(keyword_pattern),
            users.c.username.ilike(keyword_pattern),
            user_groups.c.name.ilike(keyword_pattern),
        )
    if kb_role:
        condition = condition & (kb_member_bindings.c.kb_role == kb_role)

    base_select = _member_base_select().where(condition)
    total = session.execute(
        select(func.count()).select_from(base_select.subquery())
    ).scalar_one()
    rows = session.execute(
        base_select.order_by(
            kb_member_bindings.c.created_at.desc(),
            kb_member_bindings.c.binding_id.desc(),
        )
        .offset((page_no - 1) * page_size)
        .limit(page_size)
    ).mappings()

    return PageResponse(
        items=[_member_to_dto(row) for row in rows],
        pageNo=page_no,
        pageSize=page_size,
        total=total,
    )


def search_kb_member_subjects(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    subject_type: str,
    keyword: str | None,
    limit: int,
) -> list[KbMemberSubjectOptionDTO]:
    """搜索可被绑定到知识库的用户或用户组，并标记已绑定主体。"""
    _ensure_member_manage_permission(session, current_user, kb_id)

    normalized_keyword = keyword.strip() if keyword else ""
    bound_subject_ids = set(
        session.execute(
            select(kb_member_bindings.c.subject_id).where(
                kb_member_bindings.c.kb_id == kb_id,
                kb_member_bindings.c.subject_type == subject_type,
                kb_member_bindings.c.status == "active",
            )
        ).scalars()
    )

    if subject_type == "user":
        condition = users.c.status == "active"
        condition = condition & users.c.deleted_at.is_(None)
        if normalized_keyword:
            keyword_pattern = f"%{normalized_keyword}%"
            condition = condition & or_(
                users.c.display_name.ilike(keyword_pattern),
                users.c.username.ilike(keyword_pattern),
                users.c.email.ilike(keyword_pattern),
            )

        rows = session.execute(
            select(
                users.c.user_id.label("subject_id"),
                users.c.display_name.label("label"),
                users.c.username,
                users.c.email,
                users.c.status,
            )
            .where(condition)
            .order_by(users.c.display_name.asc(), users.c.username.asc())
            .limit(limit)
        ).mappings()

        return [
            KbMemberSubjectOptionDTO(
                subjectType="user",
                subjectId=str(row["subject_id"]),
                label=row["label"],
                secondaryText=" · ".join(
                    part for part in (f"@{row['username']}", row["email"]) if part
                ),
                status=row["status"],
                isAlreadyBound=row["subject_id"] in bound_subject_ids,
            )
            for row in rows
        ]

    condition = user_groups.c.status == "active"
    condition = condition & user_groups.c.deleted_at.is_(None)
    if normalized_keyword:
        keyword_pattern = f"%{normalized_keyword}%"
        condition = condition & or_(
            user_groups.c.name.ilike(keyword_pattern),
            user_groups.c.description.ilike(keyword_pattern),
        )

    rows = session.execute(
        select(
            user_groups.c.group_id.label("subject_id"),
            user_groups.c.name.label("label"),
            user_groups.c.description,
            user_groups.c.status,
        )
        .where(condition)
        .order_by(user_groups.c.name.asc())
        .limit(limit)
    ).mappings()

    return [
        KbMemberSubjectOptionDTO(
            subjectType="group",
            subjectId=str(row["subject_id"]),
            label=row["label"],
            secondaryText=row["description"],
            status=row["status"],
            isAlreadyBound=row["subject_id"] in bound_subject_ids,
        )
        for row in rows
    ]


def create_kb_member(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    request: KbMemberCreateRequest,
) -> KbMemberBindingDTO:
    """创建知识库成员绑定；同一主体在同一知识库只允许一个有效角色。"""
    _ensure_member_manage_permission(session, current_user, kb_id)
    ensure_knowledge_base_writable(session, current_user, kb_id)
    _ensure_subject_exists(session, request)
    require_active_dict_item(session, "kb_role", request.kbRole, "kbRole")

    duplicate = session.execute(
        select(kb_member_bindings.c.binding_id)
        .where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.subject_type == request.subjectType,
            kb_member_bindings.c.subject_id == request.subjectId,
            kb_member_bindings.c.status == "active",
        )
        .limit(1)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise KbMemberBindingConflictError

    binding_id = uuid4()
    session.execute(
        insert(kb_member_bindings).values(
            binding_id=binding_id,
            kb_id=kb_id,
            subject_type=request.subjectType,
            subject_id=request.subjectId,
            kb_role=request.kbRole,
            status="active",
            created_by=UUID(current_user.user.userId),
            updated_by=UUID(current_user.user.userId),
        )
    )
    write_audit_log(
        session,
        current_user,
        "kb_member.create",
        "kb_member",
        binding_id,
        kb_id=kb_id,
        detail={
            "subjectType": request.subjectType,
            "subjectId": str(request.subjectId),
            "kbRole": request.kbRole,
        },
    )
    session.commit()
    return get_kb_member(session, current_user, kb_id, binding_id)


def get_kb_member(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> KbMemberBindingDTO:
    """读取单个有效成员绑定，用于创建和更新后返回最新 DTO。"""
    _ensure_kb_visible(session, current_user, kb_id)
    row = session.execute(
        _member_base_select().where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.binding_id == binding_id,
        )
    ).mappings().first()
    if row is None:
        raise KbMemberBindingNotFoundError
    return _member_to_dto(row)


def update_kb_member_role(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
    request: KbMemberUpdateRequest,
) -> KbMemberBindingDTO:
    """修改知识库成员角色，不改变绑定主体和历史创建信息。"""
    _ensure_member_manage_permission(session, current_user, kb_id)
    ensure_knowledge_base_writable(session, current_user, kb_id)
    require_active_dict_item(session, "kb_role", request.kbRole, "kbRole")
    result = session.execute(
        update(kb_member_bindings)
        .where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.binding_id == binding_id,
            kb_member_bindings.c.status == "active",
        )
        .values(
            kb_role=request.kbRole,
            updated_by=UUID(current_user.user.userId),
            updated_at=func.now(),
        )
    )
    if result.rowcount == 0:
        session.rollback()
        raise KbMemberBindingNotFoundError
    write_audit_log(
        session,
        current_user,
        "kb_member.update",
        "kb_member",
        binding_id,
        kb_id=kb_id,
        detail={"kbRole": request.kbRole},
    )
    session.commit()
    return get_kb_member(session, current_user, kb_id, binding_id)


def remove_kb_member(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> None:
    """移除成员时仅将绑定置为 inactive，保留授权变更审计线索。"""
    _ensure_member_manage_permission(session, current_user, kb_id)
    ensure_knowledge_base_writable(session, current_user, kb_id)
    result = session.execute(
        update(kb_member_bindings)
        .where(
            kb_member_bindings.c.kb_id == kb_id,
            kb_member_bindings.c.binding_id == binding_id,
            kb_member_bindings.c.status == "active",
        )
        .values(
            status="inactive",
            updated_by=UUID(current_user.user.userId),
            updated_at=func.now(),
        )
    )
    if result.rowcount == 0:
        session.rollback()
        raise KbMemberBindingNotFoundError
    write_audit_log(
        session,
        current_user,
        "kb_member.remove",
        "kb_member",
        binding_id,
        kb_id=kb_id,
        detail={},
    )
    session.commit()
