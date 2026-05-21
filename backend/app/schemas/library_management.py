from typing import Literal

from pydantic import BaseModel, Field


LibraryRole = Literal[
    "read_only",
    "document_manage",
    "library_viewer",
    "library_binder",
    "library_editor",
    "library_manager",
]


class LibraryDTO(BaseModel):
    """文档库主对象 DTO。"""

    libraryId: str
    ownerId: str
    name: str
    description: str | None
    visibility: str
    status: str
    documentCount: int = 0
    createdAt: str
    updatedAt: str


class LibraryDetailDTO(BaseModel):
    """文档库详情响应。"""

    libraryId: str
    ownerId: str
    name: str
    description: str | None
    visibility: str
    status: str
    documentCount: int = 0
    createdAt: str
    updatedAt: str


class CreateLibraryRequest(BaseModel):
    """创建文档库请求。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    visibility: Literal["public", "personal", "partial"] = "personal"


class UpdateLibraryRequest(BaseModel):
    """更新文档库请求。"""

    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    visibility: Literal["public", "personal", "partial"] | None = None


class LibraryMemberDTO(BaseModel):
    """文档库成员 DTO。"""

    bindingId: str
    subjectType: str
    subjectId: str
    permissionLevel: str
    status: str
    createdAt: str


class AddLibraryMemberRequest(BaseModel):
    """添加文档库成员请求。"""

    subjectType: Literal["user", "group"]
    subjectId: str
    permissionLevel: LibraryRole


class UpdateLibraryMemberRequest(BaseModel):
    """更新文档库成员权限请求。"""

    permissionLevel: LibraryRole


class LibraryPageResponse(BaseModel):
    """文档库分页响应。"""

    items: list[LibraryDTO]
    total: int
    pageNo: int
    pageSize: int
