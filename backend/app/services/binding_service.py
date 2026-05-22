"""知识库绑定服务：将文档库文档绑定到知识库进行解析入库。"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.binding import (
    BindingRevisionDTO,
    LibraryBindingDTO,
    LibraryBindResponse,
    LibraryUnbindResponse,
)
from app.tables import (
    binding_revisions,
    chunks,
    document_kb_bindings,
    document_libraries,
    document_versions,
    documents,
    ingest_jobs,
    knowledge_bases,
    parse_revisions,
    stored_files,
)


class BindingPermissionError(Exception):
    """当前用户缺少知识库操作权限。"""


class BindingDocumentNotFoundError(Exception):
    """文档库文档不存在或不属于当前用户。"""


class BindingKBNotFoundError(Exception):
    """知识库不存在。"""


class BindingAlreadyExistsError(Exception):
    """文档已绑定到该知识库。"""


class BindingNotFoundError(Exception):
    """绑定记录不存在。"""


class BindingVersionNotReadyError(Exception):
    """目标版本尚未解析完成。"""


class BindingDispatchError(Exception):
    """绑定入库任务投递失败。"""

    def __init__(self, job_ids: list[str]) -> None:
        self.job_ids = job_ids
        super().__init__(f"Failed to enqueue ingest jobs: {', '.join(job_ids)}")


class BindingBuildInProgressError(Exception):
    """有版本正在构建中，无法切换版本。"""


def _to_binding_revision_dto(row: dict) -> BindingRevisionDTO:
    """将 binding_revisions 行转换为 DTO。"""
    return BindingRevisionDTO(
        bindingRevisionId=str(row["binding_revision_id"]),
        bindingId=str(row["binding_id"]),
        knowledgeBaseId=str(row["knowledge_base_id"]),
        documentId=str(row["document_id"]),
        documentVersionId=str(row["document_version_id"]),
        parseRevisionId=str(row["parse_revision_id"]),
        status=row["status"],
        chunkCount=row["chunk_count"],
        buildStartedAt=row["build_started_at"].isoformat() if row.get("build_started_at") else None,
        buildFinishedAt=row["build_finished_at"].isoformat() if row.get("build_finished_at") else None,
        activatedAt=row["activated_at"].isoformat() if row.get("activated_at") else None,
        retiredAt=row["retired_at"].isoformat() if row.get("retired_at") else None,
        createdAt=row["created_at"].isoformat(),
        createdBy=str(row["created_by"]) if row.get("created_by") else None,
    )


def create_binding_revision(
    session: Session,
    binding_id: UUID,
    knowledge_base_id: UUID,
    document_id: UUID,
    document_version_id: UUID,
    parse_revision_id: UUID,
    created_by: UUID | None = None,
) -> UUID:
    """创建 BindingRevision 记录，状态为 building。

    Returns: binding_revision_id
    """
    binding_revision_id = uuid4()
    now = datetime.now(timezone.utc)

    session.execute(
        insert(binding_revisions).values(
            binding_revision_id=binding_revision_id,
            binding_id=binding_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            document_version_id=document_version_id,
            parse_revision_id=parse_revision_id,
            status="building",
            chunk_count=0,
            build_started_at=now,
            created_at=now,
            created_by=created_by,
        )
    )

    return binding_revision_id


def activate_binding_revision(
    session: Session,
    binding_revision_id: UUID,
) -> None:
    """激活 BindingRevision，将旧 active 版本置为 retired。"""
    now = datetime.now(timezone.utc)

    binding_rev = session.execute(
        select(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        )
    ).mappings().first()

    if not binding_rev:
        raise BindingNotFoundError
    old_active_revision_ids = list(
        session.execute(
            select(binding_revisions.c.binding_revision_id).where(
                binding_revisions.c.binding_id == binding_rev["binding_id"],
                binding_revisions.c.status == "active",
                binding_revisions.c.binding_revision_id != binding_revision_id,
            )
        ).scalars().all()
    )

    # 更新状态为 active
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        ).values(
            status="active",
            activated_at=now,
        )
    )

    # 更新 document_kb_bindings 的 active_binding_revision_id
    session.execute(
        update(document_kb_bindings).where(
            document_kb_bindings.c.binding_id == binding_rev["binding_id"],
        ).values(
            active_binding_revision_id=binding_revision_id,
        )
    )

    # 将旧的 active BindingRevision 置为 retired
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_id == binding_rev["binding_id"],
            binding_revisions.c.status == "active",
            binding_revisions.c.binding_revision_id != binding_revision_id,
        ).values(
            status="retired",
            retired_at=now,
        )
    )
    if old_active_revision_ids:
        session.execute(
            update(chunks)
            .where(
                chunks.c.binding_revision_id.in_(old_active_revision_ids),
                chunks.c.status == "active",
            )
            .values(status="retired", retired_at=now)
        )


def fail_binding_revision(
    session: Session,
    binding_revision_id: UUID,
    error_message: str | None = None,
) -> None:
    """标记 BindingRevision 为失败。"""
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        ).values(
            status="failed",
        )
    )


def _ensure_library_owner(
    session: Session,
    current_user: CurrentUserResponse,
    document_id: UUID,
) -> dict:
    """验证用户可读取该文档库文档。"""
    from app.services.permission_service import has_library_access

    user_id = UUID(current_user.user.userId)
    row = session.execute(
        select(documents).where(
            documents.c.document_id == document_id,
            documents.c.deleted_at.is_(None),
            documents.c.kb_id.is_(None),
        ).limit(1)
    ).mappings().first()
    if row is None:
        raise BindingDocumentNotFoundError
    library_id = row.get("library_id")
    if library_id:
        library_uuid = UUID(str(library_id))
        lib_row = session.execute(
            select(document_libraries).where(
                document_libraries.c.library_id == library_uuid,
                document_libraries.c.deleted_at.is_(None),
            ).limit(1)
        ).mappings().first()
        if lib_row is None:
            raise BindingDocumentNotFoundError
        if not has_library_access(
            session,
            current_user,
            permission_code="library.document.read",
            library_id=library_uuid,
            library_owner_id=UUID(str(lib_row["owner_id"])),
        ):
            raise BindingDocumentNotFoundError
    elif UUID(str(row["owner_id"])) != user_id:
        raise BindingDocumentNotFoundError
    return dict(row)


def _ensure_kb_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> dict:
    """验证用户对知识库有访问权限。"""
    row = session.execute(
        select(knowledge_bases).where(
            knowledge_bases.c.kb_id == kb_id,
            knowledge_bases.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    if row is None:
        raise BindingKBNotFoundError
    user_id = UUID(current_user.user.userId)
    if current_user.user.platformRole == "platform_admin":
        return dict(row)
    if row["created_by"] == user_id:
        return dict(row)
    raise BindingPermissionError


def _to_binding_dto(row: dict, doc_name: str = "") -> LibraryBindingDTO:
    """将绑定行转换为 DTO。"""
    return LibraryBindingDTO(
        bindingId=str(row["binding_id"]),
        documentId=str(row["document_id"]),
        documentName=doc_name,
        kbId=str(row["kb_id"]),
        versionId=str(row["version_id"]),
        chunkSize=row["chunk_size"],
        chunkOverlap=row["chunk_overlap"],
        status=row["status"],
        chunkCount=row["chunk_count"],
        errorCode=row.get("error_code"),
        errorMessage=row.get("error_message"),
        activeBindingRevisionId=str(row["active_binding_revision_id"]) if row.get("active_binding_revision_id") else None,
        bindingRevisionStatus=row.get("binding_revision_status"),
        bindingRevisionChunkCount=row.get("binding_revision_chunk_count"),
        bindingRevisionVersionId=str(row["binding_revision_version_id"]) if row.get("binding_revision_version_id") else None,
        createdAt=row["created_at"].isoformat(),
        createdBy=str(row["created_by"]) if row.get("created_by") else None,
    )


def _attach_binding_revision_summary(session: Session, row: dict) -> dict:
    """补充最适合前端展示的 BindingRevision 摘要。

    切换版本时会先出现 building revision，active revision 仍保留可用。
    前端需要优先看到正在构建的 revision，否则用户会误以为切换没有生效。
    """
    revision = session.execute(
        select(binding_revisions).where(
            binding_revisions.c.binding_id == row["binding_id"],
            binding_revisions.c.status == "building",
            binding_revisions.c.deleted_at.is_(None),
        ).order_by(binding_revisions.c.created_at.desc()).limit(1)
    ).mappings().first()

    if revision is None and row.get("active_binding_revision_id"):
        revision = session.execute(
            select(binding_revisions).where(
                binding_revisions.c.binding_revision_id == row["active_binding_revision_id"],
                binding_revisions.c.deleted_at.is_(None),
            ).limit(1)
        ).mappings().first()

    if revision is None:
        revision = session.execute(
            select(binding_revisions).where(
                binding_revisions.c.binding_id == row["binding_id"],
                binding_revisions.c.deleted_at.is_(None),
            ).order_by(binding_revisions.c.created_at.desc()).limit(1)
        ).mappings().first()

    if revision is None:
        return row

    row["binding_revision_status"] = revision["status"]
    row["binding_revision_chunk_count"] = revision["chunk_count"]
    row["binding_revision_version_id"] = revision["document_version_id"]
    return row


def bind_documents_to_kb(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    document_ids: list[UUID],
    version_id_override: UUID | None = None,
) -> LibraryBindResponse:
    """将文档库文档绑定到知识库，创建 KB 侧文档副本并投递解析任务。"""
    kb_row = _ensure_kb_permission(session, current_user, kb_id)
    kb_metadata = kb_row.get("metadata") or {}
    default_chunk_size = kb_metadata.get("chunk_size", 900)
    default_chunk_overlap = kb_metadata.get("chunk_overlap", 120)
    actor_id = UUID(current_user.user.userId)

    bindings: list[LibraryBindingDTO] = []
    dispatch_targets: list[tuple[UUID, UUID]] = []

    for doc_id in document_ids:
        lib_doc_row = _ensure_library_owner(session, current_user, doc_id)
        doc_name = lib_doc_row["name"]

        # 检查是否已有活跃绑定
        existing = session.execute(
            select(document_kb_bindings).where(
                document_kb_bindings.c.document_id == doc_id,
                document_kb_bindings.c.kb_id == kb_id,
                document_kb_bindings.c.status.in_(["pending", "processing", "active"]),
            ).limit(1)
        ).mappings().first()
        if existing is not None:
            raise BindingAlreadyExistsError(f"Document {doc_id} already bound to KB {kb_id}")

        active_version_id = lib_doc_row.get("active_version_id")
        if active_version_id is None and version_id_override is None:
            raise BindingDocumentNotFoundError(f"No active version found for document {doc_id}")

        # 绑定使用指定版本或文档库当前活跃版本。
        target_version_id = version_id_override or active_version_id
        latest_version = session.execute(
            select(document_versions).where(
                document_versions.c.version_id == target_version_id,
                document_versions.c.document_id == doc_id,
                document_versions.c.deleted_at.is_(None),
            ).limit(1)
        ).mappings().first()
        if latest_version is None:
            raise BindingDocumentNotFoundError(f"No version found for document {doc_id}")
        if latest_version["parse_status"] != "success":
            raise BindingVersionNotReadyError

        # 获取源文件
        source_file_row = session.execute(
            select(stored_files).where(
                stored_files.c.file_id == latest_version["source_file_id"],
            ).limit(1)
        ).mappings().first()
        if source_file_row is None:
            raise BindingDocumentNotFoundError(f"Source file not found for document {doc_id}")

        # 创建 KB 侧文档副本
        kb_doc_id = uuid4()
        kb_version_id = uuid4()
        job_id = uuid4()

        session.execute(
            insert(documents).values(
                document_id=kb_doc_id,
                kb_id=kb_id,
                owner_id=actor_id,
                name=doc_name,
                source_type="library_bind",
                security_level=lib_doc_row["security_level"],
                status="active",
                metadata={"library_document_id": str(doc_id)},
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

        session.execute(
            insert(document_versions).values(
                version_id=kb_version_id,
                document_id=kb_doc_id,
                version_no=1,
                source_file_id=latest_version["source_file_id"],
                status="processing",
                parse_status="pending",
                dense_index_status="pending",
                sparse_index_status="pending",
                graph_index_status="pending",
                retrieval_ready=False,
                chunk_count=0,
                metadata={
                    "library_document_id": str(doc_id),
                    "library_version_id": str(latest_version["version_id"]),
                },
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

        session.execute(
            update(documents).where(documents.c.document_id == kb_doc_id).values(
                active_version_id=kb_version_id,
            )
        )

        binding_id = uuid4()
        session.execute(
            insert(document_kb_bindings).values(
                binding_id=binding_id,
                document_id=doc_id,
                kb_id=kb_id,
                version_id=kb_version_id,
                chunk_size=default_chunk_size,
                chunk_overlap=default_chunk_overlap,
                status="pending",
                chunk_count=0,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )

        # 查找库文档版本的 ParseRevision
        parse_rev = session.execute(
            select(parse_revisions).where(
                parse_revisions.c.document_version_id == latest_version["version_id"],
                parse_revisions.c.deleted_at.is_(None),
            ).order_by(parse_revisions.c.created_at.desc()).limit(1)
        ).mappings().first()
        parse_revision_id = parse_rev["parse_revision_id"] if parse_rev else uuid4()

        # 创建 BindingRevision：记录库文档源版本，KB 侧版本仍由 document_kb_bindings.version_id 追踪。
        binding_revision_id = create_binding_revision(
            session=session,
            binding_id=binding_id,
            knowledge_base_id=kb_id,
            document_id=doc_id,
            document_version_id=latest_version["version_id"],
            parse_revision_id=parse_revision_id,
            created_by=actor_id,
        )
        session.execute(
            update(document_versions)
            .where(document_versions.c.version_id == kb_version_id)
            .values(
                metadata={
                    "library_document_id": str(doc_id),
                    "library_version_id": str(latest_version["version_id"]),
                    "binding_revision_id": str(binding_revision_id),
                }
            )
        )

        session.execute(
            insert(ingest_jobs).values(
                job_id=job_id,
                kb_id=kb_id,
                document_id=kb_doc_id,
                version_id=kb_version_id,
                job_type="upload_parse",
                status="queued",
                stage="queued",
                progress=0,
                result_summary={"binding_revision_id": str(binding_revision_id)},
                created_by=actor_id,
            )
        )

        session.flush()

        # 更新绑定状态为 processing
        binding_row = session.execute(
            update(document_kb_bindings).where(
                document_kb_bindings.c.document_id == doc_id,
                document_kb_bindings.c.kb_id == kb_id,
                document_kb_bindings.c.version_id == kb_version_id,
            ).values(status="processing").returning(document_kb_bindings)
        ).mappings().one()

        bindings.append(_to_binding_dto(dict(binding_row), doc_name=doc_name))
        dispatch_targets.append((job_id, binding_row["binding_id"]))

    session.commit()

    # 触发 Celery 任务
    failed_job_ids: list[str] = []
    for job_id, binding_id in dispatch_targets:
        try:
            from app.worker import run_document_ingest_task
            run_document_ingest_task.delay(str(job_id))
        except Exception as exc:
            error_message = f"Failed to enqueue ingest job: {exc}"
            session.execute(
                update(ingest_jobs)
                .where(ingest_jobs.c.job_id == job_id)
                .values(
                    status="failed",
                    stage="failed",
                    progress=100,
                    error_code="INGEST_ENQUEUE_FAILED",
                    error_message=error_message,
                    finished_at=func.now(),
                )
            )
            session.execute(
                update(document_kb_bindings)
                .where(document_kb_bindings.c.binding_id == binding_id)
                .values(
                    status="failed",
                    error_code="INGEST_ENQUEUE_FAILED",
                    error_message=error_message,
                    updated_by=actor_id,
                    updated_at=func.now(),
                )
            )
            failed_job_ids.append(str(job_id))

    if failed_job_ids:
        session.commit()
        raise BindingDispatchError(failed_job_ids)

    return LibraryBindResponse(bindings=bindings)


def unbind_document_from_kb(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> LibraryUnbindResponse:
    """解绑文档库文档与知识库的绑定关系。"""
    _ensure_kb_permission(session, current_user, kb_id)

    binding_row = session.execute(
        select(document_kb_bindings).where(
            document_kb_bindings.c.binding_id == binding_id,
            document_kb_bindings.c.kb_id == kb_id,
        ).limit(1)
    ).mappings().first()
    if binding_row is None:
        raise BindingNotFoundError

    # 通过 binding 的 version_id 找到 KB 侧文档
    kb_doc_row = session.execute(
        select(document_versions).where(
            document_versions.c.version_id == binding_row["version_id"],
        ).limit(1)
    ).mappings().first()

    # 更新绑定状态
    session.execute(
        update(document_kb_bindings).where(
            document_kb_bindings.c.binding_id == binding_id,
        ).values(status="disabled", updated_by=UUID(current_user.user.userId), updated_at=func.now())
    )

    # 清理 KB 侧数据
    if kb_doc_row is not None:
        from app.services.document_service import delete_document
        delete_document(
            session=session,
            current_user=current_user,
            kb_id=kb_id,
            document_id=kb_doc_row["document_id"],
            confirm_impact=True,
            reason="library_unbind",
        )

    session.commit()

    return LibraryUnbindResponse(
        bindingId=str(binding_id),
        status="disabled",
    )


def retry_binding(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
) -> dict:
    """重试失败的绑定。"""
    _ensure_kb_permission(session, current_user, kb_id)

    binding_row = session.execute(
        select(document_kb_bindings)
        .where(
            document_kb_bindings.c.binding_id == binding_id,
            document_kb_bindings.c.kb_id == kb_id,
            document_kb_bindings.c.status == "failed",
        )
        .limit(1)
    ).mappings().first()
    if binding_row is None:
        raise BindingNotFoundError

    user_id = UUID(current_user.user.userId)
    kb_ver_id = binding_row["version_id"]

    # Get KB-side document_id
    kb_doc_id = session.execute(
        select(document_versions.c.document_id)
        .where(document_versions.c.version_id == kb_ver_id)
        .limit(1)
    ).scalar()

    # Create new ingest job
    ingest_job_id = uuid4()
    session.execute(
        insert(ingest_jobs).values(
            job_id=ingest_job_id,
            kb_id=kb_id,
            document_id=kb_doc_id,
            version_id=kb_ver_id,
            job_type="upload_parse",
            status="queued",
            stage="queued",
            progress=0,
            result_summary={},
            created_by=user_id,
        )
    )

    # Reset binding status
    session.execute(
        update(document_kb_bindings)
        .where(document_kb_bindings.c.binding_id == binding_id)
        .values(
            status="processing",
            error_code=None,
            error_message=None,
            updated_by=user_id,
            updated_at=func.now(),
        )
    )

    session.commit()

    # Trigger Celery
    from app.worker import run_document_ingest_task
    run_document_ingest_task.delay(str(ingest_job_id))

    return {"bindingId": str(binding_id), "ingestJobId": str(ingest_job_id), "status": "processing"}


def list_kb_bindings(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> list[LibraryBindingDTO]:
    """列出知识库的所有文档库绑定。"""
    _ensure_kb_permission(session, current_user, kb_id)

    rows = session.execute(
        select(document_kb_bindings).where(
            document_kb_bindings.c.kb_id == kb_id,
        ).order_by(document_kb_bindings.c.created_at.desc())
    ).mappings().all()

    result: list[LibraryBindingDTO] = []
    for row in rows:
        row_dict = _attach_binding_revision_summary(session, dict(row))
        # 获取文档名称
        lib_doc = session.execute(
            select(documents.c.name).where(
                documents.c.document_id == row["document_id"],
            ).limit(1)
        ).scalar_one_or_none()
        doc_name = lib_doc or ""
        result.append(_to_binding_dto(row_dict, doc_name=doc_name))

    return result


def complete_binding_revision_build(
    session: Session,
    binding_revision_id: UUID,
    chunk_count: int,
) -> None:
    """完成 BindingRevision 构建并激活。

    此函数在 Chunk 生成和索引同步完成后调用。
    """
    now = datetime.now(timezone.utc)

    # 更新构建完成时间
    session.execute(
        update(binding_revisions).where(
            binding_revisions.c.binding_revision_id == binding_revision_id,
        ).values(
            status="active",
            chunk_count=chunk_count,
            build_finished_at=now,
            activated_at=now,
        )
    )

    # 激活新版本（会自动将旧版本置为 retired）
    activate_binding_revision(session, binding_revision_id)


def switch_binding_version(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    binding_id: UUID,
    target_library_version_id: UUID,
) -> LibraryBindingDTO:
    """切换 KB 绑定到不同的库文档版本，采用先构建后激活流程。"""
    _ensure_kb_permission(session, current_user, kb_id)

    # 加载绑定行
    binding_row = session.execute(
        select(document_kb_bindings).where(
            document_kb_bindings.c.binding_id == binding_id,
            document_kb_bindings.c.kb_id == kb_id,
        ).limit(1)
    ).mappings().first()
    if binding_row is None:
        raise BindingNotFoundError

    # 检查是否有正在构建的版本
    building_rev = session.execute(
        select(binding_revisions).where(
            binding_revisions.c.binding_id == binding_id,
            binding_revisions.c.status == "building",
        ).limit(1)
    ).mappings().first()
    if building_rev is not None:
        raise BindingBuildInProgressError("有版本正在构建中，无法切换版本")

    # 验证用户拥有库文档
    lib_doc_id = binding_row["document_id"]
    lib_doc_row = _ensure_library_owner(session, current_user, lib_doc_id)
    doc_name = lib_doc_row["name"]

    # 验证目标库版本
    target_ver = session.execute(
        select(document_versions).where(
            document_versions.c.version_id == target_library_version_id,
            document_versions.c.document_id == lib_doc_id,
            document_versions.c.deleted_at.is_(None),
        ).limit(1)
    ).mappings().first()
    if target_ver is None:
        raise BindingDocumentNotFoundError(f"Library version {target_library_version_id} not found")
    if target_ver["parse_status"] != "success":
        raise BindingVersionNotReadyError

    # 获取 KB 侧文档 ID（通过当前绑定的 version_id 找到 KB 侧 document_id）
    current_kb_version = session.execute(
        select(document_versions.c.document_id).where(
            document_versions.c.version_id == binding_row["version_id"],
        )
    ).scalar()
    if current_kb_version is None:
        raise BindingNotFoundError

    kb_doc_id = current_kb_version
    actor_id = UUID(current_user.user.userId)

    # 查找目标库版本的 ParseRevision
    parse_rev = session.execute(
        select(parse_revisions).where(
            parse_revisions.c.document_version_id == target_library_version_id,
            parse_revisions.c.deleted_at.is_(None),
        ).order_by(parse_revisions.c.created_at.desc()).limit(1)
    ).mappings().first()
    parse_revision_id = parse_rev["parse_revision_id"] if parse_rev else uuid4()

    # 创建新的 BindingRevision（状态为 building）
    binding_revision_id = create_binding_revision(
        session=session,
        binding_id=binding_id,
        knowledge_base_id=kb_id,
        document_id=lib_doc_id,
        document_version_id=target_library_version_id,
        parse_revision_id=parse_revision_id,
        created_by=actor_id,
    )

    # 查询 KB 侧文档当前最大 version_no
    max_kb_version_no = session.execute(
        select(func.max(document_versions.c.version_no))
        .where(document_versions.c.document_id == kb_doc_id)
    ).scalar() or 0

    # 创建 KB 侧新 document_versions 行
    new_kb_version_id = uuid4()
    session.execute(
        insert(document_versions).values(
            version_id=new_kb_version_id,
            document_id=kb_doc_id,
            version_no=max_kb_version_no + 1,
            source_file_id=target_ver["source_file_id"],
            status="processing",
            parse_status="pending",
            dense_index_status="pending",
            sparse_index_status="pending",
            graph_index_status="pending",
            retrieval_ready=False,
            chunk_count=0,
            metadata={
                "library_document_id": str(lib_doc_id),
                "library_version_id": str(target_library_version_id),
                "binding_revision_id": str(binding_revision_id),
            },
            created_by=actor_id,
            updated_by=actor_id,
        )
    )

    # 更新绑定指向新 KB 版本
    session.execute(
        update(document_kb_bindings)
        .where(document_kb_bindings.c.binding_id == binding_id)
        .values(
            version_id=new_kb_version_id,
            status="processing",
            updated_at=func.now(),
            updated_by=actor_id,
        )
    )

    # 创建 ingest 任务
    job_id = uuid4()
    session.execute(
        insert(ingest_jobs).values(
            job_id=job_id,
            kb_id=kb_id,
            document_id=kb_doc_id,
            version_id=new_kb_version_id,
            job_type="reparse",
            status="queued",
            stage="queued",
            progress=0,
            result_summary={"binding_revision_id": str(binding_revision_id)},
            created_by=actor_id,
        )
    )

    session.commit()

    # 触发 Celery
    try:
        from app.worker import run_document_ingest_task
        run_document_ingest_task.delay(str(job_id))
    except Exception:
        pass

    # 返回更新后的绑定 DTO
    updated_binding = session.execute(
        select(document_kb_bindings).where(document_kb_bindings.c.binding_id == binding_id)
    ).mappings().one()

    row_dict = _attach_binding_revision_summary(session, dict(updated_binding))
    return _to_binding_dto(row_dict, doc_name=doc_name)
