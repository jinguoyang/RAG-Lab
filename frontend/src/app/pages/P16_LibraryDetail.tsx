import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Download, FileText, RefreshCw, Trash2, Upload } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Alert } from "../components/rag/Alert";
import { PdfPreview } from "../components/rag/PdfPreview";
import { TextPreview } from "../components/rag/TextPreview";
import { DocxPreview } from "../components/rag/DocxPreview";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import {
  fetchLibraryDocumentDetail,
  downloadLibraryDocument,
  fetchLibraryParseJobs,
  fetchDocumentUsage,
  retryLibraryParse,
  fetchLibraryVersions,
  uploadLibraryVersionWithProgress,
  activateLibraryVersion,
  deleteLibraryVersion,
  switchBindingVersion,
} from "../services/libraryService";
import type {
  LibraryDocumentDetailDTO,
  LibraryParseJobDTO,
  LibraryDocumentUsageDTO,
  LibraryDocumentVersionDTO,
  UploadProgress,
} from "../types/library";

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

function parseStatusVariant(status: string): "success" | "error" | "running" | "queued" {
  if (status === "success") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "running";
  return "queued";
}

export function LibraryDetail() {
  const navigate = useNavigate();
  const { docId = "" } = useParams();
  const { confirm } = useConfirmDialog();

  const [detail, setDetail] = useState<LibraryDocumentDetailDTO | null>(null);
  const [versions, setVersions] = useState<LibraryDocumentVersionDTO[]>([]);
  const [parseJobs, setParseJobs] = useState<LibraryParseJobDTO[]>([]);
  const [usages, setUsages] = useState<LibraryDocumentUsageDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("overview");
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  // Version upload state
  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [uploading, setUploading] = useState(false);

  // KB version switch drawer
  const [switchDrawer, setSwitchDrawer] = useState<{ bindingId: string; kbId: string; kbName: string } | null>(null);
  const [switchVersions, setSwitchVersions] = useState<LibraryDocumentVersionDTO[]>([]);
  const [switchLoading, setSwitchLoading] = useState(false);

  async function loadData() {
    setLoading(true);
    try {
      const [detailData, versionsData, jobsData] = await Promise.all([
        fetchLibraryDocumentDetail(docId),
        fetchLibraryVersions(docId),
        fetchLibraryParseJobs(docId),
      ]);
      setDetail(detailData);
      setVersions(versionsData);
      setParseJobs(jobsData);
      void loadUsage();
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

  async function loadUsage() {
    try {
      const usageData = await fetchDocumentUsage(docId);
      setUsages(usageData.usages);
    } catch {
      // 使用情况加载失败不影响主页面
    }
  }

  async function handleRetry() {
    try {
      await retryLibraryParse(docId);
      setFeedback({ variant: "info", title: "重试已触发", message: "解析作业已重新排队，请稍后刷新。" });
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "重试失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleDownload() {
    if (!detail) return;
    try {
      const result = await downloadLibraryDocument(docId);
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

  async function handleVersionUpload() {
    if (!uploadFile) return;
    setUploading(true);
    setUploadProgress(null);
    try {
      const { promise, onProgress } = uploadLibraryVersionWithProgress(docId, uploadFile);
      onProgress(setUploadProgress);
      await promise;
      setFeedback({ variant: "success", title: "上传成功", message: "版本文件已上传，解析任务已创建。" });
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
    const confirmed = await confirm({
      title: "切换版本",
      description: `确定要将文档的活跃版本切换到 v${versionNo} 吗？此操作不会影响已绑定的知识库。`,
      confirmLabel: "确认切换",
    });
    if (!confirmed) return;
    try {
      await activateLibraryVersion(docId, versionId);
      setFeedback({ variant: "success", title: "切换成功", message: `已切换到 v${versionNo}。` });
      await loadData();
    } catch (error) {
      setFeedback({ variant: "error", title: "切换失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  async function handleDeleteVersion(versionId: string, versionNo: number) {
    const confirmed = await confirm({
      title: "删除版本",
      description: `确定要删除 v${versionNo} 吗？此操作不可撤销。`,
      confirmLabel: "确认删除",
      destructive: true,
    });
    if (!confirmed) return;
    try {
      await deleteLibraryVersion(docId, versionId);
      setFeedback({ variant: "success", title: "删除成功", message: `v${versionNo} 已删除。` });
      await loadData();
    } catch (error) {
      const msg = error instanceof Error ? error.message : "请稍后重试。";
      if (msg.includes("VERSION_IN_USE")) {
        setFeedback({ variant: "warning", title: "无法删除", message: "该版本正在被知识库绑定引用，请先在知识库中切换版本或解绑。" });
      } else if (msg.includes("VERSION_IS_ACTIVE")) {
        setFeedback({ variant: "warning", title: "无法删除", message: "不能删除当前活跃版本，请先切换到其他版本。" });
      } else {
        setFeedback({ variant: "error", title: "删除失败", message: msg });
      }
    }
  }

  async function openSwitchDrawer(bindingId: string, kbId: string, kbName: string) {
    setSwitchDrawer({ bindingId, kbId, kbName });
    setSwitchLoading(true);
    try {
      const vers = await fetchLibraryVersions(docId);
      setSwitchVersions(vers.filter((v) => v.parseStatus === "success"));
    } catch {
      setSwitchVersions([]);
    } finally {
      setSwitchLoading(false);
    }
  }

  async function handleSwitchBindingVersion(targetVersionId: string, versionNo: number) {
    if (!switchDrawer) return;
    const confirmed = await confirm({
      title: "切换绑定版本",
      description: `确定要将「${switchDrawer.kbName}」的绑定切换到 v${versionNo} 吗？知识库将重新解析该文档。`,
      confirmLabel: "确认切换",
    });
    if (!confirmed) return;
    try {
      await switchBindingVersion(switchDrawer.kbId, switchDrawer.bindingId, targetVersionId);
      setFeedback({ variant: "success", title: "切换成功", message: `绑定已切换到 v${versionNo}，知识库正在重新解析。` });
      setSwitchDrawer(null);
      await loadUsage();
    } catch (error) {
      setFeedback({ variant: "error", title: "切换失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    }
  }

  useEffect(() => {
    void loadData();
  }, [docId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="text-stone-gray">加载中...</span>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-stone-gray">文档不存在或无权访问</p>
        <Button variant="secondary" onClick={() => navigate("/library")}>返回文档库</Button>
      </div>
    );
  }

  const doc = detail.document;
  const activeVersion = detail.activeVersion;
  const previewType = getPreviewType(doc.name);

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          title={doc.name}
          breadcrumbs={[
            { label: "文档库", href: "/library" },
            { label: doc.name },
          ]}
          actions={
            <div className="flex items-center gap-2">
              <Button variant="secondary" onClick={() => void handleDownload()}>
                <Download className="w-4 h-4 mr-2" /> 下载
              </Button>
              <Button variant="secondary" onClick={() => void loadData()}>
                <RefreshCw className="w-4 h-4 mr-2" /> 刷新
              </Button>
            </div>
          }
        />
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        {/* Summary cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="rounded-xl border border-border-cream bg-ivory p-4">
            <p className="text-xs text-stone-gray">活跃版本</p>
            <p className="mt-2 font-serif text-xl text-near-black">{activeVersion ? `v${activeVersion.versionNo}` : "无"}</p>
          </div>
          <div className="rounded-xl border border-border-cream bg-ivory p-4">
            <p className="text-xs text-stone-gray">版本总数</p>
            <p className="mt-2 font-serif text-xl text-near-black">{versions.length}</p>
          </div>
          <div className="rounded-xl border border-border-cream bg-ivory p-4">
            <p className="text-xs text-stone-gray">解析状态</p>
            <p className="mt-2 font-serif text-xl text-near-black">
              {activeVersion ? (
                <Badge variant={parseStatusVariant(activeVersion.parseStatus)}>{activeVersion.parseStatus}</Badge>
              ) : "无"}
            </p>
          </div>
        </div>

        <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
          <Tabs.List className="flex border-b border-border-cream gap-6 mb-6">
            <Tabs.Trigger value="overview" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              概览
            </Tabs.Trigger>
            <Tabs.Trigger value="versions" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              版本（{versions.length}）
            </Tabs.Trigger>
            <Tabs.Trigger value="jobs" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              解析任务（{parseJobs.length}）
            </Tabs.Trigger>
            <Tabs.Trigger value="bindings" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
              KB 绑定（{usages.length}）
            </Tabs.Trigger>
          </Tabs.List>

          {/* Tab 1: Overview */}
          <Tabs.Content value="overview" className="flex-1 overflow-auto outline-none space-y-6">
            <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
              <h2 className="font-serif text-near-black mb-4">文档信息</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-stone-gray">状态：</span>
                  <StatusBadge
                    status={doc.status === "active" ? "active" : doc.status === "disabled" ? "inactive" : "draft"}
                    className="ml-2"
                  />
                </div>
                <div>
                  <span className="text-stone-gray">创建时间：</span>
                  <span className="text-near-black ml-2">{new Date(doc.createdAt).toLocaleString("zh-CN")}</span>
                </div>
              </div>
            </div>

            <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
              <h2 className="font-serif text-near-black mb-4">文档预览</h2>
              {previewType === "pdf" ? (
                <PdfPreview documentId={docId} fileName={doc.name} />
              ) : previewType === "docx" ? (
                <DocxPreview documentId={docId} />
              ) : previewType === "markdown" || previewType === "text" ? (
                activeVersion?.parseStatus === "success" ? (
                  <TextPreview documentId={docId} />
                ) : (
                  <div className="text-center py-12">
                    <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
                    <p className="text-stone-gray">
                      {activeVersion?.parseStatus === "failed" ? "文本提取失败，无法预览" : "文本提取中，请稍后刷新..."}
                    </p>
                    {activeVersion?.parseStatus === "failed" && (
                      <Button variant="secondary" className="mt-4" onClick={() => void handleRetry()}>
                        <RefreshCw className="w-4 h-4 mr-2" /> 重试解析
                      </Button>
                    )}
                  </div>
                )
              ) : (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
                  <p className="text-stone-gray">暂不支持此文件格式的在线预览</p>
                </div>
              )}
            </div>
          </Tabs.Content>

          {/* Tab 2: Versions */}
          <Tabs.Content value="versions" className="flex-1 overflow-auto outline-none">
            <div className="mb-4 flex justify-between items-center">
              <h2 className="font-serif text-near-black">版本列表</h2>
              <Button variant="primary" onClick={() => setShowUpload(true)}>
                <Upload className="w-4 h-4 mr-2" /> 上传新版本
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>版本</TableHead>
                  <TableHead>文件名</TableHead>
                  <TableHead>文件大小</TableHead>
                  <TableHead>解析状态</TableHead>
                  <TableHead>分块数</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {versions.map((v) => {
                  const isActive = v.versionId === doc.activeVersionId;
                  const canDelete = !isActive;
                  return (
                    <TableRow key={v.versionId}>
                      <TableCell className="font-mono">v{v.versionNo}</TableCell>
                      <TableCell>{v.fileName ?? "-"}</TableCell>
                      <TableCell>{formatFileSize(v.fileSize)}</TableCell>
                      <TableCell>
                        <Badge variant={parseStatusVariant(v.parseStatus)}>{v.parseStatus}</Badge>
                      </TableCell>
                      <TableCell>{v.chunkCount}</TableCell>
                      <TableCell>
                        {isActive ? (
                          <Badge variant="success">当前生效</Badge>
                        ) : (
                          <StatusBadge status={v.status === "active" ? "active" : "inactive"} />
                        )}
                      </TableCell>
                      <TableCell>{new Date(v.createdAt).toLocaleString("zh-CN")}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {!isActive && v.parseStatus === "success" && (
                            <Button variant="ghost" size="sm" onClick={() => void handleActivateVersion(v.versionId, v.versionNo)}>
                              切换
                            </Button>
                          )}
                          {canDelete && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => void handleDeleteVersion(v.versionId, v.versionNo)}
                              title="删除版本"
                            >
                              <Trash2 className="w-4 h-4 text-stone-gray hover:text-red-500" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            {/* Upload drawer */}
            {showUpload && (
              <Drawer title="上传新版本" onClose={() => { setShowUpload(false); setUploadFile(null); setUploadProgress(null); }}>
                <DrawerSection>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-stone-gray mb-2">选择文件</label>
                      <input
                        type="file"
                        accept=".txt,.md,.pdf,.docx"
                        onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                        className="block w-full text-sm text-stone-gray file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-terracotta/10 file:text-terracotta hover:file:bg-terracotta/20"
                      />
                    </div>
                    {uploadProgress && (
                      <div>
                        <div className="flex justify-between text-xs text-stone-gray mb-1">
                          <span>上传进度</span>
                          <span>{uploadProgress.percent}%</span>
                        </div>
                        <div className="w-full bg-border-cream rounded-full h-2">
                          <div className="bg-terracotta h-2 rounded-full transition-all" style={{ width: `${uploadProgress.percent}%` }} />
                        </div>
                      </div>
                    )}
                    <div className="flex gap-2 justify-end">
                      <Button variant="secondary" onClick={() => { setShowUpload(false); setUploadFile(null); setUploadProgress(null); }}>取消</Button>
                      <Button variant="primary" disabled={!uploadFile || uploading} onClick={() => void handleVersionUpload()}>
                        {uploading ? "上传中..." : "上传"}
                      </Button>
                    </div>
                  </div>
                </DrawerSection>
              </Drawer>
            )}
          </Tabs.Content>

          {/* Tab 3: Parse Jobs */}
          <Tabs.Content value="jobs" className="flex-1 overflow-auto outline-none">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>任务 ID</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>进度</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead>错误信息</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {parseJobs.map((job) => (
                  <TableRow key={job.jobId}>
                    <TableCell className="font-mono text-xs">{job.jobId.slice(0, 8)}...</TableCell>
                    <TableCell>{job.jobType}</TableCell>
                    <TableCell><StatusBadge status={job.status === "success" ? "active" : job.status === "failed" ? "error" : job.status === "running" ? "running" : "queued"} /></TableCell>
                    <TableCell>{job.progress}%</TableCell>
                    <TableCell>{new Date(job.createdAt).toLocaleString("zh-CN")}</TableCell>
                    <TableCell className="text-red-500 text-xs">{job.errorMessage ?? "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Tabs.Content>

          {/* Tab 4: KB Bindings */}
          <Tabs.Content value="bindings" className="flex-1 overflow-auto outline-none">
            {usages.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-stone-gray">该文档尚未绑定到任何知识库</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>知识库</TableHead>
                    <TableHead>绑定状态</TableHead>
                    <TableHead>分块数</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {usages.map((usage) => (
                    <TableRow key={usage.bindingId}>
                      <TableCell className="font-medium">{usage.kbName}</TableCell>
                      <TableCell>
                        <Badge variant={usage.status === "active" ? "success" : "default"}>{usage.status}</Badge>
                      </TableCell>
                      <TableCell>{usage.chunkCount}</TableCell>
                      <TableCell>{new Date(usage.createdAt).toLocaleString("zh-CN")}</TableCell>
                      <TableCell>
                        <Button variant="ghost" size="sm" onClick={() => void openSwitchDrawer(usage.bindingId, usage.kbId, usage.kbName)}>
                          切换版本
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {/* Switch version drawer */}
            {switchDrawer && (
              <Drawer title={`切换版本 — ${switchDrawer.kbName}`} onClose={() => setSwitchDrawer(null)}>
                <DrawerSection>
                  {switchLoading ? (
                    <p className="text-stone-gray text-sm">加载中...</p>
                  ) : switchVersions.length === 0 ? (
                    <p className="text-stone-gray text-sm">没有可用的已解析版本</p>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-sm text-stone-gray">选择要绑定到的库版本：</p>
                      {switchVersions.map((v) => (
                        <div
                          key={v.versionId}
                          className="rounded-lg border border-border-cream bg-parchment p-4 flex items-center justify-between gap-4 cursor-pointer hover:border-terracotta transition-colors"
                          onClick={() => void handleSwitchBindingVersion(v.versionId, v.versionNo)}
                        >
                          <div>
                            <p className="font-medium text-near-black">v{v.versionNo}</p>
                            <p className="text-xs text-stone-gray mt-1">{v.fileName ?? "-"} | 分块数: {v.chunkCount}</p>
                          </div>
                          <Badge variant={parseStatusVariant(v.parseStatus)}>{v.parseStatus}</Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </DrawerSection>
              </Drawer>
            )}
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </div>
  );
}
