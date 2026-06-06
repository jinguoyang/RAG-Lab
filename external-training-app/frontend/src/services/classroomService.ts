import { apiGet, apiPost } from "./apiClient";
import type { ClassroomSession, ClassroomEventResponse } from "../types/classroom";

export function createSession(endUserId: string, planId?: string): Promise<ClassroomSession> {
  return apiPost("/classroom/sessions", {
    endUserId,
    ...(planId ? { planId } : {}),
  });
}

export function submitEvent(
  sessionId: string,
  eventType: string,
  payload?: Record<string, unknown>,
  query?: string
): Promise<ClassroomEventResponse> {
  return apiPost(`/classroom/sessions/${sessionId}/events`, {
    eventType,
    payload: payload || {},
    ...(query ? { query } : {}),
  });
}

export function getSession(sessionId: string): Promise<unknown> {
  return apiGet(`/classroom/sessions/${sessionId}`);
}

export interface PostQuiz {
  quizId: string;
  sessionId: string;
  appId: string;
  endUserId: string;
  documentId: string;
  questions: Array<{
    questionId: string;
    questionType: string;
    content: string;
    options?: Array<{ label: string; text: string }>;
    rubric?: Record<string, unknown> | null;
  }>;
  status: string;
  createdAt: string;
}

export interface PostQuizSubmission {
  quizId: string;
  score: number;
  passed: boolean;
  results: Array<{
    questionId: string;
    questionType: string;
    score: number;
    passed: boolean;
    isCorrect?: boolean | null;
    explanation?: string | null;
  }>;
  submittedAt: string;
}

export function createPostQuiz(data: {
  sessionId: string;
  endUserId: string;
  documentId: string;
  planId?: string;
  count?: number;
}): Promise<PostQuiz> {
  return apiPost("/training/post-quizzes", data);
}

export function submitPostQuiz(
  quizId: string,
  data: { endUserId: string; answers: Array<{ questionId: string; answer: string }> }
): Promise<PostQuizSubmission> {
  return apiPost(`/training/post-quizzes/${quizId}/submissions`, data);
}
