import { apiGet } from "./apiClient";
import type { KnowledgeBase, PageResponse } from "../types/knowledgeBase";

export async function fetchKnowledgeBases(keyword?: string): Promise<PageResponse<KnowledgeBase>> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: "50" });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }

  return apiGet<PageResponse<KnowledgeBase>>(`/knowledge-bases?${params.toString()}`);
}

export async function fetchKnowledgeBase(kbId: string): Promise<KnowledgeBase> {
  return apiGet<KnowledgeBase>(`/knowledge-bases/${kbId}`);
}
