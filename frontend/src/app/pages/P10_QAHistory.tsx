import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { BookmarkPlus, Copy, Eye, FileDown, GitCompare, PlayCircle, Search, Sparkles, ThumbsDown, ThumbsUp } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { StatusBadge, Badge } from "../components/rag/Badge";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { ratingToFeedbackStatus, toQAHistoryRecord, type QAHistoryRecordViewModel } from "../adapters/qaRunAdapter";
import {
  addQARunComment,
  createConfigDraftFromQARun,
  createEvaluationRun,
  createOptimizationDraftFromEvaluationRun,
  exportEvaluationRun,
  fetchEvaluationRunConfigDiff,
  fetchEvaluationRunDetail,
  fetchEvaluationRuns,
  createEvaluationSampleFromRun,
  fetchEvaluationSamples,
  fetchQARunCollaboration,
  fetchQARunDetail,
  fetchQARunReplayContext,
  fetchQARuns,
  updateQARunCollaboration,
  updateQARunFeedback,
} from "../services/qaRunService";
import type { EvaluationRunDetailDTO, QARunCollaborationDTO, QARunDetailDTO } from "../types/qaRun";

type RatingStatus = "up" | "down" | "none";
type HistoryRecord = QAHistoryRecordViewModel;

/**
 * QA 历史页接入 E8 历史详情、人工标注、回放和评估样本接口。
 * 页面不自行推断最终权限，详情和动作结果以后端返回为准。
 */
