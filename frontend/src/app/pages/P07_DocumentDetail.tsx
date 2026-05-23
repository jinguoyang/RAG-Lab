import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { ChevronLeft, ChevronRight, Eye, FileSymlink, Image as ImageIcon, RefreshCw, RotateCcw, Save, XCircle } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { UnderlineTabs, UnderlineTabsList, UnderlineTabsTrigger, UnderlineTabsContent } from "../components/rag/UnderlineTabs";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { formatIndexStageStatus, toChunkView, toIngestJobView, toVersionRow } from "../adapters/documentAdapter";
import {
  activateDocumentVersion,
  cancelIngestJob,
  fetchChunk,
  fetchChunks,
  fetchDocumentDetail,
  fetchDocumentVersions,
  fetchIngestJobs,
  rechunkDocument,
  retryIngestJob,
  updateChunkGovernance,
} from "../services/documentService";
import type { ChunkDTO, DocumentDetailDTO, DocumentVersionDTO, IndexStageViewModel, IngestJobDTO } from "../types/document";

function indexStageVariant(status: IndexStageViewModel["status"]) {
  if (status === "success") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "running";
  if (status === "not_required") return "inactive";
  return "queued";
}

function readChunkGovernance(chunk: ChunkDTO | null): { excluded: boolean; note: string } {
  const governance = chunk?.metadata?.governance;
  if (typeof governance !== "object" || governance === null) {
    return { excluded: false, note: "" };
  }
  const record = governance as Record<string, unknown>;
  return {
    excluded: record.excluded === true,
    note: typeof record.note === "string" ? record.note : "",
  };
}

function shortTraceId(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : "-";
}

/**
 * 文档详情页接入 E7 文档生命周期接口。
 * 页面只编排交互状态，版本切换、Chunk 权限和作业动作以后端结果为准。
 */
