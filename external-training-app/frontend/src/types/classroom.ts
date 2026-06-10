export interface ClassroomSession {
  sessionId: string;
  localSessionId?: string;
  currentState: string;
  currentSectionIndex?: number;
  planId?: string;
}

export interface ClassroomUiAction {
  actionType: string;
  data: Record<string, unknown>;
}

export interface ClassroomMessage {
  messageId?: string;
  role: string;
  content: string;
  stateAtTime?: string;
  uiActions?: ClassroomUiAction[];
  metadata?: {
    uiActions?: ClassroomUiAction[];
    [key: string]: unknown;
  };
  createdAt?: string;
}

export interface ClassroomSectionSnapshot {
  sectionId: string;
  title: string;
  learningObjective?: string;
  checkpointCriteria?: string[];
  estimatedMinutes?: number;
  teachingScript?: {
    opening: string;
    explanation: string;
    scenario: string;
    interactionQuestions: string[];
    summary: string;
  } | null;
  teachingQualityScore?: number;
}

export interface ClassroomDocumentSnapshot {
  documentId: string;
  title: string;
  sections: ClassroomSectionSnapshot[];
}

export interface ClassroomSessionDetail extends ClassroomSession {
  messages: ClassroomMessage[];
  metadata: {
    pendingActions?: Array<{ label: string; eventType: string }>;
    currentDocument?: string;
    currentSectionIndex?: number;
    completedSectionIds?: string[];
    inputs?: {
      courseSnapshot?: {
        documents?: ClassroomDocumentSnapshot[];
      };
    };
    [key: string]: unknown;
  };
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
  progressUpdate?: {
    sectionIndex?: number;
    sectionTotal?: number;
    completedSections?: number;
  } | null;
}
