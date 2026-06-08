import { apiDelete, apiGet, apiPatch, apiPost } from "./apiClient";

export interface TrainingPlan {
  planId: string;
  appId?: string;
  planName?: string | null;
  jobTitle: string;
  jobDescription?: string | null;
  status: string;
  documents?: TrainingDocument[];
  abilityGroups?: unknown[];
  evidenceChunkIds?: string[];
  readingOrder?: string[];
  sections?: TrainingSection[];
  employeeIds?: string[];
  recommendReason?: string;
  completedDocuments?: string[];
  passedDocuments?: string[];
  version?: number;
  createdAt: string;
  updatedAt?: string;
}

export interface TrainingDocument {
  documentId: string;
  title: string;
  relevance?: number | null;
  abilityGroup?: string | null;
  category?: string | null;
  difficulty?: string | null;
  summary?: string | null;
}

export interface TrainingSection {
  sectionId: string;
  title: string;
  learningObjective: string;
  sourceDocumentIds: string[];
  evidenceChunkIds: string[];
  keyPoints: string[];
  checkpointCriteria: string[];
  teachingScript?: {
    opening: string;
    explanation: string;
    scenario: string;
    interactionQuestions: string[];
    summary: string;
  } | null;
  teachingQualityScore?: number;
  estimatedMinutes: number;
  required: boolean;
}

export function listPlans(): Promise<TrainingPlan[]> {
  return apiGet("/training/plans");
}

export function getPlan(planId: string): Promise<TrainingPlan> {
  return apiGet(`/training/plans/${planId}`);
}

export function generatePlanDraft(data: {
  jobTitle: string;
  jobDescription: string;
  planName?: string;
}): Promise<TrainingPlan> {
  return apiPost("/training/plans/drafts", data);
}

export function listTrainingDocuments(query = ""): Promise<TrainingDocument[]> {
  const qs = query ? `?query=${encodeURIComponent(query)}` : "";
  return apiGet(`/training/plans/documents${qs}`);
}

export function savePlan(
  planId: string,
  data: {
    planName: string;
    appId: string;
    jobTitle: string;
    jobDescription?: string | null;
    abilityGroups?: unknown[];
    documents: TrainingDocument[];
    evidenceChunkIds?: string[];
    recommendReason?: string | null;
    readingOrder: string[];
    sections?: TrainingSection[];
    employeeIds: string[];
    version?: number;
  }
): Promise<{ planId: string; status: string; message?: string }> {
  return apiPost(`/training/plans/${planId}/save`, data);
}

export function updatePlan(
  planId: string,
  data: {
    planName?: string;
    documents?: TrainingDocument[];
    readingOrder?: string[];
    sections?: TrainingSection[];
    employeeIds?: string[];
  }
): Promise<{ planId: string; status: string }> {
  return apiPatch(`/training/plans/${planId}`, data);
}

export function deletePlan(
  planId: string
): Promise<{ planId: string; status: string }> {
  return apiDelete(`/training/plans/${planId}`);
}
