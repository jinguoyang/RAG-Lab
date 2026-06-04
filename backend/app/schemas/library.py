from typing import Literal
from pydantic import BaseModel, Field


class LibraryDocumentDTO(BaseModel):
    """文档库文档主对象 DTO。"""

    documentId: str
    ownerId: str
    libraryId: str | None = None
    libraryName: str | None = None
    name: str
    sourceType: str
    status: str
    activeVersionId: str | None
    activeVersionNo: int | None = None
    activeVersionFileName: str | None = None
    latestParseStatus: str | None = None
    latestParseRevisionId: str | None = None
    createdAt: str
    updatedAt: str


class LibraryDocumentVersionDTO(BaseModel):
    """文档库源文件版本 DTO。"""

    versionId: str
    documentId: str
    versionNo: int
    sourceFileId: str
    fileName: str | None = None
    fileSize: int | None = None
    fileChecksum: str | None = None
    status: str
    parseStatus: str
    tokenCount: int | None
    activeParseRevisionId: str | None = None
    createdAt: str
    updatedAt: str


class LibraryStoredFileDTO(BaseModel):
    """文档库文件元数据 DTO。"""

    fileId: str
    fileName: str
    mimeType: str | None
    fileSize: int
    checksum: str | None
    objectKey: str


class LibraryParseJobDTO(BaseModel):
    """文档库解析作业 DTO。"""

    jobId: str
    documentId: str
    versionId: str
    jobType: str
    status: str
    progress: int
    errorCode: str | None
    errorMessage: str | None
    createdAt: str


class LibraryParseRevisionDTO(BaseModel):
    """文档库解析版本 DTO，不包含知识库分块数量。"""

    parseRevisionId: str
    documentVersionId: str
    status: str
    contentFormat: str
    contentLength: int
    contentHash: str | None
    parserName: str | None
    parserVersion: str | None
    parseOptions: dict
    errorCode: str | None = None
    errorMessage: str | None = None
    isActive: bool = False
    createdAt: str
    createdBy: str | None = None


class LibraryReparseRequest(BaseModel):
    """创建解析版本请求。"""

    parserName: str | None = "auto"
    parserVersion: str | None = None
    contentFormat: Literal["markdown", "text"] = "markdown"
    parseOptions: dict = Field(default_factory=dict)
    reason: str | None = None


class LibraryUploadParseOptions(BaseModel):
    """上传文档/版本时的解析选项。"""

    parserName: str | None = "auto"
    contentFormat: Literal["markdown", "text"] = "markdown"
    parseOptions: dict | None = None


class LibraryParseRevisionCreateResponse(BaseModel):
    """创建解析版本后的排队响应。"""

    jobId: str
    parseRevisionId: str
    status: str


class LibraryDocumentUploadResponse(BaseModel):
    """文档库上传成功响应。"""

    document: LibraryDocumentDTO
    version: LibraryDocumentVersionDTO
    parseJob: LibraryParseJobDTO
    storedFile: LibraryStoredFileDTO


class LibraryDocumentDetailDTO(BaseModel):
    """文档库文档详情响应。"""

    document: LibraryDocumentDTO
    activeVersion: LibraryDocumentVersionDTO | None


class LibraryDocumentUpdateRequest(BaseModel):
    """文档库文档更新请求。"""

    name: str | None = None
    status: str | None = None


class LibraryTextPreviewResponse(BaseModel):
    """文本预览响应。"""
    text: str
    truncated: bool
    fullLength: int


class LibraryParsedChunkDTO(BaseModel):
    """解析后的分块数据。"""
    content: str
    tokenCount: int
    section: str | None = None
    pageNo: int | None = None
    startOffset: int | None = None
    endOffset: int | None = None


class LibraryFullTextResponse(BaseModel):
    """完整文本响应。"""
    text: str


class LibraryParsedChunksResponse(BaseModel):
    """结构化解析分块响应。"""
    chunks: list[LibraryParsedChunkDTO]


class LibraryDocumentUsageDTO(BaseModel):
    """文档使用情况：绑定的知识库列表。"""
    bindingId: str
    kbId: str
    kbName: str
    status: str
    chunkCount: int
    createdAt: str


class LibraryDocumentUsageResponse(BaseModel):
    """文档使用情况响应。"""
    documentId: str
    usages: list[LibraryDocumentUsageDTO]


class BatchActionRequest(BaseModel):
    """批量操作请求。"""
    documentIds: list[str] = Field(..., min_length=1, max_length=100)
    action: Literal["delete", "reparse", "disable"]


class BatchActionFailedItem(BaseModel):
    """批量操作失败项。"""
    documentId: str
    error: str
    message: str


class BatchActionSummary(BaseModel):
    """批量操作汇总。"""
    total: int
    succeeded: int
    failed: int


class BatchActionResponse(BaseModel):
    """批量操作响应。"""
    succeeded: list[str]
    failed: list[BatchActionFailedItem]
    summary: BatchActionSummary


class LibraryStatsResponse(BaseModel):
    """文档库统计响应。"""
    totalDocuments: int
    todayUploads: int
    pendingParse: int


class LibraryVersionUploadResponse(BaseModel):
    """上传新版本成功响应。"""
    version: LibraryDocumentVersionDTO
    parseJob: LibraryParseJobDTO
    storedFile: LibraryStoredFileDTO


class LibraryVersionActivateRequest(BaseModel):
    """切换活跃版本请求。"""
    confirmImpact: bool = False


class LibraryVersionActivateResponse(BaseModel):
    """切换活跃版本响应。"""
    documentId: str
    activeVersionId: str
    previousActiveVersionId: str | None


class LibraryParseRevisionActivateRequest(BaseModel):
    """切换活动解析修订请求。"""
    parseRevisionId: str


class LibraryParseRevisionActivateResponse(BaseModel):
    """切换活动解析修订响应。"""
    documentId: str
    versionId: str
    activeParseRevisionId: str | None
    previousActiveParseRevisionId: str | None
