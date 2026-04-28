import { apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import type {
  EvaluationSampleDTO,
  EvaluationSamplePage,
  QARunCreateResponse,
  QARunDetailDTO,
  QARunFeedbackResponse,
  QARunPage,
  QARunReplayContextDTO,
  QARunStatusDTO,
} from "../types/qaRun";

export async function createQARun(
  kbId: string,
  query: string,
  overrideParams?: Record<string, unknown>,
  sourceRunId?: string,
  configRevisionId?: string,
): Promise<QARunCreateResponse> {
  return apiPostJson<QARunCreateResponse>(`/knowledge-bases/${kbId}/qa-runs`, {
    query,
    configRevisionId,
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

export async function fetchQARuns(
  kbId: string,
  keyword?: string,
  filters: { status?: string; feedbackStatus?: string } = {},
): Promise<QARunPage> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: "50" });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.feedbackStatus) {
    params.set("feedbackStatus", filters.feedbackStatus);
  }

  return apiGet<QARunPage>(`/knowledge-bases/${kbId}/qa-runs?${params.toString()}`);
}

export async function updateQARunFeedback(
  kbId: string,
  runId: string,
  feedbackStatus: string,
  failureType?: string,
  feedbackNote?: string,
): Promise<QARunFeedbackResponse> {
  return apiPatchJson<QARunFeedbackResponse>(`/knowledge-bases/${kbId}/qa-runs/${runId}/feedback`, {
    feedbackStatus,
    failureType,
    feedbackNote,
  });
}

export async function fetchQARunReplayContext(
  kbId: string,
  runId: string,
): Promise<QARunReplayContextDTO> {
  return apiGet<QARunReplayContextDTO>(`/knowledge-bases/${kbId}/qa-runs/${runId}/replay-context`);
}

export async function createConfigDraftFromQARun(kbId: string, runId: string): Promise<unknown> {
  return apiPostJson<unknown>(`/knowledge-bases/${kbId}/qa-runs/${runId}/config-revision-draft`, {});
}

export async function createEvaluationSampleFromRun(
  kbId: string,
  runId: string,
  expectedAnswer?: string | null,
): Promise<EvaluationSampleDTO> {
  return apiPostJson<EvaluationSampleDTO>(`/knowledge-bases/${kbId}/qa-runs/${runId}/evaluation-samples`, {
    expectedAnswer,
  });
}

export async function fetchEvaluationSamples(kbId: string): Promise<EvaluationSamplePage> {
  return apiGet<EvaluationSamplePage>(`/knowledge-bases/${kbId}/qa-runs/evaluation-samples?pageNo=1&pageSize=50`);
}
