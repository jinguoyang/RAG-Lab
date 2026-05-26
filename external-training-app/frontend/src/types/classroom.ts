export interface ClassroomSession {
  sessionId: string;
  localSessionId?: string;
  currentState: string;
  planId?: string;
}

export interface ClassroomUiAction {
  actionType: string;
  data: Record<string, unknown>;
}

export interface ClassroomMessage {
  role: string;
  content: string;
  uiActions?: ClassroomUiAction[];
  createdAt?: string;
}

export interface ClassroomEventResponse {
  eventId: string;
  sessionId: string;
  eventType: string;
  resultState: string;
  visibleContent: string;
  classroomState: string;
  uiActions: ClassroomUiAction[];
  citations: unknown[];
  control: {
    canProceed: boolean;
    requiresInput: boolean;
    inputType?: string;
  };
}
