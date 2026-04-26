import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge, StatusBadge } from "../components/rag/Badge";
import {
  Play,
  Settings2,
  Activity,
  Zap,
  Network,
  AlignLeft,
  Info,
  FileText,
  Save,
  History as HistoryIcon,
  Copy,
} from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";
import { toQADebugResult } from "../adapters/qaRunAdapter";
import { createQARun, fetchQARunDetail, fetchQARunStatus } from "../services/qaRunService";

type DebugScenario = "success" | "partial" | "permission";

interface RunSeedState {
  query?: string;
  sourceRunId?: string;
  revision?: string;
  scenario?: DebugScenario;
}

interface CandidateRecord {
  id: string;
  source: "Dense" | "Sparse" | "Graph" | "Mock";
  title: string;
  score: string;
  decision: string;
}

interface ScenarioPayload {
  status: "success" | "partial" | "failed";
  answer: string[];
  runMeta: string;
  notice?: { variant: "info" | "warning"; title: string; message: string };
  rewrite: string;
  retrievalCards: { channel: string; summary: string }[];
  candidates: CandidateRecord[];
  citations: {
    id: string;
    type: "document" | "graph";
    title: string;
    snippet: string;
    meta: string;
  }[];
  diagnostics: {
    recalled: string;
    deduped: string;
    filtered: string;
    finalContext: string;
    rerankSummary: string;
  };
}

