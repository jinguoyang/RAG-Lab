import type { PageResponse } from "./knowledgeBase";

export type ConfigRevisionStatus = "draft" | "saved" | "active" | "archived" | "invalid";

export interface PipelineDefinition {
  version: string;
  constraintsVersion: string;
  mode: "constrained-stage-pipeline";
  stages: string[];
  nodes: PipelineDefinitionNode[];
  templateId?: string | null;
  validationSnapshot?: Record<string, unknown>;
}

export interface PipelineDefinitionNode {
  id: string;
  type: string;
  stage: string;
  enabled: boolean;
  locked?: boolean;
  params?: Record<string, unknown>;
}

export interface PipelineValidationIssueDTO {
  code: string;
  message: string;
  field: string | null;
}

export interface PipelineValidationResultDTO {
  valid: boolean;
  errors: PipelineValidationIssueDTO[];
  warnings: PipelineValidationIssueDTO[];
  normalizedPipelineDefinition: PipelineDefinition;
}

export interface ConfigRevisionDTO {
  configRevisionId: string;
  kbId: string;
  revisionNo: number;
  sourceTemplateId: string | null;
  status: ConfigRevisionStatus;
  pipelineDefinition: PipelineDefinition;
  validationSnapshot: Record<string, unknown>;
  remark: string | null;
  activatedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConfigRevisionCreateResponse {
  configRevisionId: string;
  revisionNo: number;
  status: ConfigRevisionStatus;
  validationSnapshot: Record<string, unknown>;
}

export interface ConfigRevisionActivationResponse {
  activeConfigRevisionId: string;
  previousActiveConfigRevisionId: string | null;
  activatedAt: string;
  auditLogId: string | null;
}

export interface RevisionRecordViewModel {
  id: string;
  revisionNo: string;
  createdBy: string;
  createdAt: string;
  note: string;
  status: "queued" | "active" | "inactive" | "failed";
  active: boolean;
}

export type ConfigRevisionPage = PageResponse<ConfigRevisionDTO>;
