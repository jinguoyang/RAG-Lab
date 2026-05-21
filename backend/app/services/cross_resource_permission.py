"""跨资源权限校验服务。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.tables import (
    binding_revisions,
    documents,
    ingest_jobs,
    library_parse_jobs,
)
from app.services.permission_service import has_library_permission, has_kb_permission


def check_cross_resource_permission(
    session: Session,
    current_user: CurrentUserResponse,
    source_library_id: UUID,
    target_kb_id: UUID,
) -> bool:
    """检查跨资源绑定权限。

    需要同时具备：
    1. 源文档库的 library.document.bind 权限
    2. 目标知识库的 kb.document.bind 权限

    两者都通过才返回 True。
    """
    if not has_library_permission(session, current_user, "library.document.bind"):
        return False
    if not has_kb_permission(session, current_user, target_kb_id, "kb.document.bind"):
        return False
    return True


def check_document_version_delete_permission(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    document_id: UUID,
    version_id: UUID,
) -> tuple[bool, str]:
    """检查文档版本删除权限。

    依次检查：
    1. 是否有 library.version.delete 权限
    2. 该版本是否是文档的当前活跃版本
    3. 该版本是否有活跃的 BindingRevision
    4. 该版本是否有待处理/运行中的解析或入库任务

    Returns:
        (allowed, reason) - 是否允许删除及原因
    """
    # 1. 检查权限
    if not has_library_permission(session, current_user, "library.version.delete"):
        return False, "没有 library.version.delete 权限"

    # 2. 检查是否是活跃版本
    active_version_id = session.execute(
        select(documents.c.active_version_id).where(
            documents.c.document_id == document_id,
        )
    ).scalar()
    if active_version_id is not None and active_version_id == version_id:
        return False, "该版本是文档的当前活跃版本，不能删除"

    # 3. 检查是否有活跃的 BindingRevision
    active_binding = session.execute(
        select(binding_revisions.c.binding_revision_id).where(
            binding_revisions.c.document_version_id == version_id,
            binding_revisions.c.status == "active",
        )
    ).first()
    if active_binding is not None:
        return False, "该版本有活跃的绑定修订，不能删除"

    # 4. 检查是否有待处理/运行中的解析任务
    pending_parse_jobs = session.execute(
        select(library_parse_jobs.c.job_id).where(
            library_parse_jobs.c.version_id == version_id,
            library_parse_jobs.c.status.in_(["pending", "running"]),
        )
    ).scalars().all()
    if pending_parse_jobs:
        return False, "该版本有待处理的解析任务，不能删除"

    # 5. 检查是否有待处理/运行中的入库任务
    pending_ingest_jobs = session.execute(
        select(ingest_jobs.c.job_id).where(
            ingest_jobs.c.version_id == version_id,
            ingest_jobs.c.status.in_(["pending", "running"]),
        )
    ).scalars().all()
    if pending_ingest_jobs:
        return False, "该版本有待处理的入库任务，不能删除"

    return True, ""
