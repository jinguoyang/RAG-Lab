from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.audit import AuditExportResponse, AuditLogDTO, AuditReportResponse
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.services.audit_service import build_audit_report, export_audit_logs, list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("/report", response_model=AuditReportResponse)
def read_audit_report(
    kb_id: Annotated[UUID | None, Query(alias="kbId")] = None,
    action: str | None = None,
    resource_type: Annotated[str | None, Query(alias="resourceType")] = None,
    resource_id: Annotated[UUID | None, Query(alias="resourceId")] = None,
    actor_id: Annotated[UUID | None, Query(alias="actorId")] = None,
    keyword: str | None = None,
    created_from: Annotated[datetime | None, Query(alias="createdFrom")] = None,
    created_to: Annotated[datetime | None, Query(alias="createdTo")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AuditReportResponse:
    """返回审计报表聚合结果。"""
    try:
        return build_audit_report(
            session=session,
            current_user=current_user,
            kb_id=kb_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/export", response_model=AuditExportResponse)
def export_audit_report(
    export_format: Annotated[str, Query(alias="format")] = "csv",
    kb_id: Annotated[UUID | None, Query(alias="kbId")] = None,
    action: str | None = None,
    resource_type: Annotated[str | None, Query(alias="resourceType")] = None,
    resource_id: Annotated[UUID | None, Query(alias="resourceId")] = None,
    actor_id: Annotated[UUID | None, Query(alias="actorId")] = None,
    keyword: str | None = None,
    created_from: Annotated[datetime | None, Query(alias="createdFrom")] = None,
    created_to: Annotated[datetime | None, Query(alias="createdTo")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> AuditExportResponse:
    """导出审计日志文本内容。"""
    try:
        return export_audit_logs(
            session=session,
            current_user=current_user,
            export_format=export_format,
            kb_id=kb_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=PageResponse[AuditLogDTO])
def read_audit_logs(
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    kb_id: Annotated[UUID | None, Query(alias="kbId")] = None,
    action: str | None = None,
    resource_type: Annotated[str | None, Query(alias="resourceType")] = None,
    resource_id: Annotated[UUID | None, Query(alias="resourceId")] = None,
    actor_id: Annotated[UUID | None, Query(alias="actorId")] = None,
    keyword: str | None = None,
    created_from: Annotated[datetime | None, Query(alias="createdFrom")] = None,
    created_to: Annotated[datetime | None, Query(alias="createdTo")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[AuditLogDTO]:
    """查询审计日志，供发布验收和线上排障按资源、操作者和时间范围定位操作。"""
    try:
        return list_audit_logs(
            session=session,
            current_user=current_user,
            page_no=page_no,
            page_size=page_size,
            kb_id=kb_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
