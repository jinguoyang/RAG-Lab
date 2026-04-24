import * as Tabs from "@radix-ui/react-tabs";
import { useMemo, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "../components/rag/Table";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import {
  Download,
  RefreshCw,
  FileSymlink,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";

interface ChunkRecord {
  id: string;
  page: number;
  text: string;
  tokens: number;
  metadata: string;
  heading: string;
}

interface VersionRecord {
  id: string;
  status: "success" | "running" | "failed";
  createdAt: string;
  source: string;
  active: boolean;
}

interface JobRecord {
  id: string;
  status: "success" | "running" | "failed";
  initiator: string;
  startedAt: string;
  duration: string;
  error?: string;
}

const CHUNKS: ChunkRecord[] = [
  {
    id: "chk-001",
    page: 1,
    text: "The Q3 revenue was $45M, exceeding estimates by nearly 12%. Operating expenses decreased by 4% to $12M, improving net margin.",
    tokens: 120,
    metadata: "{ type: 'paragraph', section: 'Executive Summary' }",
    heading: "Executive Summary / Financial Highlights",
  },
  {
    id: "chk-002",
    page: 1,
    text: "The Aurora product line faces a four-week supplier delay in APAC, with downstream risk to both Q3 revenue recognition and Q4 launch planning.",
    tokens: 104,
    metadata: "{ type: 'risk_item', source: 'supply_chain_review' }",
    heading: "Risk Register / Supply Chain",
  },
  {
    id: "chk-003",
    page: 2,
    text: "Looking forward to Q4, management expects a 10% growth if supplier bottlenecks are resolved before November.",
    tokens: 145,
    metadata: "{ type: 'conclusion', confidence: 'medium' }",
    heading: "Forward Looking Statement",
  },
];

const VERSIONS: VersionRecord[] = [
  {
    id: "v3",
    status: "success",
    createdAt: "2026-04-22 14:30",
    source: "界面上传",
    active: true,
  },
  {
    id: "v2",
    status: "success",
    createdAt: "2026-04-21 11:20",
    source: "API 上传",
    active: false,
  },
  {
    id: "v1",
    status: "failed",
    createdAt: "2026-04-19 09:12",
    source: "首次导入",
    active: false,
  },
];

const JOBS: JobRecord[] = [
  {
    id: "job-1092",
    status: "success",
    initiator: "admin",
    startedAt: "2026-04-22 14:30",
    duration: "45s",
  },
  {
    id: "job-1088",
    status: "failed",
    initiator: "asmith",
    startedAt: "2026-04-19 09:12",
    duration: "18s",
    error: "PDF parser failed on malformed table structure.",
  },
];

/**
 * 文档详情页原型。
 * 重点补齐原型阶段必须清楚的三件事：版本切换、Chunk 详情、失败作业反馈。
 */
export function DocumentDetail() {
  const [activeTab, setActiveTab] = useState("chunks");
  const [selectedChunk, setSelectedChunk] = useState<ChunkRecord | null>(null);
  const [versions, setVersions] = useState(VERSIONS);
  const [jobs, setJobs] = useState(JOBS);
  const [isSwitchDialogOpen, setIsSwitchDialogOpen] = useState(false);
  const [pendingVersion, setPendingVersion] = useState<string | null>(null);
  const [isReparseDialogOpen, setIsReparseDialogOpen] = useState(false);
  const [maskChunkText, setMaskChunkText] = useState(false);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "warning" | "info";
    title: string;
    message: string;
  } | null>(null);

  const activeVersion = useMemo(
    () => versions.find((version) => version.active)?.id ?? "v3",
    [versions],
  );

  const displayedChunk = selectedChunk ?? CHUNKS[0];

  function openSwitchDialog(versionId: string) {
    setPendingVersion(versionId);
    setIsSwitchDialogOpen(true);
  }

  /**
   * 原型阶段不用真的切换后端 active version，
   * 但需要把“会影响后续 QA”这个风险显式展示出来。
   */
  function handleConfirmSwitchVersion() {
    if (!pendingVersion) return;

    setVersions((current) =>
      current.map((version) => ({
        ...version,
        active: version.id === pendingVersion,
      })),
    );
    setFeedback({
      variant: "warning",
      title: "生效版本已切换",
      message: `已将 ${pendingVersion} 设为当前生效版本。后续 QA 调试将基于新版本执行。`,
    });
    setIsSwitchDialogOpen(false);
    setPendingVersion(null);
  }

  function handleRetryJob(jobId: string) {
    setJobs((current) =>
      current.map((job) =>
        job.id === jobId
          ? { ...job, status: "running", duration: "重新执行中", error: undefined }
          : job,
      ),
    );
    setFeedback({
      variant: "info",
      title: "作业已重试",
      message: `已重新拉起 ${jobId}，评审时可以看到失败原因与重试入口。`,
    });
  }

  function handleConfirmReparse() {
    setJobs((current) => [
      {
        id: `job-${Math.floor(1200 + Math.random() * 900)}`,
        status: "running",
        initiator: "current_user",
        startedAt: "刚刚",
        duration: "初始化中",
      },
      ...current,
    ]);
    setFeedback({
      variant: "info",
      title: "文档重解析已发起",
      message: "原型阶段重点展示重解析的确认、反馈和作业记录，不必前置真实解析能力。",
    });
    setIsReparseDialogOpen(false);
    setActiveTab("jobs");
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <div className="flex items-center gap-2 text-sm text-stone-gray mb-2">
        <span className="cursor-pointer hover:text-terracotta">文档中心</span>
        <ChevronRight className="w-4 h-4" />
        <span className="text-near-black font-medium">Q3_Earnings_Report_Draft.pdf</span>
      </div>

      <PageHeader
        title="Q3_Earnings_Report_Draft.pdf"
        description="查看文档版本、Chunk、Ingest 作业与权限可见性。"
        actions={
          <>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" /> 下载原文
            </Button>
            <Button
              variant="outline"
              onClick={() => openSwitchDialog("v2")}
            >
              <FileSymlink className="w-4 h-4 mr-2" /> 切换版本
            </Button>
            <Button variant="primary" onClick={() => setIsReparseDialogOpen(true)}>
              <RefreshCw className="w-4 h-4 mr-2" /> 重解析
            </Button>
          </>
        }
        contextLabels={
          <>
            <Badge variant="success">生效版本：{activeVersion}</Badge>
            <Badge variant="info">文档 ID：doc-9012</Badge>
            <Badge variant="warning">机密</Badge>
          </>
        }
      />

      {feedback && (
        <Alert
          variant={feedback.variant}
          title={feedback.title}
          onClose={() => setFeedback(null)}
        >
          {feedback.message}
        </Alert>
      )}

      <div className="flex items-center justify-between rounded-xl border border-border-cream bg-ivory px-4 py-3">
        <div className="flex items-center gap-2 text-sm text-stone-gray">
          <ShieldAlert className="w-4 h-4 text-warning-amber" />
          <span>切换开关可模拟无 `kb.chunk.read` 权限时的脱敏态。</span>
        </div>
        <label className="flex items-center gap-2 text-sm text-near-black">
          <input
            type="checkbox"
            className="rounded text-terracotta focus:ring-focus-blue"
            checked={maskChunkText}
            onChange={(e) => setMaskChunkText(e.target.checked)}
          />
          模拟 Chunk 正文不可见
        </label>
      </div>

      <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
        <Tabs.List className="flex border-b border-border-cream gap-6 mb-6">
          <Tabs.Trigger value="versions" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            版本（{versions.length}）
          </Tabs.Trigger>
          <Tabs.Trigger value="chunks" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            Chunks ({CHUNKS.length})
          </Tabs.Trigger>
          <Tabs.Trigger value="jobs" className="pb-2 text-stone-gray font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all">
            入库作业（{jobs.length}）
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="chunks" className="flex-1 overflow-auto bg-ivory rounded-xl border border-border-cream outline-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">页码</TableHead>
                <TableHead>内容摘要</TableHead>
                <TableHead className="w-24">Token 数</TableHead>
                <TableHead className="w-48">元数据</TableHead>
                <TableHead className="w-24">Chunk ID</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {CHUNKS.map((chunk) => (
                <TableRow
                  key={chunk.id}
                  className="cursor-pointer hover:bg-border-cream/30"
                  onClick={() => setSelectedChunk(chunk)}
                >
                  <TableCell>{chunk.page}</TableCell>
                  <TableCell className="max-w-md truncate" title={chunk.text}>
                    {maskChunkText ? "无权限查看正文，点击查看脱敏详情说明。" : chunk.text}
                  </TableCell>
                  <TableCell>{chunk.tokens}</TableCell>
                  <TableCell mono className="text-xs text-olive-gray">
                    {chunk.metadata}
                  </TableCell>
                  <TableCell mono>{chunk.id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tabs.Content>

        <Tabs.Content value="versions" className="flex-1 overflow-auto outline-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>版本</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>来源</TableHead>
                <TableHead>是否生效</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {versions.map((version) => (
                <TableRow key={version.id}>
                  <TableCell mono>{version.id}</TableCell>
                  <TableCell>
                    <StatusBadge status={version.status} />
                  </TableCell>
                  <TableCell>{version.createdAt}</TableCell>
                  <TableCell>{version.source}</TableCell>
                  <TableCell>
                    {version.active ? (
                      <Badge variant="success">当前生效</Badge>
                    ) : (
                      <span className="text-stone-gray">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {version.active ? (
                      <span className="text-xs text-stone-gray">当前生效</span>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-terracotta"
                        onClick={() => openSwitchDialog(version.id)}
                      >
                        设为生效版本
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tabs.Content>

        <Tabs.Content value="jobs" className="flex-1 overflow-auto outline-none">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>作业 ID</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>发起人</TableHead>
                <TableHead>开始时间</TableHead>
                <TableHead>耗时</TableHead>
                <TableHead>错误信息</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => (
                <TableRow key={job.id}>
                  <TableCell mono>{job.id}</TableCell>
                  <TableCell>
                    <StatusBadge status={job.status} />
                  </TableCell>
                  <TableCell>{job.initiator}</TableCell>
                  <TableCell>{job.startedAt}</TableCell>
                  <TableCell>{job.duration}</TableCell>
                  <TableCell className="max-w-xs text-stone-gray">
                    {job.error ?? "-"}
                  </TableCell>
                  <TableCell>
                    {job.status === "failed" ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-terracotta"
                        onClick={() => handleRetryJob(job.id)}
                      >
                        <RefreshCw className="w-3 h-3 mr-1" /> 重试
                      </Button>
                    ) : (
                      <span className="text-xs text-stone-gray">-</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Tabs.Content>
      </Tabs.Root>

      <Drawer
        isOpen={selectedChunk !== null}
        onClose={() => setSelectedChunk(null)}
        title={displayedChunk.id ? `Chunk 详情 · ${displayedChunk.id}` : "Chunk 详情"}
        width="640px"
      >
        <DrawerSection title="原始文本">
          {maskChunkText ? (
            <Alert variant="permission" title="正文已脱敏">
              当前用户缺少 `kb.chunk.read` 权限。原型阶段必须把“对象可见但正文不可见”的状态画出来。
            </Alert>
          ) : (
            <div className="p-4 bg-border-cream/20 rounded-md font-sans text-near-black leading-relaxed whitespace-pre-wrap">
              {displayedChunk.text}
            </div>
          )}
        </DrawerSection>
        <DrawerSection title="元数据">
          <pre className="p-4 bg-parchment border border-border-cream rounded-md text-xs font-mono overflow-auto">
{`{
  "source_doc": "doc-9012",
  "version": "${activeVersion}",
  "page_num": ${displayedChunk.page},
  "chunk_id": "${displayedChunk.id}",
  "heading": "${displayedChunk.heading}",
  "token_count": ${displayedChunk.tokens}
}`}
          </pre>
        </DrawerSection>
        <DrawerSection title="向量预览">
          <div className="p-4 border border-border-cream rounded-md bg-ivory text-xs font-mono text-stone-gray truncate">
            [0.0123, -0.0456, 0.0891, 0.0023, -0.0567, 0.0189, ...] (1536 dims)
          </div>
        </DrawerSection>
      </Drawer>

      <Dialog open={isSwitchDialogOpen} onOpenChange={setIsSwitchDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认切换生效版本</DialogTitle>
            <DialogDescription>
              切换后，后续 QA 与检索结果都将以新版本为基准。这类风险操作建议在原型阶段就显式确认。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-border-cream bg-parchment p-4 text-sm text-near-black">
            当前版本：{activeVersion}
            <br />
            目标版本：{pendingVersion}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsSwitchDialogOpen(false)}>
              取消
            </Button>
            <Button variant="primary" onClick={handleConfirmSwitchVersion}>
              确认切换
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isReparseDialogOpen} onOpenChange={setIsReparseDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认重解析文档</DialogTitle>
            <DialogDescription>
              重解析会重新生成 Chunk、向量和图数据。原型阶段不必执行真实解析，但必须明确影响面。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsReparseDialogOpen(false)}>
              取消
            </Button>
            <Button variant="primary" onClick={handleConfirmReparse}>
              发起重解析
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
