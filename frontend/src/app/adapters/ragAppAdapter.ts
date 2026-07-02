import type {
  AppConversationSummaryViewModel,
  AppInvocationDTO,
  AppInvocationViewModel,
  AppMessageDTO,
  AppMessageViewModel,
  AppTrainingReportDTO,
  AppTrainingReportViewModel,
  EmbeddedAppDeploymentDTO,
  EmbeddedAppDeploymentViewModel,
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
  const isEmbeddedSystemKey = key.keyType === "embedded_system";
  return {
    id: key.apiKeyId,
    appId: key.appId,
    keyPrefix: key.keyPrefix,
    status: key.status,
    statusLabel: RAG_APP_API_KEY_STATUS_LABELS[key.status] ?? key.status,
    sourceLabel: key.displayName || (isEmbeddedSystemKey ? "内置嵌入页调用 Key" : "普通 API Key"),
    managedByLabel: key.managedBy === "system" ? "系统管理" : "用户管理",
    deletable: key.deletable,
    expiresAtLabel: key.expiresAt ? formatDateTime(key.expiresAt) : "永不过期",
    lastUsedAtLabel: formatDateTime(key.lastUsedAt),
    createdAtLabel: formatDateTime(key.createdAt),
  };
}

const EMBEDDED_DEPLOYMENT_STATUS_LABELS: Record<string, string> = {
  pending: "待启动",
  running: "运行中",
  stopped: "已停止",
  failed: "失败",
};

const EMBEDDED_HEALTH_STATUS_LABELS: Record<string, string> = {
  unknown: "未检查",
  healthy: "健康",
  unhealthy: "异常",
};

export function toEmbeddedAppDeploymentViewModel(
  deployment: EmbeddedAppDeploymentDTO,
): EmbeddedAppDeploymentViewModel {
  return {
    id: deployment.deploymentId,
    appType: deployment.appType,
    databaseName: deployment.databaseName,
    backendPortLabel: String(deployment.backendPort),
    frontendPortLabel: String(deployment.frontendPort),
    serviceNameLabel: deployment.serviceName || "-",
    status: deployment.status,
    statusLabel: EMBEDDED_DEPLOYMENT_STATUS_LABELS[deployment.status] ?? deployment.status,
    healthStatus: deployment.healthStatus,
    healthLabel: EMBEDDED_HEALTH_STATUS_LABELS[deployment.healthStatus] ?? deployment.healthStatus,
    publicUrl: deployment.publicUrl,
    lastStartAtLabel: formatDateTime(deployment.lastStartAt),
    lastStopAtLabel: formatDateTime(deployment.lastStopAt),
    lastHealthCheckAtLabel: formatDateTime(deployment.lastHealthCheckAt),
    errorMessage: deployment.errorMessage,
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
  const trainingResult = message.metadata?.trainingResult;
  const score = typeof trainingResult === "object" && trainingResult !== null && "score" in trainingResult
    ? Number(trainingResult.score)
    : null;
  const passed = typeof trainingResult === "object" && trainingResult !== null && "passed" in trainingResult
    ? Boolean(trainingResult.passed)
    : null;
  const passingScore = typeof trainingResult === "object" && trainingResult !== null && "passingScore" in trainingResult
    ? Number(trainingResult.passingScore)
    : null;
  return {
    id: message.messageId,
    role: message.role,
    roleLabel: message.role === "user" ? "用户" : "助手",
    content: message.content,
    qaRunId: message.qaRunId,
    status: message.status,
    createdAtLabel: formatDateTime(message.createdAt),
    trainingResultLabel: score == null || Number.isNaN(score)
      ? undefined
      : `训练得分 ${score} / 100 · ${passed ? "已通过" : "未通过"}${passingScore == null || Number.isNaN(passingScore) ? "" : ` · 及格分 ${passingScore}`}`,
  };
}

export function toRagAppTrainingReportViewModel(report: AppTrainingReportDTO): AppTrainingReportViewModel {
  const passRateLabel = `${Math.round(report.passRate * 100)}%`;
  const averageScoreLabel = report.averageScore == null ? "-" : String(report.averageScore);
  return {
    summaryLabel: `${report.totalSubmissions} 次训练 · 通过率 ${passRateLabel} · 平均分 ${averageScoreLabel}`,
    latestSubmittedAtLabel: formatDateTime(report.latestSubmittedAt),
    totalSubmissions: report.totalSubmissions,
    passedSubmissions: report.passedSubmissions,
    failedSubmissions: report.failedSubmissions,
    passRateLabel,
    averageScoreLabel,
  };
}
