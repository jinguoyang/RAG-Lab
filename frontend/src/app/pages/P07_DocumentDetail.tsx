import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { ChevronLeft, ChevronRight, Eye, FileSymlink, RefreshCw, RotateCcw, XCircle } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { toChunkView, toIngestJobView, toVersionRow } from "../adapters/documentAdapter";
import {
  activateDocumentVersion,
  cancelIngestJob,
  fetchChunk,
  fetchChunks,
  fetchDocumentDetail,
  fetchDocumentVersions,
  fetchIngestJobs,
  reparseDocument,
  retryIngestJob,
} from "../services/documentService";
import type { ChunkDTO, DocumentDetailDTO, DocumentVersionDTO, IngestJobDTO } from "../types/document";

/**
 * 文档详情页接入 E7 文档生命周期接口。
 * 页面只编排交互状态，版本切换、Chunk 权限和作业动作以后端结果为准。
 */
export function DocumentDetail() {
  const { kbId = "", docId = "" } = useParams();
  const confirm = useConfirmDialog();
  const [activeTab, setActiveTab] = useState("versions");
  const [detail, setDetail] = useState<DocumentDetailDTO | null>(null);
  const [versions, setVersions] = useState<DocumentVersionDTO[]>([]);
  const [jobs, setJobs] = useState<IngestJobDTO[]>([]);
  const [chunks, setChunks] = useState<ChunkDTO[]>([]);
  const [chunkPageNo, setChunkPageNo] = useState(1);
  const [chunkTotal, setChunkTotal] = useState(0);
  const [selectedChunk, setSelectedChunk] = useState<ChunkDTO | null>(null);
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

  async function handleReparse() {
    const ok = await confirm({
      title: "确认重解析文档？",
      description: "重解析会生成新的文档版本和 Chunk，不会删除旧版本。新版本需要切换后才会成为 active version。",
      confirmText: "重解析",
    });
    if (!ok || !kbId || !docId) return;

    setActionLoading("reparse");
    try {
      await reparseDocument(kbId, docId, "P07 手动重解析");
      setFeedback({ variant: "success", title: "重解析已完成", message: "已生成新版本和 Chunk，可在版本列表中切换生效。" });
      await loadData(1);
    } catch (error) {
      setFeedback({ variant: "error", title: "重解析失败", message: error instanceof Error ? error.message : "请稍后重试。" });
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
      setSelectedChunk(await fetchChunk(kbId, chunk.chunkId));
    } catch (error) {
      setFeedback({ variant: "error", title: "Chunk 详情加载失败", message: error instanceof Error ? error.message : "请检查权限。" });
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
        description="查看文档版本、Chunk、入库作业，并执行重解析与 active version 切换。"
        actions={
          <>
            <Button variant="outline" disabled={loading} onClick={() => void loadData()}>
              <RefreshCw className="w-4 h-4 mr-2" /> 刷新
            </Button>
            <Button variant="primary" disabled={actionLoading === "reparse"} onClick={() => void handleReparse()}>
              <FileSymlink className="w-4 h-4 mr-2" /> 重解析
            </Button>
          </>
        }
        contextLabels={
          document && (
            <>
              <Badge variant="info">文档 ID：{document.documentId}</Badge>
              <Badge variant="default">密级：{document.securityLevel}</Badge>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Active Version</p>
          <p className="mt-2 font-serif text-xl text-near-black">{activeVersion ? `v${activeVersion.versionNo}` : "未生成"}</p>
        </div>
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Chunk Count</p>
          <p className="mt-2 font-serif text-xl text-near-black">{activeVersion?.chunkCount ?? 0}</p>
        </div>
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Retrieval Ready</p>
          <p className="mt-2 font-serif text-xl text-near-black">{activeVersion?.retrievalReady ? "已就绪" : "未就绪"}</p>
        </div>
      </div>

      <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <Tabs.List className="flex border-b border-border-cream gap-6 mb-6">
          <Tabs.Trigger value="versions" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            版本（{versionRows.length}）
          </Tabs.Trigger>
          <Tabs.Trigger value="chunks" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            Chunks（{chunkTotal}）
          </Tabs.Trigger>
          <Tabs.Trigger value="jobs" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            入库作业（{jobRows.length}）
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="versions" className="flex-1 overflow-auto outline-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>解析状态</TableHead>
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
                    <TableCell>{row.parseStatusLabel}</TableCell>
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
        </Tabs.Content>

        <Tabs.Content value="chunks" className="flex-1 overflow-auto outline-none space-y-3">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>序号</TableHead>
                <TableHead>页码</TableHead>
                <TableHead>章节</TableHead>
                <TableHead>正文摘要</TableHead>
                <TableHead>Token</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {chunkRows.map((chunk, index) => (
                <TableRow key={chunk.id}>
                  <TableCell mono>{chunk.indexLabel}</TableCell>
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
        </Tabs.Content>

        <Tabs.Content value="jobs" className="flex-1 overflow-auto outline-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>作业 ID</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>阶段</TableHead>
                <TableHead>进度</TableHead>
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
                    <TableCell><StatusBadge status={row.status} /></TableCell>
                    <TableCell>{row.stage}</TableCell>
                    <TableCell>{row.progress}%</TableCell>
                    <TableCell>{row.createdAtLabel}</TableCell>
                    <TableCell className="max-w-xs text-stone-gray">{row.errorMessage}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={!["failed", "cancelled"].includes(job.status) || actionLoading === job.jobId}
                          onClick={() => void handleRetryJob(job)}
                        >
                          <RotateCcw className="w-4 h-4 mr-2" /> 重试
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
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
        </Tabs.Content>
      </Tabs.Root>

      <Drawer isOpen={Boolean(selectedChunk)} onClose={() => setSelectedChunk(null)} title="Chunk 详情" width="640px">
        {selectedChunk && (
          <>
            <DrawerSection title="基础信息">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-stone-gray">Chunk ID：</span><span className="font-mono">{selectedChunk.chunkId}</span></div>
                <div><span className="text-stone-gray">序号：</span>{selectedChunk.chunkIndex}</div>
                <div><span className="text-stone-gray">章节：</span>{selectedChunk.section || "-"}</div>
                <div><span className="text-stone-gray">Token：</span>{selectedChunk.tokenCount ?? "-"}</div>
              </div>
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
          </>
        )}
      </Drawer>
    </div>
  );
}
