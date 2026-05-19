import { apiDownload, apiGet, apiPatchJson, apiPostForm } from "./apiClient";
import type { ApiDownload } from "./apiClient";
import type {
  LibraryDocumentDTO,
  LibraryDocumentDetailDTO,
  LibraryDocumentPage,
  LibraryDocumentUploadResponse,
  LibraryParseJobDTO,
} from "../types/library";

interface FetchLibraryDocumentsParams {
  keyword?: string;
  pageNo?: number;
  pageSize?: number;
  status?: string;
}

export async function fetchLibraryDocuments({
  keyword,
  pageNo = 1,
  pageSize = 20,
  status,
}: FetchLibraryDocumentsParams = {}): Promise<LibraryDocumentPage> {
  const params = new URLSearchParams({ pageNo: String(pageNo), pageSize: String(pageSize) });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }
  if (status) {
    params.set("status", status);
  }

  return apiGet<LibraryDocumentPage>(`/library/documents?${params.toString()}`);
}

export async function uploadLibraryDocument(
  file: File,
  name: string,
  securityLevel: string,
): Promise<LibraryDocumentUploadResponse> {
  const body = new FormData();
  body.set("file", file);
  if (name.trim()) {
    body.set("name", name.trim());
  }
  body.set("securityLevel", securityLevel);

  return apiPostForm<LibraryDocumentUploadResponse>("/library/documents", body);
}

export async function fetchLibraryDocumentDetail(
  documentId: string,
): Promise<LibraryDocumentDetailDTO> {
  return apiGet<LibraryDocumentDetailDTO>(`/library/documents/${documentId}`);
}

export async function downloadLibraryDocument(
  documentId: string,
): Promise<ApiDownload> {
  return apiDownload(`/library/documents/${documentId}/download`);
}

export async function updateLibraryDocument(
  documentId: string,
  body: { name?: string; status?: string },
): Promise<LibraryDocumentDTO> {
  return apiPatchJson<LibraryDocumentDTO>(`/library/documents/${documentId}`, body);
}

export async function fetchLibraryParseJobs(
  documentId: string,
): Promise<LibraryParseJobDTO[]> {
  return apiGet<LibraryParseJobDTO[]>(`/library/documents/${documentId}/parse-jobs`);
}
