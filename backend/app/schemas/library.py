from pydantic import BaseModel
from pydantic import Field


class LibraryDocumentDTO(BaseModel):
    """文档库文档主对象 DTO。"""

    documentId: str
    ownerId: str
    name: str
    sourceType: str
    securityLevel: str
    status: str
    activeVersionId: str | None
    createdAt: str
    updatedAt: str


class LibraryDocumentVersionDTO(BaseModel):
    """文档库版本 DTO，精简为文本提取状态。"""

    versionId: str
    documentId: str
    versionNo: int
    sourceFileId: str
    status: str
    parseStatus: str
    chunkCount: int
    tokenCount: int | None
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
