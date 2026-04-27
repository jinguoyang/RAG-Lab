import { apiGet, apiPostForm } from "./apiClient";
import type {
  DocumentDetailDTO,
  DocumentPage,
  DocumentUploadResponse,
  DocumentVersionDTO,
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

export async function uploadDocument(
  kbId: string,
  file: File,
  name: string,
  securityLevel: string,
): Promise<DocumentUploadResponse> {
  const body = new FormData();
  body.set("file", file);
  if (name.trim()) {
    body.set("name", name.trim());
  }
  body.set("securityLevel", securityLevel);

  return apiPostForm<DocumentUploadResponse>(`/knowledge-bases/${kbId}/documents`, body);
}

export async function fetchDocumentDetail(
  kbId: string,
  documentId: string,
): Promise<DocumentDetailDTO> {
  return apiGet<DocumentDetailDTO>(`/knowledge-bases/${kbId}/documents/${documentId}`);
}

export async function fetchDocumentVersions(
  kbId: string,
  documentId: string,
): Promise<DocumentVersionDTO[]> {
  return apiGet<DocumentVersionDTO[]>(`/knowledge-bases/${kbId}/documents/${documentId}/versions`);
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
