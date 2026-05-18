from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.dictionary import DictionaryItemCreateRequest, DictionaryItemDTO, DictionaryItemUpdateRequest, DictionaryTypeDTO
from app.services.dictionary_service import (
    DictionaryConflictError,
    DictionaryNotFoundError,
    DictionaryPermissionError,
    DictionaryValidationError,
    create_dictionary_item,
    list_dictionary_items,
    list_dictionary_types,
    update_dictionary_item,
)

router = APIRouter(prefix="/dictionaries", tags=["dictionaries"])


def _raise_dictionary_error(exc: Exception) -> None:
    """将字典服务异常映射为 HTTP 响应。"""
    if isinstance(exc, DictionaryPermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PERMISSION_DENIED") from exc
    if isinstance(exc, DictionaryNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary not found.") from exc
    if isinstance(exc, DictionaryConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Dictionary item conflicts with active data.") from exc
    if isinstance(exc, DictionaryValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise exc


@router.get("", response_model=list[DictionaryTypeDTO])
def read_dictionary_types(session: Session = Depends(get_db_session)) -> list[DictionaryTypeDTO]:
    """返回系统字典类型列表。"""
    return list_dictionary_types(session)


@router.get("/{type_code}/items", response_model=list[DictionaryItemDTO])
def read_dictionary_items(
    type_code: str,
    active_only: Annotated[bool, Query(alias="activeOnly")] = True,
    session: Session = Depends(get_db_session),
) -> list[DictionaryItemDTO]:
    """按类型返回字典项；默认只返回 active 项供页面下拉使用。"""
    try:
        return list_dictionary_items(session, type_code, active_only)
    except Exception as exc:
        _raise_dictionary_error(exc)


@router.post("/{type_code}/items", response_model=DictionaryItemDTO, status_code=status.HTTP_201_CREATED)
def create_dictionary_item_endpoint(
    type_code: str,
    request: DictionaryItemCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DictionaryItemDTO:
    """创建字典项。"""
    try:
        return create_dictionary_item(session, current_user, type_code, request)
    except Exception as exc:
        _raise_dictionary_error(exc)


@router.patch("/{type_code}/items/{item_code}", response_model=DictionaryItemDTO)
def update_dictionary_item_endpoint(
    type_code: str,
    item_code: str,
    request: DictionaryItemUpdateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> DictionaryItemDTO:
    """更新字典项；code 不允许变更。"""
    try:
        return update_dictionary_item(session, current_user, type_code, item_code, request)
    except Exception as exc:
        _raise_dictionary_error(exc)
