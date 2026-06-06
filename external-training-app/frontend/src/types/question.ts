export interface TrainingQuestion {
  questionId: string;
  planId: string;
  appId: string;
  documentId?: string | null;
  questionType: string;
  category: string;
  content: string;
  options?: QuestionOption[] | null;
  correctAnswer?: string | null;
  explanation?: string | null;
  rubric?: Record<string, unknown> | null;
  evidenceChunkIds: string[];
  status: string;
  createdAt: string;
  updatedAt?: string | null;
}

export interface QuestionOption {
  label?: string;
  text?: string;
  value?: string;
  [key: string]: unknown;
}

export interface QuestionDraftRequest {
  planId: string;
  jobTitle: string;
  abilityGroups: string[];
  count?: number | null;
  documentIds: string[];
}

export interface QuestionReviewRequest {
  decision: "approved" | "rejected";
  notes: string;
}

export interface QuestionUpdateRequest {
  content?: string;
  options?: QuestionOption[];
  correctAnswer?: string;
  explanation?: string;
  rubric?: Record<string, unknown>;
  evidenceChunkIds?: string[];
}
