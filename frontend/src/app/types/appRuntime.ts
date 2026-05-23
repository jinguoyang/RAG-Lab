export type AppRuntimeResponseMode = "blocking" | "streaming";
export type AppRuntimeFeedbackStatus = string;

export interface AppRuntimeChatRequest {
  query: string;
  conversationId?: string | null;
  endUserId?: string | null;
  inputs?: Record<string, unknown> | null;
  responseMode?: AppRuntimeResponseMode;
}

export interface AppRuntimeCitationDTO {
  citationId: string;
  evidenceId: string;
  label: string | null;
  locationSnapshot: Record<string, unknown>;
}

export interface AppRuntimeChatResponse {
  answer: string;
  conversationId: string;
  messageId: string;
  runId: string;
  citations: AppRuntimeCitationDTO[];
  usage: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface AppRuntimeEmbedTokenRequest {
  ttlSeconds?: number;
  allowedOrigin?: string | null;
  endUserId?: string | null;
}

export interface AppRuntimeEmbedTokenResponse {
  embedToken: string;
  appId: string;
  expiresAt: string;
}

export interface AppRuntimeRetrieveRequest {
  query: string;
  topK?: number;
}

export interface AppRuntimeRetrievedEvidenceDTO {
  evidenceId: string;
  chunkId: string;
  label: string | null;
  summary: string;
  locationSnapshot: Record<string, unknown>;
}

export interface AppRuntimeRetrieveResponse {
  appId: string;
  kbId: string;
  evidences: AppRuntimeRetrievedEvidenceDTO[];
  metadata: Record<string, unknown>;
}

export interface AppRuntimeFeedbackRequest {
  feedbackStatus: AppRuntimeFeedbackStatus;
  failureType?: string | null;
  feedbackNote?: string | null;
  createEvaluationSample?: boolean;
  expectedAnswer?: string | null;
  expectedEvidence?: Record<string, unknown> | null;
}

export interface AppRuntimeFeedbackResponse {
  messageId: string;
  runId: string;
  feedbackStatus: string;
  failureType: string | null;
  feedbackNote: string | null;
  evaluationSampleId: string | null;
  createdAt: string;
}

export interface AppRuntimeSseEvent {
  event: string;
  data: unknown;
}
