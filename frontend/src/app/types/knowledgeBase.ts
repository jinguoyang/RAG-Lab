export interface KnowledgeBase {
  kbId: string;
  name: string;
  description: string | null;
  ownerId: string;
  defaultSecurityLevel: string;
  sparseIndexEnabled: boolean;
  graphIndexEnabled: boolean;
  requiredForActivation: {
    dense: boolean;
    sparse: boolean;
    graph: boolean;
  };
  status: "draft" | "active" | "disabled" | "archived";
  activeConfigRevisionId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeBaseCardViewModel {
  id: string;
  name: string;
  description: string;
  status: "active" | "inactive";
  updatedAtLabel: string;
  retrievalSummary: string;
}

export interface PageResponse<T> {
  items: T[];
  pageNo: number;
  pageSize: number;
  total: number;
}

export type KbMemberSubjectType = "user" | "group";
export type KbRole = "kb_owner" | "kb_editor" | "kb_operator" | "kb_viewer";

export interface KbMemberBinding {
  bindingId: string;
  kbId: string;
  subjectType: KbMemberSubjectType;
  subjectId: string;
  subjectName: string;
  subjectStatus: string;
  kbRole: KbRole;
  status: "active" | "inactive";
  createdAt: string;
  updatedAt: string;
}

export interface KbMemberSubjectOption {
  subjectType: KbMemberSubjectType;
  subjectId: string;
  label: string;
  secondaryText: string | null;
  status: string;
  isAlreadyBound: boolean;
}

export interface KbMemberCreateRequest {
  subjectType: KbMemberSubjectType;
  subjectId: string;
  kbRole: KbRole;
}

export interface KbMemberUpdateRequest {
  kbRole: KbRole;
}

export interface PermissionSummary {
  resourceType: string;
  resourceId: string;
  permissions: string[];
  deniedReasons: string[];
  roles: string[];
  subjectKeys: string[];
  inheritedFromPlatformRole: boolean;
}
