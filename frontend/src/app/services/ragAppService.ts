import { apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import type {
  AppInvocationListParams,
  AppInvocationPage,
  AppInvocationStatsDTO,
  AppConversationDetailDTO,
  RagAppApiKeyCreateRequest,
  RagAppApiKeyCreateResponse,
  RagAppApiKeyDTO,
  RagAppApiKeyRevokeResponse,
  RagAppCreateRequest,
  RagAppDTO,
  RagAppListParams,
  RagAppPage,
  RagAppUpdateRequest,
} from "../types/ragApp";

function buildListParams(params: Record<string, string | number | undefined | null>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    searchParams.set(key, String(value));
  }
  return searchParams.toString();
}

export async function listRagApps({
  pageNo = 1,
  pageSize = 20,
  keyword,
  kbId,
  status,
}: RagAppListParams = {}): Promise<RagAppPage> {
  const query = buildListParams({ pageNo, pageSize, keyword: keyword?.trim(), kbId, status });
  return apiGet<RagAppPage>(`/rag-apps?${query}`);
}

export async function getRagApp(appId: string): Promise<RagAppDTO> {
  return apiGet<RagAppDTO>(`/rag-apps/${appId}`);
}

export async function createRagApp(payload: RagAppCreateRequest): Promise<RagAppDTO> {
  return apiPostJson<RagAppDTO>("/rag-apps", payload);
}

export async function updateRagApp(appId: string, payload: RagAppUpdateRequest): Promise<RagAppDTO> {
  return apiPatchJson<RagAppDTO>(`/rag-apps/${appId}`, payload);
}

export async function listRagAppApiKeys(appId: string): Promise<RagAppApiKeyDTO[]> {
  return apiGet<RagAppApiKeyDTO[]>(`/rag-apps/${appId}/api-keys`);
}

export async function createRagAppApiKey(
  appId: string,
  payload: RagAppApiKeyCreateRequest = {},
): Promise<RagAppApiKeyCreateResponse> {
  return apiPostJson<RagAppApiKeyCreateResponse>(`/rag-apps/${appId}/api-keys`, payload);
}

export async function revokeRagAppApiKey(
  appId: string,
  apiKeyId: string,
): Promise<RagAppApiKeyRevokeResponse> {
  return apiPostJson<RagAppApiKeyRevokeResponse>(`/rag-apps/${appId}/api-keys/${apiKeyId}/revoke`, {});
}

export async function listRagAppInvocations(
  appId: string,
  { pageNo = 1, pageSize = 20, status }: AppInvocationListParams = {},
): Promise<AppInvocationPage> {
  const query = buildListParams({ pageNo, pageSize, status });
  return apiGet<AppInvocationPage>(`/rag-apps/${appId}/invocations?${query}`);
}

export async function getRagAppInvocationStats(appId: string): Promise<AppInvocationStatsDTO> {
  return apiGet<AppInvocationStatsDTO>(`/rag-apps/${appId}/stats`);
}

export async function getRagAppConversationDetail(
  appId: string,
  conversationId: string,
): Promise<AppConversationDetailDTO> {
  return apiGet<AppConversationDetailDTO>(`/rag-apps/${appId}/conversations/${conversationId}`);
}
