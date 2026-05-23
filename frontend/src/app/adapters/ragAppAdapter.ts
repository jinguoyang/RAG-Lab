import type {
  AppConversationSummaryViewModel,
  AppInvocationDTO,
  AppInvocationViewModel,
  AppMessageDTO,
  AppMessageViewModel,
  RagAppApiKeyDTO,
  RagAppApiKeyViewModel,
  RagAppDTO,
  RagAppViewModel,
} from "../types/ragApp";

export const RAG_APP_STATUS_LABELS = {
  active: "启用",
  disabled: "停用",
  archived: "已归档",
} as const;

export const RAG_APP_API_KEY_STATUS_LABELS = {
  active: "启用",
  revoked: "已撤销",
} as const;

export const APP_INVOCATION_STATUS_LABELS = {
  running: "运行中",
  success: "成功",
  failed: "失败",
} as const;

export const RAG_APP_SCENARIO_LABELS: Record<string, string> = {
  knowledge_qa: "知识库问答助手",
  employee_training: "员工培训助手",
};

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function shortId(value: string | null | undefined, length = 8): string {
  if (!value) return "-";
  return value.length <= length ? value : value.slice(0, length);
}

function summarizeObject(value: Record<string, unknown>): string {
  const entries = Object.entries(value)
    .filter(([, item]) => item !== null && item !== undefined && item !== "")
    .slice(0, 3);
  if (entries.length === 0) return "-";
  return entries.map(([key, item]) => `${key}: ${String(item)}`).join(" · ");
}

export function toRagAppViewModel(app: RagAppDTO): RagAppViewModel {
  const publishChannelLabels = [
    app.publishChannels?.api ? "API" : null,
    app.publishChannels?.embed ? "嵌入页" : null,
  ].filter(Boolean);
  const embedEnabled = app.embedSettings?.enabled === true || app.publishChannels?.embed === true;
  return {
    id: app.appId,
    name: app.name,
    description: app.description?.trim() ?? "",
    kbId: app.kbId,
    defaultRevisionLabel: app.defaultConfigRevisionId
      ? shortId(app.defaultConfigRevisionId, 12)
      : "跟随知识库",
    status: app.status,
    statusLabel: RAG_APP_STATUS_LABELS[app.status] ?? app.status,
    scenarioType: app.scenarioType,
    scenarioLabel: RAG_APP_SCENARIO_LABELS[app.scenarioType] ?? app.scenarioType,
    publishChannelLabel: publishChannelLabels.length > 0 ? publishChannelLabels.join(" / ") : "-",
    embedStatusLabel: embedEnabled ? "已启用" : "未启用",
    updatedAtLabel: formatDateTime(app.updatedAt),
  };
}

export function toRagAppApiKeyViewModel(key: RagAppApiKeyDTO): RagAppApiKeyViewModel {
  return {
    id: key.apiKeyId,
    appId: key.appId,
    keyPrefix: key.keyPrefix,
    status: key.status,
    statusLabel: RAG_APP_API_KEY_STATUS_LABELS[key.status] ?? key.status,
    expiresAtLabel: key.expiresAt ? formatDateTime(key.expiresAt) : "永不过期",
    lastUsedAtLabel: formatDateTime(key.lastUsedAt),
    createdAtLabel: formatDateTime(key.createdAt),
  };
}

export function toAppInvocationViewModel(invocation: AppInvocationDTO): AppInvocationViewModel {
  const errorCode = invocation.errorCode || "";
  return {
    id: invocation.invocationId,
    appId: invocation.appId,
    status: invocation.status,
    statusLabel: APP_INVOCATION_STATUS_LABELS[invocation.status] ?? invocation.status,
    errorLabel: errorCode ? `${errorCode}` : "-",
    latencyLabel: invocation.status === "running" ? "运行中" : invocation.latencyMs == null ? "-" : `${invocation.latencyMs}ms`,
    conversationId: invocation.conversationId,
    messageId: invocation.messageId,
    qaRunId: invocation.qaRunId,
    createdAtLabel: formatDateTime(invocation.createdAt),
    requestSummaryLabel: summarizeObject(invocation.requestSummary),
    responseSummaryLabel: summarizeObject(invocation.responseSummary),
  };
}

export function groupInvocationsByConversation(
  invocations: AppInvocationDTO[],
): AppConversationSummaryViewModel[] {
  const grouped = new Map<string, AppConversationSummaryViewModel & { lastCalledAtRaw: string }>();
  for (const invocation of invocations) {
    if (!invocation.conversationId) continue;
    const existing = grouped.get(invocation.conversationId);
    if (!existing) {
      grouped.set(invocation.conversationId, {
        conversationId: invocation.conversationId,
        invocationCount: 1,
        successCount: invocation.status === "success" ? 1 : 0,
        failedCount: invocation.status === "failed" ? 1 : 0,
        lastCalledAtLabel: formatDateTime(invocation.createdAt),
        lastCalledAtRaw: invocation.createdAt,
        lastQaRunId: invocation.qaRunId,
      });
      continue;
    }

    existing.invocationCount += 1;
    existing.successCount += invocation.status === "success" ? 1 : 0;
    existing.failedCount += invocation.status === "failed" ? 1 : 0;
    if (new Date(invocation.createdAt).getTime() > new Date(existing.lastCalledAtRaw).getTime()) {
      existing.lastCalledAtRaw = invocation.createdAt;
      existing.lastCalledAtLabel = formatDateTime(invocation.createdAt);
      existing.lastQaRunId = invocation.qaRunId;
    }
  }

  return Array.from(grouped.values())
    .sort((left, right) => new Date(right.lastCalledAtRaw).getTime() - new Date(left.lastCalledAtRaw).getTime())
    .map(({ lastCalledAtRaw, ...item }) => item);
}

export function toAppMessageViewModel(message: AppMessageDTO): AppMessageViewModel {
  return {
    id: message.messageId,
    role: message.role,
    roleLabel: message.role === "user" ? "用户" : "助手",
    content: message.content,
    qaRunId: message.qaRunId,
    status: message.status,
    createdAtLabel: formatDateTime(message.createdAt),
  };
}
