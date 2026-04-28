import { formatDateTime } from "./documentAdapter";
import type {
  GraphCommunityDTO,
  GraphEntityDTO,
  GraphPathDTO,
  GraphSnapshotDTO,
  GraphSupportingChunkDTO,
} from "../types/graph";

export interface GraphAnalysisViewModel {
  snapshotId: string | null;
  snapshotStatus: "success" | "failed" | "running" | "queued" | "partial";
  entityCount: string;
  relationCount: string;
  communityCount: string;
  updatedAt: string;
  staleReason: string | null;
}

export interface GraphResultViewModel {
  id: string;
  kind: "entity" | "path" | "community";
  title: string;
  subtitle: string;
  supportKeys: Record<string, string | null>;
}

export interface GraphChunkViewModel {
  id: string;
  documentName: string;
  location: string;
  preview: string;
  securityLevel: string;
}

function compactNumber(value: number | null): string {
  return value == null ? "-" : value.toLocaleString("zh-CN");
}

function toStatus(status: string): GraphAnalysisViewModel["snapshotStatus"] {
  if (status === "failed") return "failed";
  if (status === "running") return "running";
  if (status === "queued") return "queued";
  if (status === "stale") return "partial";
  return "success";
}

export function toGraphAnalysisView(snapshot: GraphSnapshotDTO | null): GraphAnalysisViewModel {
  return {
    snapshotId: snapshot?.graphSnapshotId ?? null,
    snapshotStatus: toStatus(snapshot?.status ?? "queued"),
    entityCount: compactNumber(snapshot?.entityCount ?? null),
    relationCount: compactNumber(snapshot?.relationCount ?? null),
    communityCount: compactNumber(snapshot?.communityCount ?? null),
    updatedAt: snapshot ? formatDateTime(snapshot.updatedAt) : "-",
    staleReason: snapshot?.staleReason ?? null,
  };
}

export function entityToResult(entity: GraphEntityDTO): GraphResultViewModel {
  return {
    id: entity.entityKey || entity.name,
    kind: "entity",
    title: entity.name,
    subtitle: entity.type || "Entity",
    supportKeys: { nodeKey: entity.entityKey, relationKey: null, communityKey: null },
  };
}

export function pathToResult(path: GraphPathDTO): GraphResultViewModel {
  return {
    id: path.pathKey,
    kind: "path",
    title: `${path.sourceEntity.name} -> ${path.targetEntity.name}`,
    subtitle: `${path.relationType} · ${path.hopCount} hop`,
    supportKeys: path.supportKeys,
  };
}

export function communityToResult(community: GraphCommunityDTO): GraphResultViewModel {
  return {
    id: community.communityKey,
    kind: "community",
    title: community.title,
    subtitle: `${community.entityCount ?? 0} entities · ${community.summary || "无摘要"}`,
    supportKeys: community.supportKeys,
  };
}

export function chunkToViewModel(chunk: GraphSupportingChunkDTO): GraphChunkViewModel {
  return {
    id: chunk.chunkId,
    documentName: chunk.documentName,
    location: `chunk ${chunk.chunkIndex}`,
    preview: chunk.contentPreview,
    securityLevel: chunk.securityLevel,
  };
}
