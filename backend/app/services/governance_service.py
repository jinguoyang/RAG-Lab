from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, insert, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.governance import (
    ConfigReleaseRecordCreateRequest,
    ConfigReleaseRecordDTO,
    ConfigRollbackConfirmRequest,
)
from app.schemas.qa_run import (
    QARunCollaborationDTO,
    QARunCollaborationUpdateRequest,
    QARunCommentCreateRequest,
    QARunCommentDTO,
)
from app.services.audit_service import write_audit_log
from app.services.permission_service import has_kb_permission
from app.tables import audit_logs, config_revisions, knowledge_bases, qa_runs


class GovernancePermissionError(Exception):
    """当前用户缺少治理接口所需权限。"""


class GovernanceConflictError(ValueError):
    """治理操作参数与当前资源状态冲突。"""


def _now() -> datetime:
    """统一生成治理记录时间戳，避免响应和持久化格式漂移。"""
    return datetime.now(UTC)


def _read_knowledge_base(session: Session, kb_id: UUID) -> RowMapping | None:
    """读取未删除知识库；调用方负责按接口语义处理权限。"""
    return session.execute(
        select(knowledge_bases)
        .where(knowledge_bases.c.kb_id == kb_id, knowledge_bases.c.deleted_at.is_(None))
        .limit(1)
    ).mappings().first()


def _require_kb_permission(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    permission_code: str,
) -> RowMapping | None:
    """确认知识库存在并检查权限，不可见和不存在由路由统一映射。"""
    kb_row = _read_knowledge_base(session, kb_id)
    if kb_row is None:
        return None
    if not has_kb_permission(session, current_user, kb_id, permission_code):
        raise GovernancePermissionError
    return kb_row


def _read_config_revision(session: Session, kb_id: UUID, revision_id: UUID) -> RowMapping | None:
    """读取指定知识库下未删除的配置版本。"""
    return session.execute(
        select(config_revisions)
        .where(
            config_revisions.c.kb_id == kb_id,
            config_revisions.c.config_revision_id == revision_id,
            config_revisions.c.deleted_at.is_(None),
        )
        .limit(1)
    ).mappings().first()


def _to_release_record_dto(row: RowMapping) -> ConfigReleaseRecordDTO:
    """将审计日志转换为配置发布记录 DTO。"""
    detail = row["detail"] or {}
    action = row["action"]
    return ConfigReleaseRecordDTO(
        releaseRecordId=str(row["audit_log_id"]),
        configRevisionId=str(row["resource_id"]),
        action=action,
        changeSummary=str(detail.get("changeSummary") or detail.get("reason") or action),
        linkedEvaluationRunId=detail.get("linkedEvaluationRunId"),
        rollbackPlan=detail.get("rollbackPlan"),
        rollbackConfirmed=bool(detail.get("rollbackConfirmed") or action == "config_release.rollback_confirm"),
        rollbackTargetRevisionId=detail.get("targetRevisionId"),
        actorId=str(row["actor_id"]) if row["actor_id"] else None,
        createdAt=row["created_at"].isoformat(),
        detail=detail,
    )


def list_config_release_records(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
) -> list[ConfigReleaseRecordDTO] | None:
    """返回知识库配置发布与回滚确认记录，来源为审计日志。"""
    if _require_kb_permission(session, current_user, kb_id, "kb.view") is None:
        return None

    rows = session.execute(
        select(audit_logs)
        .where(
            audit_logs.c.kb_id == kb_id,
            audit_logs.c.resource_type == "config_revision",
            audit_logs.c.action.in_(
                [
                    "config_release.record",
                    "config_release.rollback_confirm",
                    "config_revision.activate",
                ]
            ),
        )
        .order_by(audit_logs.c.created_at.desc(), audit_logs.c.audit_log_id.desc())
        .limit(100)
    ).mappings()
    return [_to_release_record_dto(row) for row in rows]


