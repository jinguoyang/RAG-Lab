import * as Tabs from "@radix-ui/react-tabs";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { ChevronRight, FileSymlink, RefreshCw, ShieldAlert } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { toIngestJobView, toVersionRow } from "../adapters/documentAdapter";
import {
  fetchDocumentDetail,
  fetchDocumentVersions,
  fetchIngestJobs,
} from "../services/documentService";
import type { DocumentDetailDTO, DocumentVersionDTO, IngestJobDTO } from "../types/document";

/**
 * 文档详情真实接口接入页。
 * Sprint 03 暂不实现 Chunk 查询，因此 Chunk 页签保留明确的后续范围说明。
 */
export function DocumentDetail() {
  const { kbId = "", docId = "" } = useParams();
  const [activeTab, setActiveTab] = useState("versions");
  const [detail, setDetail] = useState<DocumentDetailDTO | null>(null);
  const [versions, setVersions] = useState<DocumentVersionDTO[]>([]);
  const [jobs, setJobs] = useState<IngestJobDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{
    variant: "info" | "success" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  async function loadData() {
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
    void loadData();
  }, [kbId, docId]);

  const versionRows = useMemo(
    () => versions.map((version) => toVersionRow(version, detail?.document.activeVersionId ?? null)),
    [versions, detail?.document.activeVersionId],
  );
  const jobRows = useMemo(() => jobs.map(toIngestJobView), [jobs]);
  const document = detail?.document;
  const activeVersion = detail?.activeVersion;

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
        description="查看文档基础信息、版本状态和关联 ingest 作业。"
        actions={
          <>
            <Button variant="outline" disabled>
              <FileSymlink className="w-4 h-4 mr-2" /> 切换版本
            </Button>
            <Button variant="primary" disabled onClick={() => undefined}>
              <RefreshCw className="w-4 h-4 mr-2" /> 重解析
            </Button>
          </>
        }
        contextLabels={
          document && (
            <>
              <Badge variant="info">文档 ID：{document.documentId}</Badge>
              <Badge variant="default">密级：{document.securityLevel}</Badge>
              <Badge variant={document.status === "active" ? "success" : "inactive"}>
                状态：{document.status}
              </Badge>
            </>
          )
        }
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
        </Alert>
      )}

      <div className="flex items-center justify-between rounded-xl border border-border-cream bg-ivory px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-stone-gray">
          <ShieldAlert className="w-4 h-4 text-warning-amber" />
          <span>Sprint 03 只接入文档、版本和作业状态；Chunk 正文读取留到后续解析链路。</span>
        </div>
        <Button variant="outline" size="sm" disabled={loading} onClick={() => void loadData()}>
          刷新
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Active Version</p>
          <p className="mt-2 font-serif text-xl text-near-black">
            {activeVersion ? `v${activeVersion.versionNo}` : "未生成"}
          </p>
        </div>
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Chunk Count</p>
          <p className="mt-2 font-serif text-xl text-near-black">{activeVersion?.chunkCount ?? 0}</p>
        </div>
        <div className="rounded-xl border border-border-cream bg-ivory p-4">
          <p className="text-xs text-stone-gray">Retrieval Ready</p>
          <p className="mt-2 font-serif text-xl text-near-black">
            {activeVersion?.retrievalReady ? "已就绪" : "未就绪"}
          </p>
        </div>
      </div>

      <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <Tabs.List className="flex border-b border-border-cream gap-6 mb-6">
          <Tabs.Trigger value="versions" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            版本（{versionRows.length}）
          </Tabs.Trigger>
          <Tabs.Trigger value="chunks" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            Chunks
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
                <TableHead>是否生效</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versionRows.map((version) => (
                <TableRow key={version.id}>
                  <TableCell mono>{version.versionNo}</TableCell>
                  <TableCell>
                    <StatusBadge status={version.status} />
                  </TableCell>
                  <TableCell>{version.parseStatusLabel}</TableCell>
                  <TableCell>{version.chunkCount}</TableCell>
                  <TableCell>{version.retrievalReadyLabel}</TableCell>
                  <TableCell>{version.createdAtLabel}</TableCell>
                  <TableCell>
                    {version.active ? <Badge variant="success">当前生效</Badge> : <span className="text-stone-gray">-</span>}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tabs.Content>

        <Tabs.Content value="chunks" className="flex-1 overflow-auto outline-none">
          <div className="rounded-xl border border-dashed border-border-warm bg-ivory p-10 text-center">
            <h3 className="text-lg font-serif text-near-black">Chunk 查询尚未纳入 Sprint 03</h3>
            <p className="mt-2 text-sm text-stone-gray">
              本轮只保证上传后可追踪文档、版本和 IngestJob。真实解析和 Chunk 写入会在后续迭代接入。
            </p>
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
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobRows.map((job) => (
                <TableRow key={job.id}>
                  <TableCell mono>{job.id}</TableCell>
                  <TableCell>
                    <StatusBadge status={job.status} />
                  </TableCell>
                  <TableCell>{job.stage}</TableCell>
                  <TableCell>{job.progress}%</TableCell>
                  <TableCell>{job.createdAtLabel}</TableCell>
                  <TableCell className="max-w-xs text-stone-gray">{job.errorMessage}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}