const SCENARIO_MAP: Record<DebugScenario, ScenarioPayload> = {
  success: {
    status: "success",
    answer: [
      "Q3 产品延期的核心风险主要集中在收入缺口和市场窗口损失。根据 Q3 Draft Report，Aurora 产品线延迟 4 周可能带来约 1200 万美元的季度收入缺口。",
      "图检索进一步补充了根因链路：APAC 区域的 Supplier B 已被标记为 bottleneck，这意味着问题不仅影响 Q3，还会把 Q4 的供应计划继续拖长。",
    ],
    runMeta: "run_88f92a • 1.2 秒 • 428 tokens • 生效版本 rev_042",
    rewrite:
      "Q3 product delays impact risk revenue supply chain Aurora supplier bottleneck",
    retrievalCards: [
      { channel: "Dense", summary: "Top 20 chunks，阈值 0.75" },
      { channel: "Sparse", summary: "Top 15 chunks，命中 Aurora 和 APAC 关键词" },
      { channel: "Graph", summary: "深度 2，命中 8 个实体、2 条关键关系" },
    ],
    candidates: [
      {
        id: "chk-001",
        source: "Dense",
        title: "Q3 revenue impact paragraph",
        score: "0.92",
        decision: "保留，作为最终回答主证据",
      },
      {
        id: "graph-node-12",
        source: "Graph",
        title: "Aurora -> Supplier B -> APAC bottleneck",
        score: "0.88",
        decision: "保留，补足根因链路",
      },
      {
        id: "chk-044",
        source: "Sparse",
        title: "Generic delivery policy",
        score: "0.67",
        decision: "淘汰，语义相关但不回答当前问题",
      },
    ],
    citations: [
      {
        id: "1",
        type: "document",
        title: "Q3_Earnings_Report_Draft.pdf",
        snippet:
          "\"...delaying the Aurora product line by even 4 weeks could result in a projected $12M miss on the quarterly forecast...\"",
        meta: "Chunk ID: chk-001 | 第 4 页 | 点击跳转文档详情",
      },
      {
        id: "2",
        type: "graph",
        title: "图谱子图：APAC 供应商",
        snippet:
          "Paths: (Aurora Line) -[DEPENDS_ON]-> (Supplier B) -[LOCATED_IN]-> (APAC). Supplier B Status: BOTTLENECK.",
        meta: "来源于图谱检索",
      },
    ],
    diagnostics: {
      recalled: "43",
      deduped: "38",
      filtered: "-2",
      finalContext: "5",
      rerankSummary: "Graph context 上升到 Top2，噪声 Sparse 命中被压低。",
    },
  },
  partial: {
    status: "partial",
    answer: [
      "当前结果为部分降级成功。系统仍然给出了文档侧可验证结论：Aurora 产品线延期会造成收入缺口，并影响 Q4 计划。",
      "但图检索链路本次执行失败，因此根因网络只保留了文本侧证据，图侧关系没有进入最终上下文。",
    ],
    runMeta: "run_91ad43 • 1.6 秒 • 396 tokens • 部分降级",
    notice: {
      variant: "warning",
      title: "部分降级成功",
      message:
        "Dense / Sparse 正常，Graph 检索超时并被降级跳过。原型阶段需要明确区分“部分成功”和“整体失败”。",
    },
    rewrite: "Aurora delay revenue impact Q3 Q4 supply chain risk",
    retrievalCards: [
      { channel: "Dense", summary: "Top 20 chunks，已完成" },
      { channel: "Sparse", summary: "Top 15 chunks，已完成" },
      { channel: "Graph", summary: "800ms 后超时，已从最终上下文跳过" },
    ],
    candidates: [
      {
        id: "chk-001",
        source: "Dense",
        title: "Q3 revenue impact paragraph",
        score: "0.91",
        decision: "保留",
      },
      {
        id: "chk-002",
        source: "Sparse",
        title: "Supply chain risk register",
        score: "0.74",
        decision: "保留，补足延期背景",
      },
      {
        id: "graph-timeout",
        source: "Graph",
        title: "图谱检索请求",
        score: "-",
        decision: "失败，未进入融合",
      },
    ],
    citations: [
      {
        id: "1",
        type: "document",
        title: "Q3_Earnings_Report_Draft.pdf",
        snippet:
          "\"...delaying the Aurora product line by even 4 weeks could result in a projected $12M miss...\"",
        meta: "Chunk ID: chk-001 | 第 4 页 | 点击跳转文档详情",
      },
    ],
    diagnostics: {
      recalled: "31",
      deduped: "27",
      filtered: "0",
      finalContext: "4",
      rerankSummary: "Graph 失败后只基于文档侧候选重排。",
    },
  },
  permission: {
    status: "success",
    answer: [
      "当前回答成功生成，但最终上下文经过权限裁剪。系统命中了两个高相关候选，其中 1 个因为权限不足未进入生成上下文。",
      "因此回答仍能给出收入风险结论，但不会展示被裁剪 chunk 的正文内容。",
    ],
    runMeta: "run_71ce22 • 1.1 秒 • 355 tokens • 权限过滤",
    notice: {
      variant: "info",
      title: "存在权限裁剪",
      message:
        "检索阶段命中候选，但有部分 chunk 因权限不足未进入最终上下文。这个状态应该在原型阶段明确露出。",
    },
    rewrite: "Aurora product delay revenue impact privileged chunks filtered",
    retrievalCards: [
      { channel: "Dense", summary: "Top 20 chunks，其中 1 个机密 chunk 被过滤" },
      { channel: "Sparse", summary: "Top 15 chunks" },
      { channel: "Graph", summary: "深度 2，保留图摘要" },
    ],
    candidates: [
      {
        id: "chk-001",
        source: "Dense",
        title: "Q3 revenue impact paragraph",
        score: "0.92",
        decision: "保留",
      },
      {
        id: "chk-sec-009",
        source: "Dense",
        title: "机密董事会备忘录片段",
        score: "0.89",
        decision: "权限过滤，未进入最终上下文",
      },
      {
        id: "graph-node-12",
        source: "Graph",
        title: "Supplier bottleneck graph summary",
        score: "0.83",
        decision: "保留",
      },
    ],
    citations: [
      {
        id: "1",
        type: "document",
        title: "Q3_Earnings_Report_Draft.pdf",
        snippet:
          "\"...the projected $12M miss on the quarterly forecast...\"",
        meta: "Chunk ID: chk-001 | 第 4 页 | 点击跳转文档详情",
      },
      {
        id: "2",
        type: "graph",
        title: "图摘要",
        snippet: "Supplier B remains the critical bottleneck in APAC.",
        meta: "机密 chunk 已在生成前过滤",
      },
    ],
    diagnostics: {
      recalled: "39",
      deduped: "35",
      filtered: "-1",
      finalContext: "4",
      rerankSummary: "权限裁剪发生在 rerank 之后、生成之前。",
    },
  },
};

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function isUuid(value: string | undefined): value is string {
  return Boolean(value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value));
}

