from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import RowMapping, and_, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.dictionary import DictionaryItemCreateRequest, DictionaryItemDTO, DictionaryItemUpdateRequest, DictionaryTypeDTO
from app.tables import system_dict_items, system_dict_types


class DictionaryPermissionError(Exception):
    """当前用户缺少平台字典管理权限。"""


class DictionaryNotFoundError(Exception):
    """字典类型或字典项不存在。"""


class DictionaryConflictError(Exception):
    """字典项与现有数据冲突。"""


class DictionaryValidationError(ValueError):
    """业务写入引用了不存在或未启用的字典项。"""


FIXED_CODE_TYPES: dict[str, set[str]] = {
    "platform_role": {"platform_admin", "platform_user"},
    "kb_role": {"kb_owner", "kb_editor", "kb_operator", "kb_viewer"},
}


def _now() -> datetime:
    """统一生成字典更新时间。"""
    return datetime.now(UTC)


def _actor_id(current_user: CurrentUserResponse) -> UUID:
    """读取当前用户 ID，用于审计字段。"""
    return UUID(current_user.user.userId)


def _ensure_dictionary_manage_permission(current_user: CurrentUserResponse) -> None:
    """平台字典属于全局配置，只允许平台管理员或平台用户管理权限修改。"""
    if (
        current_user.user.platformRole != "platform_admin"
        and "platform.user.manage" not in current_user.platformPermissions
    ):
        raise DictionaryPermissionError


def _type_condition(type_code: str):
    """构造 active 字典类型查询条件，避免重复书写软删除判断。"""
    return and_(
        system_dict_types.c.code == type_code,
        system_dict_types.c.status == "active",
        system_dict_types.c.deleted_at.is_(None),
    )


def _read_type_row(session: Session, type_code: str) -> RowMapping:
    """读取可用字典类型。"""
    row = session.execute(select(system_dict_types).where(_type_condition(type_code)).limit(1)).mappings().first()
    if row is None:
        raise DictionaryNotFoundError
    return row


