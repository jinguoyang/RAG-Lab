import type { PageResponse } from "./knowledgeBase";

export type LibraryDocumentStatus = "active" | "disabled" | "archived";
export type LibraryParseJobStatus = "queued" | "running" | "success" | "failed" | "cancelled";

export interface LibraryDocumentDTO {
  documentId: string;
  ownerId: string;
  name: string;
  sourceType: string;
  securityLevel: string;
  status: LibraryDocumentStatus;
  activeVersionId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface LibraryDocumentVersionDTO {
  versionId: string;
  documentId: string;
  versionNo: number;
  sourceFileId: string;
  status: string;
  parseStatus: "pending" | "running" | "success" | "failed";
  chunkCount: number;
  tokenCount: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface LibraryStoredFileDTO {
  fileId: string;
  fileName: string;
  mimeType: string | null;
  fileSize: number;
  checksum: string | null;
  objectKey: string;
}

export interface LibraryParseJobDTO {
  jobId: string;
  documentId: string;
  versionId: string;
  jobType: string;
  status: LibraryParseJobStatus;
  progress: number;
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string;
}

export interface LibraryDocumentUploadResponse {
  document: LibraryDocumentDTO;
  version: LibraryDocumentVersionDTO;
  parseJob: LibraryParseJobDTO;
  storedFile: LibraryStoredFileDTO;
}

export interface LibraryDocumentDetailDTO {
  document: LibraryDocumentDTO;
  activeVersion: LibraryDocumentVersionDTO | null;
}

export type LibraryDocumentPage = PageResponse<LibraryDocumentDTO>;

export interface LibraryTextPreviewResponse {
  text: string;
  truncated: boolean;
  fullLength: number;
}

export interface LibraryFullTextResponse {
  text: string;
}

export interface LibraryParsedChunkDTO {
  content: string;
  tokenCount: number;
  section?: string;
  pageNo?: number;
}

export interface LibraryParsedChunksResponse {
  chunks: LibraryParsedChunkDTO[];
}

export interface LibraryDocumentUsageDTO {
  bindingId: string;
  kbId: string;
  kbName: string;
  status: string;
  chunkCount: number;
  createdAt: string;
}

export interface LibraryDocumentUsageResponse {
  documentId: string;
  usages: LibraryDocumentUsageDTO[];
}
