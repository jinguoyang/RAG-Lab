import { formatDateTime } from "./documentAdapter";
import type { GraphCommunityDTO, GraphPathDTO, GraphSnapshotDTO, GraphSupportingChunkDTO } from "../types/graph";

export interface GraphSnapshotViewModel {
  id: string;
  status: GraphSnapshotDTO["status"];
  statusLabel: string;
  countsLabel: string;
  updatedAtLabel: string;
  staleLabel: string | null;
  errorMessage: string | null;
}

const SNAPSHOT_STATUS_LABELS: Record<GraphSnapshotDTO["status"], string> = {
  queued: "排队中",
  running: "构建中",
  success: "可用",
  failed: "失败",
  stale: "已过期",
};

/**
 * 将后端图快照 DTO 转换为 P11 页面展示摘要，避免页面散落状态文案。
 */
export function toGraphSnapshotViewModel(snapshot: GraphSnapshotDTO): GraphSnapshotViewModel {
  const entityCount = snapshot.entityCount ?? 0;
  const relationCount = snapshot.relationCount ?? 0;
  const communityCount = snapshot.communityCount ?? 0;

  return {
    id: snapshot.graphSnapshotId,
    status: snapshot.status,
    statusLabel: SNAPSHOT_STATUS_LABELS[snapshot.status],
    countsLabel: `${entityCount.toLocaleString()} 实体 · ${relationCount.toLocaleString()} 关系 · ${communityCount.toLocaleString()} 社区`,
    updatedAtLabel: formatDateTime(snapshot.updatedAt),
    staleLabel: snapshot.staleReason ? `${snapshot.staleReason}${snapshot.staleAt ? ` · ${formatDateTime(snapshot.staleAt)}` : ""}` : null,
    errorMessage: snapshot.errorMessage,
  };
}

/**
 * 生成人可读路径描述，图结果本身不作为最终 Evidence。
 */
export function describePath(path: GraphPathDTO): string {
  return `${path.sourceEntity.name} --${path.relationType}--> ${path.targetEntity.name}`;
}

/**
 * 生成社区摘要描述，优先保留后端 summary，缺省时回退到实体数量。
 */
export function describeCommunity(community: GraphCommunityDTO): string {
  if (community.summary.trim()) {
    return community.summary;
  }
  return community.entityCount === null ? "暂无社区摘要。" : `包含 ${community.entityCount} 个实体。`;
}

/**
 * 生成支撑 Chunk 来源描述，只展示后端授权返回的预览和元数据。
 */
export function describeChunk(chunk: GraphSupportingChunkDTO): string {
  return `${chunk.documentName} · #${chunk.chunkIndex} · ${chunk.securityLevel}`;
}
