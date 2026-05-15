export interface TokenUsageSummaryDTO {
  stepKey: string;
  totalCalls: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalTokens: number;
  avgInputTokens: number | null;
  avgOutputTokens: number | null;
  avgLatencyMs: number | null;
}

export interface TokenUsageResponse {
  kbId: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalTokens: number;
  runCount: number;
  steps: TokenUsageSummaryDTO[];
}

export interface CostSummaryResponse {
  kbId: string;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalTokens: number;
  runCount: number;
  estimatedCostUsd: number | null;
  pricingNote: string;
}
