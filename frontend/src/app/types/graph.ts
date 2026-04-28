export type GraphSnapshotStatus = "queued" | "running" | "success" | "failed" | "stale";

export interface GraphQueryDiagnosticsDTO {
  degraded: boolean;
  degradedReason: string | null;
  provider: string;
}

export interface GraphSnapshotDTO {
  graphSnapshotId: string;
  kbId: string;
  status: GraphSnapshotStatus;
  sourceScope: Record<string, unknown>;
  neo4jGraphKey: string | null;
  staleReason: string | null;
  staleAt: string | null;
  entityCount: number | null;
  relationCount: number | null;
  communityCount: number | null;
  jobId: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GraphEntityDTO {
  entityKey: string | null;
  name: string;
  type: string | null;
  aliases: string[] | null;
  metadata: Record<string, unknown>;
}

export interface GraphPathDTO {
  pathKey: string;
  sourceEntity: GraphEntityDTO;
  targetEntity: GraphEntityDTO;
  relationType: string;
  hopCount: number;
  supportKeys: Record<string, string | null>;
  metadata: Record<string, unknown>;
}

export interface GraphCommunityDTO {
  communityKey: string;
  title: string;
  summary: string;
  entityCount: number | null;
  supportKeys: Record<string, string | null>;
  metadata: Record<string, unknown>;
}

export interface GraphSupportingChunkDTO {
  chunkId: string;
  documentId: string;
  documentName: string;
  chunkIndex: number;
  contentPreview: string;
  securityLevel: string;
  refType: string;
  metadata: Record<string, unknown>;
}

export interface GraphPage<T> {
  items: T[];
  pageNo: number;
  pageSize: number;
  total: number;
}

export interface GraphSearchResponse<T> {
  items: T[];
  graphSnapshotId: string | null;
  diagnostics?: GraphQueryDiagnosticsDTO;
}

export interface GraphSupportingChunksResponse {
  items: GraphSupportingChunkDTO[];
  filteredCount: number;
}
