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
