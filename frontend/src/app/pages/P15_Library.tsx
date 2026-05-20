import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { Search, Upload, Download, FileText, ChevronLeft, ChevronRight, Trash2, RefreshCw, Power } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Card, CardContent } from "../components/rag/Card";
import { chooseActiveDictionaryValue, dictionaryItemsToOptions, fetchDictionaryItemsWithFallback } from "../services/dictionaryService";
import {
  fetchLibraryDocuments,
  uploadLibraryDocumentWithProgress,
  downloadLibraryDocument,
  fetchLibraryStats,
  batchAction,
} from "../services/libraryService";
import type { LibraryDocumentDTO, LibraryParseJobStatus, LibraryStatsResponse, UploadProgress } from "../types/library";
import type { DictionaryItemDTO } from "../types/dictionary";

const PAGE_SIZE = 20;

function parseStatusVariant(status: string) {
  if (status === "success") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "running";
  return "queued";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function Library() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<LibraryDocumentDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [pageNo, setPageNo] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [uploadLevel, setUploadLevel] = useState("internal");
  const [securityLevelItems, setSecurityLevelItems] = useState<DictionaryItemDTO[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  const [stats, setStats] = useState<LibraryStatsResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchLibraryStats();
      setStats(data);
    } catch {}
  }, []);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  async function loadData(keyword = searchTerm, nextPageNo = pageNo) {
    setLoading(true);
    try {
      const page = await fetchLibraryDocuments({
        keyword,
        pageNo: nextPageNo,
        pageSize: PAGE_SIZE,
        status: statusFilter || undefined,
      });
      setDocuments(page.items);
      setTotal(page.total);
      setPageNo(page.pageNo);
      void loadStats();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "文档库加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务。",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData("", 1);
  }, [statusFilter]);

  useEffect(() => {
    void fetchDictionaryItemsWithFallback("security_level").then((items) => {
      setSecurityLevelItems(items);
      setUploadLevel((current) => chooseActiveDictionaryValue(items, current, "internal"));
    });
  }, []);

  const securityLevelOptions = useMemo(() => dictionaryItemsToOptions(securityLevelItems), [securityLevelItems]);

  async function handleSearchSubmit() {
    await loadData(searchTerm, 1);
  }

  async function handleUploadSubmit() {
    if (!selectedFile) {
      setFeedback({ variant: "warning", title: "请选择文件", message: "请先选择要上传的文档。" });
      return;
    }
    setUploading(true);
    setUploadProgress(null);
    try {
      const upload = uploadLibraryDocumentWithProgress(selectedFile, uploadName, uploadLevel);
      upload.onProgress((progress) => setUploadProgress(progress));
      await upload.promise;
      setFeedback({ variant: "success", title: "上传成功", message: "文档已上传，文本提取任务已创建。" });
      setSelectedFile(null);
      setUploadName("");
      setIsUploadOpen(false);
      setUploadProgress(null);
      await loadData(searchTerm, 1);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "上传失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setUploading(false);
      setUploadProgress(null);
    }
  }

  function handleUploadFileChange(file: File | null) {
    setSelectedFile(file);
    setUploadName(file?.name ?? "");
  }

  async function handleDownload(doc: LibraryDocumentDTO) {
    try {
      const result = await downloadLibraryDocument(doc.documentId);
      const url = URL.createObjectURL(result.blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = result.fileName ?? doc.name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "下载失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    }
  }

  async function handleBatchAction(action: "delete" | "reparse" | "disable") {
    if (selectedIds.size === 0) return;
    const actionLabel = { delete: "删除", reparse: "重新解析", disable: "停用" }[action];
    if (!confirm(`确定要${actionLabel}选中的 ${selectedIds.size} 个文档吗？`)) return;

    setBatchLoading(true);
    try {
      const result = await batchAction(Array.from(selectedIds), action);
      setFeedback({
        variant: result.failed.length > 0 ? "warning" : "success",
        title: `批量${actionLabel}完成`,
        message: `成功 ${result.summary.succeeded} 个，失败 ${result.summary.failed} 个`,
      });
      setSelectedIds(new Set());
      await loadData(searchTerm, pageNo);
      await loadStats();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: `批量${actionLabel}失败`,
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setBatchLoading(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="我的文档库"
        description="管理个人文档，上传后可预览并按需绑定到知识库。"
        actions={
          <Button onClick={() => setIsUploadOpen(true)}>
            <Upload className="w-4 h-4 mr-2" /> 上传文档
          </Button>
        }
      />

      <div className="flex-1 min-h-0 overflow-auto p-8 space-y-6">
        {feedback && (
          <Alert
            variant={feedback.variant}
            title={feedback.title}
            onClose={() => setFeedback(null)}
          >
            {feedback.message}
          </Alert>
        )}

        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-3 gap-4">
            <Card className="cursor-pointer hover:border-terracotta transition-colors" onClick={() => { setStatusFilter(""); void loadData("", 1); }}>
              <CardContent className="py-4">
                <div className="text-2xl font-semibold text-near-black">{stats.totalDocuments}</div>
                <div className="text-sm text-stone-gray">总文档数</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-4">
                <div className="text-2xl font-semibold text-near-black">{stats.todayUploads}</div>
                <div className="text-sm text-stone-gray">今日上传</div>
              </CardContent>
            </Card>
            <Card className="cursor-pointer hover:border-terracotta transition-colors" onClick={() => { setStatusFilter("active"); void loadData("", 1); }}>
              <CardContent className="py-4">
                <div className="text-2xl font-semibold text-amber-600">{stats.pendingParse}</div>
                <div className="text-sm text-stone-gray">待解析</div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* 搜索和筛选 */}
        <div className="flex items-center gap-4">
          <div className="flex-1 max-w-md">
            <Input
              placeholder="搜索文档名称..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSearchSubmit()}
              icon={<Search className="w-4 h-4" />}
            />
          </div>
          <select
            className="border border-border-cream rounded-md px-3 py-2 text-sm bg-ivory"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">全部状态</option>
            <option value="active">正常</option>
            <option value="disabled">已停用</option>
            <option value="archived">已归档</option>
          </select>
          <Button variant="secondary" onClick={() => void handleSearchSubmit()}>
            搜索
          </Button>
        </div>

        {/* 批量操作栏 */}
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-3 p-3 bg-parchment rounded-lg border border-border-cream">
            <span className="text-sm text-near-black">已选 {selectedIds.size} 个文档</span>
            <Button variant="ghost" size="sm" disabled={batchLoading} onClick={() => void handleBatchAction("reparse")}>
              <RefreshCw className="w-4 h-4 mr-1" /> 重新解析
            </Button>
            <Button variant="ghost" size="sm" disabled={batchLoading} onClick={() => void handleBatchAction("disable")}>
              <Power className="w-4 h-4 mr-1" /> 停用
            </Button>
            <Button variant="ghost" size="sm" disabled={batchLoading} onClick={() => void handleBatchAction("delete")} className="text-red-600 hover:text-red-700">
              <Trash2 className="w-4 h-4 mr-1" /> 删除
            </Button>
          </div>
        )}

        {/* 文档列表 */}
        {loading ? (
          <div className="text-center py-12 text-stone-gray">加载中...</div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
            <p className="text-stone-gray">暂无文档</p>
            <p className="text-sm text-stone-gray mt-1">点击"上传文档"开始使用</p>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === documents.length && documents.length > 0}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedIds(new Set(documents.map((d) => d.documentId)));
                        } else {
                          setSelectedIds(new Set());
                        }
                      }}
                      className="h-4 w-4 accent-terracotta"
                    />
                  </TableHead>
                  <TableHead>文档名称</TableHead>
                  <TableHead>密级</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow
                    key={doc.documentId}
                    onClick={() => navigate(`/library/${doc.documentId}`)}
                  >
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(doc.documentId)}
                        onChange={(e) => {
                          const next = new Set(selectedIds);
                          if (e.target.checked) next.add(doc.documentId);
                          else next.delete(doc.documentId);
                          setSelectedIds(next);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="h-4 w-4 accent-terracotta"
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-stone-gray" />
                        <span className="truncate max-w-[300px]">{doc.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="info">{doc.securityLevel}</Badge>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={doc.status === "active" ? "active" : doc.status === "disabled" ? "inactive" : "draft"} />
                    </TableCell>
                    <TableCell>{new Date(doc.createdAt).toLocaleString("zh-CN")}</TableCell>
                    <TableCell>{new Date(doc.updatedAt).toLocaleString("zh-CN")}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDownload(doc);
                        }}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-stone-gray">共 {total} 个文档</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={pageNo <= 1}
                    onClick={() => void loadData(searchTerm, pageNo - 1)}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <span className="text-sm text-near-black">{pageNo} / {totalPages}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={pageNo >= totalPages}
                    onClick={() => void loadData(searchTerm, pageNo + 1)}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* 上传抽屉 */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/30" onClick={() => setIsUploadOpen(false)} />
          <div className="relative ml-auto w-[420px] bg-ivory border-l border-border-cream flex flex-col shadow-xl">
            <div className="p-6 border-b border-border-cream">
              <h2 className="text-lg font-serif text-near-black">上传文档</h2>
              <p className="text-sm text-stone-gray mt-1">文件将保存到个人文档库</p>
            </div>
            <div className="flex-1 p-6 space-y-4 overflow-auto">
              <div>
                <label className="block text-sm font-medium text-near-black mb-1">选择文件</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".txt,.md,.pdf,.docx"
                  onChange={(e) => handleUploadFileChange(e.target.files?.[0] ?? null)}
                />
                <Button
                  variant="secondary"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full"
                >
                  {selectedFile ? selectedFile.name : "点击选择文件"}
                </Button>
                {selectedFile && (
                  <p className="text-xs text-stone-gray mt-1">{formatFileSize(selectedFile.size)}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-near-black mb-1">文档名称</label>
                <Input
                  value={uploadName}
                  onChange={(e) => setUploadName(e.target.value)}
                  placeholder="留空则使用文件名"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-near-black mb-1">密级</label>
                <select
                  className="w-full border border-border-cream rounded-md px-3 py-2 text-sm bg-white"
                  value={uploadLevel}
                  onChange={(e) => setUploadLevel(e.target.value)}
                >
                  {securityLevelOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>
            {uploading && uploadProgress && (
              <div className="px-6 pb-2 space-y-2">
                <div className="flex justify-between text-sm text-stone-gray">
                  <span>上传中: {selectedFile?.name}</span>
                  <span>{uploadProgress.percent}% ({formatFileSize(uploadProgress.loaded)}/{formatFileSize(uploadProgress.total)})</span>
                </div>
                <div className="w-full bg-border-cream rounded-full h-2">
                  <div
                    className="bg-terracotta h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress.percent}%` }}
                  />
                </div>
              </div>
            )}
            <div className="p-6 border-t border-border-cream flex items-center gap-3">
              <Button variant="secondary" className="flex-1" onClick={() => setIsUploadOpen(false)}>
                取消
              </Button>
              <Button className="flex-1" disabled={uploading} onClick={() => void handleUploadSubmit()}>
                {uploading ? "上传中..." : "确认上传"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
