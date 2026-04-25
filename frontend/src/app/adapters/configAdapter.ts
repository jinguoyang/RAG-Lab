import { formatDateTime } from "./documentAdapter";
import type {
  ConfigRevisionDTO,
  ConfigRevisionStatus,
  RevisionRecordViewModel,
} from "../types/config";

function revisionStatusToViewStatus(
  status: ConfigRevisionStatus,
): RevisionRecordViewModel["status"] {
  if (status === "active") return "active";
  if (status === "invalid") return "failed";
  if (status === "archived") return "inactive";
  return "queued";
}

export function toRevisionRecord(revision: ConfigRevisionDTO): RevisionRecordViewModel {
  return {
    id: revision.configRevisionId,
    revisionNo: `rev_${String(revision.revisionNo).padStart(3, "0")}`,
    createdBy: "current_user",
    createdAt: formatDateTime(revision.createdAt),
    note: revision.remark || "未填写保存说明",
    status: revisionStatusToViewStatus(revision.status),
    active: revision.status === "active",
  };
}
