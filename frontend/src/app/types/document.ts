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
  createdAt: string;
}

export interface ChunkDTO {
  chunkId: string;
  versionId: string;
  documentId: string;
  kbId: string;
  chunkIndex: number;
  pageNo: number | null;
  section: string | null;
  content: string;
  contentHash: string | null;
  tokenCount: number | null;
  securityLevel: string;
  status: "active" | "inactive" | "deleted";
  metadata: Record<string, unknown>;
  createdAt: string;
}

export interface DocumentVersionActivateResponse {
  documentId: string;
  activeVersionId: string;
  previousActiveVersionId: string | null;
  auditLogId: string;
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
