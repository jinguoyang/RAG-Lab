"""知识库绑定相关 DTO。"""
from datetime import datetime

from pydantic import BaseModel, model_validator


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
    activeChunkRevisionId: str | None = None
    chunkRevisionStatus: str | None = None
    chunkRevisionChunkCount: int | None = None
    chunkRevisionVersionId: str | None = None
    createdAt: str
    createdBy: str | None = None


class LibraryBindRequest(BaseModel):
    """绑定请求。"""
    documentIds: list[str]
    versionId: str | None = None


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


class RechunkRequest(BaseModel):
    """重新分块请求。"""
    strategy: str = "fixed_size"
    params: dict | None = None

    @model_validator(mode="after")
    def validate_fixed_size_params(self) -> "RechunkRequest":
        """校验固定长度分块参数，避免非法作业进入异步队列。"""
        if self.strategy != "fixed_size":
            raise ValueError("Only fixed_size rechunk strategy is supported.")
        params = self.params or {}
        chunk_size = params.get("chunk_size")
        chunk_overlap = params.get("chunk_overlap", 0)
        if type(chunk_size) is not int or not 100 <= chunk_size <= 4000:
            raise ValueError("chunk_size must be an integer between 100 and 4000.")
        if type(chunk_overlap) is not int or chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be a non-negative integer smaller than chunk_size.")
        return self


class ChunkRevisionDTO(BaseModel):
    """绑定版本修订记录。"""
    chunkRevisionId: str
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
