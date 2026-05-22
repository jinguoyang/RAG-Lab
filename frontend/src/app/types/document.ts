import type { PageResponse } from "./knowledgeBase";

export type JobStatus = "queued" | "running" | "success" | "failed" | "cancelled";
export type DocumentStatus = "active" | "disabled" | "archived";
export type VersionStatus = "processing" | "active" | "inactive" | "failed";

export interface DocumentDTO {
  documentId: string;
  kbId: string;
  name: string;
  sourceType: string;
  securityLevel: string;
  status: DocumentStatus;
  activeVersionId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentVersionDTO {
  versionId: string;
  documentId: string;
  versionNo: number;
  sourceFileId: string;
  status: VersionStatus;
  parseStatus: "pending" | "running" | "success" | "failed";
  denseIndexStatus: "not_required" | "pending" | "running" | "success" | "failed";
  sparseIndexStatus: "not_required" | "pending" | "running" | "success" | "failed";
  graphIndexStatus: "not_required" | "pending" | "running" | "success" | "failed";
  retrievalReady: boolean;
  chunkCount: number;
  tokenCount: number | null;
  createdAt: string;
  updatedAt: string;
  sourceModality?: string | null;
}

export interface IndexStageViewModel {
  key: "parse" | "embedding" | "milvus" | "opensearch" | "graph_extract" | "graph_index";
  label: string;
  status: "not_required" | "pending" | "running" | "success" | "failed";
}

export interface IngestJobDTO {
  jobId: string;
  kbId: string;
  documentId: string | null;
  versionId: string | null;
  jobType: string;
  status: JobStatus;
  stage: string | null;
  progress: number;
  errorCode: string | null;
  errorMessage: string | null;
  resultSummary: Record<string, unknown> | null;
  createdAt: string;
}

export interface ChunkDTO {
  chunkId: string;
  versionId: string;
  documentId: string;
  kbId: string;
  bindingRevisionId: string | null;
  parseRevisionId: string | null;
  documentVersionId: string | null;
  chunkIndex: number;
  pageNo: number | null;
  section: string | null;
  startOffset: number | null;
  endOffset: number | null;
  sectionPath: string | null;
  heading: string | null;
  summary: string | null;
  content: string;
  contentHash: string | null;
  tokenCount: number | null;
  securityLevel: string;
  status: "active" | "inactive" | "retired" | "deleted";
  metadata: Record<string, unknown>;
  createdAt: string;
}

export interface ChunkGovernanceResponse {
  chunk: ChunkDTO;
  excluded: boolean;
  governanceNote: string | null;
  permissionInheritance: string;
}

export interface DocumentQualityIssueDTO {
  issueType: string;
  severity: "high" | "medium" | "low";
  documentId: string | null;
  versionId: string | null;
  chunkId: string | null;
  contentHash: string | null;
  sampleChunkIds: string[];
  recommendedAction: string | null;
  targetStore: string | null;
  count: number;
  message: string;
}

export interface DocumentQualitySummaryDTO {
  kbId: string;
  documentCount: number;
  activeChunkCount: number;
  failedVersionCount: number;
  emptyChunkCount: number;
  duplicateChunkGroupCount: number;
  permissionAnomalyCount: number;
  issues: DocumentQualityIssueDTO[];
}

export interface DocumentVersionActivateResponse {
  documentId: string;
  activeVersionId: string;
  previousActiveVersionId: string | null;
  auditLogId: string;
}

export interface DocumentDeleteCleanupJobDTO {
  targetStore: string;
  syncJobId: string | null;
  status: JobStatus;
  errorMessage: string | null;
}

export interface DocumentDeleteResponse {
  documentId: string;
  deletedAt: string;
  auditLogId: string;
  cleanupJobs: DocumentDeleteCleanupJobDTO[];
  warnings: string[];
}

export interface BulkDocumentGovernanceRequest {
  operation: "reparse" | "disable" | "rebuild_index";
  documentIds: string[];
  confirmImpact: boolean;
  reason?: string | null;
  targetStore?: string | null;
}

export interface BulkDocumentGovernanceResponse {
  operation: string;
  requestedCount: number;
  successCount: number;
  failedCount: number;
  affectedIds: string[];
  errors: string[];
}

export interface IndexSyncJobDTO {
  syncJobId: string;
  kbId: string;
  targetStore: string;
  syncType: string;
  scope: Record<string, unknown>;
  requiredForActivation: boolean;
  status: JobStatus;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface IndexSyncRebuildRequest {
  targetStore: string;
  documentId?: string | null;
  versionId?: string | null;
}

export interface DocumentDetailDTO {
  document: DocumentDTO;
  activeVersion: DocumentVersionDTO | null;
}

export interface DocumentUploadResponse {
  document: DocumentDTO;
  version: DocumentVersionDTO;
  ingestJob: IngestJobDTO;
}

export interface DocumentRowViewModel {
  id: string;
  name: string;
  status: JobStatus;
  securityLevel: string;
  updatedAtLabel: string;
}

export interface VersionRowViewModel {
  id: string;
  versionNo: string;
  status: JobStatus;
  parseStatusLabel: string;
  chunkCount: number;
  retrievalReadyLabel: string;
  createdAtLabel: string;
  active: boolean;
  indexStages: IndexStageViewModel[];
}

export interface IngestJobViewModel {
  id: string;
  documentId: string | null;
  versionId: string | null;
  status: JobStatus;
  stage: string;
  progress: number;
  createdAtLabel: string;
  errorMessage: string;
  indexStages: IndexStageViewModel[];
}

export interface ChunkViewModel {
  id: string;
  indexLabel: string;
  pageLabel: string;
  section: string;
  preview: string;
  tokenCount: number | null;
  metadataText: string;
}

export type DocumentPage = PageResponse<DocumentDTO>;
export type IngestJobPage = PageResponse<IngestJobDTO>;
export type ChunkPage = PageResponse<ChunkDTO>;
export type IndexSyncJobPage = PageResponse<IndexSyncJobDTO>;
