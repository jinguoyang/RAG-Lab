import { apiDelete, apiGet, apiPostJson } from "./apiClient";
import type {
  UserCreateRequest,
  UserGroupCreateRequest,
  UserGroupDetail,
  UserGroupPage,
  UserGroupSummary,
  UserPage,
  UserSummary,
} from "../types/userGroup";

interface PageParams {
  keyword?: string;
  pageNo?: number;
  pageSize?: number;
}

function buildPageQuery({ keyword, pageNo = 1, pageSize = 20 }: PageParams): string {
  const params = new URLSearchParams({ pageNo: String(pageNo), pageSize: String(pageSize) });
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }
  return params.toString();
}

export async function fetchUsers(params: PageParams = {}): Promise<UserPage> {
  return apiGet<UserPage>(`/users?${buildPageQuery(params)}`);
}

export async function createUser(request: UserCreateRequest): Promise<UserSummary> {
  return apiPostJson<UserSummary>("/users", request);
}

export async function disableUser(userId: string): Promise<UserSummary> {
  return apiPostJson<UserSummary>(`/users/${userId}/disable`, {});
}

export async function fetchUserGroups(params: PageParams = {}): Promise<UserGroupPage> {
  return apiGet<UserGroupPage>(`/groups?${buildPageQuery(params)}`);
}

export async function createUserGroup(request: UserGroupCreateRequest): Promise<UserGroupSummary> {
  return apiPostJson<UserGroupSummary>("/groups", request);
}

export async function fetchUserGroup(groupId: string): Promise<UserGroupDetail> {
  return apiGet<UserGroupDetail>(`/groups/${groupId}`);
}

export async function addUsersToGroup(groupId: string, userIds: string[]): Promise<UserGroupDetail> {
  return apiPostJson<UserGroupDetail>(`/groups/${groupId}/members`, { userIds });
}

export async function removeUserFromGroup(groupId: string, userId: string): Promise<void> {
  return apiDelete(`/groups/${groupId}/members/${userId}`);
}
