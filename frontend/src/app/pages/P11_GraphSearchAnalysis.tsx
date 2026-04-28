import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { GitBranch, Network, RefreshCw, Search } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import {
  chunkToViewModel,
  communityToResult,
  entityToResult,
  pathToResult,
  toGraphAnalysisView,
  type GraphResultViewModel,
} from "../adapters/graphAdapter";
import {
  fetchGraphCommunities,
  fetchGraphEntities,
  fetchGraphPaths,
  fetchGraphSnapshots,
  fetchGraphSupportingChunks,
} from "../services/graphService";
import type { GraphQueryDiagnosticsDTO, GraphSnapshotDTO, GraphSupportingChunkDTO } from "../types/graph";

type ResultMode = "entity" | "path" | "community";

/**
 * 图谱检索分析页接入 Epic9 Graph API。
 * 页面只展示后端授权后的支撑 Chunk，权限裁剪数量以后端 filteredCount 为准。
 */
export function GraphSearchAnalysis() {
  const { kbId = "" } = useParams();
  const [snapshots, setSnapshots] = useState<GraphSnapshotDTO[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("Supplier");
  const [mode, setMode] = useState<ResultMode>("path");
  const [results, setResults] = useState<GraphResultViewModel[]>([]);
  const [selectedResult, setSelectedResult] = useState<GraphResultViewModel | null>(null);
  const [supportingChunks, setSupportingChunks] = useState<GraphSupportingChunkDTO[]>([]);
  const [filteredCount, setFilteredCount] = useState(0);
  const [diagnostics, setDiagnostics] = useState<GraphQueryDiagnosticsDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ variant: "info" | "warning" | "error"; title: string; message: string } | null>(null);

  const selectedSnapshot = useMemo(
    () => snapshots.find((snapshot) => snapshot.graphSnapshotId === selectedSnapshotId) ?? snapshots[0] ?? null,
    [snapshots, selectedSnapshotId],
  );
  const analysis = useMemo(() => toGraphAnalysisView(selectedSnapshot), [selectedSnapshot]);
  const chunkRows = useMemo(() => supportingChunks.map(chunkToViewModel), [supportingChunks]);

  async function loadSnapshots() {
    if (!kbId) return;
    setLoading(true);
    try {
      const page = await fetchGraphSnapshots(kbId);
      setSnapshots(page.items);
      setSelectedSnapshotId((current) => current ?? page.items[0]?.graphSnapshotId ?? null);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "图快照加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务和知识库权限。",
      });
    } finally {
      setLoading(false);
    }
  }

  async function runSearch(nextMode = mode) {
    if (!kbId || !keyword.trim()) return;
    setLoading(true);
    setSelectedResult(null);
    setSupportingChunks([]);
    setFilteredCount(0);
    try {
      const snapshotId = selectedSnapshot?.graphSnapshotId ?? null;
      if (nextMode === "entity") {
        const response = await fetchGraphEntities(kbId, keyword.trim(), snapshotId);
        setResults(response.items.map(entityToResult));
        setDiagnostics(null);
      } else if (nextMode === "path") {
        const response = await fetchGraphPaths(kbId, keyword.trim(), snapshotId);
        setResults(response.items.map(pathToResult));
        setDiagnostics(response.diagnostics);
      } else {
        const response = await fetchGraphCommunities(kbId, keyword.trim(), snapshotId);
        setResults(response.items.map(communityToResult));
        setDiagnostics(response.diagnostics);
      }
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "图查询失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setLoading(false);
    }
  }

  async function openResult(result: GraphResultViewModel) {
    setSelectedResult(result);
    if (!kbId || !selectedSnapshot?.graphSnapshotId) return;
    try {
      const response = await fetchGraphSupportingChunks(kbId, selectedSnapshot.graphSnapshotId, result.supportKeys);
      setSupportingChunks(response.items);
      setFilteredCount(response.filteredCount);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "支撑 Chunk 加载失败",
        message: error instanceof Error ? error.message : "请检查 Chunk 读取权限。",
      });
    }
  }

  useEffect(() => {
    void loadSnapshots();
  }, [kbId]);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="图谱检索分析"
        description="查看图快照、实体、关系路径、社区摘要和授权支撑证据。"
        actions={
          <Button variant="outline" disabled={loading} onClick={() => void loadSnapshots()}>
            <RefreshCw className="w-4 h-4 mr-2" /> 刷新快照
          </Button>
        }
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
        </Alert>
      )}
      {analysis.staleReason && (
        <Alert variant="warning" title="图快照已过期">
          当前快照原因：{analysis.staleReason}
        </Alert>
      )}
      {diagnostics?.degraded && (
        <Alert variant="warning" title="图 Provider 降级">
          {diagnostics.degradedReason || "当前图 Provider 不可用，结果为空。"}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        <div className="space-y-4 flex flex-col min-h-0">
          <Card className="shrink-0">
            <CardHeader>
              <CardTitle>查询条件</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-near-black">关键词</label>
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
                  <Input
                    className="pl-9"
                    value={keyword}
                    onChange={(event) => setKeyword(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") void runSearch();
                    }}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-near-black">查询类型</label>
                <select
                  className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm"
                  value={mode}
                  onChange={(event) => {
                    const nextMode = event.target.value as ResultMode;
                    setMode(nextMode);
                    void runSearch(nextMode);
                  }}
                >
                  <option value="path">关系路径</option>
                  <option value="entity">实体</option>
                  <option value="community">社区摘要</option>
                </select>
              </div>
              <Button variant="primary" className="w-full" disabled={loading || !keyword.trim()} onClick={() => void runSearch()}>
                <GitBranch className="w-4 h-4 mr-2" /> 查询图谱
              </Button>
            </CardContent>
          </Card>

          <Card className="flex-1 overflow-auto">
            <CardHeader className="sticky top-0 bg-ivory z-10 border-b border-border-cream">
              <CardTitle>图谱状态</CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-stone-gray">快照状态</span>
                <StatusBadge status={analysis.snapshotStatus} />
              </div>
              <div className="flex justify-between border-b border-border-cream pb-2">
                <span className="text-stone-gray">实体总数</span>
                <span className="font-mono text-near-black">{analysis.entityCount}</span>
              </div>
              <div className="flex justify-between border-b border-border-cream pb-2">
                <span className="text-stone-gray">关系总数</span>
                <span className="font-mono text-near-black">{analysis.relationCount}</span>
              </div>
              <div className="flex justify-between border-b border-border-cream pb-2">
                <span className="text-stone-gray">社区总数</span>
                <span className="font-mono text-near-black">{analysis.communityCount}</span>
              </div>
              <div className="flex justify-between border-b border-border-cream pb-2">
                <span className="text-stone-gray">最近更新</span>
                <span className="font-mono text-near-black">{analysis.updatedAt}</span>
              </div>
              {snapshots.length > 1 && (
                <select
                  className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm"
                  value={selectedSnapshot?.graphSnapshotId ?? ""}
                  onChange={(event) => setSelectedSnapshotId(event.target.value)}
                >
                  {snapshots.map((snapshot) => (
                    <option key={snapshot.graphSnapshotId} value={snapshot.graphSnapshotId}>
                      {snapshot.graphSnapshotId.slice(0, 8)} · {snapshot.status}
                    </option>
                  ))}
                </select>
              )}
            </CardContent>
          </Card>
        </div>

        <Card className="lg:col-span-2 flex flex-col overflow-hidden bg-parchment border-border-warm">
          <CardHeader className="bg-ivory border-b border-border-cream">
            <div className="flex items-center justify-between gap-3">
              <CardTitle>查询结果</CardTitle>
              <Badge variant="info">{results.length} 条</Badge>
            </div>
          </CardHeader>
          <CardContent className="flex-1 min-h-0 overflow-auto p-0">
            {results.length === 0 ? (
              <div className="h-full min-h-[280px] flex flex-col items-center justify-center text-stone-gray">
                <Network className="w-8 h-8 mb-3 text-terracotta" />
                <span>{loading ? "正在查询图谱..." : "暂无图结果"}</span>
              </div>
            ) : (
              <Table className="rounded-none border-0">
                <TableHeader>
                  <TableRow>
                    <TableHead>类型</TableHead>
                    <TableHead>标题</TableHead>
                    <TableHead>摘要</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {results.map((result) => (
                    <TableRow key={`${result.kind}-${result.id}`} onClick={() => void openResult(result)}>
                      <TableCell><Badge variant="default">{result.kind}</Badge></TableCell>
                      <TableCell className="font-medium">{result.title}</TableCell>
                      <TableCell className="text-stone-gray">{result.subtitle}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>

          <div className="shrink-0 p-4 border-t border-border-cream bg-ivory space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-serif text-near-black">支撑 Chunk</h4>
              {filteredCount > 0 && <Badge variant="warning">已裁剪 {filteredCount}</Badge>}
            </div>
            {selectedResult && <p className="text-sm text-stone-gray">{selectedResult.title}</p>}
            {chunkRows.length === 0 ? (
              <p className="text-sm text-stone-gray">选择图结果后查看授权支撑证据。</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {chunkRows.map((chunk) => (
                  <li key={chunk.id} className="rounded-md border border-border-cream bg-parchment p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-xs text-terracotta">{chunk.documentName} · {chunk.location}</span>
                      <Badge variant="default">{chunk.securityLevel}</Badge>
                    </div>
                    <p className="mt-2 text-stone-gray leading-relaxed">{chunk.preview}</p>
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
