import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Search, Upload, Download, FileWarning, Eye, ChevronLeft, ChevronRight, Database, RefreshCw, Trash2 } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { formatIndexStageStatus, toDocumentRow, toIngestJobView } from "../adapters/documentAdapter";
import {
  fetchDocuments,
  fetchIndexSyncJobs,
  fetchIngestJobs,
  deleteDocument,
  downloadDocumentSource,
  rebuildIndexSync,
  runBulkDocumentGovernance,
  uploadDocument,
} from "../services/documentService";
import type { BulkDocumentGovernanceRequest, DocumentDTO, IndexStageViewModel, IndexSyncJobDTO, IngestJobDTO, JobStatus } from "../types/document";

const DOCUMENT_PAGE_SIZE = 10;
type BatchOperation = BulkDocumentGovernanceRequest["operation"];

const BATCH_OPERATION_LABELS: Record<BatchOperation, string> = {
  reparse: "批量重解析",
  disable: "批量停用",
  rebuild_index: "批量重建索引",
};

function indexStageVariant(status: IndexStageViewModel["status"]) {
  if (status === "success") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "running";
  if (status === "not_required") return "inactive";
  return "queued";
}

/**
 * 文档中心真实接口接入页。
 * 页面只管理筛选和上传交互，后端 DTO 到展示行的转换集中在 adapter 中。
 */
