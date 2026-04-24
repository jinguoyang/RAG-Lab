import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
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
import { Input } from "../components/rag/Input";
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
  Search,
  Upload,
  RefreshCw,
  Download,
  FileWarning,
} from "lucide-react";

type DocStatus = "queued" | "running" | "success" | "failed";

interface DocumentRecord {
  id: string;
  name: string;
  version: string;
  status: DocStatus;
  parsedAt: string;
  uploader: string;
  level: string;
}

interface IngestJob {
  id: string;
  docName: string;
  status: DocStatus;
  stage: string;
  triggeredAt: string;
}

const INITIAL_DOCS: DocumentRecord[] = [
  {
    id: "doc-9012",
    name: "Q3_Earnings_Report_Draft.pdf",
    version: "v3",
    status: "success",
    parsedAt: "2026-04-22 14:30",
    uploader: "admin",
    level: "Confidential",
  },
  {
    id: "doc-9013",
    name: "Employee_Handbook_2026.docx",
    version: "v1",
    status: "running",
    parsedAt: "2026-04-22 14:15",
    uploader: "jdoe",
    level: "Internal",
  },
  {
    id: "doc-9014",
    name: "API_v2_Specification.md",
    version: "v4",
    status: "failed",
    parsedAt: "2026-04-21 09:00",
    uploader: "asmith",
    level: "Internal",
  },
  {
    id: "doc-9015",
    name: "Marketing_Plan_Q4.pptx",
    version: "v2",
    status: "success",
    parsedAt: "2026-04-20 16:45",
    uploader: "admin",
    level: "Public",
  },
];

const INITIAL_JOBS: IngestJob[] = [
  {
    id: "job-1095",
    docName: "Employee_Handbook_2026.docx",
    status: "running",
    stage: "Chunking + embedding",
    triggeredAt: "2026-04-22 14:15",
  },
  {
    id: "job-1094",
    docName: "API_v2_Specification.md",
    status: "failed",
    stage: "Parser validation",
    triggeredAt: "2026-04-21 09:00",
  },
  {
    id: "job-1093",
    docName: "Q3_Earnings_Report_Draft.pdf",
    status: "success",
    stage: "Completed",
    triggeredAt: "2026-04-22 14:30",
  },
];

/**
 * 文档中心原型页。
 * 这里补的是原型阶段必须能演示的闭环：上传、筛选、批量重解析、失败重试，以及最近作业反馈。
 */
