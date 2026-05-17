export type AppRuntimeResponseMode = "blocking" | "streaming";
export type AppRuntimeFeedbackStatus =
  | "correct"
  | "partiallyCorrect"
  | "partially_correct"
  | "wrong"
  | "citationError"
  | "citation_error"
  | "noEvidence"
  | "no_evidence";

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