export function DocumentCenter() {
  const navigate = useNavigate();
  const confirm = useConfirmDialog();
  const { kbId = "" } = useParams();
  const [documents, setDocuments] = useState<DocumentDTO[]>([]);
  const [documentTotal, setDocumentTotal] = useState(0);
  const [pageNo, setPageNo] = useState(1);
  const [jobs, setJobs] = useState<IngestJobDTO[]>([]);
  const [indexSyncJobs, setIndexSyncJobs] = useState<IndexSyncJobDTO[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [batchOperation, setBatchOperation] = useState<BatchOperation>("reparse");
  const [targetStore, setTargetStore] = useState("milvus");
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | JobStatus>("");
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [uploadLevel, setUploadLevel] = useState("public");
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  async function loadData(keyword = searchTerm, nextPageNo = pageNo) {
    if (!kbId) return;
    setLoading(true);
    try {
      const [documentPage, jobPage] = await Promise.all([
        fetchDocuments(kbId, { keyword, pageNo: nextPageNo, pageSize: DOCUMENT_PAGE_SIZE }),
        fetchIngestJobs(kbId),
      ]);
      const indexSyncPage = await fetchIndexSyncJobs(kbId);
      setDocuments(documentPage.items);
      setDocumentTotal(documentPage.total);
      setPageNo(documentPage.pageNo);
      setJobs(jobPage.items);
      setIndexSyncJobs(indexSyncPage.items);
      setSelectedDocumentIds((current) => current.filter((documentId) => documentPage.items.some((item) => item.documentId === documentId)));
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "文档中心加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务和数据库连接。",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData("", 1);
  }, [kbId]);

  const rows = useMemo(() => documents.map(toDocumentRow), [documents]);
  const jobRows = useMemo(() => jobs.map(toIngestJobView), [jobs]);
  const filteredRows = useMemo(
    () => rows.filter((row) => !statusFilter || row.status === statusFilter),
    [rows, statusFilter],
  );

  async function handleSearchSubmit() {
    await loadData(searchTerm, 1);
  }

  async function handleUploadSubmit() {
    if (!selectedFile || !kbId) {
      setFeedback({
        variant: "warning",
        title: "请选择文件",
        message: "上传接口需要真实文件对象，才能生成文件大小和 checksum。",
      });
      return;
    }

    setUploading(true);
    try {
      await uploadDocument(kbId, selectedFile, uploadName, uploadLevel);
      setFeedback({
        variant: "success",
        title: "上传请求已创建",
        message: "文档、首个版本和 queued 入库作业已写入数据库。",
      });
      setSelectedFile(null);
      setUploadName("");
      setIsUploadOpen(false);
      await loadData(searchTerm, 1);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "上传失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setUploading(false);
    }
  }

  function handleUploadFileChange(file: File | null) {
    setSelectedFile(file);
    setUploadName(file?.name ?? "");
  }

  async function handlePageChange(nextPageNo: number) {
    await loadData(searchTerm, nextPageNo);
  }

  function toggleDocumentSelection(documentId: string, checked: boolean) {
    setSelectedDocumentIds((current) => (
      checked ? Array.from(new Set([...current, documentId])) : current.filter((item) => item !== documentId)
    ));
  }

  function toggleCurrentPageSelection(checked: boolean) {
    const currentPageIds = filteredRows.map((row) => row.id);
    setSelectedDocumentIds((current) => (
      checked
        ? Array.from(new Set([...current, ...currentPageIds]))
        : current.filter((item) => !currentPageIds.includes(item))
    ));
  }

  async function handleBatchGovernance() {
    if (selectedDocumentIds.length === 0) {
      setFeedback({ variant: "warning", title: "请选择文档", message: "批量治理需要先选择至少一个文档。" });
      return;
    }
    const label = BATCH_OPERATION_LABELS[batchOperation];
    const ok = await confirm({
      title: `确认${label}？`,
      description: `${label}会影响 ${selectedDocumentIds.length} 个文档，操作会写入审计记录。`,
      confirmText: label,
    });
    if (!ok) return;

    setLoading(true);
    try {
      const response = await runBulkDocumentGovernance(kbId, {
        operation: batchOperation,
        documentIds: selectedDocumentIds,
        confirmImpact: true,
        reason: `P06 ${label}`,
        targetStore: batchOperation === "rebuild_index" ? targetStore : null,
      });
      setFeedback({
        variant: response.failedCount > 0 ? "warning" : "success",
        title: `${label}已提交`,
        message: `成功 ${response.successCount} 项，失败 ${response.failedCount} 项。`,
      });
      setSelectedDocumentIds([]);
      await loadData(searchTerm, pageNo);
    } catch (error) {
      setFeedback({ variant: "error", title: `${label}失败`, message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setLoading(false);
    }
  }

  async function handleKnowledgeBaseIndexRebuild() {
    const ok = await confirm({
      title: `重建 ${targetStore} 索引？`,
      description: "未选择文档时会按当前知识库 active Chunk 范围重建目标副本。",
      confirmText: "重建索引",
    });
    if (!ok) return;

    setLoading(true);
    try {
      await rebuildIndexSync(kbId, { targetStore });
      const nextJobs = await fetchIndexSyncJobs(kbId);
      setIndexSyncJobs(nextJobs.items);
      setFeedback({ variant: "success", title: "索引重建已创建", message: `${targetStore} 副本重建作业已写入。` });
    } catch (error) {
      setFeedback({ variant: "error", title: "索引重建失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setLoading(false);
    }
  }

  /**
   * 触发浏览器下载文件流，后端负责权限校验和 MinIO 对象读取。
   */
  function triggerBrowserDownload(blob: Blob, fileName: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  async function handleDownloadDocument(documentId: string, documentName: string) {
    setDownloadingDocumentId(documentId);
    try {
      const download = await downloadDocumentSource(kbId, documentId);
      triggerBrowserDownload(download.blob, download.fileName || documentName);
      setFeedback({ variant: "success", title: "原文下载已开始", message: `正在下载“${documentName}”。` });
    } catch (error) {
      setFeedback({
        variant: "warning",
        title: "原文档暂不可下载",
        message: error instanceof Error ? error.message : "未能从对象存储读取原始文件，请稍后重试或联系管理员。",
      });
    } finally {
      setDownloadingDocumentId(null);
    }
  }

  async function handleDeleteDocument(documentId: string, documentName: string) {
    const ok = await confirm({
      title: "确认删除文档？",
      description: `删除“${documentName}”后，文档会立即从列表、检索和图支撑结果中移除，并尝试清理 MinIO 与检索副本。`,
      confirmText: "删除文档",
      variant: "destructive",
    });
    if (!ok) return;

    setLoading(true);
    try {
      const response = await deleteDocument(kbId, documentId, `P06 删除文档：${documentName}`);
      setFeedback({
        variant: response.warnings.length > 0 ? "warning" : "success",
        title: response.warnings.length > 0 ? "文档已删除，副本清理待处理" : "文档已删除",
        message: response.warnings.length > 0
          ? response.warnings.join("；")
          : `已创建 ${response.cleanupJobs.length} 个清理作业。`,
      });
      setSelectedDocumentIds((current) => current.filter((item) => item !== documentId));
      await loadData(searchTerm, pageNo);
    } catch (error) {
      setFeedback({ variant: "error", title: "删除失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setLoading(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(documentTotal / DOCUMENT_PAGE_SIZE));
  const currentPageSelected = filteredRows.length > 0 && filteredRows.every((row) => selectedDocumentIds.includes(row.id));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="文档中心"
        description="管理文档元数据、版本入口与最近 ingest 作业。"
        actions={
          <>
            <Button variant="outline" disabled>
              <Download className="w-4 h-4 mr-2" /> 导出筛选结果
            </Button>
            <Button variant="primary" onClick={() => setIsUploadOpen(true)}>
              <Upload className="w-4 h-4 mr-2" /> 上传文档
            </Button>
          </>
        }
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
        </Alert>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-6">
        <div className="space-y-6 min-w-0">
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative w-full max-w-80">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
              <Input
                placeholder="按文档名搜索..."
                className="pl-9"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") void handleSearchSubmit();
                }}
              />
            </div>
            <Button variant="outline" onClick={() => void handleSearchSubmit()}>
              搜索
            </Button>
            <select
              className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none focus:ring-1 focus:ring-focus-blue"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as "" | JobStatus)}
            >
              <option value="">全部状态</option>
              <option value="success">可见文档</option>
              <option value="cancelled">非活动</option>
            </select>
            <div className="ml-auto text-sm text-stone-gray">
              {loading ? "加载中..." : `共 ${documentTotal} 条，当前页 ${filteredRows.length} 条`}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border-cream bg-ivory p-4">
            <span className="text-sm text-stone-gray">已选 {selectedDocumentIds.length} 个文档</span>
            <select
              className="px-3 py-2 bg-parchment border border-border-cream rounded-md text-sm text-near-black focus:outline-none focus:ring-1 focus:ring-focus-blue"
              value={batchOperation}
              onChange={(event) => setBatchOperation(event.target.value as BatchOperation)}
            >
              <option value="reparse">批量重解析</option>
              <option value="disable">批量停用</option>
              <option value="rebuild_index">批量重建索引</option>
            </select>
            {batchOperation === "rebuild_index" && (
              <select
                className="px-3 py-2 bg-parchment border border-border-cream rounded-md text-sm text-near-black focus:outline-none focus:ring-1 focus:ring-focus-blue"
                value={targetStore}
                onChange={(event) => setTargetStore(event.target.value)}
              >
                <option value="milvus">milvus</option>
                <option value="opensearch">opensearch</option>
                <option value="neo4j">neo4j</option>
              </select>
            )}
            <Button variant="outline" disabled={loading || selectedDocumentIds.length === 0} onClick={() => void handleBatchGovernance()}>
              <RefreshCw className="w-4 h-4 mr-2" /> 执行治理
            </Button>
          </div>

          {filteredRows.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border-warm bg-ivory p-10 text-center">
              <div className="mx-auto mb-3 w-12 h-12 rounded-full bg-parchment flex items-center justify-center">
                <FileWarning className="w-5 h-5 text-stone-gray" />
              </div>
              <h3 className="text-lg font-serif text-near-black">暂无文档</h3>
              <p className="mt-2 text-sm text-stone-gray">
                上传文档后会立即生成文档对象、首个版本和 queued 入库作业。
              </p>
            </div>
          ) : (
            <div className="overflow-auto border border-border-cream rounded-xl">
              <Table tableClassName="min-w-0 table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <input
                        type="checkbox"
                        aria-label="选择当前页文档"
                        checked={currentPageSelected}
                        onChange={(event) => toggleCurrentPageSelection(event.target.checked)}
                      />
                    </TableHead>
                    <TableHead>文档名</TableHead>
                    <TableHead className="w-20 whitespace-nowrap">状态</TableHead>
                    <TableHead className="w-20 whitespace-nowrap">密级</TableHead>
                    <TableHead className="w-36 whitespace-nowrap">更新时间</TableHead>
                    <TableHead className="w-36 text-right whitespace-nowrap">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRows.map((doc) => (
                    <TableRow
                      key={doc.id}
                      className="cursor-pointer hover:bg-border-cream/30"
                      onClick={() => navigate(`/kb/${kbId}/docs/${doc.id}`)}
                    >
                      <TableCell onClick={(event) => event.stopPropagation()}>
                        <input
                          type="checkbox"
                          aria-label={`选择文档 ${doc.name}`}
                          checked={selectedDocumentIds.includes(doc.id)}
                          onChange={(event) => toggleDocumentSelection(doc.id, event.target.checked)}
                        />
                      </TableCell>
                      <TableCell className="font-medium min-w-0">
                        <span className="block truncate" title={doc.name}>{doc.name}</span>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <StatusBadge status={doc.status} />
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <Badge variant="default">{doc.securityLevel}</Badge>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">{doc.updatedAtLabel}</TableCell>
                      <TableCell className="text-right whitespace-nowrap">
                        <Button
                          variant="ghost"
                          size="sm"
                          title="查看详情"
                          onClick={(event) => {
                            event.stopPropagation();
                            navigate(`/kb/${kbId}/docs/${doc.id}`);
                          }}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="原文下载"
                          disabled={downloadingDocumentId === doc.id}
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleDownloadDocument(doc.id, doc.name);
                          }}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          title="删除文档"
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleDeleteDocument(doc.id, doc.name);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {!loading && documentTotal > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-stone-gray">
              <span>共 {documentTotal} 个文档</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={loading || pageNo <= 1}
                  onClick={() => void handlePageChange(pageNo - 1)}
                >
                  <ChevronLeft className="w-4 h-4 mr-1" /> 上一页
                </Button>
                <span className="min-w-20 text-center text-near-black">{pageNo} / {totalPages}</span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={loading || pageNo >= totalPages}
                  onClick={() => void handlePageChange(pageNo + 1)}
                >
                  下一页 <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border-cream bg-ivory p-5">
            <h3 className="font-serif text-lg text-near-black">最近入库作业</h3>
            <p className="mt-1 text-sm text-stone-gray">来自 `/ingest-jobs` 的真实作业状态。</p>
          </div>

          <div className="space-y-3">
            {jobRows.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border-warm bg-ivory p-4 text-sm text-stone-gray">
                暂无入库作业。
              </div>
            ) : (
              jobRows.map((job) => (
                <div key={job.id} className="rounded-xl border border-border-cream bg-ivory p-4 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-near-black truncate">{job.stage}</p>
                      <p className="text-xs text-stone-gray font-mono mt-1">{job.id}</p>
                    </div>
                    <StatusBadge status={job.status} />
                  </div>
                  <div className="text-sm text-stone-gray">
                    <div>进度：{job.progress}%</div>
                    <div className="mt-1">触发时间：{job.createdAtLabel}</div>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {job.indexStages.map((stage) => (
                      <Badge key={stage.key} variant={indexStageVariant(stage.status)}>
                        {stage.label}: {formatIndexStageStatus(stage.status)}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="rounded-xl border border-border-cream bg-ivory p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-serif text-lg text-near-black">索引同步作业</h3>
                <p className="mt-1 text-sm text-stone-gray">查看目标副本、失败原因，并可重建当前知识库索引。</p>
              </div>
              <Button variant="ghost" size="sm" disabled={loading} onClick={() => void handleKnowledgeBaseIndexRebuild()} title="重建索引">
                <Database className="w-4 h-4" />
              </Button>
            </div>
            <div className="mt-4 space-y-3">
              {indexSyncJobs.length === 0 ? (
                <p className="text-sm text-stone-gray">暂无索引同步作业。</p>
              ) : (
                indexSyncJobs.slice(0, 5).map((job) => (
                  <div key={job.syncJobId} className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-near-black">{job.targetStore}</span>
                      <StatusBadge status={job.status} />
                    </div>
                    <p className="mt-1 text-xs text-stone-gray">类型：{job.syncType}</p>
                    {job.errorMessage && <p className="mt-1 text-xs text-error-red">{job.errorMessage}</p>}
                  </div>
                ))
              )}
            </div>
          </div>
        </aside>
      </div>

      <Drawer isOpen={isUploadOpen} onClose={() => setIsUploadOpen(false)} title="上传文档" width="560px">
        <DrawerSection title="上传信息">
          <div className="space-y-4">
            <div>
              <input
                ref={fileInputRef}
                type="file"
                className="sr-only"
                onChange={(event) => handleUploadFileChange(event.target.files?.[0] ?? null)}
              />
              <div className="flex flex-wrap items-center gap-3">
                <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
                  <Upload className="w-4 h-4 mr-2" /> 选择文件
                </Button>
                <span className="text-sm text-stone-gray">
                  {selectedFile ? selectedFile.name : "未选择文件"}
                </span>
              </div>
            </div>
            <Input
              label="文档名称"
              value={uploadName}
              onChange={(event) => setUploadName(event.target.value)}
              helperText="留空时后端会使用原始文件名。"
            />
            <div>
              <label className="block mb-2 text-sm font-medium text-near-black">文档密级</label>
              <select
                className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-[10px]"
                value={uploadLevel}
                onChange={(event) => setUploadLevel(event.target.value)}
              >
                <option value="public">公开</option>
                <option value="internal">内部</option>
                <option value="confidential">机密</option>
              </select>
            </div>
          </div>
        </DrawerSection>
        <DrawerSection title="提交结果">
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setIsUploadOpen(false)}>
              取消
            </Button>
            <Button variant="primary" disabled={uploading} onClick={() => void handleUploadSubmit()}>
              {uploading ? "提交中..." : "创建上传任务"}
            </Button>
          </div>
        </DrawerSection>
      </Drawer>
    </div>
  );
}
