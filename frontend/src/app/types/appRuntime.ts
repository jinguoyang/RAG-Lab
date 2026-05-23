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

export type AppRuntimeStructuredAction = "training_explain" | "training_quiz_generate";

export interface AppRuntimeStructuredRunRequest {
  action: AppRuntimeStructuredAction;
  topic: string;
  conversationId?: string | null;
  endUserId?: string | null;
  difficulty?: string | null;
  questionCount?: number | null;
  inputs?: Record<string, unknown> | null;
}

export interface AppRuntimeTrainingQuestionDTO {
  questionId: string;
  type: string;
  stem: string;
  options: string[];
  correctAnswer?: string;
  explanation?: string;
}

export interface AppRuntimeStructuredRunResponse {
  appId: string;
  conversationId: string;
  messageId: string;
  runId: string;
  action: AppRuntimeStructuredAction;
  output: {
    explanation?: {
      topic: string;
      summary: string;
      keyPoints: string[];
    };
    quiz?: {
      topic: string;
      difficulty: string;
      questionCount: number;
      questions: AppRuntimeTrainingQuestionDTO[];
    };
  };
  metadata: Record<string, unknown>;
}

export interface AppRuntimeTrainingAnswerDTO {
  questionId: string;
  answer: string;
}

export interface AppRuntimeTrainingQuizSubmissionRequest {
  conversationId: string;
  quizMessageId: string;
  answers: AppRuntimeTrainingAnswerDTO[];
}

export interface AppRuntimeTrainingQuestionResultDTO {
  questionId: string;
  answer: string;
  correctAnswer: string;
  isCorrect: boolean;
  explanation: string;
}

export interface AppRuntimeTrainingQuizSubmissionResponse {
  conversationId: string;
  messageId: string;
  quizMessageId: string;
  runId: string;
  score: number;
  passed: boolean;
  passingScore: number;
  results: AppRuntimeTrainingQuestionResultDTO[];
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
