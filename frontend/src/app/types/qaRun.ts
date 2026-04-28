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
  overrideSnapshot: Record<string, unknown>;
  feedbackStatus: string;
  feedbackNote: string | null;
  failureType: string | null;
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
  feedbackNote: string | null;
  failureType: string | null;
  createdBy: string | null;
  createdAt: string;
  latencyMs: number | null;
}

export interface QARunFeedbackResponse {
  runId: string;
  feedbackStatus: string;
  failureType: string | null;
  feedbackNote: string | null;
  updatedAt: string;
}

export interface QARunReplayContextDTO {
  sourceRunId: string;
  query: string;
  configRevisionId: string;
  overrideParams: Record<string, unknown>;
  suggestedMode: "replay" | "copyAsNew";
  warnings: string[];
}

export interface EvaluationSampleDTO {
  sampleId: string;
  kbId: string;
  sourceRunId: string | null;
  query: string;
  expectedAnswer: string | null;
  expectedEvidence: Record<string, unknown>;
  status: string;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export type QARunPage = PageResponse<QARunListItemDTO>;
export type EvaluationSamplePage = PageResponse<EvaluationSampleDTO>;
