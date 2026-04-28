import { apiGet } from "./apiClient";
import type {
  GraphCommunityDTO,
  GraphEntityDTO,
  GraphPage,
  GraphPathDTO,
  GraphSearchResponse,
  GraphSnapshotDTO,
  GraphSupportingChunksResponse,
} from "../types/graph";

interface SupportingChunkParams {
  nodeKey?: string;
  relationKey?: string;
  communityKey?: string;
}

function appendSnapshot(params: URLSearchParams, graphSnapshotId?: string): void {
  if (graphSnapshotId) {
    params.set("graphSnapshotId", graphSnapshotId);
  }
}

/**
 * 读取知识库图快照列表，默认依赖后端更新时间倒序返回最新快照。
 */
export async function fetchGraphSnapshots(kbId: string): Promise<GraphPage<GraphSnapshotDTO>> {
  const params = new URLSearchParams({ pageNo: "1", pageSize: "20" });
  return apiGet<GraphPage<GraphSnapshotDTO>>(`/knowledge-bases/${kbId}/graph-snapshots?${params.toString()}`);
}

/**
 * 按关键词搜索图实体；正文证据仍必须通过支撑 Chunk 接口回落。
 */
export async function searchGraphEntities(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string,
): Promise<GraphSearchResponse<GraphEntityDTO>> {
  const params = new URLSearchParams({ keyword: keyword.trim(), limit: "20" });
  appendSnapshot(params, graphSnapshotId);
  return apiGet<GraphSearchResponse<GraphEntityDTO>>(`/knowledge-bases/${kbId}/graph/entities?${params.toString()}`);
}

/**
 * 按关键词搜索关系路径摘要，页面只消费摘要和后端诊断信息。
 */
export async function searchGraphPaths(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string,
): Promise<GraphSearchResponse<GraphPathDTO>> {
  const params = new URLSearchParams({ keyword: keyword.trim(), limit: "20" });
  appendSnapshot(params, graphSnapshotId);
  return apiGet<GraphSearchResponse<GraphPathDTO>>(`/knowledge-bases/${kbId}/graph/paths?${params.toString()}`);
}

/**
 * 按关键词搜索社区摘要；空结果和 Provider 降级由后端 diagnostics 区分。
 */
export async function searchGraphCommunities(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string,
): Promise<GraphSearchResponse<GraphCommunityDTO>> {
  const params = new URLSearchParams({ keyword: keyword.trim(), limit: "20" });
  appendSnapshot(params, graphSnapshotId);
  return apiGet<GraphSearchResponse<GraphCommunityDTO>>(`/knowledge-bases/${kbId}/graph/communities?${params.toString()}`);
}

/**
 * 查询图对象的授权支撑 Chunk，权限裁剪数量完全以后端 filteredCount 为准。
 */
export async function fetchGraphSupportingChunks(
  kbId: string,
  graphSnapshotId: string,
  { nodeKey, relationKey, communityKey }: SupportingChunkParams,
): Promise<GraphSupportingChunksResponse> {
  const params = new URLSearchParams({ graphSnapshotId });
  if (nodeKey) params.set("nodeKey", nodeKey);
  if (relationKey) params.set("relationKey", relationKey);
  if (communityKey) params.set("communityKey", communityKey);

  return apiGet<GraphSupportingChunksResponse>(`/knowledge-bases/${kbId}/graph/supporting-chunks?${params.toString()}`);
}
