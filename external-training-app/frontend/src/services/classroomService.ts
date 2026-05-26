import { apiGet, apiPost } from "./apiClient";
import type { ClassroomSession, ClassroomEventResponse } from "../types/classroom";

export function createSession(endUserId: string, planId?: string): Promise<ClassroomSession> {
  const params = new URLSearchParams({ endUserId });
  if (planId) params.set("planId", planId);
  return apiPost(`/classroom/sessions?${params}`, {});
}

export function submitEvent(
  sessionId: string,
  eventType: string,
  payload?: Record<string, unknown>,
  query?: string
): Promise<ClassroomEventResponse> {
  const params = new URLSearchParams({ eventType, payload: JSON.stringify(payload || {}) });
  if (query) params.set("query", query);
  return apiPost(`/classroom/sessions/${sessionId}/events?${params}`, {});
}

export function getSession(sessionId: string): Promise<unknown> {
  return apiGet(`/classroom/sessions/${sessionId}`);
}