async function waitForDetailReady(kbId: string, runId: string) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const status = await fetchQARunStatus(kbId, runId);
    if (status.detailReady) {
      return status;
    }
    await delay(500);
  }

  throw new Error("QA Run 尚未完成，请稍后在历史页查看。");
}

/**
 * QA 调试页原型。
 * 原型阶段必须补的是“单次实验闭环”：运行、查看链路、看到降级/权限异常、保存与回放入口。
 */
export function QADebug() {
  const navigate = useNavigate();
  const location = useLocation();
  const { kbId } = useParams();
  const seed = (location.state as RunSeedState | null) ?? {};

  const [query, setQuery] = useState(seed.query ?? "");
  const [isRunning, setIsRunning] = useState(false);
  const [showResults, setShowResults] = useState(Boolean(seed.query));
  const [scenario, setScenario] = useState<DebugScenario>(seed.scenario ?? "success");
  const [runResult, setRunResult] = useState<ScenarioPayload | null>(null);
  const [overrideMode, setOverrideMode] = useState(Boolean(seed.sourceRunId));
  const [rewriteEnabled, setRewriteEnabled] = useState(true);
  const [channels, setChannels] = useState({
    dense: true,
    sparse: true,
    graph: true,
  });
  const [rerankerTopN, setRerankerTopN] = useState("5");
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(
    seed.sourceRunId
      ? {
          variant: "info",
          title: "已从历史记录回放",
          message: `已带入 ${seed.sourceRunId} 的 query 与运行上下文，你可以继续做本次实验覆盖。`,
        }
      : null,
  );

  const result = useMemo(() => runResult ?? SCENARIO_MAP[scenario], [runResult, scenario]);

  useEffect(() => {
    if (!seed.query) return;
    setQuery(seed.query);
    setScenario(seed.scenario ?? "success");
    setShowResults(true);
  }, [seed.query, seed.scenario]);

  /**
   * 原型运行逻辑只模拟关键状态切换，
   * 重点让评审能看到“单次运行产生哪些中间结果与异常反馈”。
   */
  async function handleRun() {
    if (!query.trim()) {
      setFeedback({
        variant: "error",
        title: "请输入 Query",
        message: "原型阶段至少要保证基本校验成立，避免空运行。",
      });
      return;
    }

    if (!channels.dense && !channels.sparse && !channels.graph) {
      setFeedback({
        variant: "error",
        title: "不能全部关闭检索通道",
        message: "这类前置校验建议在原型阶段就体现，避免拖到实现阶段才发现交互缺口。",
      });
      return;
    }

    setIsRunning(true);
    setShowResults(false);
    setFeedback(null);
    setRunResult(null);

    try {
      const created = await createQARun(
        kbId || "",
        query.trim(),
        { rewriteEnabled, channels, rerankerTopN },
        isUuid(seed.sourceRunId) ? seed.sourceRunId : undefined,
      );
      await waitForDetailReady(kbId || "", created.runId);
      const detail = await fetchQARunDetail(kbId || "", created.runId);
      const nextResult = toQADebugResult(detail);
      setRunResult(nextResult);
      setIsRunning(false);
      setShowResults(true);
      setFeedback({
        variant: nextResult.status === "partial" ? "warning" : nextResult.status === "failed" ? "error" : "success",
        title: nextResult.status === "partial" ? "运行完成（部分降级）" : nextResult.status === "failed" ? "运行失败" : "运行完成",
        message:
          nextResult.status === "partial"
            ? "Graph 通道失败但其余链路完成。"
            : "已生成答案、证据、候选和诊断信息。",
      });
    } catch (error) {
      setIsRunning(false);
      setShowResults(false);
      setFeedback({
        variant: "error",
        title: "QA Run 创建失败",
        message: error instanceof Error ? error.message : "请检查后端服务和 active ConfigRevision。",
      });
    }
  }

  function handleSaveAction(action: "run" | "preset" | "draft") {
    const actionMessage = {
      run: "已保留本次调试记录，后续可在 QA History 中继续回看。",
      preset: "已保存为调试预设。是否真正持久化可留到详细设计与研发阶段。",
      draft: "已生成可沉淀到配置中心的 revision 草稿入口，但不会直接修改 active pipeline。",
    };

    setFeedback({
      variant: "success",
      title: "原型动作已触发",
      message: actionMessage[action],
    });
  }

  function handleReplayHistory() {
    navigate(`/kb/${kbId}/history`);
  }

  function handleOpenCitation(citationType: "document" | "graph") {
    if (citationType === "document") {
      navigate(`/kb/${kbId}/docs/doc-9012`);
      return;
    }

    navigate(`/kb/${kbId}/graph`);
  }

  return (
    <div className="flex flex-col h-full bg-parchment">
      <div className="shrink-0 p-4 border-b border-border-cream bg-ivory flex items-center justify-between">
        <div>
          <h1 className="text-xl font-serif text-near-black">QA 调试器</h1>
          <p className="text-xs text-stone-gray">
            执行单次问答实验，查看实际执行链路；本页只做临时覆盖，不修改正式 Pipeline 拓扑。
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={handleReplayHistory}>
            <HistoryIcon className="w-4 h-4 mr-2" /> 最近运行
          </Button>
          <Button variant="primary" disabled={isRunning} onClick={handleRun}>
            <Play className="w-4 h-4 mr-2" /> {isRunning ? "运行中..." : "开始调试"}
          </Button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-1/3 min-w-[340px] max-w-[420px] border-r border-border-cream bg-ivory overflow-y-auto p-4 space-y-6">
          {feedback && (
            <Alert
              variant={feedback.variant}
              title={feedback.title}
              onClose={() => setFeedback(null)}
            >
              {feedback.message}
            </Alert>
          )}

          <div className="rounded-lg border border-border-cream bg-parchment p-3 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-near-black">运行上下文</span>
              <Badge variant="info">{seed.revision ?? "rev_042"}</Badge>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                className={`rounded-md border px-3 py-2 text-left ${
                  !overrideMode
                    ? "border-terracotta bg-ivory text-terracotta"
                    : "border-border-cream bg-ivory text-stone-gray"
                }`}
                onClick={() => setOverrideMode(false)}
              >
                使用生效版本
              </button>
              <button
                className={`rounded-md border px-3 py-2 text-left ${
                  overrideMode
                    ? "border-terracotta bg-ivory text-terracotta"
                    : "border-border-cream bg-ivory text-stone-gray"
                }`}
                onClick={() => setOverrideMode(true)}
              >
                使用本次覆盖参数
              </button>
            </div>
          </div>

          <div className="space-y-3">
            <label className="text-sm font-medium text-near-black">原始问题</label>
            <textarea
              className="w-full h-24 p-3 bg-parchment border border-border-cream rounded-lg text-sm focus:ring-1 focus:ring-focus-blue focus:outline-none resize-none"
              placeholder="Q3 产品延期的主要风险是什么？"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Input
              label="实验备注"
              defaultValue={seed.sourceRunId ? `Replay from ${seed.sourceRunId}` : "Investigate delay risk"}
            />
          </div>

          <div className="border border-border-cream rounded-lg overflow-hidden">
            <div className="bg-parchment p-3 border-b border-border-cream flex items-center justify-between">
              <span className="text-sm font-medium text-near-black flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-terracotta" /> 临时覆盖参数
              </span>
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  className="rounded text-terracotta"
                  checked={overrideMode}
                  onChange={(e) => setOverrideMode(e.target.checked)}
                />
                启用
              </label>
            </div>
            <div className="p-4 space-y-4 bg-ivory">
              <div className="space-y-2">
                <label className="text-xs font-medium text-stone-gray">演示场景</label>
                <select
                  className="w-full px-3 py-2 bg-parchment border border-border-cream rounded-md text-sm"
                  value={scenario}
                  onChange={(e) => {
                    setScenario(e.target.value as DebugScenario);
                    setRunResult(null);
                  }}
                >
                  <option value="success">正常成功</option>
                  <option value="partial">部分降级成功</option>
                  <option value="permission">权限裁剪场景</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-stone-gray">问题改写</label>
                <label className="flex items-center gap-2 bg-parchment p-2 rounded border border-border-cream text-sm">
                  <input
                    type="checkbox"
                    checked={rewriteEnabled}
                    onChange={(e) => setRewriteEnabled(e.target.checked)}
                    className="rounded text-terracotta"
                  />
                  启用问题重写
                </label>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-stone-gray">检索通道</label>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <label className="flex items-center gap-2 bg-parchment p-2 rounded border border-border-cream">
                    <input
                      type="checkbox"
                      checked={channels.dense}
                      onChange={(e) =>
                        setChannels((current) => ({ ...current, dense: e.target.checked }))
                      }
                      className="rounded text-terracotta"
                    />
                    Dense
                  </label>
                  <label className="flex items-center gap-2 bg-parchment p-2 rounded border border-border-cream">
                    <input
                      type="checkbox"
                      checked={channels.sparse}
                      onChange={(e) =>
                        setChannels((current) => ({ ...current, sparse: e.target.checked }))
                      }
                      className="rounded text-terracotta"
                    />
                    Sparse
                  </label>
                  <label className="flex items-center gap-2 bg-parchment p-2 rounded border border-border-cream">
                    <input
                      type="checkbox"
                      checked={channels.graph}
                      onChange={(e) =>
                        setChannels((current) => ({ ...current, graph: e.target.checked }))
                      }
                      className="rounded text-terracotta"
                    />
                    Graph
                  </label>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-medium text-stone-gray">重排 Top-N</label>
                <Input
                  type="number"
                  value={rerankerTopN}
                  onChange={(e) => setRerankerTopN(e.target.value)}
                  className="bg-transparent h-8"
                />
              </div>

              <div className="p-2 bg-warning-amber/10 border border-warning-amber/20 rounded text-xs text-warning-amber">
                覆盖参数仅影响本次运行，不会修改 active revision（{seed.revision ?? "rev_042"}）。
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col bg-parchment overflow-hidden">
          {!isRunning && !showResults && (
            <div className="flex-1 flex items-center justify-center text-stone-gray flex-col gap-4">
              <Activity className="w-12 h-12 opacity-20" />
              <p>输入问题后运行调试，即可查看中间链路与诊断信息。</p>
            </div>
          )}

          {isRunning && (
            <div className="flex-1 flex items-center justify-center">
              <div className="space-y-4 text-center">
                <div className="w-8 h-8 border-4 border-terracotta border-t-transparent rounded-full animate-spin mx-auto"></div>
                <p className="text-sm font-medium text-near-black">正在执行 RAG Pipeline...</p>
                <p className="text-xs text-stone-gray font-mono">
                  {scenario === "partial" ? "图检索超时，已回退" : "正在从混合索引检索"}
                </p>
              </div>
            </div>
          )}

          {showResults && (
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {result.notice && (
                <Alert variant={result.notice.variant} title={result.notice.title}>
                  {result.notice.message}
                </Alert>
              )}

              <section className="bg-ivory border border-border-cream rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-border-cream bg-white">
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={result.status} />
                    <span className="text-xs text-stone-gray font-mono">{result.runMeta}</span>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <h2 className="font-serif text-xl text-near-black">最终答案</h2>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm" onClick={() => handleSaveAction("run")}>
                        <Save className="w-4 h-4 mr-2" /> 保存本次结果
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleSaveAction("preset")}>
                        <Copy className="w-4 h-4 mr-2" /> 保存为预设
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => handleSaveAction("draft")}>
                        沉淀为 Revision 草稿
                      </Button>
                    </div>
                  </div>
                </div>
                <div className="p-6 text-sm text-near-black leading-relaxed space-y-4">
                  {result.answer.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
              </section>

              <Tabs.Root defaultValue="trace" className="bg-ivory border border-border-cream rounded-xl shadow-sm">
                <div className="p-2 border-b border-border-cream">
                  <Tabs.List className="flex gap-2 flex-wrap">
                    <Tabs.Trigger value="trace" className="px-4 py-2 text-sm font-medium text-stone-gray hover:text-near-black data-[state=active]:bg-parchment data-[state=active]:text-terracotta rounded-md transition-colors">
                      实际执行链路
                    </Tabs.Trigger>
                    <Tabs.Trigger value="retrieval" className="px-4 py-2 text-sm font-medium text-stone-gray hover:text-near-black data-[state=active]:bg-parchment data-[state=active]:text-terracotta rounded-md transition-colors">
                      检索与融合
                    </Tabs.Trigger>
                    <Tabs.Trigger value="evidence" className="px-4 py-2 text-sm font-medium text-stone-gray hover:text-near-black data-[state=active]:bg-parchment data-[state=active]:text-terracotta rounded-md transition-colors">
                      证据与引用
                    </Tabs.Trigger>
                  </Tabs.List>
                </div>

                <Tabs.Content value="trace" className="p-6 space-y-8 outline-none">
                  <div className="rounded-lg border border-border-cream bg-parchment p-3 text-xs leading-relaxed text-stone-gray">
                    这里展示的是本次 QARun 实际执行链路。问题改写、检索、融合、权限过滤、生成、引用的拓扑来自 P08 当前 revision；本页覆盖项仅影响本次运行参数。
                  </div>
                  <div className="relative pl-6 border-l-2 border-border-cream space-y-8">
                    <div className="relative">
                      <div className="absolute w-4 h-4 rounded-full bg-parchment border-2 border-terracotta -left-[35px] top-1"></div>
                      <h3 className="text-sm font-bold text-near-black mb-1">1. 问题改写</h3>
                      <div className="text-xs text-stone-gray mb-2 font-mono">
                        {rewriteEnabled ? "150ms • prompt v2" : "Skipped • using original query"}
                      </div>
                      <div className="bg-parchment p-3 rounded border border-border-cream text-sm text-near-black">
                        {rewriteEnabled ? result.rewrite : query}
                      </div>
                    </div>

                    <div className="relative">
                      <div className="absolute w-4 h-4 rounded-full bg-parchment border-2 border-terracotta -left-[35px] top-1"></div>
                      <h3 className="text-sm font-bold text-near-black mb-1">2. 多路检索</h3>
                      <div className="text-xs text-stone-gray mb-2 font-mono">
                        Dense / Sparse / Graph 通道
                      </div>
                      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
                        {result.retrievalCards.map((card) => (
                          <div
                            key={card.channel}
                            className="bg-ivory p-3 rounded border border-border-cream flex flex-col gap-2"
                          >
                            <div className="flex items-center gap-2">
                              {card.channel === "Dense" && <Zap className="w-4 h-4 text-terracotta" />}
                              {card.channel === "Sparse" && <AlignLeft className="w-4 h-4 text-terracotta" />}
                              {card.channel === "Graph" && <Network className="w-4 h-4 text-terracotta" />}
                              <span className="text-xs font-medium text-near-black">{card.channel}</span>
                            </div>
                            <span className="text-xs text-stone-gray">{card.summary}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="relative">
                      <div className="absolute w-4 h-4 rounded-full bg-parchment border-2 border-terracotta -left-[35px] top-1"></div>
                      <h3 className="text-sm font-bold text-near-black mb-1">3. 融合与重排</h3>
                      <div className="text-xs text-stone-gray mb-2 font-mono">
                        RRF + reranker topN={rerankerTopN}
                      </div>
                      <div className="bg-parchment p-3 rounded border border-border-cream text-sm text-near-black">
                        召回候选经去重、融合、重排后形成最终上下文。评审重点在于“淘汰原因是否可解释”。
                      </div>
                    </div>

                    <div className="relative">
                      <div className="absolute w-4 h-4 rounded-full bg-parchment border-2 border-success-green -left-[35px] top-1"></div>
                      <h3 className="text-sm font-bold text-near-black mb-1">4. LLM 生成</h3>
                      <div className="text-xs text-stone-gray mb-2 font-mono">
                        已注入严格引用约束
                      </div>
                      <div className="text-xs text-stone-gray flex items-center gap-1">
                        <Info className="w-3 h-3" /> 回答、证据、上下文裁剪信息已汇总到同一页面。
                      </div>
                    </div>
                  </div>
                </Tabs.Content>

                <Tabs.Content value="retrieval" className="p-6 outline-none">
                  <div className="space-y-4">
                    {result.candidates.map((candidate) => (
                      <div
                        key={candidate.id}
                        className="rounded-lg border border-border-cream bg-parchment p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <Badge variant="default">{candidate.source}</Badge>
                              <span className="font-medium text-near-black">{candidate.title}</span>
                            </div>
                            <p className="mt-2 text-sm text-stone-gray">{candidate.decision}</p>
                          </div>
                          <span className="text-xs font-mono text-olive-gray">score {candidate.score}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </Tabs.Content>

                <Tabs.Content value="evidence" className="p-0 outline-none">
                  <div className="divide-y divide-border-cream">
                    {result.citations.map((citation) => (
                      <div
                        key={citation.id}
                        className="p-4 hover:bg-border-cream/20 transition-colors cursor-pointer"
                        onClick={() => handleOpenCitation(citation.type)}
                      >
                        <div className="flex gap-3">
                          <div className="mt-1 bg-terracotta text-white w-6 h-6 rounded flex items-center justify-center text-xs font-bold shrink-0">
                            [{citation.id}]
                          </div>
                          <div>
                            <div className="flex items-center gap-2 mb-1">
                              {citation.type === "document" ? (
                                <FileText className="w-3 h-3 text-stone-gray" />
                              ) : (
                                <Network className="w-3 h-3 text-stone-gray" />
                              )}
                              <span className="text-sm font-medium text-near-black">{citation.title}</span>
                            </div>
                            <p className="text-sm text-stone-gray font-serif italic mb-2">
                              {citation.snippet}
                            </p>
                            <div className="text-xs text-olive-gray font-mono">{citation.meta}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Tabs.Content>
              </Tabs.Root>
            </div>
          )}
        </div>

        <div className="w-1/4 min-w-[300px] border-l border-border-cream bg-ivory p-4 space-y-6 overflow-y-auto">
          {showResults ? (
            <>
              <h3 className="font-serif text-lg text-near-black mb-4 flex items-center gap-2">
                <Activity className="w-5 h-5 text-terracotta" /> 诊断信息
              </h3>

              <div className="space-y-4">
                <Card>
                  <CardHeader className="py-3 px-4 bg-parchment border-b border-border-cream">
                    <CardTitle className="text-sm">检索漏斗</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3">
                    <div className="flex justify-between text-xs">
                      <span className="text-stone-gray">总召回量</span>
                      <span className="font-mono text-near-black">{result.diagnostics.recalled}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-stone-gray">去重后</span>
                      <span className="font-mono text-near-black">{result.diagnostics.deduped}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-stone-gray">权限过滤</span>
                      <span className="font-mono text-error-red">{result.diagnostics.filtered}</span>
                    </div>
                    <div className="flex justify-between text-xs font-medium border-t border-border-cream pt-2">
                      <span className="text-near-black">最终上下文大小</span>
                      <span className="font-mono text-near-black">{result.diagnostics.finalContext}</span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="py-3 px-4 bg-parchment border-b border-border-cream">
                    <CardTitle className="text-sm">重排影响</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 text-xs space-y-2">
                    <p className="text-olive-gray">{result.diagnostics.rerankSummary}</p>
                    <div className="pt-2 border-t border-border-cream text-stone-gray">
                      当前覆盖模式：{overrideMode ? "本次运行覆盖参数" : "生效版本"}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center text-stone-gray text-sm text-center px-4">
              运行一次调试后，这里会展示召回漏斗、重排影响、权限裁剪与异常信息。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
