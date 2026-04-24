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
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { StatusBadge, Badge } from "../components/rag/Badge";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import {
  Search,
  Download,
  PlayCircle,
  ThumbsUp,
  ThumbsDown,
  Eye,
  GitCompare,
  BookmarkPlus,
} from "lucide-react";
import { useNavigate, useParams } from "react-router";

type RunStatus = "success" | "partial" | "failed";
type RatingStatus = "up" | "down" | "none";

interface HistoryRecord {
  id: string;
  query: string;
  status: RunStatus;
  user: string;
  time: string;
  rev: string;
  rating: RatingStatus;
  hasOverrides: boolean;
  failureType: string;
  answer: string;
}

const INITIAL_HISTORY: HistoryRecord[] = [
  {
    id: "run-88f9",
    query: "Q3 延期的主要风险是什么？",
    status: "success",
    user: "admin",
    time: "10 分钟前",
    rev: "rev_042",
    rating: "up",
    hasOverrides: false,
    failureType: "无",
    answer: "Aurora 延期可能带来 1200 万美元收入缺口，并造成 Q4 供应链连锁风险。",
  },
  {
    id: "run-88fa",
    query: "给我看远程办公的员工手册。",
    status: "success",
    user: "jdoe",
    time: "1 小时前",
    rev: "rev_042",
    rating: "down",
    hasOverrides: true,
    failureType: "引用不完整",
    answer: "返回了远程办公摘要，但缺少 HR handbook 的直接引用。",
  },
  {
    id: "run-88fb",
    query: "Q3 延期的主要风险是什么？",
    status: "partial",
    user: "asmith",
    time: "3 小时前",
    rev: "rev_041",
    rating: "none",
    hasOverrides: true,
    failureType: "Graph 超时降级",
    answer: "文档侧给出了收入风险，但图检索链路失败。",
  },
  {
    id: "run-88fc",
    query: "解释一下 API v2 的限流规则。",
    status: "failed",
    user: "system",
    time: "1 天前",
    rev: "rev_041",
    rating: "none",
    hasOverrides: false,
    failureType: "未召回到正确文档",
    answer: "运行失败，未返回有效答案。",
  },
];

/**
 * QA 历史页原型。
 * 原型阶段必须能看见：详情、人工标注、失败归因、同 query 对比、回放到调试页。
 */
