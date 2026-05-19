import { apiDelete, apiDownload, apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import { API_BASE_URL } from "./apiClient";
import type { ApiDownload } from "./apiClient";
import type {
  BatchActionResponse,
  LibraryDocumentDTO,
  LibraryDocumentDetailDTO,
  LibraryDocumentPage,
  LibraryDocumentUploadResponse,
  LibraryDocumentUsageResponse,
  LibraryFullTextResponse,
  LibraryParseJobDTO,
  LibraryParsedChunksResponse,
  LibraryStatsResponse,
  LibraryTextPreviewResponse,
  UploadProgress,
  UploadWithProgressResult,
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

export function uploadLibraryDocumentWithProgress(
  file: File,
  name: string,
  securityLevel: string,
): UploadWithProgressResult {
  const body = new FormData();
  body.set("file", file);
  if (name.trim()) {
    body.set("name", name.trim());
  }
  body.set("securityLevel", securityLevel);

  const xhr = new XMLHttpRequest();
  let progressCallback: ((progress: UploadProgress) => void) | null = null;

  const promise = new Promise<LibraryDocumentUploadResponse>((resolve, reject) => {
    xhr.open("POST", `${API_BASE_URL}/library/documents`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && progressCallback) {
        progressCallback({
          loaded: event.loaded,
          total: event.total,
          percent: Math.round((event.loaded / event.total) * 100),
        });
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as LibraryDocumentUploadResponse);
      } else {
        let message = `上传失败: ${xhr.status}`;
        try {
          const body = JSON.parse(xhr.responseText);
          message = body.detail || body.message || message;
        } catch {}
        reject(new Error(message));
      }
    };

    xhr.onerror = () => reject(new Error("网络错误，请检查连接"));
    xhr.onabort = () => reject(new Error("上传已取消"));

    xhr.send(body);
  });

  return {
    promise,
    cancel: () => xhr.abort(),
    onProgress: (callback) => { progressCallback = callback; },
  };
}

// 保留原有函数作为向后兼容
export async function uploadLibraryDocument(
  file: File,
  name: string,
  securityLevel: string,
): Promise<LibraryDocumentUploadResponse> {
  return uploadLibraryDocumentWithProgress(file, name, securityLevel).promise;
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

export async function fetchDocumentText(
  documentId: string,
  mode: "preview" | "full" | "chunks" = "preview",
): Promise<LibraryTextPreviewResponse | LibraryFullTextResponse | LibraryParsedChunksResponse> {
  return apiGet(`/library/documents/${documentId}/text?mode=${mode}`);
}

export async function fetchDocumentUsage(
  documentId: string,
): Promise<LibraryDocumentUsageResponse> {
  return apiGet(`/library/documents/${documentId}/usage`);
}

export async function deleteLibraryDocument(
  documentId: string,
): Promise<void> {
  return apiDelete(`/library/documents/${documentId}`);
}

export async function retryLibraryParse(
  documentId: string,
): Promise<{ jobId: string; status: string }> {
  return apiPostJson(`/library/documents/${documentId}/parse-retry`, {});
}

export async function bindDocumentsToKB(
  kbId: string,
  documentIds: string[],
): Promise<{ bindings: Array<{ bindingId: string; documentId: string; status: string }> }> {
  return apiPostJson(`/knowledge-bases/${kbId}/library-bindings`, { documentIds });
}

export async function listKBBindings(
  kbId: string,
): Promise<Array<{ bindingId: string; documentId: string; documentName: string; status: string; chunkCount: number }>> {
  return apiGet(`/knowledge-bases/${kbId}/library-bindings`);
}

export async function unbindDocument(
  kbId: string,
  bindingId: string,
): Promise<void> {
  return apiDelete(`/knowledge-bases/${kbId}/library-bindings/${bindingId}`);
}

export async function retryBinding(
  kbId: string,
  bindingId: string,
): Promise<{ bindingId: string; status: string }> {
  return apiPostJson(`/knowledge-bases/${kbId}/library-bindings/${bindingId}/retry`, {});
}

export async function fetchLibraryStats(): Promise<LibraryStatsResponse> {
  return apiGet<LibraryStatsResponse>("/library/documents/stats");
}

export async function batchAction(
  documentIds: string[],
  action: "delete" | "reparse" | "disable",
): Promise<BatchActionResponse> {
  return apiPostJson<BatchActionResponse>("/library/documents/batch-actions", {
    documentIds,
    action,
  });
}
