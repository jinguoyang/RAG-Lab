from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.knowledge_base import (
    KbMemberBindingDTO,
    KbMemberCreateRequest,
    KbMemberUpdateRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDTO,
)
from app.services.knowledge_base_service import (
    KbMemberBindingConflictError,
    KbMemberBindingNotFoundError,
    KbMemberSubjectNotFoundError,
    KnowledgeBaseNotFoundError,
    KnowledgeBasePermissionError,
    create_knowledge_base,
    create_kb_member,
    get_knowledge_base,
    list_knowledge_bases,
    list_kb_members,
    remove_kb_member,
    update_kb_member_role,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


def _raise_member_error(exc: Exception) -> None:
    """将成员服务层异常映射为 HTTP 响应，保持路由函数主体清爽。"""
    if isinstance(exc, KnowledgeBaseNotFoundError | KbMemberBindingNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base member binding not found.",
        ) from exc
    if isinstance(exc, KnowledgeBasePermissionError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user cannot manage knowledge base members.",
        ) from exc
    if isinstance(exc, KbMemberSubjectNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member subject not found.",
        ) from exc
    if isinstance(exc, KbMemberBindingConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member subject already has an active binding in this knowledge base.",
        ) from exc
    raise exc


@router.get("", response_model=PageResponse[KnowledgeBaseDTO])
def read_knowledge_bases(
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[KnowledgeBaseDTO]:
    """分页返回当前开发用户可见的知识库列表。"""
    return list_knowledge_bases(session, current_user, page_no, page_size, keyword)


@router.post("", response_model=KnowledgeBaseDTO, status_code=status.HTTP_201_CREATED)
def create_knowledge_base_endpoint(
    request: KnowledgeBaseCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> KnowledgeBaseDTO:
    """创建知识库基础记录，供 E1 平台工作台联调使用。"""
    try:
        return create_knowledge_base(session, current_user, request)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Knowledge base conflicts with existing data.",
        ) from exc


@router.get("/{kb_id}", response_model=KnowledgeBaseDTO)
def read_knowledge_base(
    kb_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> KnowledgeBaseDTO:
    """返回单个知识库详情；不可见资源按不存在处理。"""
    knowledge_base = get_knowledge_base(session, current_user, kb_id)
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )
    return knowledge_base


@router.get("/{kb_id}/members", response_model=PageResponse[KbMemberBindingDTO])
def read_kb_members(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[KbMemberBindingDTO]:
    """分页返回知识库成员绑定，支撑 P12 成员列表。"""
    try:
        return list_kb_members(session, current_user, kb_id, page_no, page_size, keyword)
    except Exception as exc:
        _raise_member_error(exc)


@router.post(
    "/{kb_id}/members",
    response_model=KbMemberBindingDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_kb_member_endpoint(
    kb_id: UUID,
    request: KbMemberCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> KbMemberBindingDTO:
    """添加知识库成员绑定，一个主体在同一知识库内只保留一个有效角色。"""
    try:
        return create_kb_member(session, current_user, kb_id, request)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Knowledge base member binding conflicts with existing data.",
        ) from exc
    except Exception as exc:
        _raise_member_error(exc)


@router.patch("/{kb_id}/members/{binding_id}", response_model=KbMemberBindingDTO)
def update_kb_member_endpoint(
    kb_id: UUID,
    binding_id: UUID,
    request: KbMemberUpdateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> KbMemberBindingDTO:
    """修改知识库成员角色。"""
    try:
        return update_kb_member_role(session, current_user, kb_id, binding_id, request)
    except Exception as exc:
        _raise_member_error(exc)


@router.delete("/{kb_id}/members/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kb_member_endpoint(
    kb_id: UUID,
    binding_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    """移除知识库成员绑定；服务层采用 inactive 失效而非物理删除。"""
    try:
        remove_kb_member(session, current_user, kb_id, binding_id)
    except Exception as exc:
        _raise_member_error(exc)
