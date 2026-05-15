import { apiGet } from "./apiClient";
import type { CostSummaryResponse, TokenUsageResponse } from "../types/observability";

export async function fetchTokenUsage(kbId: string): Promise<TokenUsageResponse> {
  return apiGet<TokenUsageResponse>(`/knowledge-bases/${kbId}/observability/token-usage`);
}

export async function fetchCostSummary(kbId: string): Promise<CostSummaryResponse> {
  return apiGet<CostSummaryResponse>(`/knowledge-bases/${kbId}/observability/cost-summary`);
}
