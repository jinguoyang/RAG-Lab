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
  // Sprint 42: traceability metadata
  sourceStatus?: string;  // "available" | "source_deleted"
  documentName?: string | null;
  versionNo?: number | null;
  chunkRevisionId?: string | null;
  /** 兼容旧运行记录，后端新字段为 chunkRevisionId。 */
  bindingRevisionId?: string | null;
  parseRevisionId?: string | null;
  documentVersionId?: string | null;
  pageNo?: number | null;
  sectionPath?: string | null;
  chunkStatus?: string | null;
}

export interface QARunCitationDTO {
  citationId: string;
  evidenceId: string;
  label: string | null;
  locationSnapshot: Record<string, unknown>;
}

export interface QARunAnswerBlockDTO {
  text: string;
  citationEvidenceIds: string[];
}

export interface QARunDetailDTO {
  runId: string;
  sourceRunId: string | null;
  status: QARunStatus;
  kbId: string;
  configRevisionId: string;
  query: string;
  rewrittenQuery: string | null;
  answer: string | null;
  answerBlocks?: QARunAnswerBlockDTO[];
  retrievalDiagnostics: Record<string, unknown>;
  overrideSnapshot: Record<string, unknown>;
  pipelineSnapshot: Record<string, unknown>;
  nodeParamSnapshot: Record<string, unknown>;
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
  sourceRunId: string | null;
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
  createdByName: string | null;
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
  retrievalChannels: string[];
  retrievalTopK: Record<string, number>;
  temperature: number;
  maxContextTokens: number;
  graphSnapshotId: string | null;
  providerDiagnostics: Record<string, unknown>;
  suggestedMode: "replay" | "copyAsNew";
  warnings: string[];
}

export interface QARunCompareSummaryDTO {
  runId: string;
  status: QARunStatus;
  configRevisionId: string;
  answer: string | null;
  evidenceCount: number;
  citationCount: number;
  latencyMs: number | null;
  createdAt: string;
}

export interface QARunCompareEvidenceDeltaDTO {
  added: string[];
  removed: string[];
  shared: string[];
}

export interface QARunCompareTraceDeltaDTO {
  stepKey: string;
  sourceStatus: string | null;
  targetStatus: string | null;
  sourceLatencyMs: number | null;
  targetLatencyMs: number | null;
}

export interface QARunCompareDTO {
  source: QARunCompareSummaryDTO;
  target: QARunCompareSummaryDTO;
  answerChanged: boolean;
  evidenceDelta: QARunCompareEvidenceDeltaDTO;
  citationDelta: QARunCompareEvidenceDeltaDTO;
  traceDelta: QARunCompareTraceDeltaDTO[];
  configDiff: ConfigRevisionDiffItemDTO[];
  warnings: string[];
}

export interface QARunCommentDTO {
  commentId: string;
  authorId: string;
  content: string;
  createdAt: string;
}

export interface QARunCollaborationDTO {
  runId: string;
  sharedWithSubjectKeys: string[];
  ownerId: string | null;
  handlingStatus: string;
  comments: QARunCommentDTO[];
  updatedAt: string | null;
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

export interface EvaluationRunDTO {
  evaluationRunId: string;
  kbId: string;
  configRevisionId: string;
  status: string;
  totalSamples: number;
  passedSamples: number;
  failedSamples: number;
  cancelledSamples: number;
  passRate: number;
  errorSummary: Record<string, number>;
  remark: string | null;
  createdBy: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface EvaluationResultDTO {
  evaluationResultId: string;
  evaluationRunId: string;
  sampleId: string;
  sourceRunId: string | null;
  actualRunId: string | null;
  status: "passed" | "failed" | "cancelled";
  query: string;
  expectedAnswer: string | null;
  actualAnswer: string | null;
  failureReason: string | null;
  metrics: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface EvaluationRunDetailDTO {
  run: EvaluationRunDTO;
  results: EvaluationResultDTO[];
}

export interface EvaluationRunExportResponse {
  evaluationRunId: string;
  format: "csv" | "markdown";
  fileName: string;
  content: string;
}

export interface ConfigRevisionDiffItemDTO {
  path: string;
  before: unknown;
  after: unknown;
}

export interface EvaluationRunConfigDiffDTO {
  evaluationRunId: string;
  fromConfigRevisionId: string;
  toConfigRevisionId: string;
  diffItems: ConfigRevisionDiffItemDTO[];
}

export interface EvaluationOptimizationRecommendationDTO {
  title: string;
  paramPath: string;
  before: unknown;
  after: unknown;
  expectedImpact: string;
  risk: string;
  relatedSampleIds: string[];
}

export interface EvaluationOptimizationDraftResponse {
  evaluationRunId: string;
  configRevisionId: string;
  remark: string;
  recommendations: EvaluationOptimizationRecommendationDTO[];
}

export type QARunPage = PageResponse<QARunListItemDTO>;
export type EvaluationSamplePage = PageResponse<EvaluationSampleDTO>;
export type EvaluationRunPage = PageResponse<EvaluationRunDTO>;
