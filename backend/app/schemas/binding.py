"""知识库绑定相关 DTO。"""
from datetime import datetime

from pydantic import BaseModel


class LibraryBindingDTO(BaseModel):
    """文档库绑定到知识库的绑定记录。"""
    bindingId: str
    documentId: str
    documentName: str
    kbId: str
    versionId: str
    chunkSize: int
    chunkOverlap: int
    status: str
    chunkCount: int
    errorCode: str | None = None
    errorMessage: str | None = None
    createdAt: str
    createdBy: str | None = None


class LibraryBindRequest(BaseModel):
    """绑定请求。"""
    documentIds: list[str]


class LibraryBindResponse(BaseModel):
    """绑定响应。"""
    bindings: list[LibraryBindingDTO]


class LibraryUnbindResponse(BaseModel):
    """解绑响应。"""
    bindingId: str
    status: str


class SwitchBindingVersionRequest(BaseModel):
    """切换绑定版本请求。"""
    libraryVersionId: str


class BindingRevisionDTO(BaseModel):
    """绑定版本修订记录。"""
    bindingRevisionId: str
    bindingId: str
    knowledgeBaseId: str
    documentId: str
    documentVersionId: str
    parseRevisionId: str
    status: str
    chunkCount: int
    buildStartedAt: str | None = None
    buildFinishedAt: str | None = None
    activatedAt: str | None = None
    retiredAt: str | None = None
    createdAt: str
    createdBy: str | None = None
