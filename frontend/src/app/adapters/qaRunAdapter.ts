import { formatDateTime } from "./documentAdapter";
import type { QARunDetailDTO, QARunListItemDTO } from "../types/qaRun";
import { deriveQAPartialDiagnostics, type QAPartialDiagnostics } from "../utils/qaPartialDiagnostics";

export interface QADebugResultViewModel {
  status: "success" | "partial" | "failed";
  answer: string[];
  answerBlocks: {
    text: string;
    citationIds: string[];
  }[];
  runMeta: string;
  notice?: { variant: "info" | "warning"; title: string; message: string };
  rewrite: string;
  rewriteTrace: QARewriteTraceViewModel;
  retrievalCards: { channel: string; summary: string }[];
  candidates: {
    id: string;
    source: "Dense" | "Sparse" | "Graph" | "Mock" | "Postgres";
    title: string;
    score: string;
    decision: string;
    snippet?: string;
  }[];
  citations: {
    id: string;
    evidenceId: string;
    type: "document" | "graph";
    title: string;
    snippet: string;
    meta: string;
    documentId?: string | null;
    chunkId?: string | null;
    sourceModality?: string | null;
    sourceFileId?: string | null;
    region?: string | null;
    visionConfidence?: string | null;
  }[];
  diagnostics: {
    recalled: string;
    deduped: string;
    filtered: string;
    finalContext: string;
    rerankSummary: string;
  };
  partialDiagnostics: QAPartialDiagnostics;
}

export interface QARewriteTraceViewModel {
  originalQuery: string;
  rewrittenQuery: string;
  statusLabel: string;
  providerLabel: string;
  usedOriginalQuery: boolean;
  errorMessage: string | null;
}

export interface QAHistoryRecordViewModel {
  id: string;
  sourceRunId: string | null;
  query: string;
  status: "success" | "partial" | "failed";
  user: string;
  userName: string;
  time: string;
  rev: string;
  rating: "up" | "down" | "none";
  feedbackStatus: string;
  hasOverrides: boolean;
  failureType: string;
  answer: string;
}

function statusToViewStatus(status: string): "success" | "partial" | "failed" {
  if (status === "partial") return "partial";
  if (status === "failed" || status === "cancelled") return "failed";
  return "success";
}

function feedbackToRating(feedbackStatus: string): "up" | "down" | "none" {
  if (feedbackStatus === "correct") return "up";
  if (["wrong", "citation_error", "no_evidence"].includes(feedbackStatus)) return "down";
  return "none";
}

export function ratingToFeedbackStatus(rating: "up" | "down" | "none"): string {
  if (rating === "up") return "correct";
  if (rating === "down") return "wrong";
  return "unrated";
}

