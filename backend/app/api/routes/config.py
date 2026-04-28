from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.config import (
    ConfigRevisionActivateRequest,
    ConfigRevisionActivationResponse,
    ConfigRevisionCreateRequest,
    ConfigRevisionCreateResponse,
    ConfigRevisionDraftFromRevisionRequest,
    ConfigRevisionDTO,
    ConfigTemplateDTO,
    PipelineValidateRequest,
    PipelineValidationResultDTO,
)
from app.services.config_service import (
    activate_config_revision,
    create_config_revision,
    create_revision_draft_from_revision,
    get_config_revision,
    list_config_revisions,
    list_config_templates,
    validate_pipeline_for_knowledge_base,
)
from app.services.knowledge_base_service import KnowledgeBaseDisabledError

template_router = APIRouter(prefix="/config-templates", tags=["config-templates"])
revision_router = APIRouter(
    prefix="/knowledge-bases/{kb_id}/config-revisions",
    tags=["config-revisions"],
)


@template_router.get("", response_model=list[ConfigTemplateDTO])
def read_config_templates(
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> list[ConfigTemplateDTO]:
    """返回当前可用配置模板；开发期只要求登录态。"""
    _ = current_user
    return list_config_templates(session)


@revision_router.post("/validate", response_model=PipelineValidationResultDTO)
def validate_pipeline(
    kb_id: UUID,
    request: PipelineValidateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PipelineValidationResultDTO:
    """执行后端 Pipeline 二次校验，当前规则不依赖数据库状态。"""
    response = validate_pipeline_for_knowledge_base(session, current_user, kb_id, request)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@revision_router.post("", response_model=ConfigRevisionCreateResponse, status_code=status.HTTP_201_CREATED)
def save_config_revision(
    kb_id: UUID,
    request: ConfigRevisionCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConfigRevisionCreateResponse:
    """保存新的 ConfigRevision；校验不通过时返回 400。"""
    try:
        response, validation = create_config_revision(session, current_user, kb_id, request)
    except KnowledgeBaseDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="KB_DISABLED: knowledge base is disabled.",
        ) from exc
    if response is None and validation.valid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.model_dump(),
        )
    return response


@revision_router.get("", response_model=PageResponse[ConfigRevisionDTO])
def read_config_revisions(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[ConfigRevisionDTO]:
    """分页返回配置版本历史。"""
    response = list_config_revisions(session, current_user, kb_id, page_no, page_size)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@revision_router.post("/drafts/from-revision", response_model=ConfigRevisionDTO, status_code=status.HTTP_201_CREATED)
def create_draft_from_revision(
    kb_id: UUID,
    request: ConfigRevisionDraftFromRevisionRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConfigRevisionDTO:
    """从历史 Revision 复制 pipelineDefinition，生成新的 draft。"""
    try:
        response = create_revision_draft_from_revision(session, current_user, kb_id, request)
    except KnowledgeBaseDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="KB_DISABLED: knowledge base is disabled.",
        ) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config revision not found.")
    return response


@revision_router.get("/{revision_id}", response_model=ConfigRevisionDTO)
def read_config_revision(
    kb_id: UUID,
    revision_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConfigRevisionDTO:
    """返回单个配置版本详情。"""
    response = get_config_revision(session, current_user, kb_id, revision_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config revision not found.")
    return response


@revision_router.post("/{revision_id}/activate", response_model=ConfigRevisionActivationResponse)
def activate_revision(
    kb_id: UUID,
    revision_id: UUID,
    request: ConfigRevisionActivateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> ConfigRevisionActivationResponse:
    """激活指定 Revision；保存与激活保持分离。"""
    try:
        response = activate_config_revision(
            session=session,
            current_user=current_user,
            kb_id=kb_id,
            revision_id=revision_id,
            confirm_impact=request.confirmImpact,
        )
    except KnowledgeBaseDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="KB_DISABLED: knowledge base is disabled.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config revision not found.")
    return response
