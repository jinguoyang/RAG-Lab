import { apiGet, apiPostJson } from "./apiClient";
import type { QARunCreateResponse, QARunDetailDTO, QARunPage, QARunStatusDTO } from "../types/qaRun";

export async function createQARun(
  kbId: string,
  query: string,
  overrideParams?: Record<string, unknown>,
  sourceRunId?: string,
): Promise<QARunCreateResponse> {
  return apiPostJson<QARunCreateResponse>(`/knowledge-bases/${kbId}/qa-runs`, {
    query,
    overrideParams,
    sourceRunId,
  });
}

export async function fetchQARunStatus(kbId: string, runId: string): Promise<QARunStatusDTO> {
  return apiGet<QARunStatusDTO>(`/knowledge-bases/${kbId}/qa-runs/${runId}/status`);
}

export async function fetchQARunDetail(kbId: string, runId: string): Promise<QARunDetailDTO> {
  return apiGet<QARunDetailDTO>(`/knowledge-bases/${kbId}/qa-runs/${runId}`);
}

export async function fetchQARuns(kbId: string, keyword?: string): Promise<QARunPage> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: "50" });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }

  return apiGet<QARunPage>(`/knowledge-bases/${kbId}/qa-runs?${params.toString()}`);
}
