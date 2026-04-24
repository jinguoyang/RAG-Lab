from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResponse(BaseModel, Generic[T]):
    """分页响应结构，字段命名与接口设计说明保持 camelCase。"""

    items: list[T]
    pageNo: int
    pageSize: int
    total: int


class PageQuery(BaseModel):
    """分页查询参数的基础校验，避免各列表接口重复定义边界。"""

    pageNo: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)
    keyword: str | None = None
