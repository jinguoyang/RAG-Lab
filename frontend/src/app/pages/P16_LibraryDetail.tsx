import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { Copy, Download, FileText, RefreshCw, Settings2, Trash2, Upload } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { UnderlineTabs, UnderlineTabsList, UnderlineTabsTrigger, UnderlineTabsContent } from "../components/rag/UnderlineTabs";
import { Button } from "../components/rag/Button";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Alert } from "../components/rag/Alert";
import { PdfPreview } from "../components/rag/PdfPreview";
import { TextPreview } from "../components/rag/TextPreview";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { Input } from "../components/rag/Input";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import {
  activateLibraryVersion,
  createLibraryParseRevision,
  deleteLibraryVersion,
  downloadLibraryDocument,
  fetchDocumentText,
  fetchDocumentUsage,
  fetchLibraryDocumentDetail,
  fetchLibraryParseRevisions,
  fetchLibraryVersions,
  getDeletionImpact,
  uploadLibraryVersionWithProgress,
} from "../services/libraryService";
import type {
  DeletionImpactAnalysis,
  LibraryDocumentDetailDTO,
  LibraryDocumentUsageDTO,
  LibraryDocumentVersionDTO,
  ParseRevisionDTO,
  UploadProgress,
} from "../types/library";

const DocxPreview = lazy(async () => ({
  default: (await import("../components/rag/DocxPreview")).DocxPreview,
}));

function getPreviewType(fileName: string): "pdf" | "markdown" | "text" | "docx" | "unsupported" {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "md" || ext === "markdown") return "markdown";
  if (ext === "txt") return "text";
  if (ext === "docx") return "docx";
  return "unsupported";
}

function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function parseStatusVariant(status: string | null | undefined): "success" | "error" | "running" | "queued" {
  if (status === "success" || status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "running";
  return "queued";
}

function parseOptionsSummary(options?: Record<string, unknown>) {
  if (!options || Object.keys(options).length === 0) return "-";
  return Object.entries(options)
    .filter(([key]) => key !== "errorCode" && key !== "errorMessage")
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" / ") || "-";
}

