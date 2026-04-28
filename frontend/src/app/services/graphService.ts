import { apiGet } from "./apiClient";
import type {
  GraphCommunitySearchResponse,
  GraphEntitySearchResponse,
  GraphPathSearchResponse,
  GraphSnapshotDTO,
  GraphSnapshotPage,
  GraphSupportingChunksResponse,
} from "../types/graph";

export async function fetchGraphSnapshots(kbId: string): Promise<GraphSnapshotPage> {
  return apiGet<GraphSnapshotPage>(`/knowledge-bases/${kbId}/graph-snapshots?pageNo=1&pageSize=20`);
}

export async function fetchGraphSnapshot(kbId: string, graphSnapshotId: string): Promise<GraphSnapshotDTO> {
  return apiGet<GraphSnapshotDTO>(`/knowledge-bases/${kbId}/graph-snapshots/${graphSnapshotId}`);
}

export async function fetchGraphEntities(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string | null,
): Promise<GraphEntitySearchResponse> {
  const params = new URLSearchParams({ keyword, limit: "20" });
  if (graphSnapshotId) params.set("graphSnapshotId", graphSnapshotId);
  return apiGet<GraphEntitySearchResponse>(`/knowledge-bases/${kbId}/graph/entities?${params.toString()}`);
}

export async function fetchGraphPaths(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string | null,
): Promise<GraphPathSearchResponse> {
  const params = new URLSearchParams({ keyword, limit: "20" });
  if (graphSnapshotId) params.set("graphSnapshotId", graphSnapshotId);
  return apiGet<GraphPathSearchResponse>(`/knowledge-bases/${kbId}/graph/paths?${params.toString()}`);
}

export async function fetchGraphCommunities(
  kbId: string,
  keyword?: string,
  graphSnapshotId?: string | null,
): Promise<GraphCommunitySearchResponse> {
  const params = new URLSearchParams({ limit: "20" });
  if (keyword?.trim()) params.set("keyword", keyword.trim());
  if (graphSnapshotId) params.set("graphSnapshotId", graphSnapshotId);
  return apiGet<GraphCommunitySearchResponse>(`/knowledge-bases/${kbId}/graph/communities?${params.toString()}`);
}

export async function fetchGraphSupportingChunks(
  kbId: string,
  graphSnapshotId: string,
  supportKeys: Record<string, string | null>,
): Promise<GraphSupportingChunksResponse> {
  const params = new URLSearchParams({ graphSnapshotId });
  if (supportKeys.nodeKey) params.set("nodeKey", supportKeys.nodeKey);
  if (supportKeys.relationKey) params.set("relationKey", supportKeys.relationKey);
  if (supportKeys.communityKey) params.set("communityKey", supportKeys.communityKey);
  return apiGet<GraphSupportingChunksResponse>(`/knowledge-bases/${kbId}/graph/supporting-chunks?${params.toString()}`);
}
