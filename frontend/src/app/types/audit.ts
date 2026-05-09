import type { PageResponse } from "./knowledgeBase";

export interface AuditLogDTO {
  auditLogId: string;
  actorId: string | null;
  action: string;
  resourceType: string;
  resourceId: string;
  kbId: string | null;
  documentId: string | null;
  detail: Record<string, unknown>;
  createdAt: string;
}

export type AuditLogPage = PageResponse<AuditLogDTO>;
