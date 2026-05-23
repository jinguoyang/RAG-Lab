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
  if (
    stage === "parse" ||
    stage === "embedding" ||
    stage === "dense_index" ||
    stage === "sparse_index" ||
    stage === "graph_extract" ||
    stage === "graph_index" ||
    stage === "index_sync"
  ) {
    return "running";
  }
  return "pending";
}

export function formatIndexStageStatus(status: IndexStageViewModel["status"]): string {
  const labels: Record<IndexStageViewModel["status"], string> = {
    not_required: "未启用",
    pending: "待处理",
    running: "处理中",
    success: "成功",
    failed: "失败",
  };
  return labels[status];
}

function normalizeIndexStageStatus(value: unknown, fallback: IndexStageViewModel["status"]): IndexStageViewModel["status"] {
  if (
    value === "not_required" ||
    value === "pending" ||
    value === "running" ||
    value === "success" ||
    value === "failed"
  ) {
    return value;
  }
  return fallback;
}

function readJobErrorSummary(job: IngestJobDTO): Record<string, { status?: unknown }> | null {
  const summary = job.resultSummary?.error_summary;
  if (typeof summary !== "object" || summary === null) {
    return null;
  }
  return summary as Record<string, { status?: unknown }>;
}

function readGraphExtractionErrorCount(job: IngestJobDTO): number {
  const errors = job.resultSummary?.graphExtractionErrors;
  return Array.isArray(errors) ? errors.length : 0;
}

function inferMissingReplicaStatus(job: IngestJobDTO, key: "milvus" | "opensearch" | "neo4j"): IndexStageViewModel["status"] {
  const message = (job.errorMessage || "").toLowerCase();
  if (message.includes(key)) {
    return "failed";
  }
  return "not_required";
}

function stageOrder(stage: string | null): number {
  const stages = ["queued", "parse", "embedding", "dense_index", "sparse_index", "graph_extract", "graph_index", "completed"];
  const normalized =
    stage === "index_sync"
      ? "dense_index"
      : stage === "milvus"
        ? "dense_index"
        : stage === "opensearch"
          ? "sparse_index"
          : stage || "queued";
  const index = stages.indexOf(normalized);
  return index >= 0 ? index : 0;
}

function statusByCurrentStage(job: IngestJobDTO, stageKey: IndexStageViewModel["key"]): IndexStageViewModel["status"] {
  if (job.status === "success") {
    return "success";
  }
  if (job.status === "failed") {
    return job.stage === stageKey ? "failed" : stageOrder(job.stage) > stageOrder(stageKey) ? "success" : "pending";
  }
  const currentOrder = stageOrder(job.stage);
  const targetOrder = stageOrder(stageKey);
  if (currentOrder > targetOrder) {
    return "success";
  }
  if (currentOrder === targetOrder) {
    return "running";
  }
  return "pending";
}

function toJobIndexStages(job: IngestJobDTO): IndexStageViewModel[] {
  const derivedStatus = jobStatusToIndexStatus(job.status, job.stage);
  const errorSummary = readJobErrorSummary(job);
  if (errorSummary) {
    return [
      { key: "parse", label: "解析", status: normalizeIndexStageStatus(errorSummary.parse?.status, derivedStatus) },
      { key: "embedding", label: "Embedding", status: normalizeIndexStageStatus(errorSummary.embedding?.status, derivedStatus) },
      { key: "milvus", label: "Milvus", status: normalizeIndexStageStatus(errorSummary.milvus?.status, inferMissingReplicaStatus(job, "milvus")) },
      { key: "opensearch", label: "OpenSearch", status: normalizeIndexStageStatus(errorSummary.opensearch?.status, inferMissingReplicaStatus(job, "opensearch")) },
      { key: "graph_extract", label: "Graph 抽取", status: normalizeIndexStageStatus(errorSummary.neo4j?.status, inferMissingReplicaStatus(job, "neo4j")) },
      { key: "graph_index", label: "Neo4j", status: normalizeIndexStageStatus(errorSummary.neo4j?.status, inferMissingReplicaStatus(job, "neo4j")) },
    ];
  }

  return [
    { key: "parse", label: "解析", status: statusByCurrentStage(job, "parse") },
    { key: "embedding", label: "Embedding", status: statusByCurrentStage(job, "embedding") },
    { key: "milvus", label: "Milvus", status: statusByCurrentStage(job, "milvus") },
    { key: "opensearch", label: "OpenSearch", status: statusByCurrentStage(job, "opensearch") },
    { key: "graph_extract", label: "Graph 抽取", status: statusByCurrentStage(job, "graph_extract") },
    { key: "graph_index", label: "Neo4j", status: statusByCurrentStage(job, "graph_index") },
  ];
}

export function toDocumentRow(document: DocumentDTO): DocumentRowViewModel {
  return {
    id: document.documentId,
    name: document.name,
    status: document.status === "active" ? "success" : "cancelled",
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
      { key: "milvus", label: "Milvus", status: version.denseIndexStatus },
      { key: "opensearch", label: "OpenSearch", status: version.sparseIndexStatus },
      { key: "graph_index", label: "Neo4j", status: version.graphIndexStatus },
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
    graphExtractionErrorCount: readGraphExtractionErrorCount(job),
    indexStages: toJobIndexStages(job),
  };
}

export function toChunkView(chunk: ChunkDTO): ChunkViewModel {
  return {
    id: chunk.chunkId,
    indexLabel: `#${chunk.chunkIndex}`,
    pageLabel: chunk.pageNo ? `P${chunk.pageNo}` : "-",
    section: chunk.sectionPath || chunk.heading || chunk.section || "-",
    preview: (chunk.summary || chunk.content).length > 120 ? `${(chunk.summary || chunk.content).slice(0, 120)}...` : (chunk.summary || chunk.content),
    tokenCount: chunk.tokenCount,
    metadataText: JSON.stringify(chunk.metadata),
  };
}
