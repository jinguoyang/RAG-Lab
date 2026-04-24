import type { KnowledgeBase, KnowledgeBaseCardViewModel } from "../types/knowledgeBase";

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function buildRetrievalSummary(kb: KnowledgeBase): string {
  const channels = ["Dense"];
  if (kb.sparseIndexEnabled) {
    channels.push("Sparse");
  }
  if (kb.graphIndexEnabled) {
    channels.push("Graph");
  }

  return channels.join(" + ");
}

export function toKnowledgeBaseCard(kb: KnowledgeBase): KnowledgeBaseCardViewModel {
  return {
    id: kb.kbId,
    name: kb.name,
    description: kb.description || "暂无描述",
    status: kb.status === "active" ? "active" : "inactive",
    updatedAtLabel: formatDateTime(kb.updatedAt),
    retrievalSummary: buildRetrievalSummary(kb),
  };
}
