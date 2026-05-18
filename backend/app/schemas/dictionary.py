from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


DictionaryStatus = Literal["active", "disabled"]


class DictionaryTypeDTO(BaseModel):
    """系统字典类型，供平台字典管理页展示。"""

    dictTypeId: str
    code: str
    name: str
    description: str | None
    status: DictionaryStatus
    createdAt: str
    updatedAt: str


class DictionaryItemDTO(BaseModel):
    """系统字典项，前端下拉和标签展示统一消费该 DTO。"""

    dictItemId: str
    typeCode: str
    code: str
    name: str
    description: str | None
    sortOrder: int
    status: DictionaryStatus
    extra: dict[str, Any]
    createdAt: str
    updatedAt: str


class DictionaryItemCreateRequest(BaseModel):
    """创建字典项请求；角色类字典的 code 会在服务层按白名单收口。"""

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    sortOrder: int = 0
    status: DictionaryStatus = "active"
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code", "name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """去除首尾空白，避免写入不可见编码或名称。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("Dictionary text is required.")
        return stripped


class DictionaryItemUpdateRequest(BaseModel):
    """更新字典项请求；不允许修改 code，避免破坏历史业务引用。"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    sortOrder: int | None = None
    status: DictionaryStatus | None = None
    extra: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, value: Any) -> Any:
        """PATCH 可省略字段，但不能把数据库非空列显式更新为 null。"""
        if isinstance(value, dict):
            for field_name in ("sortOrder", "status", "extra"):
                if field_name in value and value[field_name] is None:
                    raise ValueError(f"{field_name} cannot be null.")
        return value

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        """更新名称时裁剪空白。"""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Dictionary name is required.")
        return stripped