export function DocumentDetail() {
  const { kbId = "", docId = "" } = useParams();
  const location = useLocation();
  const confirm = useConfirmDialog();
  const [activeTab, setActiveTab] = useState("versions");
  const [detail, setDetail] = useState<DocumentDetailDTO | null>(null);
  const [versions, setVersions] = useState<DocumentVersionDTO[]>([]);
  const [jobs, setJobs] = useState<IngestJobDTO[]>([]);
  const [chunks, setChunks] = useState<ChunkDTO[]>([]);
  const [chunkPageNo, setChunkPageNo] = useState(1);
  const [chunkTotal, setChunkTotal] = useState(0);
  const [selectedChunk, setSelectedChunk] = useState<ChunkDTO | null>(null);
  const [isRechunkOpen, setIsRechunkOpen] = useState(false);
  const [chunkSizeInput, setChunkSizeInput] = useState(900);
  const [chunkOverlapInput, setChunkOverlapInput] = useState(120);
  const [governanceExcluded, setGovernanceExcluded] = useState(false);
  const [governanceNoteInput, setGovernanceNoteInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    variant: "info" | "success" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  async function loadChunks(versionId: string, pageNo = chunkPageNo) {
    if (!kbId || !docId || !versionId) return;
    const nextChunks = await fetchChunks(kbId, docId, versionId, pageNo, 10);
    setChunks(nextChunks.items);
    setChunkTotal(nextChunks.total);
    setChunkPageNo(nextChunks.pageNo);
  }

  async function loadData(nextChunkPageNo = chunkPageNo) {
    if (!kbId || !docId) return;
    setLoading(true);
    try {
      const [nextDetail, nextVersions, nextJobs] = await Promise.all([
        fetchDocumentDetail(kbId, docId),
        fetchDocumentVersions(kbId, docId),
        fetchIngestJobs(kbId, docId),
      ]);
      setDetail(nextDetail);
      setVersions(nextVersions);
      setJobs(nextJobs.items);
      const activeVersionId = nextDetail.document.activeVersionId;
      if (activeVersionId) {
        const nextChunks = await fetchChunks(kbId, docId, activeVersionId, nextChunkPageNo, 10);
        setChunks(nextChunks.items);
        setChunkTotal(nextChunks.total);
        setChunkPageNo(nextChunks.pageNo);
      } else {
        setChunks([]);
        setChunkTotal(0);
      }
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "文档详情加载失败",
        message: error instanceof Error ? error.message : "请检查文档是否存在或后端服务是否可用。",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData(1);
  }, [kbId, docId]);

  useEffect(() => {
    const state = location.state as {
      focusChunkId?: string | null;
      governanceIssue?: { chunkId?: string | null; versionId?: string | null; recommendedAction?: string | null };
    } | null;
    if (state?.focusChunkId) {
      setActiveTab("chunks");
      void fetchChunk(kbId, state.focusChunkId)
        .then((chunk) => {
          const governance = readChunkGovernance(chunk);
          setSelectedChunk(chunk);
          setGovernanceExcluded(governance.excluded);
          setGovernanceNoteInput(governance.note);
        })
        .catch((error) => {
          setFeedback({ variant: "error", title: "Chunk 详情加载失败", message: error instanceof Error ? error.message : "请检查权限。" });
        });
      return;
    }
    const governanceIssue = state?.governanceIssue;
    if (!governanceIssue) return;
    if (governanceIssue.chunkId) {
      setActiveTab("chunks");
      void fetchChunk(kbId, governanceIssue.chunkId).then((chunk) => {
        const governance = readChunkGovernance(chunk);
        setSelectedChunk(chunk);
        setGovernanceExcluded(governance.excluded);
        setGovernanceNoteInput(governance.note);
      });
      return;
    }
    if (governanceIssue.versionId) {
      setActiveTab("versions");
    }
  }, [kbId, location.state]);

  async function handleRechunk() {
    if (!kbId || !docId) return;
    if (chunkOverlapInput >= chunkSizeInput) {
      setFeedback({ variant: "warning", title: "分块参数无效", message: "重叠长度必须小于分块长度。" });
      return;
    }
    setActionLoading("rechunk");
    try {
      await rechunkDocument(kbId, docId, { chunkSize: chunkSizeInput, chunkOverlap: chunkOverlapInput });
      setFeedback({ variant: "success", title: "重分块已提交", message: "新的 ChunkRevision 已进入构建流程。" });
      setIsRechunkOpen(false);
      await loadData(1);
    } catch (error) {
      setFeedback({ variant: "error", title: "重分块失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function handleActivate(version: DocumentVersionDTO) {
    const ok = await confirm({
      title: `切换到 v${version.versionNo}？`,
      description: "切换 active version 会影响后续检索和 QA，旧版本仍会保留用于追溯。",
      confirmText: "切换版本",
    });
    if (!ok || !kbId || !docId) return;

    setActionLoading(version.versionId);
    try {
      await activateDocumentVersion(kbId, docId, version.versionId, "P07 手动切换 active version");
      setFeedback({ variant: "success", title: "版本已切换", message: `v${version.versionNo} 已成为当前 active version。` });
      await loadData(1);
      setActiveTab("chunks");
    } catch (error) {
      setFeedback({ variant: "error", title: "版本切换失败", message: error instanceof Error ? error.message : "请确认版本已解析并检索就绪。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRetryJob(job: IngestJobDTO) {
    if (!kbId) return;
    setActionLoading(job.jobId);
    try {
      await retryIngestJob(kbId, job.jobId);
      setFeedback({ variant: "success", title: "作业已重试", message: "新的重试作业已生成并执行完成。" });
      await loadData(1);
    } catch (error) {
      setFeedback({ variant: "error", title: "作业重试失败", message: error instanceof Error ? error.message : "当前作业状态可能不允许重试。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function handleCancelJob(job: IngestJobDTO) {
    if (!kbId) return;
    setActionLoading(job.jobId);
    try {
      await cancelIngestJob(kbId, job.jobId);
      setFeedback({ variant: "success", title: "作业已取消", message: "作业状态已更新为 cancelled。" });
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "作业取消失败", message: error instanceof Error ? error.message : "只有排队或运行中的作业可取消。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function openChunk(chunk: ChunkDTO) {
    if (!kbId) return;
    setSelectedChunk(chunk);
    try {
      const nextChunk = await fetchChunk(kbId, chunk.chunkId);
      const governance = readChunkGovernance(nextChunk);
      setSelectedChunk(nextChunk);
      setGovernanceExcluded(governance.excluded);
      setGovernanceNoteInput(governance.note);
    } catch (error) {
      setFeedback({ variant: "error", title: "Chunk 详情加载失败", message: error instanceof Error ? error.message : "请检查权限。" });
    }
  }

  async function handleSaveChunkGovernance() {
    if (!kbId || !selectedChunk) return;
    setActionLoading(`chunk-governance-${selectedChunk.chunkId}`);
    try {
      const response = await updateChunkGovernance(
        kbId,
        selectedChunk.chunkId,
        governanceExcluded,
        governanceNoteInput.trim() || null,
      );
      const governance = readChunkGovernance(response.chunk);
      setSelectedChunk(response.chunk);
      setGovernanceExcluded(governance.excluded);
      setGovernanceNoteInput(governance.note);
      setFeedback({
        variant: "success",
        title: "Chunk 治理已保存",
        message: `permissionInheritance：${response.permissionInheritance}`,
      });
      if (activeVersion) {
        await loadChunks(activeVersion.versionId, chunkPageNo);
      }
    } catch (error) {
      setFeedback({ variant: "error", title: "Chunk 治理保存失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setActionLoading(null);
    }
  }

  const versionRows = useMemo(
    () => versions.map((version) => toVersionRow(version, detail?.document.activeVersionId ?? null)),
    [versions, detail?.document.activeVersionId],
  );
  const jobRows = useMemo(() => jobs.map(toIngestJobView), [jobs]);
  const chunkRows = useMemo(() => chunks.map(toChunkView), [chunks]);
  const document = detail?.document;
  const activeVersion = detail?.activeVersion;
  const totalChunkPages = Math.max(1, Math.ceil(chunkTotal / 10));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <div className="flex items-center gap-2 text-sm text-stone-gray mb-2">
        <Link to={`/kb/${kbId}/docs`} className="hover:text-terracotta">
          文档中心
        </Link>
        <ChevronRight className="w-4 h-4" />
        <span className="text-near-black font-medium">{document?.name || docId}</span>
      </div>

      <PageHeader
        title={document?.name || "文档详情"}
        description="查看文档版本、Chunks、处理作业，并执行重分块与 active version 切换。"
        actions={
          <>
            <Button variant="outline" disabled={loading} onClick={() => void loadData()}>
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} /> {loading ? "刷新中..." : "刷新"}
            </Button>
            <Button variant="primary" disabled={actionLoading === "rechunk"} onClick={() => setIsRechunkOpen(true)}>
              <RotateCcw className="w-4 h-4 mr-2" /> 重分块
            </Button>
          </>
        }
        contextLabels={
          document && (
            <>
              <Badge variant="info">文档 ID：{document.documentId}</Badge>
              <Badge variant={document.status === "active" ? "success" : "inactive"}>状态：{document.status}</Badge>
            </>
          )
        }
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
        </Alert>
      )}
      {loading && (
        <div role="status" aria-live="polite">
          <Alert variant="info" title="正在刷新文档详情">
            正在从后端读取文档、版本、作业和 Chunk，请稍候。
          </Alert>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Active Version</p>
          <div className="mt-2 flex items-center gap-2">
            <span className="font-serif text-xl text-near-black">{activeVersion ? `v${activeVersion.versionNo}` : "未生成"}</span>
            {activeVersion?.sourceModality === "image" && (
              <Badge variant="info"><ImageIcon className="w-3 h-3 mr-1 inline" />图片</Badge>
            )}
          </div>
        </div>
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Active ChunkRevision</p>
          <p className="mt-2 font-mono text-base text-near-black">{shortTraceId(chunks[0]?.chunkRevisionId)}</p>
          <p className="mt-1 text-xs text-stone-gray">当前页 Chunk 来自该入库版本</p>
        </div>
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">ParseRevision</p>
          <p className="mt-2 font-mono text-base text-near-black">{shortTraceId(chunks[0]?.parseRevisionId)}</p>
          <p className="mt-1 text-xs text-stone-gray">{activeVersion?.retrievalReady ? "检索已就绪" : "检索未就绪"}</p>
        </div>
      </div>

      <UnderlineTabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <UnderlineTabsList className="mb-6">
          <UnderlineTabsTrigger value="versions">
            版本（{versionRows.length}）
          </UnderlineTabsTrigger>
          <UnderlineTabsTrigger value="chunks">
            Chunks（{chunkTotal}）
          </UnderlineTabsTrigger>
          <UnderlineTabsTrigger value="jobs">
            处理作业（{jobRows.length}）
          </UnderlineTabsTrigger>
        </UnderlineTabsList>

        <UnderlineTabsContent value="versions" className="flex-1 overflow-auto outline-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>解析状态</TableHead>
                <TableHead>副本状态</TableHead>
                <TableHead>Chunk 数</TableHead>
                <TableHead>检索就绪</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versions.map((version, index) => {
                const row = versionRows[index];
                return (
                  <TableRow key={version.versionId}>
                    <TableCell mono>{row.versionNo}</TableCell>
                    <TableCell><StatusBadge status={row.status} /></TableCell>
                    <TableCell>{formatIndexStageStatus(version.parseStatus)}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1.5">
                        {row.indexStages.map((stage) => (
                          <span key={stage.key} title={`${stage.label}: ${formatIndexStageStatus(stage.status)}`}>
                            <Badge variant={indexStageVariant(stage.status)}>
                              {stage.label}
                            </Badge>
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>{row.chunkCount}</TableCell>
                    <TableCell>{row.retrievalReadyLabel}</TableCell>
                    <TableCell>{row.createdAtLabel}</TableCell>
                    <TableCell>
                      {row.active ? (
                        <Badge variant="success">当前生效</Badge>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={!version.retrievalReady || actionLoading === version.versionId}
                          onClick={() => void handleActivate(version)}
                        >
                          <FileSymlink className="w-4 h-4 mr-2" /> 切换
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </UnderlineTabsContent>

        <UnderlineTabsContent value="chunks" className="flex-1 overflow-auto outline-none space-y-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>序号</TableHead>
                <TableHead>回溯版本</TableHead>
                <TableHead>页码</TableHead>
                <TableHead>章节 / 位置</TableHead>
                <TableHead>正文摘要</TableHead>
                <TableHead>Token</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {chunkRows.map((chunk, index) => (
                <TableRow key={chunk.id}>
                  <TableCell mono>{chunk.indexLabel}</TableCell>
                  <TableCell>
                    <div className="flex flex-col gap-1 text-xs">
                      <span className="font-mono text-near-black">CR {shortTraceId(chunks[index].chunkRevisionId)}</span>
                      <span className="font-mono text-stone-gray">PR {shortTraceId(chunks[index].parseRevisionId)}</span>
                    </div>
                  </TableCell>
                  <TableCell>{chunk.pageLabel}</TableCell>
                  <TableCell>{chunk.section}</TableCell>
                  <TableCell className="max-w-xl text-stone-gray">{chunk.preview}</TableCell>
                  <TableCell>{chunk.tokenCount ?? "-"}</TableCell>
                  <TableCell>
                    <Button variant="outline" size="sm" onClick={() => void openChunk(chunks[index])}>
                      <Eye className="w-4 h-4 mr-2" /> 查看
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between text-sm text-stone-gray">
            <span>第 {chunkPageNo} / {totalChunkPages} 页</span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!activeVersion || chunkPageNo <= 1}
                onClick={() => activeVersion && void loadChunks(activeVersion.versionId, chunkPageNo - 1)}
              >
                <ChevronLeft className="w-4 h-4 mr-1" /> 上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!activeVersion || chunkPageNo >= totalChunkPages}
                onClick={() => activeVersion && void loadChunks(activeVersion.versionId, chunkPageNo + 1)}
              >
                下一页 <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </UnderlineTabsContent>

        <UnderlineTabsContent value="jobs" className="flex-1 overflow-auto outline-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>作业 ID</TableHead>
                <TableHead>进度</TableHead>
                <TableHead>处理链路</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>错误信息</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job, index) => {
                const row = jobRows[index];
                return (
                  <TableRow key={job.jobId}>
                    <TableCell mono>{row.id}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={row.status} />
                        <span className="text-xs text-stone-gray">{row.progress}%（{row.stage}）</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1.5">
                        {row.indexStages.map((stage) => (
                          <span key={stage.key} title={`${stage.label}: ${formatIndexStageStatus(stage.status)}`}>
                            <Badge variant={indexStageVariant(stage.status)}>
                              {stage.label}
                            </Badge>
                          </span>
                        ))}
                        {row.graphExtractionErrorCount > 0 && (
                          <Badge variant="warning">Graph 抽取部分失败: {row.graphExtractionErrorCount}</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>{row.createdAtLabel}</TableCell>
                    <TableCell className="max-w-xs text-stone-gray">{row.errorMessage}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="whitespace-nowrap"
                          disabled={!["failed", "cancelled"].includes(job.status) || actionLoading === job.jobId}
                          onClick={() => void handleRetryJob(job)}
                        >
                          <RotateCcw className="w-4 h-4 mr-2" /> 重试
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="whitespace-nowrap"
                          disabled={!["queued", "running"].includes(job.status) || actionLoading === job.jobId}
                          onClick={() => void handleCancelJob(job)}
                        >
                          <XCircle className="w-4 h-4 mr-2" /> 取消
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </UnderlineTabsContent>
      </UnderlineTabs>

      <Drawer isOpen={Boolean(selectedChunk)} onClose={() => setSelectedChunk(null)} title="Chunk 详情" width="640px">
        {selectedChunk && (
          <>
            <DrawerSection title="基础信息">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-stone-gray">Chunk ID：</span><span className="font-mono">{selectedChunk.chunkId}</span></div>
                <div><span className="text-stone-gray">序号：</span>{selectedChunk.chunkIndex}</div>
                <div><span className="text-stone-gray">状态：</span>{selectedChunk.status}</div>
                <div><span className="text-stone-gray">页码：</span>{selectedChunk.pageNo ?? "-"}</div>
                <div><span className="text-stone-gray">章节：</span>{selectedChunk.sectionPath || selectedChunk.heading || selectedChunk.section || "-"}</div>
                <div><span className="text-stone-gray">Token：</span>{selectedChunk.tokenCount ?? "-"}</div>
                <div><span className="text-stone-gray">ChunkRevision：</span><span className="font-mono">{selectedChunk.chunkRevisionId || "-"}</span></div>
                <div><span className="text-stone-gray">ParseRevision：</span><span className="font-mono">{selectedChunk.parseRevisionId || "-"}</span></div>
                <div><span className="text-stone-gray">DocumentVersion：</span><span className="font-mono">{selectedChunk.documentVersionId || "-"}</span></div>
                <div><span className="text-stone-gray">Offset：</span>{selectedChunk.startOffset ?? "-"} - {selectedChunk.endOffset ?? "-"}</div>
              </div>
              {selectedChunk.metadata?.sourceModality === "image" && (
                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                  <Badge variant="info">
                    <ImageIcon className="w-3 h-3 mr-1 inline" />图片证据
                  </Badge>
                  {typeof selectedChunk.metadata.region === "string" && (
                    <span className="text-stone-gray">区域: {selectedChunk.metadata.region}</span>
                  )}
                  {typeof selectedChunk.metadata.visionConfidence === "string" && (
                    <span className="text-stone-gray">解析置信度: {selectedChunk.metadata.visionConfidence}</span>
                  )}
                </div>
              )}
            </DrawerSection>
            <DrawerSection title="正文">
              <pre className="whitespace-pre-wrap break-words rounded-lg border border-border-cream bg-parchment p-4 text-sm leading-relaxed text-near-black">
                {selectedChunk.content}
              </pre>
            </DrawerSection>
            <DrawerSection title="Metadata">
              <pre className="whitespace-pre-wrap break-words rounded-lg border border-border-cream bg-parchment p-4 text-xs text-olive-gray">
                {JSON.stringify(selectedChunk.metadata, null, 2)}
              </pre>
            </DrawerSection>
            <DrawerSection title="治理标记">
              <div className="space-y-4">
                <label className="flex items-center gap-2 text-sm text-near-black">
                  <input
                    type="checkbox"
                    checked={governanceExcluded}
                    onChange={(event) => setGovernanceExcluded(event.target.checked)}
                  />
                  排除 Chunk
                </label>
                <textarea
                  className="min-h-24 w-full rounded-lg border border-border-cream bg-parchment p-3 text-sm text-near-black focus:outline-none focus:ring-1 focus:ring-focus-blue"
                  value={governanceNoteInput}
                  onChange={(event) => setGovernanceNoteInput(event.target.value)}
                  placeholder="填写治理备注，说明排除或恢复原因。"
                />
                <Button
                  variant="primary"
                  disabled={actionLoading === `chunk-governance-${selectedChunk.chunkId}`}
                  onClick={() => void handleSaveChunkGovernance()}
                >
                  <Save className="w-4 h-4 mr-2" /> 保存治理标记
                </Button>
              </div>
            </DrawerSection>
          </>
        )}
      </Drawer>

      <Drawer isOpen={isRechunkOpen} onClose={() => setIsRechunkOpen(false)} title="调整分块策略">
        <DrawerSection title="固定长度分块">
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm text-olive-gray">分块长度</label>
              <input
                type="number"
                min={100}
                max={4000}
                value={chunkSizeInput}
                onChange={(event) => setChunkSizeInput(Number(event.target.value))}
                className="w-full rounded-[8px] border border-border-cream bg-white px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-olive-gray">重叠长度</label>
              <input
                type="number"
                min={0}
                max={1000}
                value={chunkOverlapInput}
                onChange={(event) => setChunkOverlapInput(Number(event.target.value))}
                className="w-full rounded-[8px] border border-border-cream bg-white px-3 py-2 text-sm"
              />
            </div>
          </div>
        </DrawerSection>
        <DrawerSection>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setIsRechunkOpen(false)}>取消</Button>
            <Button variant="primary" disabled={actionLoading === "rechunk"} onClick={() => void handleRechunk()}>
              {actionLoading === "rechunk" ? "提交中..." : "提交重分块"}
            </Button>
          </div>
        </DrawerSection>
      </Drawer>
    </div>
  );
}
