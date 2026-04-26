import type { PageResponse } from "./knowledgeBase";

export type QARunStatus = "draft" | "queued" | "running" | "success" | "partial" | "failed" | "cancelled";

export interface QARunCreateResponse {
  runId: string;
  status: QARunStatus;
  kbId: string;
  configRevisionId: string;
  query: string;
  createdAt: string;
  statusUrl: string;
  detailUrl: string;
}

export interface QARunStatusDTO {
  runId: string;
  status: QARunStatus;
  currentStage: string;
  progress: number;
  stageMessage: string;
  startedAt: string | null;
  finishedAt: string | null;
  detailReady: boolean;
}

export interface QARunTraceStepDTO {
  stepKey: string;
  status: string;
  inputSummary: Record<string, unknown>;
  outputSummary: Record<string, unknown>;
  metrics: Record<string, unknown>;
  errorCode: string | null;
  errorMessage: string | null;
}

export interface QARunCandidateDTO {
  candidateId: string;
  chunkId: string | null;
  sourceType: string;
  rawScore: number | null;
  rerankScore: number | null;
  rankNo: number | null;
  isAuthorized: boolean;
  dropReason: string | null;
  metadata: Record<string, unknown>;
}

export interface QARunEvidenceDTO {
  evidenceId: string;
  chunkId: string;
  candidateId: string | null;
  contentSnapshot: string | null;
  sourceSnapshot: Record<string, unknown>;
  redactionStatus: string;
}

export interface QARunCitationDTO {
  citationId: string;
  evidenceId: string;
  label: string | null;
  locationSnapshot: Record<string, unknown>;
}

export interface QARunDetailDTO {
  runId: string;
  status: QARunStatus;
  kbId: string;
  configRevisionId: string;
  query: string;
  rewrittenQuery: string | null;
  answer: string | null;
  retrievalDiagnostics: Record<string, unknown>;
  candidates: QARunCandidateDTO[];
  evidence: QARunEvidenceDTO[];
  citations: QARunCitationDTO[];
  trace: QARunTraceStepDTO[];
  metrics: Record<string, unknown>;
  createdAt: string;
}

export interface QARunListItemDTO {
  runId: string;
  kbId: string;
  configRevisionId: string;
  query: string;
  status: QARunStatus;
  answer: string | null;
  hasOverride: boolean;
  feedbackStatus: string;
  createdBy: string | null;
  createdAt: string;
  latencyMs: number | null;
}

export type QARunPage = PageResponse<QARunListItemDTO>;
