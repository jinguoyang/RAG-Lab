import { apiDelete, apiDownload, apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import { API_BASE_URL } from "./apiClient";
import type { ApiDownload } from "./apiClient";
import type {
  BatchActionResponse,
  DeletionImpactAnalysis,
  LibraryDocumentDTO,
  LibraryDocumentDetailDTO,
  LibraryDocumentPage,
  LibraryDocumentUploadResponse,
  LibraryDocumentUsageResponse,
  LibraryDocumentVersionDTO,
  LibraryDTO,
  LibraryFullTextResponse,
  LibraryMemberDTO,
  LibraryPageResponse,
  LibraryParseJobDTO,
  LibraryParsedChunksResponse,
  LibraryStatsResponse,
  LibraryTextPreviewResponse,
  LibraryVersionActivateResponse,
  LibraryVersionUploadResponse,
  UploadProgress,
  UploadWithProgressResult,
} from "../types/library";

interface FetchLibraryDocumentsParams {
  keyword?: string;
  pageNo?: number;
  pageSize?: number;
  status?: string;
  libraryId?: string;
}

export async function fetchLibraryDocuments({
  keyword,
  pageNo = 1,
  pageSize = 20,
  status,
  libraryId,
}: FetchLibraryDocumentsParams = {}): Promise<LibraryDocumentPage> {
  const params = new URLSearchParams({ pageNo: String(pageNo), pageSize: String(pageSize) });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }
  if (status) {
    params.set("status", status);
  }
  if (libraryId) {
    params.set("library_id", libraryId);
  }

  return apiGet<LibraryDocumentPage>(`/library/documents?${params.toString()}`);
}

export function uploadLibraryDocumentWithProgress(
  file: File,
  name: string,
  libraryId?: string,
): UploadWithProgressResult {
  const body = new FormData();
  body.set("file", file);
  if (name.trim()) {
    body.set("name", name.trim());
  }
  if (libraryId) {
    body.set("libraryId", libraryId);
  }

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
  libraryId?: string,
): Promise<LibraryDocumentUploadResponse> {
  return uploadLibraryDocumentWithProgress(file, name, libraryId).promise;
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

// --- 版本管理 API ---

export async function fetchLibraryVersions(
  documentId: string,
): Promise<LibraryDocumentVersionDTO[]> {
  return apiGet(`/library/documents/${documentId}/versions`);
}

export function uploadLibraryVersionWithProgress(
  documentId: string,
  file: File,
): UploadWithProgressResult {
  const body = new FormData();
  body.set("file", file);

  const xhr = new XMLHttpRequest();
  let progressCallback: ((progress: UploadProgress) => void) | null = null;

  const promise = new Promise<LibraryVersionUploadResponse>((resolve, reject) => {
    xhr.open("POST", `${API_BASE_URL}/library/documents/${documentId}/versions`);

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
        resolve(JSON.parse(xhr.responseText) as LibraryVersionUploadResponse);
      } else {
        let message = `上传失败: ${xhr.status}`;
        try {
          const errBody = JSON.parse(xhr.responseText);
          message = errBody.detail || errBody.message || message;
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

export async function activateLibraryVersion(
  documentId: string,
  versionId: string,
  confirmImpact: boolean = true,
): Promise<LibraryVersionActivateResponse> {
  return apiPostJson(`/library/documents/${documentId}/versions/${versionId}/activate`, { confirmImpact });
}

export async function deleteLibraryVersion(
  documentId: string,
  versionId: string,
): Promise<void> {
  return apiDelete(`/library/documents/${documentId}/versions/${versionId}`);
}

export async function getDeletionImpact(
  documentId: string,
  versionId: string,
): Promise<DeletionImpactAnalysis> {
  return apiGet<DeletionImpactAnalysis>(`/library/documents/${documentId}/versions/${versionId}/deletion-impact`);
}

export async function switchBindingVersion(
  kbId: string,
  bindingId: string,
  libraryVersionId: string,
): Promise<{ bindingId: string; status: string }> {
  return apiPostJson(`/knowledge-bases/${kbId}/library-bindings/${bindingId}/switch-version`, { libraryVersionId });
}

// --- 文档库管理 API ---

export async function fetchLibraries(params: {
  pageNo?: number;
  pageSize?: number;
  keyword?: string;
} = {}): Promise<LibraryPageResponse> {
  const searchParams = new URLSearchParams({
    page_no: String(params.pageNo ?? 1),
    page_size: String(params.pageSize ?? 20),
  });
  if (params.keyword?.trim()) {
    searchParams.set("keyword", params.keyword.trim());
  }
  return apiGet<LibraryPageResponse>(`/library?${searchParams.toString()}`);
}

export async function createLibrary(body: {
  name: string;
  description?: string;
  visibility: "public" | "personal" | "partial";
}): Promise<LibraryDTO> {
  return apiPostJson<LibraryDTO>("/library", body);
}

export async function fetchLibraryDetail(libraryId: string): Promise<LibraryDTO> {
  return apiGet<LibraryDTO>(`/library/${libraryId}`);
}

export async function updateLibrary(
  libraryId: string,
  body: { name?: string; description?: string; visibility?: string },
): Promise<LibraryDTO> {
  return apiPatchJson<LibraryDTO>(`/library/${libraryId}`, body);
}

export async function deleteLibrary(libraryId: string): Promise<void> {
  return apiDelete(`/library/${libraryId}`);
}

export async function fetchLibraryMembers(libraryId: string): Promise<LibraryMemberDTO[]> {
  return apiGet<LibraryMemberDTO[]>(`/library/${libraryId}/members`);
}

export async function addLibraryMember(
  libraryId: string,
  body: { subjectType: "user" | "group"; subjectId: string; permissionLevel: "read_only" | "document_manage" },
): Promise<LibraryMemberDTO> {
  return apiPostJson<LibraryMemberDTO>(`/library/${libraryId}/members`, body);
}

export async function updateLibraryMember(
  libraryId: string,
  bindingId: string,
  body: { permissionLevel: "read_only" | "document_manage" },
): Promise<LibraryMemberDTO> {
  return apiPatchJson<LibraryMemberDTO>(`/library/${libraryId}/members/${bindingId}`, body);
}

export async function removeLibraryMember(libraryId: string, bindingId: string): Promise<void> {
  return apiDelete(`/library/${libraryId}/members/${bindingId}`);
}
