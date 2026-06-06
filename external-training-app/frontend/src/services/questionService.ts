import { apiGet, apiPatch, apiPost } from "./apiClient";
import type {
  QuestionDraftRequest,
  QuestionReviewRequest,
  QuestionUpdateRequest,
  TrainingQuestion,
} from "../types/question";

export function listQuestions(planId?: string): Promise<TrainingQuestion[]> {
  const query = planId ? `?planId=${encodeURIComponent(planId)}` : "";
  return apiGet(`/training/questions${query}`);
}

export function generateQuestionDrafts(data: QuestionDraftRequest): Promise<TrainingQuestion[]> {
  return apiPost("/training/questions/drafts", data);
}

export function reviewQuestion(
  questionId: string,
  data: QuestionReviewRequest
): Promise<{ questionId: string; status: string }> {
  return apiPost(`/training/questions/${questionId}/review`, data);
}

export function updateQuestion(
  questionId: string,
  data: QuestionUpdateRequest
): Promise<{ questionId: string; status: string }> {
  return apiPatch(`/training/questions/${questionId}`, data);
}

export function publishQuestion(
  questionId: string
): Promise<{ questionId: string; status: string }> {
  return apiPost(`/training/questions/${questionId}/publish`, {});
}

export function createQuestion(data: {
  planId: string;
  documentId?: string;
  questionType: string;
  content: string;
  options?: { label: string; text: string }[];
  correctAnswer?: string;
  explanation?: string;
}): Promise<TrainingQuestion> {
  return apiPost("/training/questions", data);
}

export function getQuestionCountByDocument(
  planId: string
): Promise<Record<string, number>> {
  return apiGet(`/training/questions/count-by-document?planId=${encodeURIComponent(planId)}`);
}

export function appealQuestion(
  questionId: string,
  data: { endUserId: string; reason: string; answerRecordId?: string }
): Promise<unknown> {
  return apiPost(`/training/questions/${questionId}/appeals`, data);
}