function readNumber(source: Record<string, unknown>, key: string): number {
  const value = source[key];
  return typeof value === "number" ? value : 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(source: Record<string, unknown>, key: string): string | null {
  const value = source[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function readChunkRevisionId(...sources: Record<string, unknown>[]): string | null {
  for (const source of sources) {
    const value =
      readString(source, "chunkRevisionId") ??
      readString(source, "bindingRevisionId") ??
      readString(source, "chunk_revision_id") ??
      readString(source, "binding_revision_id");
    if (value) {
      return value;
    }
  }
  return null;
}

function readNestedNumber(source: Record<string, unknown>, path: string[]): number | null {
  let current: unknown = source;
  for (const key of path) {
    if (!isRecord(current)) return null;
    current = current[key];
  }
  return typeof current === "number" ? current : null;
}

function formatScore(value: number | null | undefined): string | null {
  if (typeof value !== "number") return null;
  return value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

function traceStep(detail: QARunDetailDTO, stepKey: string) {
  return detail.trace.find((step) => step.stepKey === stepKey);
}

export function toQARewriteTrace(detail: QARunDetailDTO): QARewriteTraceViewModel {
  const step = traceStep(detail, "queryRewrite");
  const rewrittenFromTrace = step && isRecord(step.outputSummary) ? readString(step.outputSummary, "rewrittenQuery") : null;
  const rewrittenQuery = detail.rewrittenQuery?.trim() || rewrittenFromTrace || detail.query;
  const usedOriginalQuery = !detail.rewrittenQuery?.trim() || rewrittenQuery === detail.query || step?.status === "skipped";
  const provider = step && isRecord(step.metrics) ? readString(step.metrics, "provider") : null;
  const statusLabel =
    step?.status === "partial"
      ? "改写降级，使用原始问题"
      : step?.status === "skipped" || usedOriginalQuery
        ? "未改写，使用原始问题"
        : "已改写";

  return {
    originalQuery: detail.query,
    rewrittenQuery,
    statusLabel,
    providerLabel: provider ?? "-",
    usedOriginalQuery,
    errorMessage: step?.errorMessage ?? null,
  };
}

function readTraceOutputNumber(detail: QARunDetailDTO, stepKey: string, key: string): number | null {
  const output = traceStep(detail, stepKey)?.outputSummary;
  return isRecord(output) && typeof output[key] === "number" ? output[key] : null;
}

function readTraceInputNumber(detail: QARunDetailDTO, stepKey: string, key: string): number | null {
  const input = traceStep(detail, stepKey)?.inputSummary;
  return isRecord(input) && typeof input[key] === "number" ? input[key] : null;
}

function readTraceMetricNumber(detail: QARunDetailDTO, stepKey: string, key: string): number | null {
  const metrics = traceStep(detail, stepKey)?.metrics;
  return isRecord(metrics) && typeof metrics[key] === "number" ? metrics[key] : null;
}

function retrievalCardSummary(
  detail: QARunDetailDTO,
  diagnostics: Record<string, unknown>,
  channel: "dense" | "sparse" | "graph",
): string {
  const stepKey = `${channel}Retrieval`;
  const count = readNumber(diagnostics, `${channel}Count`);
  const multiQueryCount = readTraceMetricNumber(detail, "multiQuery", "actualQueryCount") ?? 1;
  const queryMultiplier = channel === "dense" ? 1 : multiQueryCount;
  const dropped = readTraceOutputNumber(detail, stepKey, "droppedByScoreThreshold") ?? 0;
  const topK =
    readTraceMetricNumber(detail, stepKey, "topK") ??
    readNestedNumber(diagnostics, ["pipelineParams", "retrievalTopK", channel]);
  const threshold =
    readTraceMetricNumber(detail, stepKey, "scoreThreshold") ??
    readNestedNumber(diagnostics, ["pipelineParams", "retrievalScoreThreshold", channel]);
  const details = [
    dropped > 0 ? `阈值过滤 ${dropped} 条` : null,
    typeof topK === "number" && queryMultiplier > 1 ? `${queryMultiplier} 个 query × topK ${topK}` : null,
    typeof topK === "number" && queryMultiplier <= 1 ? `topK ${topK}` : null,
    typeof threshold === "number" ? `阈值 ${threshold}` : null,
  ].filter(Boolean);

  return details.length > 0 ? `${count} 条原始候选（${details.join(" · ")}）` : `${count} 条原始候选`;
}

function candidateTitle(metadata: Record<string, unknown>, fallback: string): string {
  const documentName = readString(metadata, "documentName");
  const section = readString(metadata, "section");
  const chunkIndex = typeof metadata.chunkIndex === "number" ? `#${metadata.chunkIndex}` : null;
  return [documentName ?? fallback, chunkIndex, section].filter(Boolean).join(" · ");
}

function candidateScore(candidate: QARunDetailDTO["candidates"][number]): string {
  const retrievalScores = isRecord(candidate.metadata.retrievalScores) ? candidate.metadata.retrievalScores : {};
  const parts = [
    formatScore(candidate.rerankScore ?? candidate.rawScore)
      ? `rerank ${formatScore(candidate.rerankScore ?? candidate.rawScore)}`
      : null,
    formatScore(readNestedNumber(candidate.metadata, ["fusedScore"])),
    ...Object.entries(retrievalScores).map(([channel, score]) =>
      typeof score === "number" ? `${channel} ${formatScore(score)}` : null,
    ),
  ].filter(Boolean);

  return parts.length > 0 ? parts.join(" · ") : "-";
}

function candidateDecision(candidate: QARunDetailDTO["candidates"][number], evidenceIndex?: number): string {
  if (!candidate.isAuthorized) {
    return candidate.dropReason ? `权限/治理裁剪：${candidate.dropReason}` : "权限/治理裁剪";
  }
  if (typeof evidenceIndex === "number") {
    return `权限通过，进入最终上下文，对应 Evidence [${evidenceIndex}]`;
  }
  return "权限通过，但当前历史记录未保存对应 Evidence（旧运行可能只保存首条）";
}

function diagnosticsFromTrace(detail: QARunDetailDTO, diagnostics: Record<string, unknown>, evidenceCount: number) {
  const recalled =
    readTraceOutputNumber(detail, "fusion", "inputCandidates") ??
    readNumber(diagnostics, "denseCount") + readNumber(diagnostics, "sparseCount") + readNumber(diagnostics, "graphCount");
  const deduped = readTraceOutputNumber(detail, "fusion", "candidateCount") ?? readNumber(diagnostics, "fusedCount");
  const reranked = readTraceOutputNumber(detail, "rerank", "candidateCount");
  const authorizedAfterPermission = readTraceOutputNumber(detail, "permissionFilter", "authorizedCandidates");
  const authorizedForContext = readTraceInputNumber(detail, "contextPacking", "authorizedEvidenceCount");
  const finalContext = readTraceOutputNumber(detail, "contextPacking", "contextCandidateCount") ?? evidenceCount;
  const expandedContext =
    readTraceInputNumber(detail, "rerank", "expandedContextCandidates") ??
    readTraceOutputNumber(detail, "contextPacking", "expandedContextCandidates") ??
    0;
  const droppedByPermission =
    readTraceOutputNumber(detail, "permissionFilter", "droppedCandidates") ??
    readNumber(diagnostics, "droppedByPermission");

  return {
    recalled,
    deduped,
    reranked,
    authorizedAfterPermission,
    authorizedForContext,
    finalContext,
    expandedContext,
    droppedByPermission,
  };
}

export function toQADebugResult(detail: QARunDetailDTO): QADebugResultViewModel {
  const diagnostics = detail.retrievalDiagnostics;
  const evidenceCount = detail.evidence.length;
  const funnel = diagnosticsFromTrace(detail, diagnostics, evidenceCount);
  const evidenceById = new Map(detail.evidence.map((item) => [item.evidenceId, item]));
  const evidenceByCandidateId = new Map(
    detail.evidence
      .filter((item) => item.candidateId)
      .map((item) => [item.candidateId as string, item]),
  );
  const evidenceIndexByCandidateId = new Map(
    detail.evidence
      .filter((item) => item.candidateId)
      .map((item, index) => [item.candidateId as string, index + 1]),
  );

  const answerBlocks =
    detail.answerBlocks && detail.answerBlocks.length > 0
      ? detail.answerBlocks.map((block) => ({
          text: block.text,
          citationIds: block.citationEvidenceIds,
        }))
      : (detail.answer ? [detail.answer] : ["运行已创建，当前暂无回答。"]).map((text) => ({
          text,
          citationIds: [],
        }));
  const citedEvidenceIds = Array.from(
    new Set(answerBlocks.flatMap((block) => block.citationIds).filter((evidenceId) => evidenceById.has(evidenceId))),
  );
  const citationRows =
    citedEvidenceIds.length > 0
      ? citedEvidenceIds
          .map((evidenceId) => detail.citations.find((citation) => citation.evidenceId === evidenceId))
          .filter((citation): citation is QARunDetailDTO["citations"][number] => Boolean(citation))
      : detail.citations;
  const citedEvidenceCount = citedEvidenceIds.length > 0 ? citationRows.length : 0;
  const correctiveAdded =
    typeof funnel.authorizedForContext === "number" && typeof funnel.authorizedAfterPermission === "number"
      ? Math.max(0, funnel.authorizedForContext - funnel.authorizedAfterPermission)
      : null;
  const contextSummaryParts = [
    `Fusion 后 ${funnel.deduped} 条`,
    `Rerank 后 ${funnel.reranked ?? "-"} 条`,
    typeof correctiveAdded === "number" && correctiveAdded > 0 && typeof funnel.authorizedForContext === "number"
      ? `Corrective RAG 追加 ${correctiveAdded} 条，授权上下文 ${funnel.authorizedForContext} 条`
      : typeof funnel.authorizedForContext === "number"
        ? `授权上下文 ${funnel.authorizedForContext} 条`
        : null,
    funnel.expandedContext > 0 ? `chunkWindow 扩展 ${funnel.expandedContext} 条` : null,
    `生成上下文 ${funnel.finalContext} 条`,
    citedEvidenceIds.length > 0 ? `答案实际引用 ${citedEvidenceCount} 条` : `当前历史记录未提供句级引用，展示持久化 Citation/Evidence ${evidenceCount} 条`,
  ].filter(Boolean);

  return {
    status: statusToViewStatus(detail.status),
    answer: answerBlocks.map((block) => block.text),
    answerBlocks,
    runMeta: `${detail.runId} • ${detail.metrics.latencyMs ?? "-"} ms • rev ${detail.configRevisionId}`,
    rewrite: detail.rewrittenQuery || detail.query,
    rewriteTrace: toQARewriteTrace(detail),
    retrievalCards: [
      { channel: "Dense", summary: retrievalCardSummary(detail, diagnostics, "dense") },
      { channel: "Sparse", summary: retrievalCardSummary(detail, diagnostics, "sparse") },
      { channel: "Graph", summary: retrievalCardSummary(detail, diagnostics, "graph") },
    ],
    candidates: detail.candidates.map((candidate) => {
      const evidence = evidenceByCandidateId.get(candidate.candidateId);
      return {
        id: candidate.candidateId,
        source:
          candidate.sourceType === "mock"
            ? "Mock"
            : candidate.sourceType === "sparse"
              ? "Sparse"
              : candidate.sourceType === "graph"
                ? "Graph"
                : candidate.sourceType === "postgres"
                  ? "Postgres"
                  : "Dense",
        title: candidateTitle(candidate.metadata, candidate.chunkId ?? candidate.candidateId),
        score: candidateScore(candidate),
        decision: candidateDecision(candidate, evidenceIndexByCandidateId.get(candidate.candidateId)),
        snippet:
          readString(candidate.metadata, "contentPreview") ??
          evidence?.contentSnapshot ??
          readString(candidate.metadata, "section") ??
          undefined,
      };
    }),
    citations: citationRows.map((citation, index) => {
      const evidence = evidenceById.get(citation.evidenceId);
      const location = citation.locationSnapshot;
      const sourceSnapshot = evidence?.sourceSnapshot ?? {};
      const documentName = readString(location, "documentName");
      const chunkIndex = typeof location.chunkIndex === "number" ? `#${location.chunkIndex}` : null;
      const section = readString(location, "sectionPath") ?? readString(location, "section");
      const chunkRevisionId = readChunkRevisionId(location, sourceSnapshot);
      const parseRevisionId = readString(location, "parseRevisionId") ?? readString(sourceSnapshot, "parseRevisionId");
      const sourceModality = readString(location, "sourceModality") ?? readString(sourceSnapshot, "sourceModality");
      return {
        id: String(index + 1),
        evidenceId: citation.evidenceId,
        type: "document",
        title: [citation.label || "Citation", documentName, chunkIndex].filter(Boolean).join(" · "),
        snippet: evidence?.contentSnapshot || "当前证据策略未返回正文快照。",
        meta: [
          `Evidence ID: ${citation.evidenceId}`,
          chunkRevisionId ? `BR: ${chunkRevisionId.slice(0, 8)}` : null,
          parseRevisionId ? `PR: ${parseRevisionId.slice(0, 8)}` : null,
          section ? `Section: ${section}` : null,
        ].filter(Boolean).join(" | "),
        documentId: readString(location, "documentId"),
        chunkId: readString(location, "chunkId") ?? evidence?.chunkId ?? null,
        sourceModality,
        sourceFileId: readString(location, "sourceFileId") ?? readString(sourceSnapshot, "sourceFileId"),
        region: readString(location, "region") ?? readString(sourceSnapshot, "region"),
        visionConfidence: readString(sourceSnapshot, "visionConfidence"),
      };
    }),
    diagnostics: {
      recalled: String(funnel.recalled),
      deduped: String(funnel.deduped),
      filtered: String(funnel.droppedByPermission),
      finalContext: String(funnel.finalContext),
      rerankSummary: contextSummaryParts.join("；") + "。",
    },
    partialDiagnostics: deriveQAPartialDiagnostics(detail),
  };
}

export function toQAHistoryRecord(run: QARunListItemDTO): QAHistoryRecordViewModel {
  return {
    id: run.runId,
    sourceRunId: run.sourceRunId,
    query: run.query,
    status: statusToViewStatus(run.status),
    user: run.createdBy || "dev-user",
    userName: run.createdByName || run.createdBy || "未知用户",
    time: formatDateTime(run.createdAt),
    rev: `rev ${run.configRevisionId.slice(0, 8)}`,
    rating: feedbackToRating(run.feedbackStatus),
    feedbackStatus: run.feedbackStatus,
    hasOverrides: run.hasOverride,
    failureType: run.failureType || (run.status === "failed" ? "运行失败" : run.status === "partial" ? "部分降级" : "无"),
    answer: run.answer || "暂无回答。",
  };
}
