export interface ReviewTask {
  id: string;
  platformDraftId: string | null;
  platformPlanId: string | null;
  reviewType: string;
  status: string;
  submittedPayload: Record<string, unknown>;
  createdAt: string;
}

export interface ReviewSubmitRequest {
  decision: "approved" | "rejected";
  notes: string;
  adjustments?: Record<string, unknown>;
}
