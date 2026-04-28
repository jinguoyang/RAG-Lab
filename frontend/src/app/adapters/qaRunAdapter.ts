import { formatDateTime } from "./documentAdapter";
import type { QARunDetailDTO, QARunListItemDTO } from "../types/qaRun";

export interface QADebugResultViewModel {
  status: "success" | "partial" | "failed";
  answer: string[];
  runMeta: string;
  notice?: { variant: "info" | "warning"; title: string; message: string };
  rewrite: string;
  retrievalCards: { channel: string; summary: string }[];
  candidates: {
    id: string;
    source: "Dense" | "Sparse" | "Graph" | "Mock" | "Postgres";
    title: string;
    score: string;
    decision: string;
  }[];
  citations: {
    id: string;
    type: "document" | "graph";
    title: string;
    snippet: string;
    meta: string;
  }[];
  diagnostics: {
    recalled: string;
    deduped: string;
    filtered: string;
    finalContext: string;
    rerankSummary: string;
  };
}

export interface QAHistoryRecordViewModel {
  id: string;
  query: string;
  status: "success" | "partial" | "failed";
  user: string;
  time: string;
  rev: string;
  rating: "up" | "down" | "none";
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

export function toQADebugResult(detail: QARunDetailDTO): QADebugResultViewModel {
  const diagnostics = detail.retrievalDiagnostics;
  const evidenceCount = detail.evidence.length;

  return {
    status: statusToViewStatus(detail.status),
    answer: detail.answer ? [detail.answer] : ["运行已创建，当前暂无回答。"],
    runMeta: `${detail.runId} • ${detail.metrics.latencyMs ?? "-"} ms • rev ${detail.configRevisionId}`,
    rewrite: detail.rewrittenQuery || detail.query,
    retrievalCards: [
      { channel: "Dense", summary: `${readNumber(diagnostics, "denseCount")} 条候选` },
      { channel: "Sparse", summary: `${readNumber(diagnostics, "sparseCount")} 条候选` },
      { channel: "Graph", summary: `${readNumber(diagnostics, "graphCount")} 条候选` },
    ],
    candidates: detail.candidates.map((candidate) => ({
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
      title: String(candidate.metadata.documentName ?? candidate.chunkId ?? candidate.candidateId),
      score: String(candidate.rerankScore ?? candidate.rawScore ?? "-"),
      decision: candidate.isAuthorized ? "保留，已进入候选诊断" : candidate.dropReason || "权限裁剪",
    })),
    citations: detail.citations.map((citation, index) => {
      const evidence = detail.evidence.find((item) => item.evidenceId === citation.evidenceId);
      return {
        id: String(index + 1),
        type: "document",
        title: citation.label || "Citation",
        snippet: evidence?.contentSnapshot || "当前证据策略未返回正文快照。",
        meta: `Evidence ID: ${citation.evidenceId}`,
      };
    }),
    diagnostics: {
      recalled: String(detail.candidates.length),
      deduped: String(detail.candidates.length),
      filtered: `-${readNumber(diagnostics, "droppedByPermission")}`,
      finalContext: String(evidenceCount),
      rerankSummary: "当前结果来自后端 QARun 详情，Trace / Candidate / Evidence / Citation 已持久化。",
    },
  };
}

export function toQAHistoryRecord(run: QARunListItemDTO): QAHistoryRecordViewModel {
  return {
    id: run.runId,
    query: run.query,
    status: statusToViewStatus(run.status),
    user: run.createdBy || "dev-user",
    time: formatDateTime(run.createdAt),
    rev: `rev ${run.configRevisionId.slice(0, 8)}`,
    rating: feedbackToRating(run.feedbackStatus),
    hasOverrides: run.hasOverride,
    failureType: run.failureType || (run.status === "failed" ? "运行失败" : run.status === "partial" ? "部分降级" : "无"),
    answer: run.answer || "暂无回答。",
  };
}
