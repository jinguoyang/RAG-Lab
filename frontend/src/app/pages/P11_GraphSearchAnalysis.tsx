import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useParams } from "react-router";
import { Boxes, FileWarning, GitBranch, Info, Loader2, Network, Search, Waypoints } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import {
  describeChunk,
  describeCommunity,
  describePath,
  toGraphSnapshotViewModel,
} from "../adapters/graphAdapter";
import {
  fetchGraphSnapshots,
  fetchGraphSupportingChunks,
  searchGraphCommunities,
  searchGraphEntities,
  searchGraphPaths,
} from "../services/graphService";
import type {
  GraphCommunityDTO,
  GraphEntityDTO,
  GraphPathDTO,
  GraphQueryDiagnosticsDTO,
  GraphSnapshotDTO,
  GraphSupportingChunkDTO,
} from "../types/graph";

type SupportTarget =
  | { type: "entity"; label: string; nodeKey: string }
  | { type: "path"; label: string; relationKey: string }
  | { type: "community"; label: string; communityKey: string };

function snapshotBadgeVariant(status: GraphSnapshotDTO["status"]): "default" | "success" | "error" | "warning" | "info" | "running" {
  if (status === "success") return "success";
  if (status === "failed") return "error";
  if (status === "stale") return "warning";
  if (status === "running") return "running";
  if (status === "queued") return "info";
  return "default";
}

/**
 * P11 图检索分析页接入真实 Graph API。
 * 页面只展示后端返回的图摘要和 filteredCount，不在前端推断权限结果。
 */
