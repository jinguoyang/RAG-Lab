import type { PageResponse } from "./knowledgeBase";

export type RagAppStatus = "active" | "disabled" | "archived";
export type RagAppApiKeyStatus = "active" | "revoked";
export type AppInvocationStatus = "running" | "success" | "failed";
export type RagAppScenarioType = "knowledge_qa" | "employee_training" | string;

export interface RagAppDTO {
  appId: string;
  kbId: string;
  defaultConfigRevisionId: string | null;
  name: string;
  description: string | null;
  status: RagAppStatus;
  outputPolicy: Record<string, unknown>;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  // Sprint 42: KB status
  knowledgeBaseName?: string | null;
  knowledgeBaseStatus?: string | null;
  scenarioType: RagAppScenarioType;
  scenarioTemplateId: string;
  scenarioConfig: Record<string, unknown>;
  publishChannels: Record<string, boolean>;
  embedSettings: Record<string, unknown>;
}

export interface RagAppCreateRequest {
  name: string;
  kbId: string;
  defaultConfigRevisionId?: string | null;
  outputPolicy?: Record<string, unknown> | null;
  description?: string | null;
  metadata?: Record<string, unknown> | null;
  scenarioType?: RagAppScenarioType | null;
  scenarioTemplateId?: string | null;
  scenarioConfig?: Record<string, unknown> | null;
  publishChannels?: Record<string, boolean> | null;
  embedSettings?: Record<string, unknown> | null;
  createRecommendedConfigRevision?: boolean;
}

export interface RagAppUpdateRequest {
  name?: string;
  description?: string | null;
  defaultConfigRevisionId?: string | null;
  outputPolicy?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  status?: RagAppStatus;
  scenarioType?: RagAppScenarioType | null;
  scenarioTemplateId?: string | null;
  scenarioConfig?: Record<string, unknown> | null;
  publishChannels?: Record<string, boolean> | null;
  embedSettings?: Record<string, unknown> | null;
}

export interface RagAppApiKeyDTO {
  apiKeyId: string;
  appId: string;
  keyPrefix: string;
  status: RagAppApiKeyStatus;
  expiresAt: string | null;
  lastUsedAt: string | null;
  createdAt: string;
  revokedAt: string | null;
}

export interface RagAppApiKeyCreateRequest {
  expiresAt?: string | null;
}

export interface RagAppApiKeyCreateResponse {
  apiKey: string;
  item: RagAppApiKeyDTO;
}

export interface RagAppApiKeyRevokeResponse {
  apiKeyId: string;
  status: RagAppApiKeyStatus;
  revokedAt: string;
}

export interface AppInvocationDTO {
  invocationId: string;
  appId: string;
  apiKeyId: string | null;
  conversationId: string | null;
  messageId: string | null;
  qaRunId: string | null;
  status: AppInvocationStatus;
  errorCode: string | null;
  latencyMs: number | null;
  requestSummary: Record<string, unknown>;
  responseSummary: Record<string, unknown>;
  createdAt: string;
}

export type RagAppPage = PageResponse<RagAppDTO>;
export type AppInvocationPage = PageResponse<AppInvocationDTO>;

export interface AppInvocationStatsDTO {
  appId: string;
  totalInvocations: number;
  runningInvocations: number;
  successInvocations: number;
  failedInvocations: number;
  quotaExceededInvocations: number;
  concurrencyExceededInvocations: number;
  noEvidenceInvocations: number;
  averageLatencyMs: number | null;
  failureRate: number;
  noEvidenceRate: number;
}

export interface AppMessageDTO {
  messageId: string;
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  qaRunId: string | null;
  status: "success" | "failed";
  metadata: Record<string, unknown>;
  createdAt: string;
}

export interface AppConversationDetailDTO {
  conversationId: string;
  appId: string;
  endUserId: string | null;
  status: string;
  metadata: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  messages: AppMessageDTO[];
}

export interface RagAppListParams {
  pageNo?: number;
  pageSize?: number;
  keyword?: string;
  kbId?: string;
  status?: RagAppStatus | "";
}

export interface AppInvocationListParams {
  pageNo?: number;
  pageSize?: number;
  status?: AppInvocationStatus | "";
}

export interface RagAppViewModel {
  id: string;
  name: string;
  description: string;
  kbId: string;
  defaultRevisionLabel: string;
  status: RagAppStatus;
  statusLabel: string;
  scenarioType: RagAppScenarioType;
  scenarioLabel: string;
  publishChannelLabel: string;
  embedStatusLabel: string;
  updatedAtLabel: string;
}

export interface RagAppApiKeyViewModel {
  id: string;
  appId: string;
  keyPrefix: string;
  status: RagAppApiKeyStatus;
  statusLabel: string;
  expiresAtLabel: string;
  lastUsedAtLabel: string;
  createdAtLabel: string;
}

export interface AppInvocationViewModel {
  id: string;
  appId: string;
  status: AppInvocationStatus;
  statusLabel: string;
  errorLabel: string;
  latencyLabel: string;
  conversationId: string | null;
  messageId: string | null;
  qaRunId: string | null;
  createdAtLabel: string;
  requestSummaryLabel: string;
  responseSummaryLabel: string;
}

export interface AppConversationSummaryViewModel {
  conversationId: string;
  invocationCount: number;
  successCount: number;
  failedCount: number;
  lastCalledAtLabel: string;
  lastQaRunId: string | null;
}

export interface AppMessageViewModel {
  id: string;
  role: "user" | "assistant";
  roleLabel: string;
  content: string;
  qaRunId: string | null;
  status: string;
  createdAtLabel: string;
}
