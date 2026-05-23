import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Search, Download, FileWarning, Eye, ChevronLeft, ChevronRight, Database, RefreshCw, Trash2, FolderOpen } from "lucide-react";
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
} from "../services/documentService";
import { fetchLibraryDocuments, fetchLibraryVersions, bindDocumentsToKB, listKBBindings, switchBindingVersion } from "../services/libraryService";
import { fetchKbPermissionSummary } from "../services/knowledgeBaseService";
import type { BulkDocumentGovernanceRequest, DocumentDTO, IndexStageViewModel, IndexSyncJobDTO, IngestJobDTO, JobStatus } from "../types/document";
import type { LibraryBindingDTO, LibraryDocumentDTO, LibraryDocumentVersionDTO } from "../types/library";
import type { PermissionSummary } from "../types/knowledgeBase";
import { chunkRevisionStatusLabel, chunkRevisionStatusVariant } from "../utils/threeLayerPresentation";

const DOCUMENT_PAGE_SIZE = 10;
type BatchOperation = BulkDocumentGovernanceRequest["operation"];

const BATCH_OPERATION_LABELS: Record<BatchOperation, string> = {
  reparse: "批量重解析",
  disable: "批量停用",
  rebuild_index: "批量重建索引",
};

const PERMISSION_LABELS: Record<string, string> = {
  "kb.view": "查看知识库",
  "kb.member.manage": "成员管理",
  "kb.document.read": "查看文档",
  "kb.document.upload": "上传/重建",
  "kb.document.download": "下载原文",
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
  const [indexRebuildTargetStore, setIndexRebuildTargetStore] = useState("neo4j");
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | JobStatus>("");
  const [loading, setLoading] = useState(false);
  const [downloadingDocumentId, setDownloadingDocumentId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);
  const [showLibraryPicker, setShowLibraryPicker] = useState(false);
  const [libraryDocs, setLibraryDocs] = useState<LibraryDocumentDTO[]>([]);
  const [libraryTotal, setLibraryTotal] = useState(0);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [bindingLoading, setBindingLoading] = useState(false);
  const [versionPickerDoc, setVersionPickerDoc] = useState<LibraryDocumentDTO | null>(null);
  const [versionPickerVersions, setVersionPickerVersions] = useState<LibraryDocumentVersionDTO[]>([]);
  const [versionPickerLoading, setVersionPickerLoading] = useState(false);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [kbBindings, setKbBindings] = useState<LibraryBindingDTO[]>([]);
  const [switchTarget, setSwitchTarget] = useState<LibraryBindingDTO | null>(null);
  const [switchVersions, setSwitchVersions] = useState<LibraryDocumentVersionDTO[]>([]);
  const [selectedSwitchVersionId, setSelectedSwitchVersionId] = useState<string | null>(null);
  const [switchLoading, setSwitchLoading] = useState(false);
  const [permissionSummary, setPermissionSummary] = useState<PermissionSummary | null>(null);

  async function loadData(keyword = searchTerm, nextPageNo = pageNo) {
    if (!kbId) return;
    setLoading(true);
    try {
      const [documentPage, jobPage, bindingRows] = await Promise.all([
        fetchDocuments(kbId, { keyword, pageNo: nextPageNo, pageSize: DOCUMENT_PAGE_SIZE }),
        fetchIngestJobs(kbId),
        listKBBindings(kbId),
      ]);
      const indexSyncPage = await fetchIndexSyncJobs(kbId);
      setDocuments(documentPage.items);
      setDocumentTotal(documentPage.total);
      setPageNo(documentPage.pageNo);
      setJobs(jobPage.items);
      setKbBindings(bindingRows);
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
    if (!kbId) return;
    void loadData("", 1);
    void fetchKbPermissionSummary(kbId).then(setPermissionSummary).catch(() => {
      setPermissionSummary(null);
    });
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
      title: `重建 ${indexRebuildTargetStore} 索引？`,
      description: "未选择文档时会按当前知识库 active Chunk 范围重建目标副本。",
      confirmText: "重建索引",
    });
    if (!ok) return;

    setLoading(true);
    try {
      await rebuildIndexSync(kbId, { targetStore: indexRebuildTargetStore });
      const nextJobs = await fetchIndexSyncJobs(kbId);
      setIndexSyncJobs(nextJobs.items);
      setFeedback({ variant: "success", title: "索引重建已创建", message: `${indexRebuildTargetStore} 副本重建作业已写入。` });
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

  async function loadLibraryDocs() {
    setLibraryLoading(true);
    try {
      const page = await fetchLibraryDocuments({ pageSize: 100 });
      setLibraryDocs(page.items);
      setLibraryTotal(page.total);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "文档库加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务。",
      });
    } finally {
      setLibraryLoading(false);
    }
  }

  function handleOpenLibraryPicker() {
    setSelectedDocIds([]);
    setShowLibraryPicker(true);
    void loadLibraryDocs();
  }

  async function handleBind() {
    if (selectedDocIds.length === 0) {
      setFeedback({ variant: "warning", title: "请选择文档", message: "请至少选择一个文档库文档。" });
      return;
    }
    // Single document: open version picker for explicit version selection
    if (selectedDocIds.length === 1) {
      const doc = libraryDocs.find((d) => d.documentId === selectedDocIds[0]);
      if (doc) {
        setShowLibraryPicker(false);
        await openVersionPicker(doc);
        return;
      }
    }
    // Multiple documents: bind directly using active version
    await handleBindDirect();
  }

  async function handleBindDirect() {
    setBindingLoading(true);
    try {
      const result = await bindDocumentsToKB(kbId, selectedDocIds);
      setFeedback({
        variant: "success",
        title: "绑定成功",
        message: `已绑定 ${result.bindings.length} 个文档到当前知识库。`,
      });
      setShowLibraryPicker(false);
      await loadData(searchTerm, 1);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "绑定失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setBindingLoading(false);
    }
  }

  async function openVersionPicker(doc: LibraryDocumentDTO) {
    setVersionPickerDoc(doc);
    setSelectedVersionId(null);
    setVersionPickerLoading(true);
    try {
      const versions = await fetchLibraryVersions(doc.documentId);
      setVersionPickerVersions(versions.filter((v) => v.parseStatus === "success"));
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "版本加载失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
      setVersionPickerVersions([]);
    } finally {
      setVersionPickerLoading(false);
    }
  }

  async function handleBindWithSelectedVersion() {
    if (!versionPickerDoc || !selectedVersionId) return;
    setBindingLoading(true);
    try {
      const result = await bindDocumentsToKB(kbId, [versionPickerDoc.documentId], selectedVersionId);
      setFeedback({
        variant: "success",
        title: "绑定成功",
        message: `已绑定文档到当前知识库。`,
      });
      setVersionPickerDoc(null);
      await loadData(searchTerm, 1);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "绑定失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setBindingLoading(false);
    }
  }

  async function openSwitchDrawer(binding: LibraryBindingDTO) {
    setSwitchTarget(binding);
    setSelectedSwitchVersionId(null);
    setSwitchVersions([]);
    setSwitchLoading(true);
    try {
      const versions = await fetchLibraryVersions(binding.documentId);
      setSwitchVersions(versions.filter((v) => v.parseStatus === "success"));
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "版本加载失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setSwitchLoading(false);
    }
  }

  async function handleSwitchBindingVersion() {
    if (!switchTarget || !selectedSwitchVersionId) return;
    setSwitchLoading(true);
    try {
      const updated = await switchBindingVersion(kbId, switchTarget.bindingId, selectedSwitchVersionId);
      setKbBindings((current) => current.map((binding) => binding.bindingId === updated.bindingId ? updated : binding));
      setFeedback({
        variant: "success",
        title: "版本切换已提交",
        message: "新的 ChunkRevision 已进入构建流程；构建完成前旧 active revision 继续可检索。",
      });
      setSwitchTarget(null);
      await loadData(searchTerm, pageNo);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "版本切换失败",
        message: error instanceof Error ? error.message : "请确认目标版本已解析成功。",
      });
    } finally {
      setSwitchLoading(false);
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
            <Button variant="primary" onClick={handleOpenLibraryPicker}>
              <FolderOpen className="w-4 h-4 mr-2" /> 从文档库添加
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
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-serif text-lg text-near-black">知识库权限</h3>
                <p className="mt-1 text-sm text-stone-gray">当前账号在该知识库上的有效权限摘要。</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate(`/kb/${kbId}/members`)}>
                管理
              </Button>
            </div>
            {permissionSummary ? (
              <div className="mt-4 space-y-3 text-sm">
                <div className="flex flex-wrap gap-2">
                  {(permissionSummary.roles.length > 0 ? permissionSummary.roles : ["无角色"]).slice(0, 4).map((role) => (
                    <Badge key={role} variant={role === "无角色" ? "inactive" : "info"}>{role}</Badge>
                  ))}
                  {permissionSummary.inheritedFromPlatformRole && <Badge variant="success">平台继承</Badge>}
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(PERMISSION_LABELS).map(([code, label]) => (
                    <div key={code} className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment px-3 py-2">
                      <span className="text-stone-gray">{label}</span>
                      <Badge variant={permissionSummary.permissions.includes(code) ? "success" : "inactive"}>
                        {permissionSummary.permissions.includes(code) ? "允许" : "无"}
                      </Badge>
                    </div>
                  ))}
                </div>
                {permissionSummary.deniedReasons.length > 0 && (
                  <Alert variant="warning" title="存在拒绝原因">
                    {permissionSummary.deniedReasons.join("；")}
                  </Alert>
                )}
              </div>
            ) : (
              <p className="mt-4 text-sm text-stone-gray">权限摘要暂不可用，可进入成员页查看角色配置。</p>
            )}
          </div>

          <div className="rounded-xl border border-border-cream bg-ivory p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-serif text-lg text-near-black">三层绑定状态</h3>
                <p className="mt-1 text-sm text-stone-gray">展示文档库版本到知识库 ChunkRevision 的当前状态。</p>
              </div>
              <Badge variant="info">{kbBindings.length}</Badge>
            </div>
            <div className="mt-4 space-y-3">
              {kbBindings.length === 0 ? (
                <p className="text-sm text-stone-gray">暂无文档库绑定。</p>
              ) : (
                kbBindings.slice(0, 6).map((binding) => (
                  <div key={binding.bindingId} className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-near-black truncate">{binding.documentName || binding.documentId}</p>
                        <p className="mt-1 font-mono text-xs text-stone-gray">{binding.bindingId.slice(0, 8)}</p>
                      </div>
                      <Badge variant={chunkRevisionStatusVariant(binding.chunkRevisionStatus)}>
                        {chunkRevisionStatusLabel(binding.chunkRevisionStatus)}
                      </Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-stone-gray">
                      <span>Chunk: {binding.chunkRevisionChunkCount ?? binding.chunkCount}</span>
                      <span>版本: {(binding.chunkRevisionVersionId ?? binding.versionId).slice(0, 8)}</span>
                    </div>
                    {binding.errorMessage && <p className="mt-2 text-xs text-error-red">{binding.errorMessage}</p>}
                    <Button variant="ghost" size="sm" className="mt-2" onClick={() => void openSwitchDrawer(binding)}>
                      切换版本
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>

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
              <div className="flex items-center gap-2">
                <select
                  className="px-2 py-1.5 bg-parchment border border-border-cream rounded-md text-xs text-near-black focus:outline-none focus:ring-1 focus:ring-focus-blue"
                  value={indexRebuildTargetStore}
                  onChange={(event) => setIndexRebuildTargetStore(event.target.value)}
                  aria-label="索引重建目标库"
                >
                  <option value="neo4j">neo4j</option>
                  <option value="milvus">milvus</option>
                  <option value="opensearch">opensearch</option>
                </select>
                <Button variant="ghost" size="sm" disabled={loading} onClick={() => void handleKnowledgeBaseIndexRebuild()} title="重建索引">
                  <Database className="w-4 h-4" />
                </Button>
              </div>
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

      {/* 文档库选择弹窗 */}
      {showLibraryPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShowLibraryPicker(false)} />
          <div className="relative bg-ivory border border-border-cream rounded-xl shadow-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-border-cream">
              <h2 className="font-serif text-lg text-near-black">从文档库添加</h2>
              <Button variant="ghost" size="sm" onClick={() => setShowLibraryPicker(false)}>
                <span className="text-stone-gray text-lg">&times;</span>
              </Button>
            </div>
            <div className="flex-1 min-h-0 overflow-auto p-4">
              {libraryLoading ? (
                <p className="text-center text-stone-gray py-8">加载中...</p>
              ) : libraryDocs.length === 0 ? (
                <p className="text-center text-stone-gray py-8">文档库暂无文档</p>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-stone-gray mb-3">共 {libraryTotal} 个文档库文档，已选 {selectedDocIds.length} 个</p>
                  {libraryDocs.map((doc) => (
                    <label
                      key={doc.documentId}
                      className="flex items-center gap-3 p-3 rounded-lg border border-border-cream bg-parchment cursor-pointer hover:bg-border-cream/30"
                    >
                      <input
                        type="checkbox"
                        checked={selectedDocIds.includes(doc.documentId)}
                        onChange={(event) => {
                          setSelectedDocIds((current) =>
                            event.target.checked
                              ? [...current, doc.documentId]
                              : current.filter((id) => id !== doc.documentId)
                          );
                        }}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium text-near-black truncate">{doc.name}</p>
                        <p className="text-xs text-stone-gray">{doc.sourceType}</p>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-border-cream">
              <Button variant="ghost" onClick={() => setShowLibraryPicker(false)}>
                取消
              </Button>
              <Button variant="primary" disabled={bindingLoading || selectedDocIds.length === 0} onClick={() => void handleBind()}>
                {bindingLoading ? "绑定中..." : `绑定选中文档 (${selectedDocIds.length})`}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 版本选择 Drawer */}
      <Drawer isOpen={!!versionPickerDoc} onClose={() => setVersionPickerDoc(null)} title={`选择版本 — ${versionPickerDoc?.name ?? ""}`}>
        <DrawerSection title="可用版本">
          {versionPickerLoading ? (
            <p className="text-center text-stone-gray py-8">加载版本列表...</p>
          ) : versionPickerVersions.length === 0 ? (
            <p className="text-center text-stone-gray py-8">暂无可绑定的已解析版本</p>
          ) : (
            <div className="space-y-2">
              {versionPickerVersions.map((v) => (
                <label
                  key={v.versionId}
                  className="flex items-start gap-3 p-3 rounded-lg border border-border-cream bg-parchment cursor-pointer hover:bg-border-cream/30"
                >
                  <input
                    type="radio"
                    name="version-picker"
                    checked={selectedVersionId === v.versionId}
                    onChange={() => setSelectedVersionId(v.versionId)}
                    className="mt-1"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-near-black">v{v.versionNo}</p>
                    <p className="text-xs text-stone-gray">{v.fileName ?? "—"}</p>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-stone-gray">
                      <span>Chunks: {v.chunkCount}</span>
                      {v.tokenCount != null && <span>Tokens: {v.tokenCount}</span>}
                      <span>创建时间: {new Date(v.createdAt).toLocaleString()}</span>
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </DrawerSection>
        <DrawerSection>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setVersionPickerDoc(null)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={bindingLoading || !selectedVersionId}
              onClick={() => void handleBindWithSelectedVersion()}
            >
              {bindingLoading ? "绑定中..." : "使用此版本绑定"}
            </Button>
          </div>
        </DrawerSection>
      </Drawer>

      <Drawer isOpen={!!switchTarget} onClose={() => setSwitchTarget(null)} title={`切换绑定版本 — ${switchTarget?.documentName ?? ""}`}>
        <DrawerSection title="可用库文档版本">
          {switchLoading ? (
            <p className="text-center text-stone-gray py-8">加载版本列表...</p>
          ) : switchVersions.length === 0 ? (
            <p className="text-center text-stone-gray py-8">暂无可切换的已解析版本</p>
          ) : (
            <div className="space-y-2">
              {switchVersions.map((v) => (
                <label
                  key={v.versionId}
                  className="flex items-start gap-3 p-3 rounded-lg border border-border-cream bg-parchment cursor-pointer hover:bg-border-cream/30"
                >
                  <input
                    type="radio"
                    name="switch-version-picker"
                    checked={selectedSwitchVersionId === v.versionId}
                    onChange={() => setSelectedSwitchVersionId(v.versionId)}
                    className="mt-1"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-near-black">v{v.versionNo}</p>
                    <p className="text-xs text-stone-gray">{v.fileName ?? "—"}</p>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-stone-gray">
                      <span>Chunks: {v.chunkCount}</span>
                      {v.tokenCount != null && <span>Tokens: {v.tokenCount}</span>}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </DrawerSection>
        <DrawerSection>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setSwitchTarget(null)}>
              取消
            </Button>
            <Button
              variant="primary"
              disabled={switchLoading || !selectedSwitchVersionId}
              onClick={() => void handleSwitchBindingVersion()}
            >
              {switchLoading ? "提交中..." : "提交切换"}
            </Button>
          </div>
        </DrawerSection>
      </Drawer>
    </div>
  );
}
