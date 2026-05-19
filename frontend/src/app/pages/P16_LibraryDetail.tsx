import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, Download, FileText, RefreshCw } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Alert } from "../components/rag/Alert";
import { PdfPreview } from "../components/rag/PdfPreview";
import { MarkdownPreview } from "../components/rag/MarkdownPreview";
import { TextPreview } from "../components/rag/TextPreview";
import { DocxPreview } from "../components/rag/DocxPreview";
import {
  fetchLibraryDocumentDetail,
  downloadLibraryDocument,
  fetchLibraryParseJobs,
  fetchDocumentUsage,
  retryLibraryParse,
} from "../services/libraryService";
import type { LibraryDocumentDetailDTO, LibraryParseJobDTO, LibraryDocumentUsageResponse, LibraryDocumentUsageDTO } from "../types/library";

function getPreviewType(fileName: string): "pdf" | "markdown" | "text" | "docx" | "unsupported" {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "md" || ext === "markdown") return "markdown";
  if (ext === "txt") return "text";
  if (ext === "docx") return "docx";
  return "unsupported";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function LibraryDetail() {
  const navigate = useNavigate();
  const { docId = "" } = useParams();
  const [detail, setDetail] = useState<LibraryDocumentDetailDTO | null>(null);
  const [parseJobs, setParseJobs] = useState<LibraryParseJobDTO[]>([]);
  const [usages, setUsages] = useState<LibraryDocumentUsageDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const [detailData, jobsData] = await Promise.all([
        fetchLibraryDocumentDetail(docId),
        fetchLibraryParseJobs(docId),
      ]);
      setDetail(detailData);
      setParseJobs(jobsData);

      // 加载使用情况
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
      setFeedback({
        variant: "info",
        title: "重试已触发",
        message: "解析作业已重新排队，请稍后刷新。",
      });
      await loadData();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "重试失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    }
  }

  useEffect(() => {
    void loadData();
  }, [docId]);

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
      setFeedback({
        variant: "error",
        title: "下载失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    }
  }

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
  const version = detail.activeVersion;
  const latestJob = parseJobs[0];
  const previewType = getPreviewType(doc.name);

  return (
    <div className="flex flex-col h-full">
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

      <div className="flex-1 min-h-0 overflow-auto p-8 space-y-6">
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        {/* 基本信息 */}
        <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
          <h2 className="font-serif text-near-black mb-4">文档信息</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-stone-gray">密级：</span>
              <Badge variant="info" className="ml-2">{doc.securityLevel}</Badge>
            </div>
            <div>
              <span className="text-stone-gray">状态：</span>
              <StatusBadge
                status={doc.status === "active" ? "active" : doc.status === "disabled" ? "inactive" : "draft"}
                className="ml-2"
              />
            </div>
            <div>
              <span className="text-stone-gray">来源：</span>
              <span className="text-near-black ml-2">{doc.sourceType}</span>
            </div>
            <div>
              <span className="text-stone-gray">创建时间：</span>
              <span className="text-near-black ml-2">{new Date(doc.createdAt).toLocaleString("zh-CN")}</span>
            </div>
          </div>
        </div>

        {/* 版本和解析状态 */}
        {version && (
          <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
            <h2 className="font-serif text-near-black mb-4">文本提取状态</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-stone-gray">解析状态：</span>
                <Badge
                  variant={version.parseStatus === "success" ? "success" : version.parseStatus === "failed" ? "error" : version.parseStatus === "running" ? "running" : "queued"}
                  className="ml-2"
                >
                  {version.parseStatus}
                </Badge>
              </div>
              <div>
                <span className="text-stone-gray">分块数：</span>
                <span className="text-near-black ml-2">{version.chunkCount}</span>
              </div>
              {version.tokenCount != null && (
                <div>
                  <span className="text-stone-gray">Token 数：</span>
                  <span className="text-near-black ml-2">{version.tokenCount.toLocaleString()}</span>
                </div>
              )}
            </div>

            {/* 最近解析作业 */}
            {latestJob && (
              <div className="mt-4 pt-4 border-t border-border-cream">
                <h3 className="text-sm font-medium text-near-black mb-2">最近解析作业</h3>
                <div className="flex items-center gap-4 text-sm">
                  <StatusBadge status={latestJob.status} />
                  {latestJob.status === "running" && (
                    <span className="text-stone-gray">进度: {latestJob.progress}%</span>
                  )}
                  {latestJob.errorMessage && (
                    <span className="text-error-red text-xs">{latestJob.errorMessage}</span>
                  )}
                  <span className="text-stone-gray">{new Date(latestJob.createdAt).toLocaleString("zh-CN")}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 文档预览 */}
        <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
          <h2 className="font-serif text-near-black mb-4">文档预览</h2>
          {version?.parseStatus !== "success" ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
              <p className="text-stone-gray">
                {version?.parseStatus === "pending" || version?.parseStatus === "running"
                  ? "文本提取中，请稍后刷新..."
                  : version?.parseStatus === "failed"
                    ? "文本提取失败，无法预览"
                    : "等待文本提取完成"}
              </p>
              {version?.parseStatus === "failed" && (
                <Button variant="secondary" className="mt-4" onClick={() => void handleRetry()}>
                  <RefreshCw className="w-4 h-4 mr-2" /> 重试解析
                </Button>
              )}
            </div>
          ) : previewType === "pdf" ? (
            <PdfPreview documentId={docId} fileName={doc.name} />
          ) : previewType === "docx" ? (
            <DocxPreview documentId={docId} />
          ) : previewType === "markdown" ? (
            <MarkdownPreview content="" loading={false} />
          ) : previewType === "text" ? (
            <TextPreview documentId={docId} />
          ) : (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
              <p className="text-stone-gray">暂不支持此文件格式的在线预览</p>
            </div>
          )}
        </div>

        {/* 绑定的知识库 */}
        {usages.length > 0 && (
          <div className="bg-ivory border border-border-cream rounded-[12px] p-6">
            <h2 className="font-serif text-near-black mb-4">绑定的知识库</h2>
            <div className="space-y-3">
              {usages.map((usage) => (
                <div key={usage.bindingId} className="rounded-lg border border-border-cream bg-parchment p-4 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <p className="font-medium text-near-black truncate">{usage.kbName}</p>
                    <p className="text-xs text-stone-gray mt-1">分块数: {usage.chunkCount} | 创建时间: {new Date(usage.createdAt).toLocaleString("zh-CN")}</p>
                  </div>
                  <Badge variant={usage.status === "active" ? "success" : "default"}>{usage.status}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