export function GraphSearchAnalysis() {
  const { kbId = "" } = useParams();
  const [snapshots, setSnapshots] = useState<GraphSnapshotDTO[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState("");
  const [activeGraphSnapshotId, setActiveGraphSnapshotId] = useState("");
  const [keyword, setKeyword] = useState("");
  const [entities, setEntities] = useState<GraphEntityDTO[]>([]);
  const [paths, setPaths] = useState<GraphPathDTO[]>([]);
  const [communities, setCommunities] = useState<GraphCommunityDTO[]>([]);
  const [diagnostics, setDiagnostics] = useState<GraphQueryDiagnosticsDTO[]>([]);
  const [supportingChunks, setSupportingChunks] = useState<GraphSupportingChunkDTO[]>([]);
  const [filteredCount, setFilteredCount] = useState(0);
  const [selectedTargetLabel, setSelectedTargetLabel] = useState("");
  const [loadingSnapshots, setLoadingSnapshots] = useState(false);
  const [searching, setSearching] = useState(false);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedSnapshot = useMemo(
    () => snapshots.find((snapshot) => snapshot.graphSnapshotId === selectedSnapshotId) ?? null,
    [selectedSnapshotId, snapshots],
  );
  const snapshotViews = useMemo(() => snapshots.map(toGraphSnapshotViewModel), [snapshots]);
  const selectedSnapshotView = selectedSnapshot ? toGraphSnapshotViewModel(selectedSnapshot) : null;
  const degradedDiagnostics = diagnostics.filter((item) => item.degradedReason);
  const hasSearchResults = entities.length > 0 || paths.length > 0 || communities.length > 0;

  async function loadSnapshots() {
    if (!kbId) return;
    setLoadingSnapshots(true);
    setErrorMessage(null);
    try {
      const page = await fetchGraphSnapshots(kbId);
      setSnapshots(page.items);
      const latestSnapshot = page.items[0];
      setSelectedSnapshotId(latestSnapshot?.graphSnapshotId ?? "");
      setActiveGraphSnapshotId(latestSnapshot?.graphSnapshotId ?? "");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "图快照加载失败，请检查后端服务。");
    } finally {
      setLoadingSnapshots(false);
    }
  }

  useEffect(() => {
    setEntities([]);
    setPaths([]);
    setCommunities([]);
    setSupportingChunks([]);
    setFilteredCount(0);
    setSelectedTargetLabel("");
    void loadSnapshots();
  }, [kbId]);

  async function handleSearch() {
    const query = keyword.trim();
    if (!query) {
      setErrorMessage("请输入实体、关系或社区关键词。");
      return;
    }

    setSearching(true);
    setErrorMessage(null);
    setSupportingChunks([]);
    setFilteredCount(0);
    setSelectedTargetLabel("");
    try {
      const [entityResponse, pathResponse, communityResponse] = await Promise.all([
        searchGraphEntities(kbId, query, selectedSnapshotId || undefined),
        searchGraphPaths(kbId, query, selectedSnapshotId || undefined),
        searchGraphCommunities(kbId, query, selectedSnapshotId || undefined),
      ]);
      setEntities(entityResponse.items);
      setPaths(pathResponse.items);
      setCommunities(communityResponse.items);
      setDiagnostics([pathResponse.diagnostics, communityResponse.diagnostics].filter(Boolean) as GraphQueryDiagnosticsDTO[]);

      const responseSnapshotId = entityResponse.graphSnapshotId || pathResponse.graphSnapshotId || communityResponse.graphSnapshotId || "";
      setActiveGraphSnapshotId(selectedSnapshotId || responseSnapshotId);
      if (!selectedSnapshotId && responseSnapshotId) {
        setSelectedSnapshotId(responseSnapshotId);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "图查询失败，请稍后重试。");
    } finally {
      setSearching(false);
    }
  }

  async function loadSupportingChunks(target: SupportTarget) {
    const graphSnapshotId = activeGraphSnapshotId || selectedSnapshotId;
    if (!graphSnapshotId) {
      setErrorMessage("请先选择或查询到一个图快照，再查看支撑 Chunk。");
      return;
    }

    setLoadingChunks(true);
    setErrorMessage(null);
    setSelectedTargetLabel(target.label);
    try {
      const response = await fetchGraphSupportingChunks(kbId, graphSnapshotId, {
        nodeKey: target.type === "entity" ? target.nodeKey : undefined,
        relationKey: target.type === "path" ? target.relationKey : undefined,
        communityKey: target.type === "community" ? target.communityKey : undefined,
      });
      setSupportingChunks(response.items);
      setFilteredCount(response.filteredCount);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "支撑 Chunk 加载失败，请检查 Chunk 读取权限。");
    } finally {
      setLoadingChunks(false);
    }
  }

  const resultCountLabel = searching
    ? "查询中..."
    : `${entities.length} 实体 · ${paths.length} 路径 · ${communities.length} 社区`;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="图谱检索分析"
        description="查看图快照、实体路径、社区摘要和授权支撑 Chunk 回落情况。"
        actions={
          <Button variant="outline" disabled={loadingSnapshots} onClick={() => void loadSnapshots()}>
            <Network className="w-4 h-4 mr-2" /> {loadingSnapshots ? "同步中..." : "刷新图谱状态"}
          </Button>
        }
      />

      {errorMessage && (
        <Alert variant="error" title="图谱分析请求失败" onClose={() => setErrorMessage(null)}>
          {errorMessage}
        </Alert>
      )}

      {selectedSnapshot?.status === "stale" && (
        <Alert variant="warning" title="当前图快照已过期">
          {selectedSnapshotView?.staleLabel ?? "后端已标记该图快照不再代表当前检索真值，请结合最新文档版本判断。"}
        </Alert>
      )}

      {degradedDiagnostics.map((item, index) => (
        <Alert key={`${item.provider}-${index}`} variant="info" title="图查询已降级">
          {item.degradedReason}
        </Alert>
      ))}

      {filteredCount > 0 && (
        <Alert variant="permission" title="部分支撑 Chunk 已被权限裁剪">
          后端返回 filteredCount = {filteredCount}，页面不会展示未授权 Chunk 正文或来源。
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[340px_minmax(0,1fr)] gap-6 flex-1 min-h-0">
        <div className="space-y-4 flex flex-col min-h-0">
          <Card className="shrink-0">
            <CardHeader>
              <CardTitle>图查询</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Input
                label="关键词"
                placeholder="例如：Supplier B、Aurora、权限过滤"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void handleSearch();
                }}
              />
              <div className="space-y-2">
                <label className="text-sm font-medium text-near-black">图快照</label>
                <select
                  className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-[10px] text-sm text-near-black focus:outline-none focus:ring-2 focus:ring-focus-blue"
                  value={selectedSnapshotId}
                  onChange={(event) => {
                    setSelectedSnapshotId(event.target.value);
                    setActiveGraphSnapshotId(event.target.value);
                  }}
                >
                  {snapshots.length === 0 ? (
                    <option value="">暂无可选快照</option>
                  ) : (
                    snapshotViews.map((snapshot) => (
                      <option key={snapshot.id} value={snapshot.id}>
                        {snapshot.statusLabel} · {snapshot.updatedAtLabel}
                      </option>
                    ))
                  )}
                </select>
              </div>
              <Button variant="primary" className="w-full" disabled={searching || !kbId} onClick={() => void handleSearch()}>
                <Search className="w-4 h-4 mr-2" /> {searching ? "查询中..." : "查询图结果"}
              </Button>
            </CardContent>
          </Card>

          <Card className="flex-1 overflow-auto">
            <CardHeader className="sticky top-0 bg-ivory z-10 border-b border-border-cream">
              <CardTitle>图谱状态</CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4 text-sm">
              {loadingSnapshots ? (
                <div className="flex items-center gap-2 text-stone-gray">
                  <Loader2 className="w-4 h-4 animate-spin" /> 正在加载图快照...
                </div>
              ) : selectedSnapshotView ? (
                <>
                  <div className="flex items-center justify-between gap-3 border-b border-border-cream pb-2">
                    <span className="text-stone-gray">当前状态</span>
                    <Badge variant={snapshotBadgeVariant(selectedSnapshotView.status)}>{selectedSnapshotView.statusLabel}</Badge>
                  </div>
                  <div className="border-b border-border-cream pb-2">
                    <div className="text-stone-gray">图统计</div>
                    <div className="mt-1 font-mono text-near-black">{selectedSnapshotView.countsLabel}</div>
                  </div>
                  <div className="flex justify-between items-center border-b border-border-cream pb-2">
                    <span className="text-stone-gray">最近更新</span>
                    <span className="font-mono text-near-black">{selectedSnapshotView.updatedAtLabel}</span>
                  </div>
                  <div className="break-all border-b border-border-cream pb-2">
                    <div className="text-stone-gray">Snapshot ID</div>
                    <div className="mt-1 font-mono text-xs text-near-black">{selectedSnapshotView.id}</div>
                  </div>
                  {selectedSnapshotView.errorMessage && (
                    <div className="rounded-lg border border-error-red/30 bg-[#fce8e8] p-3 text-error-red">
                      {selectedSnapshotView.errorMessage}
                    </div>
                  )}
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-border-warm bg-parchment p-4 text-stone-gray">
                  暂无图快照。完成图索引构建后，后端会在这里返回快照元数据。
                </div>
              )}
              <div className="p-3 bg-info-blue/10 border border-info-blue/20 rounded text-info-blue flex items-start gap-2">
                <Info className="w-4 h-4 mt-0.5 shrink-0" />
                <span>图实体、路径和社区摘要不会直接作为 Evidence，必须回落到授权 Chunk。</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="flex flex-col overflow-hidden bg-parchment border-border-warm relative min-h-0">
          <div className="shrink-0 px-6 py-4 border-b border-border-cream bg-ivory/95 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-serif text-xl text-near-black">图查询结果</h3>
              <p className="text-sm text-stone-gray mt-1">{resultCountLabel}</p>
            </div>
            <Badge variant="default">{activeGraphSnapshotId || selectedSnapshotId || "未选择快照"}</Badge>
          </div>

          <div className="flex-1 overflow-auto relative">
            <div className="absolute inset-0 bg-[radial-gradient(#e8e6dc_1px,transparent_1px)] [background-size:16px_16px] opacity-60"></div>
            <div className="relative p-6 grid grid-cols-1 xl:grid-cols-3 gap-4">
              <ResultColumn
                title="实体"
                icon={<Boxes className="w-4 h-4 text-terracotta" />}
                loading={searching}
                emptyText={keyword.trim() ? "未命中实体。" : "输入关键词后查询实体。"}
              >
                {entities.map((entity) => (
                  <button
                    key={entity.entityKey ?? entity.name}
                    className="w-full text-left rounded-xl border border-border-cream bg-ivory p-4 hover:border-terracotta transition-colors"
                    disabled={!entity.entityKey}
                    onClick={() => entity.entityKey && void loadSupportingChunks({ type: "entity", label: entity.name, nodeKey: entity.entityKey })}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-near-black truncate">{entity.name}</p>
                        <p className="mt-1 text-xs font-mono text-stone-gray break-all">{entity.entityKey ?? "无 nodeKey"}</p>
                      </div>
                      {entity.type && <Badge variant="default">{entity.type}</Badge>}
                    </div>
                  </button>
                ))}
              </ResultColumn>

              <ResultColumn
                title="路径"
                icon={<Waypoints className="w-4 h-4 text-terracotta" />}
                loading={searching}
                emptyText={keyword.trim() ? "未命中路径。" : "输入关键词后查询路径。"}
              >
                {paths.map((path) => {
                  const relationKey = path.supportKeys.relationKey;
                  return (
                    <button
                      key={path.pathKey}
                      className="w-full text-left rounded-xl border border-border-cream bg-ivory p-4 hover:border-terracotta transition-colors"
                      disabled={!relationKey}
                      onClick={() => relationKey && void loadSupportingChunks({ type: "path", label: describePath(path), relationKey })}
                    >
                      <p className="font-medium text-near-black">{describePath(path)}</p>
                      <div className="mt-3 flex items-center gap-2 text-xs text-stone-gray">
                        <GitBranch className="w-3.5 h-3.5" />
                        <span>{path.hopCount} hop</span>
                        <span className="font-mono truncate">{relationKey ?? "无 relationKey"}</span>
                      </div>
                    </button>
                  );
                })}
              </ResultColumn>

              <ResultColumn
                title="社区"
                icon={<Network className="w-4 h-4 text-terracotta" />}
                loading={searching}
                emptyText={keyword.trim() ? "未命中社区。" : "输入关键词后查询社区。"}
              >
                {communities.map((community) => {
                  const communityKey = community.supportKeys.communityKey ?? community.communityKey;
                  return (
                    <button
                      key={community.communityKey}
                      className="w-full text-left rounded-xl border border-border-cream bg-ivory p-4 hover:border-terracotta transition-colors"
                      disabled={!communityKey}
                      onClick={() => communityKey && void loadSupportingChunks({ type: "community", label: community.title, communityKey })}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="font-medium text-near-black">{community.title}</p>
                        {community.entityCount !== null && <Badge variant="default">{community.entityCount} 实体</Badge>}
                      </div>
                      <p className="mt-2 text-sm text-stone-gray line-clamp-3">{describeCommunity(community)}</p>
                    </button>
                  );
                })}
              </ResultColumn>

              {!searching && keyword.trim() && !hasSearchResults && (
                <div className="xl:col-span-3 rounded-xl border border-dashed border-border-warm bg-ivory p-10 text-center">
                  <div className="mx-auto mb-3 w-12 h-12 rounded-full bg-parchment flex items-center justify-center">
                    <FileWarning className="w-5 h-5 text-stone-gray" />
                  </div>
                  <h3 className="text-lg font-serif text-near-black">暂无图结果</h3>
                  <p className="mt-2 text-sm text-stone-gray">后端返回空实体、路径和社区；如 Provider 降级，会在上方提示原因。</p>
                </div>
              )}
            </div>
          </div>

          <div className="shrink-0 p-4 border-t border-border-cream bg-ivory">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h4 className="font-serif text-near-black">支撑 Chunk</h4>
              <span className="text-sm text-stone-gray">
                {selectedTargetLabel ? `当前对象：${selectedTargetLabel}` : "点击实体、路径或社区查看授权支撑 Chunk"}
              </span>
            </div>
            {loadingChunks ? (
              <div className="flex items-center gap-2 text-sm text-stone-gray">
                <Loader2 className="w-4 h-4 animate-spin" /> 正在加载支撑 Chunk...
              </div>
            ) : supportingChunks.length === 0 ? (
              <div className="rounded-lg border border-dashed border-border-warm bg-parchment p-3 text-sm text-stone-gray">
                暂无可展示的授权支撑 Chunk。
              </div>
            ) : (
              <ul className="space-y-2 text-sm text-stone-gray max-h-44 overflow-auto pr-1">
                {supportingChunks.map((chunk) => (
                  <li key={chunk.chunkId} className="rounded-lg border border-border-cream bg-parchment p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-terracotta"></span>
                      <span className="font-mono text-xs text-near-black">{chunk.chunkId}</span>
                      <Badge variant="default">{chunk.refType}</Badge>
                      <span className="text-xs text-stone-gray">{describeChunk(chunk)}</span>
                    </div>
                    <p className="mt-2 text-near-black">{chunk.contentPreview}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

interface ResultColumnProps {
  title: string;
  icon: ReactNode;
  loading: boolean;
  emptyText: string;
  children: ReactNode;
}

function ResultColumn({ title, icon, loading, emptyText, children }: ResultColumnProps) {
  const hasItems = Array.isArray(children) ? children.length > 0 : Boolean(children);

  return (
    <section className="rounded-2xl border border-border-cream bg-ivory/90 p-4 min-h-[220px]">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h4 className="font-serif text-near-black">{title}</h4>
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-stone-gray">
          <Loader2 className="w-4 h-4 animate-spin" /> 加载中...
        </div>
      ) : hasItems ? (
        <div className="space-y-3">{children}</div>
      ) : (
        <p className="rounded-lg border border-dashed border-border-warm bg-parchment p-3 text-sm text-stone-gray">{emptyText}</p>
      )}
    </section>
  );
}
