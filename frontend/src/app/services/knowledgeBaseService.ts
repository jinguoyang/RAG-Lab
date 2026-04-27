import { apiDelete, apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import type {
  KbMemberBinding,
  KbMemberCreateRequest,
  KbMemberUpdateRequest,
  KnowledgeBase,
  PageResponse,
  PermissionSummary,
} from "../types/knowledgeBase";

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

export async function fetchKbMembers(kbId: string, keyword?: string): Promise<PageResponse<KbMemberBinding>> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: "100" });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }

  return apiGet<PageResponse<KbMemberBinding>>(`/knowledge-bases/${kbId}/members?${params.toString()}`);
}

export async function fetchKbPermissionSummary(kbId: string): Promise<PermissionSummary> {
  return apiGet<PermissionSummary>(`/knowledge-bases/${kbId}/permissions/summary`);
}

export async function createKbMember(kbId: string, request: KbMemberCreateRequest): Promise<KbMemberBinding> {
  return apiPostJson<KbMemberBinding>(`/knowledge-bases/${kbId}/members`, request);
}

export async function updateKbMemberRole(
  kbId: string,
  bindingId: string,
  request: KbMemberUpdateRequest,
): Promise<KbMemberBinding> {
  return apiPatchJson<KbMemberBinding>(`/knowledge-bases/${kbId}/members/${bindingId}`, request);
}

export async function deleteKbMember(kbId: string, bindingId: string): Promise<void> {
  return apiDelete(`/knowledge-bases/${kbId}/members/${bindingId}`);
}