def _type_to_dto(row: RowMapping) -> DictionaryTypeDTO:
    """将 system_dict_types 行转换为 DTO。"""
    return DictionaryTypeDTO(
        dictTypeId=str(row["dict_type_id"]),
        code=row["code"],
        name=row["name"],
        description=row["description"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _item_to_dto(row: RowMapping) -> DictionaryItemDTO:
    """将 system_dict_items 行转换为 DTO。"""
    return DictionaryItemDTO(
        dictItemId=str(row["dict_item_id"]),
        typeCode=row["type_code"],
        code=row["code"],
        name=row["name"],
        description=row["description"],
        sortOrder=row["sort_order"],
        status=row["status"],
        extra=row["extra"] or {},
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def list_dictionary_types(session: Session) -> list[DictionaryTypeDTO]:
    """返回未删除字典类型列表。"""
    rows = session.execute(
        select(system_dict_types)
        .where(system_dict_types.c.deleted_at.is_(None))
        .order_by(system_dict_types.c.code.asc())
    ).mappings()
    return [_type_to_dto(row) for row in rows]


def list_dictionary_items(session: Session, type_code: str, active_only: bool = True) -> list[DictionaryItemDTO]:
    """按字典类型返回字典项，供页面下拉和管理页复用。"""
    type_row = _read_type_row(session, type_code)
    condition = and_(
        system_dict_items.c.dict_type_id == type_row["dict_type_id"],
        system_dict_items.c.deleted_at.is_(None),
    )
    if active_only:
        condition = condition & (system_dict_items.c.status == "active")
    rows = session.execute(
        select(system_dict_items, system_dict_types.c.code.label("type_code"))
        .select_from(system_dict_items.join(system_dict_types, system_dict_items.c.dict_type_id == system_dict_types.c.dict_type_id))
        .where(condition)
        .order_by(system_dict_items.c.sort_order.asc(), system_dict_items.c.code.asc())
    ).mappings()
    return [_item_to_dto(row) for row in rows]


def is_active_dict_item(session: Session, type_code: str, item_code: str) -> bool:
    """检查业务写入值是否引用 active 字典项。"""
    exists = session.execute(
        select(system_dict_items.c.dict_item_id)
        .select_from(system_dict_items.join(system_dict_types, system_dict_items.c.dict_type_id == system_dict_types.c.dict_type_id))
        .where(
            system_dict_types.c.code == type_code,
            system_dict_types.c.status == "active",
            system_dict_types.c.deleted_at.is_(None),
            system_dict_items.c.code == item_code,
            system_dict_items.c.status == "active",
            system_dict_items.c.deleted_at.is_(None),
        )
        .limit(1)
    ).scalar_one_or_none()
    return exists is not None


def require_active_dict_item(session: Session, type_code: str, item_code: str, field_name: str) -> None:
    """业务写入前校验字典项，错误信息带上字段名便于接口定位。"""
    if not is_active_dict_item(session, type_code, item_code):
        raise DictionaryValidationError(f"{field_name} must reference an active {type_code} dictionary item.")


def _validate_item_code(type_code: str, item_code: str) -> None:
    """角色类字典只能维护既有 code，防止破坏权限矩阵。"""
    allowed_codes = FIXED_CODE_TYPES.get(type_code)
    if allowed_codes is not None and item_code not in allowed_codes:
        raise DictionaryValidationError(f"{type_code} code is fixed by backend permission contract.")


def create_dictionary_item(
    session: Session,
    current_user: CurrentUserResponse,
    type_code: str,
    request: DictionaryItemCreateRequest,
) -> DictionaryItemDTO:
    """创建字典项；code 创建后不可修改。"""
    _ensure_dictionary_manage_permission(current_user)
    type_row = _read_type_row(session, type_code)
    _validate_item_code(type_code, request.code)
    now = _now()
    try:
        row = session.execute(
            insert(system_dict_items)
            .values(
                dict_item_id=uuid4(),
                dict_type_id=type_row["dict_type_id"],
                code=request.code,
                name=request.name,
                description=request.description,
                sort_order=request.sortOrder,
                status=request.status,
                extra=request.extra,
                created_at=now,
                created_by=_actor_id(current_user),
                updated_at=now,
                updated_by=_actor_id(current_user),
            )
            .returning(system_dict_items)
        ).mappings().one()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DictionaryConflictError from exc
    item_row = dict(row)
    item_row["type_code"] = type_code
    return _item_to_dto(item_row)


def update_dictionary_item(
    session: Session,
    current_user: CurrentUserResponse,
    type_code: str,
    item_code: str,
    request: DictionaryItemUpdateRequest,
) -> DictionaryItemDTO:
    """更新字典项展示信息、排序、状态和扩展属性。"""
    _ensure_dictionary_manage_permission(current_user)
    type_row = _read_type_row(session, type_code)
    values = request.model_dump(exclude_unset=True)
    if not values:
        items = [item for item in list_dictionary_items(session, type_code, active_only=False) if item.code == item_code]
        if not items:
            raise DictionaryNotFoundError
        return items[0]

    update_values: dict[str, object] = {
        "updated_at": _now(),
        "updated_by": _actor_id(current_user),
    }
    field_map = {"sortOrder": "sort_order"}
    for key, value in values.items():
        update_values[field_map.get(key, key)] = value

    row = session.execute(
        update(system_dict_items)
        .where(
            system_dict_items.c.dict_type_id == type_row["dict_type_id"],
            system_dict_items.c.code == item_code,
            system_dict_items.c.deleted_at.is_(None),
        )
        .values(**update_values)
        .returning(system_dict_items)
    ).mappings().first()
    if row is None:
        session.rollback()
        raise DictionaryNotFoundError
    session.commit()
    item_row = dict(row)
    item_row["type_code"] = type_code
    return _item_to_dto(item_row)
