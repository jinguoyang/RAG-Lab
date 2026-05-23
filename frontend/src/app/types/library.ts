import type { PageResponse } from "./knowledgeBase";

export type LibraryDocumentStatus = "active" | "disabled" | "archived";
export type LibraryParseJobStatus = "queued" | "running" | "success" | "failed" | "cancelled";
export type LibraryMemberPermissionLevel =
  | "read_only"
  | "document_manage"
  | "library_viewer"
  | "library_binder"
  | "library_editor"
  | "library_manager";

export interface LibraryDocumentDTO {
  documentId: string;
  ownerId: string;
  libraryId: string | null;
  name: string;
  sourceType: string;
  status: LibraryDocumentStatus;
  activeVersionId: string | null;
  activeVersionNo?: number | null;
  activeVersionFileName?: string | null;
  latestParseStatus?: string | null;
  latestParseRevisionId?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface LibraryDTO {
  libraryId: string;
  ownerId: string;
  ownerName: string;
  name: string;
  description: string | null;
  status: string;
  documentCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface LibraryMemberDTO {
  bindingId: string;
  subjectType: "user" | "group";
  subjectId: string;
  permissionLevel: LibraryMemberPermissionLevel;
  status: string;
  createdAt: string;
}

export interface LibraryPageResponse {
  items: LibraryDTO[];
  total: number;
  pageNo: number;
  pageSize: number;
}

export interface ParseRevisionDTO {
  parseRevisionId: string;
  documentVersionId: string;
  status: "pending" | "running" | "success" | "failed" | "completed";
  contentFormat?: string;
  contentLength?: number;
  contentHash?: string | null;
  parserName: string | null;
  parserVersion?: string | null;
  parseOptions?: Record<string, unknown>;
  errorCode?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  createdBy?: string | null;
}

export interface LibraryDocumentVersionDTO {
  versionId: string;
  documentId: string;
  versionNo: number;
  sourceFileId: string;
  fileName?: string;
  fileSize?: number;
  fileChecksum?: string | null;
  status: string;
  parseStatus: "pending" | "running" | "success" | "failed";
  chunkCount: number;
  tokenCount: number | null;
  createdAt: string;
  updatedAt: string;
  parseRevisions?: ParseRevisionDTO[];
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

export interface LibraryStatsResponse {
  totalDocuments: number;
  todayUploads: number;
  pendingParse: number;
}

export interface BatchActionFailedItem {
  documentId: string;
  error: string;
  message: string;
}

export interface BatchActionSummary {
  total: number;
  succeeded: number;
  failed: number;
}

export interface BatchActionResponse {
  succeeded: string[];
  failed: BatchActionFailedItem[];
  summary: BatchActionSummary;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
}

export interface UploadWithProgressResult {
  promise: Promise<LibraryDocumentUploadResponse>;
  cancel: () => void;
  onProgress: (callback: (progress: UploadProgress) => void) => void;
}

export interface LibraryVersionUploadResponse {
  version: LibraryDocumentVersionDTO;
  parseJob: LibraryParseJobDTO;
  storedFile: LibraryStoredFileDTO;
}

export interface LibraryVersionActivateResponse {
  documentId: string;
  activeVersionId: string;
  previousActiveVersionId: string | null;
}

export interface LibraryReparseRequest {
  parserName?: string | null;
  parserVersion?: string | null;
  contentFormat: "markdown" | "text";
  parseOptions: Record<string, unknown>;
  reason?: string | null;
}

export interface LibraryParseRevisionCreateResponse {
  jobId: string;
  parseRevisionId: string;
  status: string;
}

export interface DeletionImpactAnalysis {
  canDelete: boolean;
  blockingReasons: string[];
  isActiveVersion: boolean;
  activeBindingCount: number;
  pendingJobsCount: number;
  qaEvidenceCount: number;
  qaCitationCount: number;
  requiresStrongConfirmation: boolean;
}

export interface LibraryBindingDTO {
  bindingId: string;
  documentId: string;
  documentName: string;
  kbId: string;
  versionId: string;
  chunkSize: number;
  chunkOverlap: number;
  status: string;
  chunkCount: number;
  errorCode?: string | null;
  errorMessage?: string | null;
  activeChunkRevisionId?: string | null;
  chunkRevisionStatus?: string | null;
  chunkRevisionChunkCount?: number | null;
  chunkRevisionVersionId?: string | null;
  createdAt: string;
  createdBy?: string | null;
}
