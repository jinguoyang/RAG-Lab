import { apiGet, apiPost } from "./apiClient";
import type { ReviewTask, ReviewSubmitRequest } from "../types/review";

export function listReviews(reviewType?: string): Promise<ReviewTask[]> {
  const query = reviewType ? `?reviewType=${reviewType}` : "";
  return apiGet(`/reviews${query}`);
}

export function generatePlanDraft(jobTitle: string, jobDescription: string): Promise<unknown> {
  return apiPost(`/reviews/plans/drafts?jobTitle=${encodeURIComponent(jobTitle)}&jobDescription=${encodeURIComponent(jobDescription)}`, {});
}

export function submitReview(taskId: string, data: ReviewSubmitRequest): Promise<unknown> {
  return apiPost(`/reviews/${taskId}/submit`, data);
}
