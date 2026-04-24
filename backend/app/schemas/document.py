from pydantic import BaseModel


class StoredFileDTO(BaseModel):
    """上传文件元数据摘要，开发期仅返回可追踪的对象引用信息。"""

    fileId: str
    fileName: str
    mimeType: str | None
    fileSize: int
    checksum: str | None
    objectKey: str


class DocumentDTO(BaseModel):
    """文档主对象 DTO，接口层保持 camelCase 命名。"""

    documentId: str
    kbId: str
    name: str
    sourceType: str
    securityLevel: str
    status: str
    activeVersionId: str | None
    createdAt: str
    updatedAt: str


class DocumentVersionDTO(BaseModel):
    """文档版本 DTO，承载解析和索引副本的最小状态。"""

    versionId: str
    documentId: str
    versionNo: int
    sourceFileId: str
    status: str
    parseStatus: str
    denseIndexStatus: str
    sparseIndexStatus: str
    graphIndexStatus: str
    retrievalReady: bool
    chunkCount: int
    tokenCount: int | None
    createdAt: str
    updatedAt: str


class IngestJobDTO(BaseModel):
    """入库作业 DTO，用于前端轮询和最近作业展示。"""

    jobId: str
    kbId: str
    documentId: str | None
    versionId: str | None
    jobType: str
    status: str
    stage: str | None
    progress: int
    errorCode: str | None
    errorMessage: str | None
    createdAt: str


class DocumentUploadResponse(BaseModel):
    """上传成功后一次性返回文档、首版本和 queued 作业。"""

    document: DocumentDTO
    version: DocumentVersionDTO
    ingestJob: IngestJobDTO
    storedFile: StoredFileDTO