export function LibraryDetail() {
  const navigate = useNavigate();
  const { libraryId = "", docId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const { confirm } = useConfirmDialog();

  const [detail, setDetail] = useState<LibraryDocumentDetailDTO | null>(null);
  const [versions, setVersions] = useState<LibraryDocumentVersionDTO[]>([]);
  const [parseRevisions, setParseRevisions] = useState<ParseRevisionDTO[]>([]);
  const [usages, setUsages] = useState<LibraryDocumentUsageDTO[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [selectedParseRevisionId, setSelectedParseRevisionId] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(searchParams.get("tab") ?? "overview");
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [uploading, setUploading] = useState(false);

  const [showReparse, setShowReparse] = useState(false);
  const [reparseSubmitting, setReparseSubmitting] = useState(false);
  const [parserName, setParserName] = useState("auto");
  const [contentFormat, setContentFormat] = useState<"markdown" | "text">("markdown");
  const [parseLanguage, setParseLanguage] = useState("zh-CN");
  const [ocrEnabled, setOcrEnabled] = useState(false);
  const [tableStrategy, setTableStrategy] = useState("preserve");
  const [extractImageText, setExtractImageText] = useState(false);
  const [preserveHeadings, setPreserveHeadings] = useState(true);

  const [deleteDrawer, setDeleteDrawer] = useState<{ versionId: string; versionNo: number } | null>(null);
  const [deleteImpact, setDeleteImpact] = useState<DeletionImpactAnalysis | null>(null);
  const [deleteImpactLoading, setDeleteImpactLoading] = useState(false);
  const [strongConfirmChecked, setStrongConfirmChecked] = useState(false);

  const activeVersion = detail?.activeVersion ?? null;
  const selectedVersion = useMemo(
    () => versions.find((version) => version.versionId === selectedVersionId) ?? activeVersion,
    [activeVersion, selectedVersionId, versions],
  );
  const selectedParseRevision = useMemo(
    () => parseRevisions.find((revision) => revision.parseRevisionId === selectedParseRevisionId)
      ?? parseRevisions.find((revision) => revision.status === "success" || revision.status === "completed"),
    [parseRevisions, selectedParseRevisionId],
  );

  async function loadData() {
    setLoading(true);
    try {
      const [detailData, versionsData, usageData] = await Promise.all([
        fetchLibraryDocumentDetail(docId),
        fetchLibraryVersions(docId),
        fetchDocumentUsage(docId),
      ]);
      setDetail(detailData);
      setVersions(versionsData);
      setUsages(usageData.usages);
      setSelectedVersionId((current) => current ?? detailData.activeVersion?.versionId ?? versionsData[0]?.versionId ?? null);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务。",
      });
    } finally {
      setLoading(false);
    }
  }

  async function loadParseRevisions(versionId: string) {
    try {
      const rows = await fetchLibraryParseRevisions(docId, versionId);
      setParseRevisions(rows);
      setSelectedParseRevisionId((current) => current ?? rows.find((row) => row.status === "success" || row.status === "completed")?.parseRevisionId);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "解析版本加载失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    }
  }

  useEffect(() => {
    void loadData();
  }, [docId]);

  useEffect(() => {
    if (selectedVersionId) {
      setSelectedParseRevisionId(undefined);
      void loadParseRevisions(selectedVersionId);
    }
  }, [selectedVersionId]);

  async function handleDownload(versionId?: string) {
    if (!detail) return;
    try {
      const result = await downloadLibraryDocument(docId, versionId);
      const url = URL.createObjectURL(result.blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = result.fileName ?? detail.document.name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setFeedback({ variant: "error", title: "下载失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleDownloadParseText(revision: ParseRevisionDTO) {
    try {
      const result = await fetchDocumentText(docId, "full", revision.parseRevisionId) as { text: string };
      const blob = new Blob([result.text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${detail?.document.name ?? "document"}-${revision.parseRevisionId.slice(0, 8)}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setFeedback({ variant: "error", title: "解析文本下载失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleCopyParseText(revision: ParseRevisionDTO) {
    try {
      const result = await fetchDocumentText(docId, "full", revision.parseRevisionId) as { text: string };
      await navigator.clipboard.writeText(result.text);
      setFeedback({ variant: "success", title: "已复制", message: "解析正文已复制到剪贴板。" });
    } catch (error) {
      setFeedback({ variant: "error", title: "复制失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleVersionUpload() {
    if (!uploadFile) return;
    setUploading(true);
    setUploadProgress(null);
    try {
      const { promise, onProgress } = uploadLibraryVersionWithProgress(docId, uploadFile);
      onProgress(setUploadProgress);
      await promise;
      setFeedback({ variant: "success", title: "上传成功", message: "源文件新版本已上传，解析任务已创建。" });
      setShowUpload(false);
      setUploadFile(null);
      setUploadProgress(null);
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "上传失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setUploading(false);
    }
  }

  async function handleActivateVersion(versionId: string, versionNo: number) {
    const ok = await confirm({
      title: "切换活跃源文件版本",
      description: `确定要将文档库当前源文件切换到 v${versionNo} 吗？已有知识库绑定不会自动变化。`,
      confirmLabel: "确认切换",
    });
    if (!ok) return;
    try {
      await activateLibraryVersion(docId, versionId);
      setFeedback({ variant: "success", title: "切换成功", message: `已切换到 v${versionNo}。` });
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "切换失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleSubmitReparse() {
    if (!selectedVersion) return;
    setReparseSubmitting(true);
    try {
      const result = await createLibraryParseRevision(docId, selectedVersion.versionId, {
        parserName,
        contentFormat,
        reason: "library_detail_reparse",
        parseOptions: {
          language: parseLanguage,
          ocrEnabled,
          tableStrategy,
          extractImageText,
          preserveHeadings,
        },
      });
      setFeedback({ variant: "success", title: "重解析已提交", message: "新的解析版本已创建并排队。" });
      setShowReparse(false);
      setSelectedParseRevisionId(result.parseRevisionId);
      await loadParseRevisions(selectedVersion.versionId);
    } catch (error) {
      setFeedback({ variant: "error", title: "重解析失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setReparseSubmitting(false);
    }
  }

  async function handleDeleteVersion(versionId: string, versionNo: number) {
    setDeleteDrawer({ versionId, versionNo });
    setDeleteImpactLoading(true);
    setStrongConfirmChecked(false);
    setDeleteImpact(null);
    try {
      setDeleteImpact(await getDeletionImpact(docId, versionId));
    } catch (error) {
      setFeedback({ variant: "error", title: "获取影响分析失败", message: error instanceof Error ? error.message : "请稍后重试。" });
      setDeleteDrawer(null);
    } finally {
      setDeleteImpactLoading(false);
    }
  }

  async function handleConfirmDelete() {
    if (!deleteDrawer || !deleteImpact) return;
    if (deleteImpact.requiresStrongConfirmation && !strongConfirmChecked) {
      setFeedback({ variant: "warning", title: "请确认", message: "请先勾选确认选项。" });
      return;
    }
    try {
      await deleteLibraryVersion(docId, deleteDrawer.versionId);
      setFeedback({ variant: "success", title: "删除成功", message: `v${deleteDrawer.versionNo} 已删除。` });
      setDeleteDrawer(null);
      setDeleteImpact(null);
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "删除失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  if (loading) {
    return <div className="flex h-full items-center justify-center text-stone-gray">加载中...</div>;
  }

  if (!detail) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4">
        <p className="text-stone-gray">文档不存在或无权访问</p>
        <Button variant="secondary" onClick={() => navigate("/library")}>返回文档库</Button>
      </div>
    );
  }

  const doc = detail.document;
  const previewType = getPreviewType(doc.name);

  return (
    <div className="flex-1 overflow-auto">
      <div className="mx-auto max-w-7xl space-y-6 p-8">
        <PageHeader
          title={doc.name}
          breadcrumbs={[
            { label: "文档库", href: "/library" },
            { label: "文档列表", href: libraryId ? `/library/${libraryId}` : "/library" },
            { label: doc.name },
          ]}
          actions={
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={() => void loadData()}>
                <RefreshCw className="mr-2 h-4 w-4" /> 刷新
              </Button>
            </div>
          }
        />
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        <UnderlineTabs value={activeTab} onValueChange={setActiveTab} className="flex min-h-0 flex-1 flex-col">
          <UnderlineTabsList className="mb-6">
            {[
              ["overview", "概览"],
              ["versions", "源文件版本"],
              ["parse", "解析版本"],
              ["preview", "预览"],
              ["usage", "使用影响"],
            ].map(([value, label]) => (
              <UnderlineTabsTrigger key={value} value={value}>
                {label}
              </UnderlineTabsTrigger>
            ))}
          </UnderlineTabsList>

          <UnderlineTabsContent value="overview" className="space-y-6 outline-none">
            <div className="rounded-lg border border-border-cream bg-ivory p-6">
              <h2 className="mb-4 font-serif text-near-black">文档信息</h2>
              <div className="grid gap-4 text-sm md:grid-cols-2">
                <div><span className="text-stone-gray">状态：</span><StatusBadge status={doc.status === "active" ? "active" : doc.status === "disabled" ? "inactive" : "draft"} className="ml-2" /></div>
                <div><span className="text-stone-gray">创建时间：</span><span className="ml-2 text-near-black">{new Date(doc.createdAt).toLocaleString("zh-CN")}</span></div>
                <div><span className="text-stone-gray">更新时间：</span><span className="ml-2 text-near-black">{new Date(doc.updatedAt).toLocaleString("zh-CN")}</span></div>
                <div><span className="text-stone-gray">当前文件：</span><span className="ml-2 text-near-black">{activeVersion?.fileName ?? doc.name}</span></div>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
              <div className="rounded-lg border border-border-cream bg-ivory p-4">
                <p className="text-xs text-stone-gray">活跃源文件版本</p>
                <p className="mt-2 font-serif text-xl text-near-black">{activeVersion ? `v${activeVersion.versionNo}` : "无"}</p>
              </div>
              <div className="rounded-lg border border-border-cream bg-ivory p-4">
                <p className="text-xs text-stone-gray">源文件版本数</p>
                <p className="mt-2 font-serif text-xl text-near-black">{versions.length}</p>
              </div>
              <div className="rounded-lg border border-border-cream bg-ivory p-4">
                <p className="text-xs text-stone-gray">当前解析状态</p>
                <p className="mt-2"><Badge variant={parseStatusVariant(selectedParseRevision?.status)}>{selectedParseRevision?.status ?? "无"}</Badge></p>
              </div>
              <div className="rounded-lg border border-border-cream bg-ivory p-4">
                <p className="text-xs text-stone-gray">知识库使用</p>
                <p className="mt-2 font-serif text-xl text-near-black">{usages.length}</p>
              </div>
            </div>
          </UnderlineTabsContent>

          <UnderlineTabsContent value="versions" className="space-y-4 outline-none">
            <div className="flex items-center justify-between">
              <h2 className="font-serif text-near-black">源文件版本</h2>
              <Button onClick={() => setShowUpload(true)}><Upload className="mr-2 h-4 w-4" /> 上传新版本</Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>版本</TableHead>
                  <TableHead>文件名</TableHead>
                  <TableHead>大小</TableHead>
                  <TableHead>文件 Hash</TableHead>
                  <TableHead>源文件状态</TableHead>
                  <TableHead>上传时间</TableHead>
                  <TableHead>当前活跃</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {versions.map((version) => {
                  const isActive = version.versionId === doc.activeVersionId;
                  return (
                    <TableRow key={version.versionId} className={selectedVersionId === version.versionId ? "bg-parchment" : ""} onClick={() => setSelectedVersionId(version.versionId)}>
                      <TableCell className="font-mono">v{version.versionNo}</TableCell>
                      <TableCell>{version.fileName ?? "-"}</TableCell>
                      <TableCell>{formatFileSize(version.fileSize)}</TableCell>
                      <TableCell className="max-w-[160px] truncate font-mono text-xs">{version.fileChecksum ?? "-"}</TableCell>
                      <TableCell><Badge variant={parseStatusVariant(version.parseStatus)}>{version.parseStatus}</Badge></TableCell>
                      <TableCell>{new Date(version.createdAt).toLocaleString("zh-CN")}</TableCell>
                      <TableCell>{isActive ? <Badge variant="success">当前活跃</Badge> : <Badge variant="default">非活跃</Badge>}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {!isActive && version.parseStatus === "success" && (
                            <Button variant="ghost" size="sm" onClick={(event) => { event.stopPropagation(); void handleActivateVersion(version.versionId, version.versionNo); }}>切换</Button>
                          )}
                          <Button variant="ghost" size="sm" title="下载该版本" onClick={(event) => { event.stopPropagation(); void handleDownload(version.versionId); }}>
                            <Download className="h-4 w-4" />
                          </Button>
                          {!isActive && (
                            <Button variant="ghost" size="sm" title="删除影响" onClick={(event) => { event.stopPropagation(); void handleDeleteVersion(version.versionId, version.versionNo); }}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </UnderlineTabsContent>

          <UnderlineTabsContent value="parse" className="space-y-4 outline-none">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <h2 className="font-serif text-near-black">解析版本</h2>
                <select className="rounded-md border border-border-cream bg-white px-3 py-2 text-sm" value={selectedVersionId ?? ""} onChange={(event) => setSelectedVersionId(event.target.value)}>
                  {versions.map((version) => <option key={version.versionId} value={version.versionId}>源文件 v{version.versionNo}</option>)}
                </select>
              </div>
              <Button onClick={() => setShowReparse(true)} disabled={!selectedVersion}>
                <RefreshCw className="mr-2 h-4 w-4" /> 重解析
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>解析版本</TableHead>
                  <TableHead>解析器</TableHead>
                  <TableHead>解析器版本</TableHead>
                  <TableHead>参数</TableHead>
                  <TableHead>产物格式</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>正文长度</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>错误信息</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {parseRevisions.map((revision) => (
                  <TableRow key={revision.parseRevisionId}>
                    <TableCell className="font-mono text-xs">{revision.parseRevisionId.slice(0, 8)}</TableCell>
                    <TableCell>{revision.parserName ?? "-"}</TableCell>
                    <TableCell>{revision.parserVersion ?? "-"}</TableCell>
                    <TableCell className="max-w-[220px] truncate text-xs" title={parseOptionsSummary(revision.parseOptions)}>{parseOptionsSummary(revision.parseOptions)}</TableCell>
                    <TableCell>{revision.contentFormat ?? "-"}</TableCell>
                    <TableCell><Badge variant={parseStatusVariant(revision.status)}>{revision.status}</Badge></TableCell>
                    <TableCell>{revision.contentLength ?? 0}</TableCell>
                    <TableCell>{new Date(revision.createdAt).toLocaleString("zh-CN")}</TableCell>
                    <TableCell className="max-w-[180px] truncate text-xs text-red-600">{revision.errorMessage ?? "-"}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" onClick={() => { setSelectedParseRevisionId(revision.parseRevisionId); setActiveTab("preview"); }}>
                          查看正文
                        </Button>
                        <Button variant="ghost" size="sm" title="复制解析文本" onClick={() => void handleCopyParseText(revision)}>
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" title="下载解析文本" onClick={() => void handleDownloadParseText(revision)}>
                          <Download className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </UnderlineTabsContent>

          <UnderlineTabsContent value="preview" className="space-y-6 outline-none">
            {previewType === "pdf" ? (
              <PdfPreview documentId={docId} fileName={doc.name} />
            ) : previewType === "docx" ? (
              <Suspense fallback={<Alert variant="info" title="正在加载 DOCX 预览器" message="首次打开 DOCX 预览时需要加载解析组件。" />}>
                <DocxPreview documentId={docId} />
              </Suspense>
            ) : previewType === "markdown" || previewType === "text" || selectedParseRevision ? (
              <TextPreview documentId={docId} parseRevisionId={selectedParseRevision?.parseRevisionId} />
            ) : (
              <div className="rounded-lg border border-border-cream bg-ivory py-12 text-center">
                <FileText className="mx-auto mb-4 h-12 w-12 text-stone-gray" />
                <p className="text-stone-gray">暂不支持此文件格式的在线预览</p>
              </div>
            )}
          </UnderlineTabsContent>

          <UnderlineTabsContent value="usage" className="outline-none">
            {usages.length === 0 ? (
              <div className="rounded-lg border border-border-cream bg-ivory py-12 text-center text-stone-gray">该文档尚未绑定到任何知识库</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>知识库</TableHead>
                    <TableHead>绑定状态</TableHead>
                    <TableHead>入库后分块数</TableHead>
                    <TableHead>创建时间</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usages.map((usage) => (
                    <TableRow key={usage.bindingId}>
                      <TableCell className="font-medium">{usage.kbName}</TableCell>
                      <TableCell><Badge variant={usage.status === "active" ? "success" : "default"}>{usage.status}</Badge></TableCell>
                      <TableCell>{usage.chunkCount}</TableCell>
                      <TableCell>{new Date(usage.createdAt).toLocaleString("zh-CN")}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </UnderlineTabsContent>
        </UnderlineTabs>

        {showUpload && (
          <Drawer isOpen={showUpload} title="上传新源文件版本" onClose={() => { setShowUpload(false); setUploadFile(null); setUploadProgress(null); }}>
            <DrawerSection>
              <div className="space-y-4">
                <input
                  type="file"
                  accept=".txt,.md,.pdf,.docx"
                  onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-stone-gray file:mr-4 file:rounded-lg file:border-0 file:bg-terracotta/10 file:px-4 file:py-2 file:text-sm file:font-medium file:text-terracotta hover:file:bg-terracotta/20"
                />
                {uploadProgress && (
                  <div>
                    <div className="mb-1 flex justify-between text-xs text-stone-gray">
                      <span>上传进度</span>
                      <span>{uploadProgress.percent}%</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-border-cream">
                      <div className="h-2 rounded-full bg-terracotta transition-all" style={{ width: `${uploadProgress.percent}%` }} />
                    </div>
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setShowUpload(false)}>取消</Button>
                  <Button disabled={!uploadFile || uploading} onClick={() => void handleVersionUpload()}>
                    {uploading ? "上传中..." : "上传"}
                  </Button>
                </div>
              </div>
            </DrawerSection>
          </Drawer>
        )}

        {showReparse && selectedVersion && (
          <Drawer isOpen={showReparse} title={`重解析源文件 v${selectedVersion.versionNo}`} onClose={() => setShowReparse(false)}>
            <DrawerSection>
              <div className="space-y-4">
                <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm text-stone-gray">
                  重解析会创建新的解析版本，不创建新的源文件版本，也不会自动影响已有知识库绑定。
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-near-black">目标源文件版本</label>
                  <select className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm" value={selectedVersion.versionId} onChange={(event) => setSelectedVersionId(event.target.value)}>
                    {versions.map((version) => <option key={version.versionId} value={version.versionId}>v{version.versionNo} - {version.fileName ?? "-"}</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-near-black">解析器</label>
                  <select className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm" value={parserName} onChange={(event) => setParserName(event.target.value)}>
                    <option value="auto">自动识别</option>
                    <option value="plain_text">纯文本</option>
                    <option value="pdf_pypdf">PDF</option>
                    <option value="docx_python_docx">DOCX</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-near-black">产物格式</label>
                  <select className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm" value={contentFormat} onChange={(event) => setContentFormat(event.target.value as "markdown" | "text")}>
                    <option value="markdown">Markdown</option>
                    <option value="text">纯文本</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-near-black">语言</label>
                  <Input value={parseLanguage} onChange={(event) => setParseLanguage(event.target.value)} />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-near-black">表格处理</label>
                  <select className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm" value={tableStrategy} onChange={(event) => setTableStrategy(event.target.value)}>
                    <option value="preserve">保留表格结构</option>
                    <option value="flatten">转为段落文本</option>
                    <option value="ignore">忽略表格</option>
                  </select>
                </div>
                <label className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment px-3 py-2 text-sm">
                  <span>启用 OCR</span>
                  <input type="checkbox" checked={ocrEnabled} onChange={(event) => setOcrEnabled(event.target.checked)} className="accent-terracotta" />
                </label>
                <label className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment px-3 py-2 text-sm">
                  <span>抽取图片文字</span>
                  <input type="checkbox" checked={extractImageText} onChange={(event) => setExtractImageText(event.target.checked)} className="accent-terracotta" />
                </label>
                <label className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment px-3 py-2 text-sm">
                  <span>保留标题结构</span>
                  <input type="checkbox" checked={preserveHeadings} onChange={(event) => setPreserveHeadings(event.target.checked)} className="accent-terracotta" />
                </label>
                <div className="flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setShowReparse(false)}>取消</Button>
                  <Button disabled={reparseSubmitting} onClick={() => void handleSubmitReparse()}>
                    <Settings2 className="mr-2 h-4 w-4" /> {reparseSubmitting ? "提交中..." : "提交重解析"}
                  </Button>
                </div>
              </div>
            </DrawerSection>
          </Drawer>
        )}

        {deleteDrawer && (
          <Drawer isOpen={!!deleteDrawer} title={`删除源文件版本 v${deleteDrawer.versionNo}`} onClose={() => { setDeleteDrawer(null); setDeleteImpact(null); }}>
            <DrawerSection>
              {deleteImpactLoading ? (
                <div className="py-8 text-center text-stone-gray">正在分析影响...</div>
              ) : deleteImpact ? (
                <div className="space-y-4">
                  <div className="rounded-lg border border-border-cream bg-parchment p-4 text-sm">
                    <div className="flex justify-between"><span className="text-stone-gray">当前活跃版本</span><span>{deleteImpact.isActiveVersion ? "是" : "否"}</span></div>
                    <div className="flex justify-between"><span className="text-stone-gray">活跃知识库绑定</span><span>{deleteImpact.activeBindingCount}</span></div>
                    <div className="flex justify-between"><span className="text-stone-gray">运行中任务</span><span>{deleteImpact.pendingJobsCount}</span></div>
                    <div className="flex justify-between"><span className="text-stone-gray">历史 QA 引用</span><span>{deleteImpact.qaEvidenceCount}</span></div>
                  </div>
                  {!deleteImpact.canDelete && (
                    <Alert variant="error" title="无法删除">
                      {deleteImpact.blockingReasons.join("；")}
                    </Alert>
                  )}
                  {deleteImpact.canDelete && deleteImpact.requiresStrongConfirmation && (
                    <label className="flex cursor-pointer items-start gap-2 text-sm">
                      <input type="checkbox" checked={strongConfirmChecked} onChange={(event) => setStrongConfirmChecked(event.target.checked)} className="mt-1 accent-terracotta" />
                      <span>我确认清理该源文件版本，并接受相关 QA 历史证据不可回放。</span>
                    </label>
                  )}
                  <div className="flex justify-end gap-2">
                    <Button variant="secondary" onClick={() => setDeleteDrawer(null)}>取消</Button>
                    <Button variant="destructive" disabled={!deleteImpact.canDelete || (deleteImpact.requiresStrongConfirmation && !strongConfirmChecked)} onClick={() => void handleConfirmDelete()}>
                      确认删除
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-stone-gray">无法加载影响分析</p>
              )}
            </DrawerSection>
          </Drawer>
        )}
      </div>
    </div>
  );
}
