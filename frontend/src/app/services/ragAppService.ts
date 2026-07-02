import { apiDelete, apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import type {
  AppInvocationListParams,
  AppInvocationPage,
  AppInvocationStatsDTO,
  AppConversationDetailDTO,
  AppTrainingReportDTO,
  BatchDeleteRagAppsResponse,
  EmbeddedAppDeploymentDTO,
  RagAppApiKeyCreateRequest,
  RagAppApiKeyCreateResponse,
  RagAppApiKeyDTO,
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

export async function deleteRagApp(appId: string): Promise<void> {
  return apiDelete(`/rag-apps/${appId}`);
}

export async function batchDeleteRagApps(appIds: string[]): Promise<BatchDeleteRagAppsResponse> {
  return apiPostJson<BatchDeleteRagAppsResponse>("/rag-apps/batch-delete", { app_ids: appIds });
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

export async function deleteRagAppApiKey(
  appId: string,
  apiKeyId: string,
): Promise<void> {
  return apiDelete(`/rag-apps/${appId}/api-keys/${apiKeyId}`);
}

export async function listRagAppEmbeddedDeployments(appId: string): Promise<EmbeddedAppDeploymentDTO[]> {
  return apiGet<EmbeddedAppDeploymentDTO[]>(`/rag-apps/${appId}/embedded-deployments`);
}

export async function startRagAppEmbeddedDeployment(
  appId: string,
  deploymentId: string,
): Promise<EmbeddedAppDeploymentDTO> {
  return apiPostJson<EmbeddedAppDeploymentDTO>(`/rag-apps/${appId}/embedded-deployments/${deploymentId}/start`, {});
}

export async function stopRagAppEmbeddedDeployment(
  appId: string,
  deploymentId: string,
): Promise<EmbeddedAppDeploymentDTO> {
  return apiPostJson<EmbeddedAppDeploymentDTO>(`/rag-apps/${appId}/embedded-deployments/${deploymentId}/stop`, {});
}

export async function restartRagAppEmbeddedDeployment(
  appId: string,
  deploymentId: string,
): Promise<EmbeddedAppDeploymentDTO> {
  return apiPostJson<EmbeddedAppDeploymentDTO>(`/rag-apps/${appId}/embedded-deployments/${deploymentId}/restart`, {});
}

export async function checkRagAppEmbeddedDeploymentHealth(
  appId: string,
  deploymentId: string,
): Promise<EmbeddedAppDeploymentDTO> {
  return apiPostJson<EmbeddedAppDeploymentDTO>(`/rag-apps/${appId}/embedded-deployments/${deploymentId}/health-check`, {});
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

export async function getRagAppTrainingReport(appId: string): Promise<AppTrainingReportDTO> {
  return apiGet<AppTrainingReportDTO>(`/rag-apps/${appId}/training-report`);
}

export async function getRagAppConversationDetail(
  appId: string,
  conversationId: string,
): Promise<AppConversationDetailDTO> {
  return apiGet<AppConversationDetailDTO>(`/rag-apps/${appId}/conversations/${conversationId}`);
}
