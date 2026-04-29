import type {
  ChunkDTO,
  ChunkViewModel,
  DocumentDTO,
  DocumentRowViewModel,
  DocumentVersionDTO,
  IngestJobDTO,
  IngestJobViewModel,
  IndexStageViewModel,
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

function jobStatusToIndexStatus(status: JobStatus, stage: string | null): IndexStageViewModel["status"] {
  if (status === "failed") {
    return "failed";
  }
  if (status === "success") {
    return "success";
  }
  if (stage === "parse" || stage === "embedding" || stage === "index_sync") {
    return "running";
  }
  return "pending";
}

function toJobIndexStages(job: IngestJobDTO): IndexStageViewModel[] {
  const derivedStatus = jobStatusToIndexStatus(job.status, job.stage);
  return [
    { key: "parse", label: "parse", status: job.stage === "queued" ? "pending" : derivedStatus },
    { key: "embedding", label: "embedding", status: job.stage === "parse" ? "pending" : derivedStatus },
    { key: "milvus", label: "milvus", status: job.stage === "index_sync" ? derivedStatus : job.status === "success" ? "success" : "pending" },
    { key: "opensearch", label: "opensearch", status: job.stage === "index_sync" ? derivedStatus : job.status === "success" ? "success" : "pending" },
    { key: "neo4j", label: "neo4j", status: job.stage === "index_sync" ? derivedStatus : job.status === "success" ? "success" : "pending" },
  ];
}

export function toDocumentRow(document: DocumentDTO): DocumentRowViewModel {
  return {
    id: document.documentId,
    name: document.name,
    status: document.status === "active" ? "success" : "cancelled",
    securityLevel: document.securityLevel,
    updatedAtLabel: formatDateTime(document.updatedAt),
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
    indexStages: [
      { key: "parse", label: "parse", status: version.parseStatus },
      { key: "embedding", label: "embedding", status: version.denseIndexStatus === "success" ? "success" : version.denseIndexStatus },
      { key: "milvus", label: "milvus", status: version.denseIndexStatus },
      { key: "opensearch", label: "opensearch", status: version.sparseIndexStatus },
      { key: "neo4j", label: "neo4j", status: version.graphIndexStatus },
    ],
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
    indexStages: toJobIndexStages(job),
  };
}

export function toChunkView(chunk: ChunkDTO): ChunkViewModel {
  return {
    id: chunk.chunkId,
    indexLabel: `#${chunk.chunkIndex}`,
    pageLabel: chunk.pageNo ? `P${chunk.pageNo}` : "-",
    section: chunk.section || "-",
    preview: chunk.content.length > 120 ? `${chunk.content.slice(0, 120)}...` : chunk.content,
    tokenCount: chunk.tokenCount,
    metadataText: JSON.stringify(chunk.metadata),
  };
}
