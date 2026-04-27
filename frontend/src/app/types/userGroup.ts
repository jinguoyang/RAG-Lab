import type { PageResponse } from "./knowledgeBase";

export type PlatformRole = "platform_admin" | "platform_user";
export type UserStatus = "active" | "disabled";
export type GroupStatus = "active" | "disabled";

export interface UserSummary {
  userId: string;
  username: string;
  displayName: string;
  email: string | null;
  platformRole: PlatformRole;
  securityLevel: string;
  status: UserStatus;
  createdAt: string;
  updatedAt: string;
}

export interface UserCreateRequest {
  username: string;
  displayName: string;
  email?: string | null;
  platformRole: PlatformRole;
  securityLevel: string;
}

export interface UserUpdateRequest {
  displayName?: string;
  email?: string | null;
  platformRole?: PlatformRole;
  securityLevel?: string;
  status?: UserStatus;
}

export interface UserGroupSummary {
  groupId: string;
  name: string;
  description: string | null;
  memberCount: number;
  status: GroupStatus;
  createdAt: string;
  updatedAt: string;
}

export interface GroupMember {
  groupMemberId: string;
  userId: string;
  username: string;
  displayName: string;
  email: string | null;
  status: UserStatus;
  joinedAt: string;
}

export interface UserGroupDetail extends UserGroupSummary {
  members: GroupMember[];
}

export interface UserGroupCreateRequest {
  name: string;
  description?: string | null;
}

export interface UserGroupUpdateRequest {
  name?: string;
  description?: string | null;
  status?: GroupStatus;
}

export type UserPage = PageResponse<UserSummary>;
export type UserGroupPage = PageResponse<UserGroupSummary>;
