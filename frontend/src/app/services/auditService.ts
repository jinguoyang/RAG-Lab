import { apiGet } from "./apiClient";
import type { AuditLogPage } from "../types/audit";

interface FetchAuditLogsParams {
  kbId?: string;
  keyword?: string;
  pageSize?: number;
}

export async function fetchAuditLogs({
  kbId,
  keyword,
  pageSize = 20,
}: FetchAuditLogsParams = {}): Promise<AuditLogPage> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: String(pageSize) });
  if (kbId) {
    params.set("kbId", kbId);
  }
  if (keyword?.trim()) {
    params.set("keyword", keyword.trim());
  }

  return apiGet<AuditLogPage>(`/audit-logs?${params.toString()}`);
}
