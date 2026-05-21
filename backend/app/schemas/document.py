from pydantic import BaseModel, Field, model_validator


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
    resultSummary: dict | None = None
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


class ChunkGovernanceRequest(BaseModel):
    """Chunk 治理标记请求；只影响后续检索，不删除正文真值。"""

    excluded: bool
    note: str | None = None


class ChunkGovernanceResponse(BaseModel):
    """Chunk 治理标记结果，包含权限继承说明。"""

    chunk: ChunkDTO
    excluded: bool
    governanceNote: str | None
    permissionInheritance: str


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


class DocumentDeleteRequest(BaseModel):
    """文档删除请求；删除会影响检索副本，必须由前端二次确认。"""

    confirmImpact: bool
    reason: str | None = None


class DocumentDeleteCleanupJobDTO(BaseModel):
    """文档删除后的外部副本清理作业摘要。"""

    targetStore: str
    syncJobId: str | None = None
    status: str
    errorMessage: str | None = None


class DocumentDeleteResponse(BaseModel):
    """文档删除结果，区分业务删除和外部副本清理状态。"""

    documentId: str
    deletedAt: str
    auditLogId: str
    cleanupJobs: list[DocumentDeleteCleanupJobDTO] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentQualityIssueDTO(BaseModel):
    """文档质量问题摘要，用于治理入口聚合展示。"""

    issueType: str
    severity: str
    documentId: str | None = None
    versionId: str | None = None
    chunkId: str | None = None
    contentHash: str | None = None
    sampleChunkIds: list[str] = Field(default_factory=list)
    recommendedAction: str | None = None
    targetStore: str | None = None
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


class BulkDocumentGovernanceRequest(BaseModel):
    """文档批量治理请求；高影响动作必须由前端二次确认。"""

    operation: str
    documentIds: list[str] = Field(default_factory=list)
    confirmImpact: bool
    reason: str | None = None
    targetStore: str | None = None


class BulkDocumentGovernanceResponse(BaseModel):
    """文档批量治理结果摘要。"""

    operation: str
    requestedCount: int
    successCount: int
    failedCount: int
    affectedIds: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    """上传成功后一次性返回文档、首版本和 queued 作业，或文件重复检查结果。"""

    status: str = "success"  # "success" or "duplicate"
    message: str = "上传成功"
    document: DocumentDTO | None = None
    version: DocumentVersionDTO | None = None
    ingestJob: IngestJobDTO | None = None
    storedFile: StoredFileDTO | None = None
    duplicateInfo: dict | None = None
    fileHash: str | None = None

    @model_validator(mode="after")
    def _validate_status_fields(self) -> "DocumentUploadResponse":
        if self.status == "success":
            missing = [
                name
                for name in ("document", "version", "ingestJob", "storedFile")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(
                    f"status='success' requires {', '.join(missing)} to be non-None"
                )
        elif self.status == "duplicate":
            if self.duplicateInfo is None:
                raise ValueError("status='duplicate' requires duplicateInfo to be non-None")
        return self


class DocumentDetailDTO(BaseModel):
    """文档详情响应，包含当前 active version 摘要。"""

    document: DocumentDTO
    activeVersion: DocumentVersionDTO | None


class DeletionImpactAnalysis(BaseModel):
    """删除影响分析结果。"""

    canDelete: bool
    blockingReasons: list[str]
    isActiveVersion: bool
    activeBindingCount: int
    pendingJobsCount: int
    qaEvidenceCount: int
    qaCitationCount: int
    requiresStrongConfirmation: bool


class DocumentVersionDeleteRequest(BaseModel):
    """文档版本删除请求。"""

    strongConfirmation: bool = False


class DocumentVersionDeleteResponse(BaseModel):
    """文档版本删除响应。"""

    status: str
    message: str
    impactAnalysis: DeletionImpactAnalysis | None = None
    deletedVersionId: str | None = None