def create_config_release_record(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    revision_id: UUID,
    request: ConfigReleaseRecordCreateRequest,
) -> ConfigReleaseRecordDTO | None:
    """写入配置发布记录；正式生效仍由 activate 接口完成。"""
    if _require_kb_permission(session, current_user, kb_id, "kb.config.manage") is None:
        return None
    if _read_config_revision(session, kb_id, revision_id) is None:
        return None

    try:
        audit_log_id = write_audit_log(
            session,
            current_user,
            "config_release.record",
            "config_revision",
            revision_id,
            kb_id=kb_id,
            detail={
                "changeSummary": request.changeSummary,
                "linkedEvaluationRunId": str(request.linkedEvaluationRunId) if request.linkedEvaluationRunId else None,
                "rollbackPlan": request.rollbackPlan,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    row = session.execute(select(audit_logs).where(audit_logs.c.audit_log_id == audit_log_id)).mappings().one()
    return _to_release_record_dto(row)


def confirm_config_rollback(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    revision_id: UUID,
    request: ConfigRollbackConfirmRequest,
) -> ConfigReleaseRecordDTO | None:
    """记录回滚影响确认；不直接切换 active revision。"""
    if _require_kb_permission(session, current_user, kb_id, "kb.config.manage") is None:
        return None
    if not request.confirmImpact:
        raise GovernanceConflictError("confirmImpact must be true.")
    if _read_config_revision(session, kb_id, revision_id) is None:
        return None
    if request.targetRevisionId and _read_config_revision(session, kb_id, request.targetRevisionId) is None:
        return None

    try:
        audit_log_id = write_audit_log(
            session,
            current_user,
            "config_release.rollback_confirm",
            "config_revision",
            revision_id,
            kb_id=kb_id,
            detail={
                "reason": request.reason,
                "rollbackConfirmed": True,
                "targetRevisionId": str(request.targetRevisionId) if request.targetRevisionId else None,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    row = session.execute(select(audit_logs).where(audit_logs.c.audit_log_id == audit_log_id)).mappings().one()
    return _to_release_record_dto(row)


def _read_visible_qa_run(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
) -> RowMapping | None:
    """按知识库可见性读取 QA Run；作者本人和历史读取者可见。"""
    if _read_knowledge_base(session, kb_id) is None:
        return None
    row = session.execute(
        select(qa_runs)
        .where(qa_runs.c.kb_id == kb_id, qa_runs.c.run_id == run_id)
        .limit(1)
    ).mappings().first()
    if row is None:
        return None
    user_id = UUID(current_user.user.userId)
    if row["created_by"] == user_id or has_kb_permission(session, current_user, kb_id, "kb.qa.history.read"):
        return row
    return None


def _collaboration_from_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    """从 metrics 中取出协作块，缺省时返回稳定结构。"""
    collaboration = (metrics or {}).get("collaboration")
    if not isinstance(collaboration, dict):
        return {
            "sharedWithSubjectKeys": [],
            "ownerId": None,
            "handlingStatus": "open",
            "comments": [],
            "updatedAt": None,
        }
    return {
        "sharedWithSubjectKeys": list(collaboration.get("sharedWithSubjectKeys") or []),
        "ownerId": collaboration.get("ownerId"),
        "handlingStatus": collaboration.get("handlingStatus") or "open",
        "comments": list(collaboration.get("comments") or []),
        "updatedAt": collaboration.get("updatedAt"),
    }


def _to_collaboration_dto(run_id: UUID, collaboration: dict[str, Any]) -> QARunCollaborationDTO:
    """将 metrics 协作块转换为前端可展示 DTO。"""
    comments = [
        QARunCommentDTO(
            commentId=str(comment.get("commentId")),
            authorId=str(comment.get("authorId")),
            content=str(comment.get("content") or ""),
            createdAt=str(comment.get("createdAt") or ""),
        )
        for comment in collaboration.get("comments", [])
        if isinstance(comment, dict)
    ]
    return QARunCollaborationDTO(
        runId=str(run_id),
        sharedWithSubjectKeys=[str(item) for item in collaboration.get("sharedWithSubjectKeys", [])],
        ownerId=str(collaboration["ownerId"]) if collaboration.get("ownerId") else None,
        handlingStatus=str(collaboration.get("handlingStatus") or "open"),
        comments=comments,
        updatedAt=collaboration.get("updatedAt"),
    )


def get_qa_run_collaboration(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
) -> QARunCollaborationDTO | None:
    """读取 QA Run 协作状态。"""
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None
    return _to_collaboration_dto(run_id, _collaboration_from_metrics(row["metrics"]))


def _save_collaboration(
    session: Session,
    current_user: CurrentUserResponse,
    row: RowMapping,
    collaboration: dict[str, Any],
) -> QARunCollaborationDTO:
    """把协作块写回 QA Run metrics，并返回最新 DTO。"""
    now = _now()
    metrics = dict(row["metrics"] or {})
    collaboration["updatedAt"] = now.isoformat()
    metrics["collaboration"] = collaboration
    updated = session.execute(
        update(qa_runs)
        .where(qa_runs.c.run_id == row["run_id"])
        .values(
            metrics=metrics,
            updated_at=now,
            updated_by=UUID(current_user.user.userId),
        )
        .returning(qa_runs)
    ).mappings().one()
    return _to_collaboration_dto(updated["run_id"], _collaboration_from_metrics(updated["metrics"]))


def update_qa_run_collaboration(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
    request: QARunCollaborationUpdateRequest,
) -> QARunCollaborationDTO | None:
    """更新分享对象、责任人和处理状态。"""
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None
    if not has_kb_permission(session, current_user, kb_id, "kb.qa.history.read"):
        raise GovernancePermissionError

    collaboration = _collaboration_from_metrics(row["metrics"])
    if request.sharedWithSubjectKeys is not None:
        collaboration["sharedWithSubjectKeys"] = request.sharedWithSubjectKeys
    if request.ownerId is not None:
        collaboration["ownerId"] = str(request.ownerId)
    if request.handlingStatus is not None:
        collaboration["handlingStatus"] = request.handlingStatus

    try:
        dto = _save_collaboration(session, current_user, row, collaboration)
        write_audit_log(
            session,
            current_user,
            "qa_run.collaboration_update",
            "qa_run",
            run_id,
            kb_id=kb_id,
            detail={
                "sharedWithSubjectKeys": collaboration["sharedWithSubjectKeys"],
                "ownerId": collaboration["ownerId"],
                "handlingStatus": collaboration["handlingStatus"],
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return dto


def add_qa_run_comment(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    run_id: UUID,
    request: QARunCommentCreateRequest,
) -> QARunCollaborationDTO | None:
    """追加 QA Run 协作评论，评论保存在协作块内。"""
    row = _read_visible_qa_run(session, current_user, kb_id, run_id)
    if row is None:
        return None

    collaboration = _collaboration_from_metrics(row["metrics"])
    comments = list(collaboration.get("comments") or [])
    comments.append(
        {
            "commentId": str(uuid4()),
            "authorId": current_user.user.userId,
            "content": request.content,
            "createdAt": _now().isoformat(),
        }
    )
    collaboration["comments"] = comments

    try:
        dto = _save_collaboration(session, current_user, row, collaboration)
        write_audit_log(
            session,
            current_user,
            "qa_run.comment_add",
            "qa_run",
            run_id,
            kb_id=kb_id,
            detail={"commentCount": len(comments)},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return dto
