import type {
  DocumentDTO,
  DocumentRowViewModel,
  DocumentVersionDTO,
  IngestJobDTO,
  IngestJobViewModel,
  JobStatus,
  VersionRowViewModel,
  VersionStatus,
} from "../types/document";

export function formatDateTime(value: string): string {
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

export function versionStatusToBadgeStatus(status: VersionStatus): JobStatus {
  if (status === "failed") {
    return "failed";
  }
  if (status === "processing") {
    return "running";
  }
  return "success";
}

export function toDocumentRow(document: DocumentDTO): DocumentRowViewModel {
  return {
    id: document.documentId,
    name: document.name,
    activeVersionLabel: document.activeVersionId ? "v?" : "未生成",
    status: document.status === "active" ? "success" : "cancelled",
    securityLevel: document.securityLevel,
    updatedAtLabel: formatDateTime(document.updatedAt),
    sourceType: document.sourceType,
  };
}

export function toVersionRow(
  version: DocumentVersionDTO,
  activeVersionId: string | null,
): VersionRowViewModel {
  return {
    id: version.versionId,
    versionNo: `v${version.versionNo}`,
    status: versionStatusToBadgeStatus(version.status),
    parseStatusLabel: version.parseStatus,
    chunkCount: version.chunkCount,
    retrievalReadyLabel: version.retrievalReady ? "已就绪" : "未就绪",
    createdAtLabel: formatDateTime(version.createdAt),
    active: version.versionId === activeVersionId,
  };
}

export function toIngestJobView(job: IngestJobDTO): IngestJobViewModel {
  return {
    id: job.jobId,
    documentId: job.documentId,
    versionId: job.versionId,
    status: job.status,
    stage: job.stage || "queued",
    progress: job.progress,
    createdAtLabel: formatDateTime(job.createdAt),
    errorMessage: job.errorMessage || "-",
  };
}
