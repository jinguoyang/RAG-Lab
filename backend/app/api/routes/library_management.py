from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUserResponse, get_current_user
from app.core.database import get_db_session
from app.schemas.library_management import (
    AddLibraryMemberRequest,
    CreateLibraryRequest,
    LibraryDTO,
    LibraryDetailDTO,
    LibraryMemberDTO,
    LibraryPageResponse,
    UpdateLibraryMemberRequest,
    UpdateLibraryRequest,
)
from app.services.library_management_service import (
    LibraryMemberConflictError,
    LibraryMemberNotFoundError,
    LibraryNotFoundError,
    LibraryPermissionError,
    add_library_member,
    create_library,
    delete_library,
    get_library_detail,
    list_libraries,
    list_library_members,
    remove_library_member,
    update_library,
    update_library_member,
)

router = APIRouter(prefix="/library", tags=["文档库管理"])


def _raise_library_mgmt_error(exc: Exception) -> None:
    if isinstance(exc, LibraryNotFoundError):
        raise HTTPException(status_code=404, detail="文档库不存在")
    if isinstance(exc, LibraryPermissionError):
        raise HTTPException(status_code=403, detail="无权限执行此操作")
    if isinstance(exc, LibraryMemberNotFoundError):
        raise HTTPException(status_code=404, detail="成员不存在")
    if isinstance(exc, LibraryMemberConflictError):
        raise HTTPException(status_code=409, detail="该成员已存在")
    raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("", response_model=LibraryPageResponse)
def list_libraries_route(
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
    page_no: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None),
) -> LibraryPageResponse:
    """列出当前用户可见的文档库。"""
    try:
        return list_libraries(db, current_user, page_no, page_size, keyword)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.post("", response_model=LibraryDTO, status_code=201)
def create_library_route(
    request: CreateLibraryRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryDTO:
    """创建文档库。"""
    try:
        return create_library(db, current_user, request)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.get("/{library_id}", response_model=LibraryDetailDTO)
def get_library_detail_route(
    library_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryDetailDTO:
    """获取文档库详情。"""
    try:
        return get_library_detail(db, current_user, library_id)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.patch("/{library_id}", response_model=LibraryDTO)
def update_library_route(
    library_id: UUID,
    request: UpdateLibraryRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryDTO:
    """更新文档库。仅所有者或平台管理员可操作。"""
    try:
        return update_library(db, current_user, library_id, request)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.delete("/{library_id}", status_code=204)
def delete_library_route(
    library_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> None:
    """删除文档库（软删除，级联删除库内文档）。仅所有者或平台管理员可操作。"""
    try:
        delete_library(db, current_user, library_id)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.get("/{library_id}/members", response_model=list[LibraryMemberDTO])
def list_members_route(
    library_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> list[LibraryMemberDTO]:
    """列出文档库成员。仅所有者或平台管理员可操作。"""
    try:
        return list_library_members(db, current_user, library_id)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.post("/{library_id}/members", response_model=LibraryMemberDTO, status_code=201)
def add_member_route(
    library_id: UUID,
    request: AddLibraryMemberRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryMemberDTO:
    """添加文档库成员。仅所有者或平台管理员可操作。"""
    try:
        return add_library_member(db, current_user, library_id, request)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.patch("/{library_id}/members/{binding_id}", response_model=LibraryMemberDTO)
def update_member_route(
    library_id: UUID,
    binding_id: UUID,
    request: UpdateLibraryMemberRequest,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryMemberDTO:
    """更新文档库成员权限级别。仅所有者或平台管理员可操作。"""
    try:
        return update_library_member(db, current_user, library_id, binding_id, request)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable


@router.delete("/{library_id}/members/{binding_id}", status_code=204)
def remove_member_route(
    library_id: UUID,
    binding_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> None:
    """移除文档库成员。仅所有者或平台管理员可操作。"""
    try:
        remove_library_member(db, current_user, library_id, binding_id)
    except Exception as exc:
        _raise_library_mgmt_error(exc)
        raise  # unreachable
