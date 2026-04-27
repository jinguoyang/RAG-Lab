import { apiDelete, apiGet, apiPatchJson, apiPostJson } from "./apiClient";
import type {
  KbMemberBinding,
  KbMemberCreateRequest,
  KbMemberSubjectOption,
  KbMemberUpdateRequest,
  KnowledgeBase,
  PageResponse,
  PermissionSummary,
  KbRole,
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

interface FetchKbMembersParams {
  keyword?: string;
  pageNo?: number;
  pageSize?: number;
  kbRole?: KbRole | "";
}

export async function fetchKbMembers(
  kbId: string,
  { keyword, pageNo = 1, pageSize = 20, kbRole }: FetchKbMembersParams = {},
): Promise<PageResponse<KbMemberBinding>> {
  const params = new URLSearchParams({ pageNo: String(pageNo), pageSize: String(pageSize) });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }
  if (kbRole) {
    params.set("kbRole", kbRole);
  }

  return apiGet<PageResponse<KbMemberBinding>>(`/knowledge-bases/${kbId}/members?${params.toString()}`);
}

export async function searchKbMemberSubjects(
  kbId: string,
  subjectType: "user" | "group",
  keyword?: string,
): Promise<KbMemberSubjectOption[]> {
  const params = new URLSearchParams({ subjectType, limit: "8" });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }

  return apiGet<KbMemberSubjectOption[]>(`/knowledge-bases/${kbId}/member-subjects/search?${params.toString()}`);
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
