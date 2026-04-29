from pydantic import BaseModel
from pydantic import Field


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


class ChunkDTO(BaseModel):
    """Chunk 正文真值 DTO；正文读取必须由后端权限控制后返回。"""

    chunkId: str
    versionId: str
    documentId: str
    kbId: str
    chunkIndex: int
    pageNo: int | None
    section: str | None
    content: str
    contentHash: str | None
    tokenCount: int | None
    securityLevel: str
    status: str
    metadata: dict = Field(default_factory=dict)
    createdAt: str


class DocumentReparseRequest(BaseModel):
    """文档重解析请求；reason 进入作业摘要和审计日志。"""

    reason: str | None = None


class DocumentVersionActivateRequest(BaseModel):
    """切换 active version 的二次确认请求。"""

    confirmImpact: bool
    reason: str | None = None


class DocumentVersionActivateResponse(BaseModel):
    """文档 active version 切换结果。"""

    documentId: str
    activeVersionId: str
    previousActiveVersionId: str | None
    auditLogId: str


class DocumentQualityIssueDTO(BaseModel):
    """文档质量问题摘要，用于治理入口聚合展示。"""

    issueType: str
    severity: str
    documentId: str | None = None
    versionId: str | None = None
    chunkId: str | None = None
    count: int
    message: str


class DocumentQualitySummaryDTO(BaseModel):
    """知识库文档质量检查汇总。"""

    kbId: str
    documentCount: int
    activeChunkCount: int
    failedVersionCount: int
    emptyChunkCount: int
    duplicateChunkGroupCount: int
    permissionAnomalyCount: int
    issues: list[DocumentQualityIssueDTO] = Field(default_factory=list)


class IndexSyncJobDTO(BaseModel):
    """索引副本同步作业 DTO，用于 P07 和运维入口观察重建状态。"""

    syncJobId: str
    kbId: str
    targetStore: str
    syncType: str
    scope: dict
    requiredForActivation: bool
    status: str
    errorMessage: str | None
    createdAt: str
    startedAt: str | None
    finishedAt: str | None


class IndexSyncRebuildRequest(BaseModel):
    """副本重建请求，可按知识库、文档或版本收窄范围。"""

    targetStore: str
    documentId: str | None = None
    versionId: str | None = None


class DocumentUploadResponse(BaseModel):
    """上传成功后一次性返回文档、首版本和 queued 作业。"""

    document: DocumentDTO
    version: DocumentVersionDTO
    ingestJob: IngestJobDTO
    storedFile: StoredFileDTO


class DocumentDetailDTO(BaseModel):
    """文档详情响应，包含当前 active version 摘要。"""

    document: DocumentDTO
    activeVersion: DocumentVersionDTO | None