export function DocumentCenter() {
  const navigate = useNavigate();
  const { kbId } = useParams();
  const [docs, setDocs] = useState(INITIAL_DOCS);
  const [jobs, setJobs] = useState(INITIAL_JOBS);
  const [selected, setSelected] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | DocStatus>("");
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isReparseConfirmOpen, setIsReparseConfirmOpen] = useState(false);
  const [uploadName, setUploadName] = useState("New_Quarterly_Report.pdf");
  const [uploadLevel, setUploadLevel] = useState("Internal");
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning";
    title: string;
    message: string;
  } | null>(null);

  const filteredDocs = useMemo(() => {
    return docs.filter((doc) => {
      const matchesSearch =
        doc.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = !statusFilter || doc.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [docs, searchTerm, statusFilter]);

  const allVisibleSelected =
    filteredDocs.length > 0 &&
    filteredDocs.every((doc) => selected.includes(doc.id));

  /**
   * 创建一条新的上传原型记录，并同步补一条 ingest 作业，方便评审时直接看到“上传后系统反馈”。
   */
  function handleUploadSubmit() {
    const nextDoc: DocumentRecord = {
      id: `doc-${Math.floor(1000 + Math.random() * 9000)}`,
      name: uploadName,
      version: "v1",
      status: "queued",
      parsedAt: "待处理",
      uploader: "current_user",
      level: uploadLevel,
    };

    const nextJob: IngestJob = {
      id: `job-${Math.floor(1000 + Math.random() * 9000)}`,
      docName: uploadName,
      status: "queued",
      stage: "Queued for parser",
      triggeredAt: "刚刚",
    };

    setDocs((current) => [nextDoc, ...current]);
    setJobs((current) => [nextJob, ...current]);
    setFeedback({
      variant: "success",
      title: "上传请求已创建",
      message:
        "原型阶段已演示“上传即生成文档对象与 ingest 作业”的反馈，后续可在详细设计中补接口与状态机。",
    });
    setIsUploadOpen(false);
  }

  /**
   * 批量重解析不需要真实执行后台任务，但原型阶段必须明确影响范围、生成中的状态和列表反馈。
   */
  function handleConfirmBulkReparse() {
    setDocs((current) =>
      current.map((doc) =>
        selected.includes(doc.id)
          ? { ...doc, status: "running", parsedAt: "重解析中" }
          : doc,
      ),
    );
    setJobs((current) => [
      {
        id: `job-${Math.floor(1000 + Math.random() * 9000)}`,
        docName: `${selected.length} documents`,
        status: "running",
        stage: "Bulk re-parse started",
        triggeredAt: "刚刚",
      },
      ...current,
    ]);
    setFeedback({
      variant: "info",
      title: "批量重解析已发起",
      message: `已将 ${selected.length} 份文档置为运行中，评审时可以明确看到“风险操作需确认”的交互。`,
    });
    setSelected([]);
    setIsReparseConfirmOpen(false);
  }

  function handleRetryFailed(docId: string) {
    const target = docs.find((doc) => doc.id === docId);
    if (!target) return;

    setDocs((current) =>
      current.map((doc) =>
        doc.id === docId ? { ...doc, status: "running", parsedAt: "重试中" } : doc,
      ),
    );
    setJobs((current) => [
      {
        id: `job-${Math.floor(1000 + Math.random() * 9000)}`,
        docName: target.name,
        status: "running",
        stage: "Retry from failed stage",
        triggeredAt: "刚刚",
      },
      ...current,
    ]);
    setFeedback({
      variant: "warning",
      title: "失败作业已重试",
      message: `已重新发起 ${target.name} 的解析任务。`,
    });
  }

  function toggleDocSelection(docId: string, checked: boolean) {
    setSelected((current) =>
      checked ? [...current, docId] : current.filter((id) => id !== docId),
    );
  }

  function toggleVisibleSelection(checked: boolean) {
    if (!checked) {
      setSelected((current) =>
        current.filter((id) => !filteredDocs.some((doc) => doc.id === id)),
      );
      return;
    }

    const visibleIds = filteredDocs.map((doc) => doc.id);
    setSelected((current) => Array.from(new Set([...current, ...visibleIds])));
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="Document Center"
        description="管理文档、版本、重解析任务与最近 ingest 作业。"
        actions={
          <>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" /> 导出筛选结果
            </Button>
            <Button variant="primary" onClick={() => setIsUploadOpen(true)}>
              <Upload className="w-4 h-4 mr-2" /> 上传文档
            </Button>
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

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-6">
        <div className="space-y-6 min-w-0">
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative w-full max-w-80">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
              <Input
                placeholder="按文档名或 ID 搜索..."
                className="pl-9"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <select
              className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none focus:ring-1 focus:ring-focus-blue"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as "" | DocStatus)}
            >
              <option value="">全部状态</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
            </select>
            <div className="ml-auto flex items-center gap-3 text-sm text-stone-gray">
              <span>当前结果 {filteredDocs.length} 条</span>
              {selected.length > 0 && (
                <Button
                  variant="outline"
                  className="text-terracotta border-terracotta hover:bg-terracotta/10"
                  onClick={() => setIsReparseConfirmOpen(true)}
                >
                  <RefreshCw className="w-4 h-4 mr-2" /> 批量重解析 ({selected.length})
                </Button>
              )}
            </div>
          </div>

          {filteredDocs.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border-warm bg-ivory p-10 text-center">
              <div className="mx-auto mb-3 w-12 h-12 rounded-full bg-parchment flex items-center justify-center">
                <FileWarning className="w-5 h-5 text-stone-gray" />
              </div>
              <h3 className="text-lg font-serif text-near-black">没有匹配的文档</h3>
              <p className="mt-2 text-sm text-stone-gray">
                原型阶段需要把空状态呈现出来，避免评审时默认所有列表都“天然有数据”。
              </p>
              <Button className="mt-4" variant="outline" onClick={() => {
                setSearchTerm("");
                setStatusFilter("");
              }}>
                清空筛选
              </Button>
            </div>
          ) : (
            <div className="overflow-auto border border-border-cream rounded-xl">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">
                      <input
                        type="checkbox"
                        checked={allVisibleSelected}
                        className="rounded border-border-warm text-terracotta focus:ring-focus-blue"
                        onChange={(e) => toggleVisibleSelection(e.target.checked)}
                      />
                    </TableHead>
                    <TableHead>文档名</TableHead>
                    <TableHead>Active Ver.</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>密级</TableHead>
                    <TableHead>最近解析</TableHead>
                    <TableHead>上传人</TableHead>
                    <TableHead>ID</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDocs.map((doc) => (
                    <TableRow
                      key={doc.id}
                      className="cursor-pointer hover:bg-border-cream/30"
                      onClick={() => navigate(`/kb/${kbId}/docs/${doc.id}`)}
                    >
                      <TableCell>
                        <input
                          type="checkbox"
                          className="rounded border-border-warm text-terracotta focus:ring-focus-blue"
                          checked={selected.includes(doc.id)}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => toggleDocSelection(doc.id, e.target.checked)}
                        />
                      </TableCell>
                      <TableCell className="font-medium">{doc.name}</TableCell>
                      <TableCell mono>{doc.version}</TableCell>
                      <TableCell>
                        <StatusBadge status={doc.status} />
                      </TableCell>
                      <TableCell>
                        <Badge variant="default">{doc.level}</Badge>
                      </TableCell>
                      <TableCell>{doc.parsedAt}</TableCell>
                      <TableCell>{doc.uploader}</TableCell>
                      <TableCell mono>{doc.id}</TableCell>
                      <TableCell>
                        {doc.status === "failed" ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-terracotta"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRetryFailed(doc.id);
                            }}
                          >
                            <RefreshCw className="w-3 h-3 mr-1" /> 重试
                          </Button>
                        ) : (
                          <span className="text-xs text-stone-gray">查看详情</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border-cream bg-ivory p-5">
            <h3 className="font-serif text-lg text-near-black">最近 Ingest 作业</h3>
            <p className="mt-1 text-sm text-stone-gray">
              原型阶段至少要把“任务反馈区”显式画出来。
            </p>
          </div>

          <div className="space-y-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="rounded-xl border border-border-cream bg-ivory p-4 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-near-black truncate">{job.docName}</p>
                    <p className="text-xs text-stone-gray font-mono mt-1">{job.id}</p>
                  </div>
                  <StatusBadge status={job.status} />
                </div>
                <div className="text-sm text-stone-gray">
                  <div>阶段：{job.stage}</div>
                  <div className="mt-1">触发时间：{job.triggeredAt}</div>
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <Drawer
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        title="上传文档"
        width="560px"
      >
        <DrawerSection title="上传信息">
          <div className="space-y-4">
            <Input
              label="文件名"
              value={uploadName}
              onChange={(e) => setUploadName(e.target.value)}
              helperText="原型阶段用文本模拟选中文件，重点展示上传后的系统反馈。"
            />
            <div>
              <label className="block mb-2 text-sm font-medium text-near-black">文档密级</label>
              <select
                className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-[10px]"
                value={uploadLevel}
                onChange={(e) => setUploadLevel(e.target.value)}
              >
                <option>Public</option>
                <option>Internal</option>
                <option>Confidential</option>
              </select>
            </div>
          </div>
        </DrawerSection>
        <DrawerSection title="预期反馈">
          <ul className="text-sm text-stone-gray space-y-2 list-disc pl-5">
            <li>提交后立即生成文档对象，状态显示为 `queued`。</li>
            <li>右侧作业栏新增一条 ingest 任务。</li>
            <li>后续接口和真正上传组件留到详细设计与研发阶段补充。</li>
          </ul>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setIsUploadOpen(false)}>
              取消
            </Button>
            <Button variant="primary" onClick={handleUploadSubmit}>
              创建上传任务
            </Button>
          </div>
        </DrawerSection>
      </Drawer>

      <Dialog open={isReparseConfirmOpen} onOpenChange={setIsReparseConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认批量重解析</DialogTitle>
            <DialogDescription>
              此操作会对选中的文档重新触发解析与向量构建。原型阶段必须明确影响范围与二次确认。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg bg-parchment border border-border-cream p-4 text-sm text-near-black">
            已选中文档：{selected.length} 份
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsReparseConfirmOpen(false)}>
              取消
            </Button>
            <Button variant="primary" onClick={handleConfirmBulkReparse}>
              确认重解析
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
