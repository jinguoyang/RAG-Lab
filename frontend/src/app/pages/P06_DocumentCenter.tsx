import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Download, FileWarning, Eye, RefreshCw, Trash2, FolderOpen } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Alert } from "../components/rag/Alert";
import { StatusBadge } from "../components/rag/Badge";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { DocumentListLayout } from "../components/rag/DocumentListLayout";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { toDocumentRow } from "../adapters/documentAdapter";
import {
  fetchDocuments,
  deleteDocument,
  downloadDocumentSource,
  runBulkDocumentGovernance,
} from "../services/documentService";
import { fetchLibraryDocuments, fetchLibraryVersions, bindDocumentsToKB } from "../services/libraryService";
import type { DocumentDTO, JobStatus } from "../types/document";
import type { LibraryDocumentDTO, LibraryDocumentVersionDTO } from "../types/library";

const DOCUMENT_PAGE_SIZE = 10;

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
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
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

  async function loadData(keyword = searchTerm, nextPageNo = pageNo) {
    if (!kbId) return;
    setLoading(true);
    try {
      const documentPage = await fetchDocuments(kbId, { keyword, pageNo: nextPageNo, pageSize: DOCUMENT_PAGE_SIZE });
      setDocuments(documentPage.items);
      setDocumentTotal(documentPage.total);
      setPageNo(documentPage.pageNo);
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
  }, [kbId]);


  const rows = useMemo(() => documents.map(toDocumentRow), [documents]);
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
      setFeedback({ variant: "warning", title: "请选择文档", message: "重新治理需要先选择至少一个文档。" });
      return;
    }
    const ok = await confirm({
      title: "确认重新治理？",
      description: `重新治理会影响 ${selectedDocumentIds.length} 个文档，操作会写入审计记录。`,
      confirmText: "重新治理",
    });
    if (!ok) return;

    setLoading(true);
    try {
      const response = await runBulkDocumentGovernance(kbId, {
        operation: "full_governance",
        documentIds: selectedDocumentIds,
        confirmImpact: true,
        reason: "P06 重新治理",
        targetStore: null,
      });
      setFeedback({
        variant: response.failedCount > 0 ? "warning" : "success",
        title: "重新治理已提交",
        message: `成功 ${response.successCount} 项，失败 ${response.failedCount} 项。`,
      });
      setSelectedDocumentIds([]);
      await loadData(searchTerm, pageNo);
    } catch (error) {
      setFeedback({ variant: "error", title: "重新治理失败", message: error instanceof Error ? error.message : "请稍后重试。" });
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

  async function handleBatchDelete() {
    if (selectedDocumentIds.length === 0) {
      setFeedback({ variant: "warning", title: "请选择文档", message: "批量删除需要先选择至少一个文档。" });
      return;
    }
    const ok = await confirm({
      title: `确认批量删除 ${selectedDocumentIds.length} 个文档？`,
      description: "删除后，文档会立即从列表、检索和图支撑结果中移除，并尝试清理 MinIO 与检索副本。此操作不可撤销。",
      confirmText: "批量删除",
      variant: "destructive",
    });
    if (!ok) return;

    setLoading(true);
    let successCount = 0;
    let failCount = 0;
    const warnings: string[] = [];
    try {
      for (const documentId of selectedDocumentIds) {
        try {
          const response = await deleteDocument(kbId, documentId, "P06 批量删除文档");
          successCount++;
          if (response.warnings.length > 0) {
            warnings.push(...response.warnings);
          }
        } catch {
          failCount++;
        }
      }
      setFeedback({
        variant: failCount > 0 ? "warning" : "success",
        title: "批量删除完成",
        message: `成功 ${successCount} 项，失败 ${failCount} 项。${warnings.length > 0 ? warnings.join("；") : ""}`,
      });
      setSelectedDocumentIds([]);
      await loadData(searchTerm, pageNo);
    } catch (error) {
      setFeedback({ variant: "error", title: "批量删除失败", message: error instanceof Error ? error.message : "请稍后重试。" });
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

  const totalPages = Math.max(1, Math.ceil(documentTotal / DOCUMENT_PAGE_SIZE));
  const currentPageSelected = filteredRows.length > 0 && filteredRows.every((row) => selectedDocumentIds.includes(row.id));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="文档中心"
        description="管理已绑定文档、版本入口与知识库治理动作。"
        actions={
          <Button variant="primary" onClick={handleOpenLibraryPicker}>
            <FolderOpen className="w-4 h-4 mr-2" /> 从文档库添加
          </Button>
        }
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
        </Alert>
      )}

      <DocumentListLayout
          search={{
            placeholder: "按文档名搜索...",
            value: searchTerm,
            onChange: setSearchTerm,
            onSearch: () => void handleSearchSubmit(),
          }}
          statusFilter={{
            value: statusFilter,
            onChange: (value) => setStatusFilter(value as "" | JobStatus),
            options: [
              { value: "", label: "全部状态" },
              { value: "success", label: "可见文档" },
              { value: "cancelled", label: "非活动" },
            ],
          }}
          batch={{
            selectedCount: selectedDocumentIds.length,
            actions: [
              {
                label: "重新治理",
                icon: <RefreshCw className="w-4 h-4" />,
                onClick: () => void handleBatchGovernance(),
              },
              {
                label: "批量删除",
                icon: <Trash2 className="w-4 h-4" />,
                variant: "destructive",
                onClick: () => void handleBatchDelete(),
              },
            ],
          }}
          loading={loading}
          itemCount={filteredRows.length}
          emptyState={
            <>
              <div className="mx-auto mb-3 w-12 h-12 rounded-full bg-parchment flex items-center justify-center">
                <FileWarning className="w-5 h-5 text-stone-gray" />
              </div>
              <h3 className="text-lg font-serif text-near-black">暂无文档</h3>
              <p className="mt-2 text-sm text-stone-gray">
                从文档库添加文档后，会在当前知识库生成可检索的 ChunkRevision。
              </p>
            </>
          }
          pagination={{
            total: documentTotal,
            pageNo,
            totalPages,
            loading,
            onPageChange: (page) => void handlePageChange(page),
          }}
        >
          {filteredRows.length > 0 && (
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
        </DocumentListLayout>

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
    </div>
  );
}
