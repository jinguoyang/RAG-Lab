import type { QARunDetailDTO, QARunTraceStepDTO } from "../types/qaRun";

export interface QAPartialDiagnosticStep {
  stepKey: string;
  label: string;
  status: string;
  errorCode: string | null;
  errorMessage: string | null;
  reason: string;
  impact: string;
}

export interface QAPartialDiagnostics {
  hasPartialIssue: boolean;
  summary: string;
  impact: string;
  providerErrors: string[];
  affectedSteps: QAPartialDiagnosticStep[];
}

const STEP_LABELS: Record<string, string> = {
  queryRewrite: "问题改写",
  embedding: "Embedding 向量化",
  denseRetrieval: "Dense 检索",
  sparseRetrieval: "Sparse 检索",
  graphRetrieval: "Graph 检索",
  fusionRerank: "融合与重排",
  permissionFilter: "权限过滤",
  generation: "LLM 生成",
};

const STEP_IMPACTS: Record<string, string> = {
  queryRewrite: "本次检索会退回原始问题，召回质量可能下降。",
  embedding: "Dense 向量召回可能缺失，结果更依赖 Sparse 或 Graph 通道。",
  denseRetrieval: "Dense 候选未完整进入融合，语义召回覆盖可能下降。",
  sparseRetrieval: "Sparse 候选未完整进入融合，关键词命中覆盖可能下降。",
  graphRetrieval: "图侧关系和根因路径未进入最终上下文，答案更依赖文档 Evidence。",
  fusionRerank: "候选融合或重排不完整，最终上下文排序可信度下降。",
  permissionFilter: "部分候选被权限裁剪，答案不会展示不可见证据正文。",
  generation: "生成阶段降级，答案可能更保守或不完整。",
};

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function stepLabel(stepKey: string): string {
  return STEP_LABELS[stepKey] ?? stepKey;
}

function stepImpact(stepKey: string): string {
  return STEP_IMPACTS[stepKey] ?? "该阶段未完整执行，结果需要结合 Trace 明细复核。";
}

function readProviderErrors(detail: QARunDetailDTO): string[] {
  const value = detail.retrievalDiagnostics.providerErrors;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function isAffectedTraceStep(step: QARunTraceStepDTO): boolean {
  return step.status === "partial" || step.status === "failed";
}

function toDiagnosticStep(step: QARunTraceStepDTO): QAPartialDiagnosticStep {
  const reason =
    readString(step.outputSummary.reason) ??
    readString(step.outputSummary.provider) ??
    readString(step.errorMessage) ??
    "后端未返回具体原因";

  return {
    stepKey: step.stepKey,
    label: stepLabel(step.stepKey),
    status: step.status,
    errorCode: step.errorCode,
    errorMessage: step.errorMessage,
    reason,
    impact: stepImpact(step.stepKey),
  };
}

/**
 * 从 QARun 详情中提取“部分成功”原因，供调试页和历史详情复用同一解释口径。
 */
export function deriveQAPartialDiagnostics(detail: QARunDetailDTO): QAPartialDiagnostics {
  const affectedSteps = detail.trace.filter(isAffectedTraceStep).map(toDiagnosticStep);
  const providerErrors = readProviderErrors(detail);

  if (affectedSteps.length > 0) {
    const labels = affectedSteps.map((step) => step.label).join("、");
    return {
      hasPartialIssue: true,
      summary: `${labels} 未完整执行，运行已按降级路径完成。`,
      impact: affectedSteps[0].impact,
      providerErrors,
      affectedSteps,
    };
  }

  if (detail.status === "partial") {
    const fallback = detail.failureType || (providerErrors.length > 0 ? providerErrors.join("、") : "后端未返回具体降级步骤");
    return {
      hasPartialIssue: true,
      summary: `本次运行被标记为部分成功：${fallback}。`,
      impact: "答案已生成，但建议结合 Evidence、Candidate 和运行日志复核缺失链路。",
      providerErrors,
      affectedSteps: [],
    };
  }

  return {
    hasPartialIssue: false,
    summary: "",
    impact: "",
    providerErrors,
    affectedSteps: [],
  };
}