export function QAHistory() {
  const navigate = useNavigate();
  const { kbId } = useParams();
  const [history, setHistory] = useState(INITIAL_HISTORY);
  const [searchTerm, setSearchTerm] = useState("");
  const [revisionFilter, setRevisionFilter] = useState("");
  const [feedbackFilter, setFeedbackFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedRun, setSelectedRun] = useState<HistoryRecord | null>(null);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info";
    title: string;
    message: string;
  } | null>(null);
  const [regressionSet, setRegressionSet] = useState<string[]>([]);

  const filteredRuns = useMemo(() => {
    return history.filter((run) => {
      const matchesSearch =
        run.query.toLowerCase().includes(searchTerm.toLowerCase()) ||
        run.id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesRevision = !revisionFilter || run.rev === revisionFilter;
      const matchesFeedback = !feedbackFilter || run.rating === feedbackFilter;
      const matchesStatus = !statusFilter || run.status === statusFilter;
      return matchesSearch && matchesRevision && matchesFeedback && matchesStatus;
    });
  }, [feedbackFilter, history, revisionFilter, searchTerm, statusFilter]);

  const sameQueryRuns = useMemo(() => {
    if (!selectedRun) return [];
    return history.filter(
      (run) => run.query === selectedRun.query && run.id !== selectedRun.id,
    );
  }, [history, selectedRun]);

  function updateRating(runId: string, rating: RatingStatus) {
    setHistory((current) =>
      current.map((run) => (run.id === runId ? { ...run, rating } : run)),
    );
    setFeedback({
      variant: "success",
      title: "人工标注已更新",
      message: "原型阶段重点是把“可标注、可归因”的能力露出来。",
    });
  }

  function addToRegression(runId: string) {
    setRegressionSet((current) =>
      current.includes(runId) ? current : [...current, runId],
    );
    setFeedback({
      variant: "info",
      title: "已加入回归样本集",
      message: `${runId} 已标记为后续版本验证样本。`,
    });
  }

  /**
   * 把历史记录带回 QA 调试页。
   * 原型阶段不需要接真实 run 快照接口，但必须把回放入口和带参跳转串起来。
   */
  function replayRun(run: HistoryRecord) {
    navigate(`/kb/${kbId}/qa`, {
      state: {
        query: run.query,
        sourceRunId: run.id,
        revision: run.rev,
        scenario:
          run.status === "partial"
            ? "partial"
            : run.failureType.includes("权限")
              ? "permission"
              : "success",
      },
    });
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="QA 历史与监控"
        description="查看历史运行、人工反馈、失败归因与同 query 回放。"
        actions={
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" /> 导出快照
          </Button>
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

      <div className="flex flex-wrap items-center gap-4 shrink-0">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input
            placeholder="搜索 query 或 run ID..."
            className="pl-9"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <select
          className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          value={revisionFilter}
          onChange={(e) => setRevisionFilter(e.target.value)}
        >
          <option value="">全部版本</option>
          <option value="rev_042">rev_042（当前生效）</option>
          <option value="rev_041">rev_041</option>
        </select>
        <select
          className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          value={feedbackFilter}
          onChange={(e) => setFeedbackFilter(e.target.value)}
        >
          <option value="">全部反馈</option>
          <option value="up">正向</option>
          <option value="down">负向</option>
          <option value="none">未标注</option>
        </select>
        <select
          className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="partial">部分成功</option>
          <option value="failed">失败</option>
        </select>
      </div>

      <div className="flex-1 overflow-auto border border-border-cream rounded-xl">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>运行 ID</TableHead>
              <TableHead className="w-1/3">问题</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>用户</TableHead>
              <TableHead>版本</TableHead>
              <TableHead>反馈</TableHead>
              <TableHead>失败类型</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredRuns.map((run) => (
              <TableRow key={run.id}>
                <TableCell mono>{run.id}</TableCell>
                <TableCell className="font-medium text-near-black max-w-[260px] truncate" title={run.query}>
                  {run.query}
                </TableCell>
                <TableCell>
                  <StatusBadge status={run.status} />
                </TableCell>
                <TableCell>{run.user}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Badge variant={run.rev === "rev_042" ? "success" : "default"}>
                      {run.rev}
                    </Badge>
                    {run.hasOverrides && <Badge variant="warning">存在覆盖参数</Badge>}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1">
                    {run.rating === "up" && <ThumbsUp className="w-4 h-4 text-success-green fill-success-green/20" />}
                    {run.rating === "down" && <ThumbsDown className="w-4 h-4 text-error-red fill-error-red/20" />}
                    {run.rating === "none" && <span className="text-stone-gray">-</span>}
                  </div>
                </TableCell>
                <TableCell className="text-stone-gray">{run.failureType}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedRun(run)}
                      title="查看详情"
                    >
                      <Eye className="w-4 h-4 text-terracotta" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => replayRun(run)}
                      title="回放到调试器"
                    >
                      <PlayCircle className="w-4 h-4 text-terracotta" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Drawer
        isOpen={selectedRun !== null}
        onClose={() => setSelectedRun(null)}
        title={selectedRun ? `运行详情 · ${selectedRun.id}` : "运行详情"}
        width="640px"
      >
        {selectedRun && (
          <>
            <DrawerSection title="运行快照">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <StatusBadge status={selectedRun.status} />
                  <Badge variant={selectedRun.rev === "rev_042" ? "success" : "default"}>
                    {selectedRun.rev}
                  </Badge>
                  {selectedRun.hasOverrides && <Badge variant="warning">存在覆盖参数</Badge>}
                </div>
                <div className="text-sm text-near-black">
                  <div className="font-medium">{selectedRun.query}</div>
                  <p className="mt-2 text-stone-gray">{selectedRun.answer}</p>
                </div>
              </div>
            </DrawerSection>

            <DrawerSection title="质量标注">
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Button
                    variant={selectedRun.rating === "up" ? "primary" : "outline"}
                    size="sm"
                    onClick={() => updateRating(selectedRun.id, "up")}
                  >
                    <ThumbsUp className="w-4 h-4 mr-2" /> 正确
                  </Button>
                  <Button
                    variant={selectedRun.rating === "down" ? "destructive" : "outline"}
                    size="sm"
                    onClick={() => updateRating(selectedRun.id, "down")}
                  >
                    <ThumbsDown className="w-4 h-4 mr-2" /> 错误 / 不满意
                  </Button>
                </div>
                <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm text-stone-gray">
                  失败类型：{selectedRun.failureType}
                </div>
              </div>
            </DrawerSection>

            <DrawerSection title="同 Query 对比">
              {sameQueryRuns.length === 0 ? (
                <p className="text-sm text-stone-gray">暂无同 query 的其它运行记录。</p>
              ) : (
                <div className="space-y-3">
                  {sameQueryRuns.map((run) => (
                    <div
                      key={run.id}
                      className="rounded-lg border border-border-cream bg-parchment p-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-near-black">{run.id}</span>
                            <Badge variant={run.rev === "rev_042" ? "success" : "default"}>
                              {run.rev}
                            </Badge>
                          </div>
                          <p className="mt-1 text-sm text-stone-gray">{run.answer}</p>
                        </div>
                        <GitCompare className="w-4 h-4 text-terracotta shrink-0" />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </DrawerSection>

            <DrawerSection title="后续动作">
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => replayRun(selectedRun)}>
                  <PlayCircle className="w-4 h-4 mr-2" /> 回放到 QA 调试
                </Button>
                <Button variant="ghost" onClick={() => addToRegression(selectedRun.id)}>
                  <BookmarkPlus className="w-4 h-4 mr-2" />
                  {regressionSet.includes(selectedRun.id) ? "已加入回归集" : "加入回归集"}
                </Button>
              </div>
            </DrawerSection>
          </>
        )}
      </Drawer>
    </div>
  );
}
