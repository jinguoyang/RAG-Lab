from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.user_group import (
    GroupMemberAddRequest,
    UserCreateRequest,
    UserGroupCreateRequest,
    UserGroupDetailDTO,
    UserGroupSummaryDTO,
    UserGroupUpdateRequest,
    UserSummaryDTO,
    UserUpdateRequest,
)
from app.services.user_group_service import (
    PlatformUserPermissionError,
    UserGroupConflictError,
    UserGroupNotFoundError,
    UserNotFoundError,
    add_group_members,
    create_user,
    create_user_group,
    disable_user,
    get_user,
    get_user_group,
    list_user_groups,
    list_users,
    remove_group_member,
    update_user,
    update_user_group,
)

users_router = APIRouter(prefix="/users", tags=["users"])
groups_router = APIRouter(prefix="/groups", tags=["groups"])


def _raise_user_group_error(exc: Exception) -> None:
    """将用户与用户组服务异常统一映射为接口响应。"""
    if isinstance(exc, PlatformUserPermissionError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user cannot manage platform users or groups.",
        ) from exc
    if isinstance(exc, UserNotFoundError | UserGroupNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User or group not found.") from exc
    if isinstance(exc, UserGroupConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User or group conflicts with active data.") from exc
    raise exc


@users_router.get("", response_model=PageResponse[UserSummaryDTO])
def read_users(
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[UserSummaryDTO]:
    """分页查询平台用户，供 P03 和 P04 添加组成员复用。"""
    try:
        return list_users(session, current_user, page_no, page_size, keyword)
    except Exception as exc:
        _raise_user_group_error(exc)


@users_router.post("", response_model=UserSummaryDTO, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    request: UserCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserSummaryDTO:
    """创建平台用户。"""
    try:
        return create_user(session, current_user, request)
    except Exception as exc:
        _raise_user_group_error(exc)


@users_router.get("/{user_id}", response_model=UserSummaryDTO)
def read_user(
    user_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserSummaryDTO:
    """读取用户详情。"""
    try:
        return get_user(session, current_user, user_id)
    except Exception as exc:
        _raise_user_group_error(exc)


@users_router.patch("/{user_id}", response_model=UserSummaryDTO)
def update_user_endpoint(
    user_id: UUID,
    request: UserUpdateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserSummaryDTO:
    """更新用户基础资料。"""
    try:
        return update_user(session, current_user, user_id, request)
    except Exception as exc:
        _raise_user_group_error(exc)


@users_router.post("/{user_id}/disable", response_model=UserSummaryDTO)
def disable_user_endpoint(
    user_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserSummaryDTO:
    """禁用用户主体。"""
    try:
        return disable_user(session, current_user, user_id)
    except Exception as exc:
        _raise_user_group_error(exc)


@groups_router.get("", response_model=PageResponse[UserGroupSummaryDTO])
def read_user_groups(
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[UserGroupSummaryDTO]:
    """分页查询用户组。"""
    try:
        return list_user_groups(session, current_user, page_no, page_size, keyword)
    except Exception as exc:
        _raise_user_group_error(exc)


@groups_router.post("", response_model=UserGroupSummaryDTO, status_code=status.HTTP_201_CREATED)
def create_user_group_endpoint(
    request: UserGroupCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserGroupSummaryDTO:
    """创建用户组。"""
    try:
        return create_user_group(session, current_user, request)
    except Exception as exc:
        _raise_user_group_error(exc)


@groups_router.get("/{group_id}", response_model=UserGroupDetailDTO)
def read_user_group(
    group_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserGroupDetailDTO:
    """读取用户组详情与成员列表。"""
    try:
        return get_user_group(session, current_user, group_id)
    except Exception as exc:
        _raise_user_group_error(exc)


@groups_router.patch("/{group_id}", response_model=UserGroupSummaryDTO)
def update_user_group_endpoint(
    group_id: UUID,
    request: UserGroupUpdateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserGroupSummaryDTO:
    """更新用户组基础资料。"""
    try:
        return update_user_group(session, current_user, group_id, request)
    except Exception as exc:
        _raise_user_group_error(exc)


@groups_router.post("/{group_id}/members", response_model=UserGroupDetailDTO)
def add_group_members_endpoint(
    group_id: UUID,
    request: GroupMemberAddRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> UserGroupDetailDTO:
    """批量添加用户组成员。"""
    try:
        return add_group_members(session, current_user, group_id, request)
    except Exception as exc:
        _raise_user_group_error(exc)


@groups_router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_group_member_endpoint(
    group_id: UUID,
    user_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> None:
    """移除用户组成员。"""
    try:
        remove_group_member(session, current_user, group_id, user_id)
    except Exception as exc:
        _raise_user_group_error(exc)