export function QAHistory() {
  const navigate = useNavigate();
  const { kbId = "" } = useParams();
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [feedbackFilter, setFeedbackFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedRun, setSelectedRun] = useState<HistoryRecord | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<QARunDetailDTO | null>(null);
  const [selectedCollaboration, setSelectedCollaboration] = useState<QARunCollaborationDTO | null>(null);
  const [commentInput, setCommentInput] = useState("");
  const [evaluationRuns, setEvaluationRuns] = useState<EvaluationRunDetailDTO["run"][]>([]);
  const [selectedEvaluationRun, setSelectedEvaluationRun] = useState<EvaluationRunDetailDTO | null>(null);
  const [selectedDiff, setSelectedDiff] = useState<{ path: string; before: unknown; after: unknown }[]>([]);
  const [evaluationCount, setEvaluationCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  async function loadHistory(keyword = searchTerm) {
    if (!kbId) return;
    setLoading(true);
    try {
      const page = await fetchQARuns(kbId, keyword, {
        status: statusFilter || undefined,
        feedbackStatus: feedbackFilter || undefined,
      });
      setHistory(page.items.map(toQAHistoryRecord));
      try {
        const samples = await fetchEvaluationSamples(kbId);
        setEvaluationCount(samples.total);
        const runPage = await fetchEvaluationRuns(kbId);
        setEvaluationRuns(runPage.items);
      } catch {
        setEvaluationCount(0);
        setEvaluationRuns([]);
      }
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "QA 历史加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务和历史权限。",
      });
    } finally {
      setLoading(false);
    }
  }

  async function openEvaluationRun(evaluationRunId: string) {
    try {
      setSelectedEvaluationRun(await fetchEvaluationRunDetail(kbId, evaluationRunId));
      const diff = await fetchEvaluationRunConfigDiff(kbId, evaluationRunId);
      setSelectedDiff(diff.diffItems.slice(0, 12));
    } catch (error) {
      setSelectedEvaluationRun(null);
      setSelectedDiff([]);
      setFeedback({
        variant: "error",
        title: "评估运行详情加载失败",
        message: error instanceof Error ? error.message : "请检查评估权限和运行状态。",
      });
    }
  }

  async function runEvaluationBatch() {
    setActionLoading("evaluation-create");
    try {
      await createEvaluationRun(kbId, { remark: "P10 手动触发回归" });
      await loadHistory(searchTerm);
      setFeedback({ variant: "success", title: "评估运行已创建", message: "已使用当前评估样本触发回归批次。" });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "创建评估运行失败",
        message: error instanceof Error ? error.message : "请检查评估样本和权限。",
      });
    } finally {
      setActionLoading(null);
    }
  }

  async function exportRun(evaluationRunId: string, format: "csv" | "markdown") {
    setActionLoading(`evaluation-export-${evaluationRunId}-${format}`);
    try {
      const response = await exportEvaluationRun(kbId, evaluationRunId, format);
      setFeedback({
        variant: "success",
        title: "评估结果已导出",
        message: `${response.fileName} 内容已生成，可复制到文档或工单系统。`,
      });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "导出失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setActionLoading(null);
    }
  }

  async function createOptimizationDraft(evaluationRunId: string) {
    setActionLoading(`evaluation-draft-${evaluationRunId}`);
    try {
      const response = await createOptimizationDraftFromEvaluationRun(kbId, evaluationRunId);
      setFeedback({
        variant: "success",
        title: "优化草稿已生成",
        message: `已创建草稿 ${response.configRevisionId.slice(0, 8)}，可到配置中心复核。`,
      });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "生成优化草稿失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setActionLoading(null);
    }
  }

  useEffect(() => {
    void loadHistory("");
  }, [kbId]);

  const sameQueryRuns = useMemo(() => {
    if (!selectedRun) return [];
    return history.filter((run) => run.query === selectedRun.query && run.id !== selectedRun.id);
  }, [history, selectedRun]);

  async function openRun(run: HistoryRecord) {
    setSelectedRun(run);
    setSelectedDetail(null);
    setSelectedCollaboration(null);
    setCommentInput("");
    try {
      const [detail, collaboration] = await Promise.all([
        fetchQARunDetail(kbId, run.id),
        fetchQARunCollaboration(kbId, run.id),
      ]);
      setSelectedDetail(detail);
      setSelectedCollaboration(collaboration);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "运行详情加载失败",
        message: error instanceof Error ? error.message : "请检查该运行记录是否仍可见。",
      });
    }
  }

  async function changeHandlingStatus(status: string) {
    if (!selectedRun) return;
    setActionLoading(`collaboration-${selectedRun.id}`);
    try {
      const response = await updateQARunCollaboration(kbId, selectedRun.id, { handlingStatus: status });
      setSelectedCollaboration(response);
      setFeedback({ variant: "success", title: "协作处理已更新", message: "责任人和处理状态以服务端记录为准。" });
    } catch (error) {
      setFeedback({ variant: "error", title: "协作处理更新失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function submitCollaborationComment() {
    if (!selectedRun || !commentInput.trim()) return;
    setActionLoading(`comment-${selectedRun.id}`);
    try {
      const response = await addQARunComment(kbId, selectedRun.id, commentInput.trim());
      setSelectedCollaboration(response);
      setCommentInput("");
      setFeedback({ variant: "success", title: "评论已添加", message: "QA Run 协作评论已保存。" });
    } catch (error) {
      setFeedback({ variant: "error", title: "评论添加失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function updateRating(runId: string, rating: RatingStatus) {
    setActionLoading(`feedback-${runId}`);
    try {
      const response = await updateQARunFeedback(
        kbId,
        runId,
        ratingToFeedbackStatus(rating),
        rating === "down" ? "manual_review_required" : undefined,
        rating === "up" ? "人工标注：正确" : rating === "down" ? "人工标注：错误或不满意" : undefined,
      );
      setHistory((current) => current.map((run) => (run.id === runId ? { ...run, rating, failureType: response.failureType || run.failureType } : run)));
      if (selectedDetail?.runId === runId) {
        setSelectedDetail({ ...selectedDetail, feedbackStatus: response.feedbackStatus, feedbackNote: response.feedbackNote, failureType: response.failureType });
      }
      setFeedback({ variant: "success", title: "人工标注已更新", message: "反馈状态和失败归因已保存到 QARun。" });
    } catch (error) {
      setFeedback({ variant: "error", title: "人工标注失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function addToRegression(run: HistoryRecord) {
    setActionLoading(`sample-${run.id}`);
    try {
      await createEvaluationSampleFromRun(kbId, run.id, selectedDetail?.answer ?? run.answer);
      const samples = await fetchEvaluationSamples(kbId);
      setEvaluationCount(samples.total);
      setFeedback({ variant: "success", title: "已加入评估样本", message: `${run.id} 已沉淀为后续回归验证样本。` });
    } catch (error) {
      setFeedback({ variant: "error", title: "加入评估样本失败", message: error instanceof Error ? error.message : "请检查评估样本管理权限。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function createDraft(run: HistoryRecord) {
    setActionLoading(`draft-${run.id}`);
    try {
      await createConfigDraftFromQARun(kbId, run.id);
      setFeedback({ variant: "success", title: "Revision 草稿已生成", message: "可到配置中心继续编辑并保存。" });
    } catch (error) {
      setFeedback({ variant: "error", title: "生成草稿失败", message: error instanceof Error ? error.message : "请检查配置管理权限。" });
    } finally {
      setActionLoading(null);
    }
  }

  async function replayRun(run: HistoryRecord) {
    setActionLoading(`replay-${run.id}`);
    try {
      const context = await fetchQARunReplayContext(kbId, run.id);
      navigate(`/kb/${kbId}/qa`, {
        state: {
          query: context.query,
          sourceRunId: context.sourceRunId,
          configRevisionId: context.configRevisionId,
          overrideParams: context.overrideParams,
          suggestedMode: context.suggestedMode,
          replayWarnings: context.warnings,
        },
      });
    } catch (error) {
      setFeedback({ variant: "error", title: "回放上下文获取失败", message: error instanceof Error ? error.message : "请检查 QA 运行权限。" });
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="QA 历史与监控"
        description="查看历史运行、人工反馈、失败归因、回放上下文与评估样本。"
        actions={<Badge variant="info">评估样本：{evaluationCount}</Badge>}
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
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
            onKeyDown={(event) => {
              if (event.key === "Enter") void loadHistory(searchTerm);
            }}
          />
        </div>
        <select
          className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          value={feedbackFilter}
          onChange={(e) => setFeedbackFilter(e.target.value)}
        >
          <option value="">全部反馈</option>
          <option value="correct">正确</option>
          <option value="wrong">错误</option>
          <option value="citation_error">引用错误</option>
          <option value="no_evidence">无证据</option>
          <option value="unrated">未标注</option>
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
          <option value="cancelled">已取消</option>
        </select>
        <Button variant="outline" onClick={() => void loadHistory(searchTerm)}>
          {loading ? "加载中..." : "搜索"}
        </Button>
        <Button variant="primary" onClick={() => void runEvaluationBatch()} disabled={actionLoading === "evaluation-create"}>
          <PlayCircle className="w-4 h-4 mr-2" /> 触发评估回归
        </Button>
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
            {history.map((run) => (
              <TableRow key={run.id}>
                <TableCell mono>{run.id}</TableCell>
                <TableCell className="font-medium text-near-black max-w-[260px] truncate" title={run.query}>
                  {run.query}
                </TableCell>
                <TableCell><StatusBadge status={run.status} /></TableCell>
                <TableCell>{run.user}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Badge variant="default">{run.rev}</Badge>
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
                    <Button variant="ghost" size="sm" onClick={() => void openRun(run)} title="查看详情">
                      <Eye className="w-4 h-4 text-terracotta" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void replayRun(run)} title="回放到调试器">
                      <PlayCircle className="w-4 h-4 text-terracotta" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="shrink-0 border border-border-cream rounded-xl p-4 bg-ivory space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-near-black">评估运行批次</h3>
          <Badge variant="default">{evaluationRuns.length} 批次</Badge>
        </div>
        <div className="max-h-48 overflow-auto space-y-2">
          {evaluationRuns.length === 0 ? (
            <p className="text-sm text-stone-gray">暂无评估运行，可点击“触发评估回归”创建。</p>
          ) : (
            evaluationRuns.map((run) => (
              <div key={run.evaluationRunId} className="rounded-lg border border-border-cream bg-parchment p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-near-black">{run.evaluationRunId.slice(0, 8)}</div>
                    <div className="text-xs text-stone-gray">
                      状态 {run.status} · 通过率 {(run.passRate * 100).toFixed(1)}% · 失败 {run.failedSamples}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" title="查看运行详情" onClick={() => void openEvaluationRun(run.evaluationRunId)}>
                      <Eye className="w-4 h-4 text-terracotta" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      title="导出 CSV"
                      disabled={actionLoading === `evaluation-export-${run.evaluationRunId}-csv`}
                      onClick={() => void exportRun(run.evaluationRunId, "csv")}
                    >
                      <FileDown className="w-4 h-4 text-terracotta" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      title="生成优化草稿"
                      disabled={actionLoading === `evaluation-draft-${run.evaluationRunId}`}
                      onClick={() => void createOptimizationDraft(run.evaluationRunId)}
                    >
                      <Sparkles className="w-4 h-4 text-terracotta" />
                    </Button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <Drawer
        isOpen={selectedRun !== null}
        onClose={() => {
          setSelectedRun(null);
          setSelectedDetail(null);
          setSelectedCollaboration(null);
          setCommentInput("");
        }}
        title={selectedRun ? `运行详情 · ${selectedRun.id}` : "运行详情"}
        width="640px"
      >
        {selectedRun && (
          <>
            <DrawerSection title="运行快照">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <StatusBadge status={selectedRun.status} />
                  <Badge variant="default">{selectedRun.rev}</Badge>
                  {selectedRun.hasOverrides && <Badge variant="warning">存在覆盖参数</Badge>}
                </div>
                <div className="text-sm text-near-black">
                  <div className="font-medium">{selectedRun.query}</div>
                  <p className="mt-2 text-stone-gray">{selectedDetail?.answer || selectedRun.answer}</p>
                </div>
              </div>
            </DrawerSection>

            <DrawerSection title="质量标注">
              <div className="space-y-3">
                <div className="flex gap-2">
                  <Button
                    variant={selectedRun.rating === "up" ? "primary" : "outline"}
                    size="sm"
                    disabled={actionLoading === `feedback-${selectedRun.id}`}
                    onClick={() => void updateRating(selectedRun.id, "up")}
                  >
                    <ThumbsUp className="w-4 h-4 mr-2" /> 正确
                  </Button>
                  <Button
                    variant={selectedRun.rating === "down" ? "destructive" : "outline"}
                    size="sm"
                    disabled={actionLoading === `feedback-${selectedRun.id}`}
                    onClick={() => void updateRating(selectedRun.id, "down")}
                  >
                    <ThumbsDown className="w-4 h-4 mr-2" /> 错误 / 不满意
                  </Button>
                </div>
                <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm text-stone-gray">
                  失败类型：{selectedDetail?.failureType || selectedRun.failureType}
                </div>
                {selectedDetail?.feedbackNote && (
                  <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm text-stone-gray">
                    备注：{selectedDetail.feedbackNote}
                  </div>
                )}
              </div>
            </DrawerSection>

            <DrawerSection title="协作处理">
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3 rounded-lg border border-border-cream bg-parchment p-3 text-sm">
                  <div>
                    <div className="text-xs text-stone-gray">责任人</div>
                    <div className="mt-1 text-near-black">{selectedCollaboration?.ownerId || "未分配"}</div>
                  </div>
                  <div>
                    <div className="text-xs text-stone-gray">处理状态</div>
                    <select
                      className="mt-1 w-full rounded-md border border-border-cream bg-white px-2 py-1 text-sm text-near-black"
                      value={selectedCollaboration?.handlingStatus || "open"}
                      disabled={actionLoading === `collaboration-${selectedRun.id}`}
                      onChange={(event) => void changeHandlingStatus(event.target.value)}
                    >
                      <option value="open">待处理</option>
                      <option value="in_progress">处理中</option>
                      <option value="resolved">已处理</option>
                      <option value="wont_fix">无需处理</option>
                    </select>
                  </div>
                </div>
                <div className="space-y-2">
                  {(selectedCollaboration?.comments || []).slice(-3).map((comment) => (
                    <div key={comment.commentId} className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
                      <div className="text-xs text-stone-gray">{comment.authorId} · {comment.createdAt}</div>
                      <div className="mt-1 text-near-black">{comment.content}</div>
                    </div>
                  ))}
                  {(selectedCollaboration?.comments || []).length === 0 && (
                    <p className="text-sm text-stone-gray">暂无协作评论。</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Input
                    value={commentInput}
                    onChange={(event) => setCommentInput(event.target.value)}
                    placeholder="添加处理备注..."
                  />
                  <Button
                    variant="outline"
                    disabled={!commentInput.trim() || actionLoading === `comment-${selectedRun.id}`}
                    onClick={() => void submitCollaborationComment()}
                  >
                    评论
                  </Button>
                </div>
              </div>
            </DrawerSection>

            <DrawerSection title="Trace 与 Evidence">
              <div className="space-y-3">
                <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm text-stone-gray">
                  Trace 步骤：{selectedDetail?.trace.length ?? "-"} · Evidence：{selectedDetail?.evidence.length ?? "-"} · Candidate：{selectedDetail?.candidates.length ?? "-"}
                </div>
                {selectedDetail?.evidence.slice(0, 3).map((evidence) => (
                  <div key={evidence.evidenceId} className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
                    <div className="font-mono text-xs text-stone-gray">{evidence.chunkId}</div>
                    <p className="mt-2 text-near-black">{evidence.contentSnapshot || "当前证据策略未返回正文快照。"}</p>
                  </div>
                ))}
              </div>
            </DrawerSection>

            <DrawerSection title="同 Query 对比">
              {sameQueryRuns.length === 0 ? (
                <p className="text-sm text-stone-gray">暂无同 query 的其它运行记录。</p>
              ) : (
                <div className="space-y-3">
                  {sameQueryRuns.map((run) => (
                    <div key={run.id} className="rounded-lg border border-border-cream bg-parchment p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-near-black">{run.id}</span>
                            <Badge variant="default">{run.rev}</Badge>
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
                <Button variant="outline" disabled={actionLoading === `replay-${selectedRun.id}`} onClick={() => void replayRun(selectedRun)}>
                  <PlayCircle className="w-4 h-4 mr-2" /> 回放到 QA 调试
                </Button>
                <Button variant="ghost" disabled={actionLoading === `sample-${selectedRun.id}`} onClick={() => void addToRegression(selectedRun)}>
                  <BookmarkPlus className="w-4 h-4 mr-2" /> 加入评估集
                </Button>
                <Button variant="ghost" disabled={actionLoading === `draft-${selectedRun.id}`} onClick={() => void createDraft(selectedRun)}>
                  <Copy className="w-4 h-4 mr-2" /> 生成 Revision 草稿
                </Button>
              </div>
            </DrawerSection>
          </>
        )}
      </Drawer>

      <Drawer
        isOpen={selectedEvaluationRun !== null}
        onClose={() => {
          setSelectedEvaluationRun(null);
          setSelectedDiff([]);
        }}
        title={selectedEvaluationRun ? `评估批次 · ${selectedEvaluationRun.run.evaluationRunId.slice(0, 8)}` : "评估批次"}
        width="640px"
      >
        {selectedEvaluationRun && (
          <>
            <DrawerSection title="批次概览">
              <div className="space-y-2 text-sm text-near-black">
                <div>状态：{selectedEvaluationRun.run.status}</div>
                <div>样本：{selectedEvaluationRun.run.totalSamples}（通过 {selectedEvaluationRun.run.passedSamples} / 失败 {selectedEvaluationRun.run.failedSamples}）</div>
                <div>通过率：{(selectedEvaluationRun.run.passRate * 100).toFixed(1)}%</div>
              </div>
            </DrawerSection>
            <DrawerSection title="配置差异（前 12 项）">
              {selectedDiff.length === 0 ? (
                <p className="text-sm text-stone-gray">该批次与来源配置无显著差异，或暂无可比较来源。</p>
              ) : (
                <div className="space-y-2">
                  {selectedDiff.map((item) => (
                    <div key={item.path} className="rounded-lg border border-border-cream bg-parchment p-2 text-xs">
                      <div className="font-mono text-near-black">{item.path}</div>
                      <div className="text-stone-gray">before: {String(item.before)}</div>
                      <div className="text-stone-gray">after: {String(item.after)}</div>
                    </div>
                  ))}
                </div>
              )}
            </DrawerSection>
            <DrawerSection title="失败样本摘要">
              <div className="space-y-2">
                {selectedEvaluationRun.results.filter((result) => result.status === "failed").slice(0, 8).map((result) => (
                  <div key={result.evaluationResultId} className="rounded-lg border border-border-cream bg-parchment p-2 text-xs text-stone-gray">
                    <div className="font-mono text-near-black">{result.sampleId.slice(0, 8)} · {result.failureReason || "failed"}</div>
                    <div className="mt-1">{result.query}</div>
                  </div>
                ))}
                {selectedEvaluationRun.results.every((result) => result.status !== "failed") && (
                  <p className="text-sm text-stone-gray">该批次无失败样本。</p>
                )}
              </div>
            </DrawerSection>
          </>
        )}
      </Drawer>
    </div>
  );
}
