import { apiDeleteJson, apiDownload, apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import type { ApiDownload } from "./apiClient";
import type {
  BulkDocumentGovernanceRequest,
  BulkDocumentGovernanceResponse,
  ChunkGovernanceResponse,
  ChunkPage,
  ChunkDTO,
  DocumentDetailDTO,
  DocumentDeleteResponse,
  DocumentPage,
  DocumentQualitySummaryDTO,
  DocumentUploadResponse,
  DocumentVersionActivateResponse,
  DocumentVersionDTO,
  IndexSyncJobDTO,
  IndexSyncJobPage,
  IndexSyncRebuildRequest,
  IngestJobDTO,
  IngestJobPage,
} from "../types/document";

interface FetchDocumentsParams {
  keyword?: string;
  pageNo?: number;
  pageSize?: number;
}

export async function fetchDocuments(
  kbId: string,
  { keyword, pageNo = 1, pageSize = 10 }: FetchDocumentsParams = {},
): Promise<DocumentPage> {
  const params = new URLSearchParams({ pageNo: String(pageNo), pageSize: String(pageSize) });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }

  return apiGet<DocumentPage>(`/knowledge-bases/${kbId}/documents?${params.toString()}`);
}

export async function fetchDocumentDetail(
  kbId: string,
  documentId: string,
): Promise<DocumentDetailDTO> {
  return apiGet<DocumentDetailDTO>(`/knowledge-bases/${kbId}/documents/${documentId}`);
}

export async function deleteDocument(
  kbId: string,
  documentId: string,
  reason?: string,
): Promise<DocumentDeleteResponse> {
  return apiDeleteJson<DocumentDeleteResponse>(`/knowledge-bases/${kbId}/documents/${documentId}`, {
    confirmImpact: true,
    reason,
  });
}

export async function downloadDocumentSource(
  kbId: string,
  documentId: string,
): Promise<ApiDownload> {
  return apiDownload(`/knowledge-bases/${kbId}/documents/${documentId}/download`);
}

export async function fetchDocumentQualitySummary(kbId: string): Promise<DocumentQualitySummaryDTO> {
  return apiGet<DocumentQualitySummaryDTO>(`/knowledge-bases/${kbId}/documents/quality-summary`);
}

export async function runBulkDocumentGovernance(
  kbId: string,
  request: BulkDocumentGovernanceRequest,
): Promise<BulkDocumentGovernanceResponse> {
  return apiPostJson<BulkDocumentGovernanceResponse>(`/knowledge-bases/${kbId}/documents/batch-governance`, request);
}

export async function fetchDocumentVersions(
  kbId: string,
  documentId: string,
): Promise<DocumentVersionDTO[]> {
  return apiGet<DocumentVersionDTO[]>(`/knowledge-bases/${kbId}/documents/${documentId}/versions`);
}

export async function reparseDocument(
  kbId: string,
  documentId: string,
  reason?: string,
): Promise<DocumentUploadResponse> {
  return apiPostJson<DocumentUploadResponse>(
    `/knowledge-bases/${kbId}/documents/${documentId}/reparse`,
    { reason },
  );
}

export async function rechunkDocument(
  kbId: string,
  documentId: string,
  params: { chunkSize: number; chunkOverlap: number },
): Promise<{ job_id: string; chunk_revision_id: string; strategy: string; params: Record<string, unknown> }> {
  return apiPostJson(`/knowledge-bases/${kbId}/documents/${documentId}/rechunk`, {
    strategy: "fixed_size",
    params: {
      chunk_size: params.chunkSize,
      chunk_overlap: params.chunkOverlap,
    },
  });
}

export async function activateDocumentVersion(
  kbId: string,
  documentId: string,
  versionId: string,
  reason?: string,
): Promise<DocumentVersionActivateResponse> {
  return apiPostJson<DocumentVersionActivateResponse>(
    `/knowledge-bases/${kbId}/documents/${documentId}/versions/${versionId}/activate`,
    { confirmImpact: true, reason },
  );
}

export async function fetchChunks(
  kbId: string,
  documentId: string,
  versionId: string,
  pageNo = 1,
  pageSize = 20,
): Promise<ChunkPage> {
  const params = new URLSearchParams({ pageNo: String(pageNo), pageSize: String(pageSize) });
  return apiGet<ChunkPage>(
    `/knowledge-bases/${kbId}/documents/${documentId}/versions/${versionId}/chunks?${params.toString()}`,
  );
}

export async function fetchChunk(kbId: string, chunkId: string): Promise<ChunkDTO> {
  return apiGet<ChunkDTO>(`/knowledge-bases/${kbId}/chunks/${chunkId}`);
}

export async function updateChunkGovernance(
  kbId: string,
  chunkId: string,
  excluded: boolean,
  note?: string | null,
): Promise<ChunkGovernanceResponse> {
  return apiPatchJson<ChunkGovernanceResponse>(`/knowledge-bases/${kbId}/chunks/${chunkId}/governance`, {
    excluded,
    note,
  });
}

export async function fetchIngestJobs(kbId: string, documentId?: string): Promise<IngestJobPage> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: "20" });
  if (documentId) {
    params.set("documentId", documentId);
  }

  return apiGet<IngestJobPage>(`/knowledge-bases/${kbId}/ingest-jobs?${params.toString()}`);
}

export async function fetchIngestJob(kbId: string, jobId: string): Promise<IngestJobDTO> {
  return apiGet<IngestJobDTO>(`/knowledge-bases/${kbId}/ingest-jobs/${jobId}`);
}

export async function retryIngestJob(kbId: string, jobId: string): Promise<IngestJobDTO> {
  return apiPostJson<IngestJobDTO>(`/knowledge-bases/${kbId}/ingest-jobs/${jobId}/retry`, {});
}

export async function cancelIngestJob(kbId: string, jobId: string): Promise<IngestJobDTO> {
  return apiPostJson<IngestJobDTO>(`/knowledge-bases/${kbId}/ingest-jobs/${jobId}/cancel`, {});
}

export async function fetchIndexSyncJobs(kbId: string, documentId?: string): Promise<IndexSyncJobPage> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: "20" });
  if (documentId) {
    params.set("documentId", documentId);
  }

  return apiGet<IndexSyncJobPage>(`/knowledge-bases/${kbId}/index-sync-jobs?${params.toString()}`);
}

export async function rebuildIndexSync(kbId: string, request: IndexSyncRebuildRequest): Promise<IndexSyncJobDTO> {
  return apiPostJson<IndexSyncJobDTO>(`/knowledge-bases/${kbId}/index-sync-jobs/rebuild`, request);
}
