import { ReactNode, useMemo, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
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
  Activity,
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Database,
  FileCheck2,
  History,
  Layers,
  Lock,
  Network,
  PlayCircle,
  Save,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Split,
  Target,
  Wand2,
  Zap,
} from "lucide-react";
import * as Tabs from "@radix-ui/react-tabs";

interface RevisionRecord {
  id: string;
  createdBy: string;
  createdAt: string;
  note: string;
  status: "success" | "queued";
  active: boolean;
}

interface PipelineNode {
  id: string;
  label: string;
  stageId: string;
  description: string;
  locked?: boolean;
  enabled: boolean;
  icon: ReactNode;
  params: string[];
  rule: string;
}

interface PipelineStage {
  id: string;
  title: string;
  summary: string;
}

const INITIAL_REVISIONS: RevisionRecord[] = [
  {
    id: "rev_042",
    createdBy: "kb_admin",
    createdAt: "2026-04-22 18:30",
    note: "当前生产配置，Graph 权重 0.3",
    status: "success",
    active: true,
  },
  {
    id: "rev_041",
    createdBy: "asmith",
    createdAt: "2026-04-21 10:20",
    note: "上一个稳定版本",
    status: "success",
    active: false,
  },
  {
    id: "rev_040",
    createdBy: "jdoe",
    createdAt: "2026-04-20 09:00",
    note: "禁用 graph 的历史版本",
    status: "success",
    active: false,
  },
];

const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: "preprocess",
    title: "1. 输入与问题预处理",
    summary: "Input 与 Query Rewrite 固定发生在检索之前。",
  },
  {
    id: "retrieval",
    title: "2. 并行召回",
    summary: "Dense / Sparse / Graph 可开关，但至少保留一路。",
  },
  {
    id: "fusion",
    title: "3. 融合与安全过滤",
    summary: "候选融合后必须经过权限过滤，再进入最终上下文。",
  },
  {
    id: "generation",
    title: "4. 生成与引用",
    summary: "生成、证据和 Citation 绑定，引用只能来自授权 Evidence。",
  },
  {
    id: "diagnostics",
    title: "5. 输出与诊断",
    summary: "Answer、Trace、Metrics 用于调试和历史回放。",
  },
];

function NodeCard({
  node,
  isSelected,
  onSelect,
}: {
  node: PipelineNode;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-xl border p-3 text-left transition-all ${
        isSelected
          ? "border-terracotta bg-[#fff8f4] shadow-sm"
          : "border-border-cream bg-ivory hover:border-terracotta/40"
      } ${!node.enabled ? "opacity-60" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 text-terracotta">{node.icon}</span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-near-black">{node.label}</span>
              {node.locked && <Badge variant="info">Locked</Badge>}
              {!node.enabled && <Badge variant="inactive">Disabled</Badge>}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-stone-gray">{node.description}</p>
          </div>
        </div>
        <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-border-warm" />
      </div>
    </button>
  );
}

/**
 * 配置中心原型页。
 * P08 负责正式 Pipeline 编排、Revision 保存和 Active 切换；单次运行覆盖仍留在 P09。
 */
export function ConfigCenter() {
  const [activeTab, setActiveTab] = useState("designer");
  const [revisions, setRevisions] = useState(INITIAL_REVISIONS);
  const [selectedTemplate, setSelectedTemplate] = useState("Standard Hybrid (Default)");
  const [selectedNodeId, setSelectedNodeId] = useState("queryRewrite");
  const [isRevisionDrawerOpen, setIsRevisionDrawerOpen] = useState(false);
  const [pendingActivation, setPendingActivation] = useState<string | null>(null);
  const [isActivationDialogOpen, setIsActivationDialogOpen] = useState(false);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(true);
  const [queryRewriteEnabled, setQueryRewriteEnabled] = useState(true);
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const [retrievalChannels, setRetrievalChannels] = useState({
    dense: true,
    sparse: true,
    graph: true,
  });

  const activeRevision = useMemo(
    () => revisions.find((revision) => revision.active)?.id ?? "rev_042",
    [revisions],
  );

  const pipelineNodes = useMemo<PipelineNode[]>(
    () => [
      {
        id: "input",
        label: "Input",
        stageId: "preprocess",
        description: "接收用户 query、知识库上下文与当前 revision。",
        locked: true,
        enabled: true,
        icon: <PlayCircle className="h-4 w-4" />,
        params: ["kbId", "query", "activeRevision"],
        rule: "系统入口节点，不允许删除或绕过。",
      },
      {
        id: "queryRewrite",
        label: "Query Rewrite",
        stageId: "preprocess",
        description: "对原始问题做改写、扩展和保留原问策略。",
        enabled: queryRewriteEnabled,
        icon: <Wand2 className="h-4 w-4" />,
        params: ["Prompt v2", "保留原始问题", "输出 rewrittenQuery"],
        rule: "如果启用，必须位于任何检索节点之前。",
      },
      {
        id: "dense",
        label: "Dense Retrieval",
        stageId: "retrieval",
        description: "向量语义召回，按知识库、版本、权限条件过滤。",
        enabled: retrievalChannels.dense,
        icon: <Zap className="h-4 w-4" />,
        params: ["topK=20", "minScore=0.75", "weight=0.4"],
        rule: "只能在召回阶段运行，输出必须回表 Chunk。",
      },
      {
        id: "sparse",
        label: "Sparse Retrieval",
        stageId: "retrieval",
        description: "BM25/关键词召回，补足实体名、编号和术语命中。",
        enabled: retrievalChannels.sparse,
        icon: <Search className="h-4 w-4" />,
        params: ["topK=15", "minScore=12.5", "weight=0.3"],
        rule: "只能在召回阶段运行，结果进入 Fusion 前需统一候选结构。",
      },
      {
        id: "graph",
        label: "Graph Retrieval",
        stageId: "retrieval",
        description: "基于 Neo4j 做实体和关系扩展，增强根因链路。",
        enabled: retrievalChannels.graph,
        icon: <Network className="h-4 w-4" />,
        params: ["hopDepth=2", "maxNodes=50", "weight=0.3"],
        rule: "图结果必须回落到授权 Chunk / Evidence 后才能用于生成。",
      },
      {
        id: "fusion",
        label: "Fusion",
        stageId: "fusion",
        description: "合并多路召回结果，执行去重、权重融合与候选截断。",
        locked: true,
        enabled: true,
        icon: <Split className="h-4 w-4" />,
        params: ["RRF", "dedup by chunkId", "candidateLimit=40"],
        rule: "只能接收 Retrieval 阶段输出，不允许直接接收用户输入。",
      },
      {
        id: "permissionFilter",
        label: "Permission Filter",
        stageId: "fusion",
        description: "在最终上下文进入 LLM 前执行权限裁剪。",
        locked: true,
        enabled: true,
        icon: <ShieldCheck className="h-4 w-4" />,
        params: ["kb scope", "doc status", "security level", "deny first"],
        rule: "安全边界节点，不允许删除、禁用或移动到生成之后。",
      },
      {
        id: "rerank",
        label: "Rerank",
        stageId: "fusion",
        description: "对融合候选做精排，并记录淘汰原因。",
        enabled: rerankEnabled,
        icon: <Target className="h-4 w-4" />,
        params: ["bge-reranker-v2-m3", "topN=5", "保留淘汰解释"],
        rule: "只能处理已融合且已标准化的候选列表。",
      },
      {
        id: "generation",
        label: "LLM Generation",
        stageId: "generation",
        description: "使用授权上下文生成回答，注入引用约束。",
        locked: true,
        enabled: true,
        icon: <BrainCircuit className="h-4 w-4" />,
        params: ["model=claude-3-5-sonnet", "temperature=0.1", "strict citation"],
        rule: "只能读取权限过滤后的上下文。",
      },
      {
        id: "citation",
        label: "Citation Builder",
        stageId: "generation",
        description: "把答案片段绑定到 Evidence 与 Chunk。",
        locked: true,
        enabled: true,
        icon: <FileCheck2 className="h-4 w-4" />,
        params: ["minEvidence=1", "click to document", "click to graph"],
        rule: "Citation 必须来自授权 Evidence，不能引用被裁剪内容。",
      },
      {
        id: "output",
        label: "Answer / Trace / Metrics",
        stageId: "diagnostics",
        description: "输出最终答案、Evidence、运行 Trace 与诊断指标。",
        locked: true,
        enabled: true,
        icon: <Activity className="h-4 w-4" />,
        params: ["answer", "evidence", "trace", "metrics"],
        rule: "诊断输出必须绑定本次 ConfigRevision 和 QARun。",
      },
    ],
    [queryRewriteEnabled, rerankEnabled, retrievalChannels],
  );

  const selectedNode = useMemo(
    () => pipelineNodes.find((node) => node.id === selectedNodeId) ?? pipelineNodes[0],
    [pipelineNodes, selectedNodeId],
  );

  const hasRetrievalChannel =
    retrievalChannels.dense || retrievalChannels.sparse || retrievalChannels.graph;

  const validationRules = [
    {
      label: "Query Rewrite 如果启用，必须位于 Retrieval 前。",
      valid: true,
    },
    {
      label: "Dense、Sparse、Graph 至少启用一路。",
      valid: hasRetrievalChannel,
    },
    {
      label: "Fusion 只能接收检索阶段结果。",
      valid: true,
    },
    {
      label: "Permission Filter 必须存在，且必须位于生成之前。",
      valid: true,
    },
    {
      label: "Graph Retrieval 输出必须回落到 Chunk / Evidence。",
      valid: true,
    },
    {
      label: "Citation 必须来自授权 Evidence。",
      valid: true,
    },
  ];

  const isPipelineValid = validationRules.every((rule) => rule.valid);

  function handleTemplateSelect(templateName: string) {
    setSelectedTemplate(templateName);
    setHasUnsavedChanges(true);
    setFeedback({
      variant: "info",
      title: "已套用 Pipeline 模板",
      message: `${templateName} 已加载到受约束画布。模板只能改变节点参数和启用状态，不能绕过系统阶段。`,
    });
  }

  /**
   * 原型阶段这里不要求真实保存配置字段，
   * 但必须明确“保存即生成新 revision”的产品语义。
   */
  function handleSaveRevision() {
    if (!isPipelineValid) {
      setFeedback({
        variant: "error",
        title: "Pipeline 校验未通过",
        message: "请至少启用一路检索通道，并修复右侧 Validation 中的错误后再保存。",
      });
      return;
    }

    const nextId = `rev_0${43 + revisions.length - INITIAL_REVISIONS.length}`;
    const nextRevision: RevisionRecord = {
      id: nextId,
      createdBy: "current_user",
      createdAt: "刚刚",
      note: `基于 ${selectedTemplate} 保存的新 Pipeline revision`,
      status: "queued",
      active: false,
    };

    setRevisions((current) => [nextRevision, ...current]);
    setHasUnsavedChanges(false);
    setFeedback({
      variant: "success",
      title: "已生成新 Revision",
      message: `${nextId} 已创建但尚未生效。保存的是受约束 pipelineDefinition，激活仍需二次确认。`,
    });
    setIsRevisionDrawerOpen(true);
  }

  function requestActivate(revisionId: string) {
    setPendingActivation(revisionId);
    setIsActivationDialogOpen(true);
  }

  function handleConfirmActivation() {
    if (!pendingActivation) return;

    setRevisions((current) =>
      current.map((revision) => ({
        ...revision,
        active: revision.id === pendingActivation,
        status: revision.id === pendingActivation ? "success" : revision.status,
      })),
    );
    setFeedback({
      variant: "warning",
      title: "Active Revision 已切换",
      message: `后续 QA 调试将基于 ${pendingActivation} 的 Pipeline 编排执行。`,
    });
    setIsActivationDialogOpen(false);
    setPendingActivation(null);
  }

  function handleNodeToggle(nodeId: string, enabled: boolean) {
    const node = pipelineNodes.find((item) => item.id === nodeId);
    if (!node || node.locked) {
      setFeedback({
        variant: "warning",
        title: "系统锁定节点不可修改",
        message: "Input、Permission Filter、Citation、Trace 等节点属于系统护栏，不能删除、禁用或移动。",
      });
      return;
    }

    if (nodeId === "queryRewrite") setQueryRewriteEnabled(enabled);
    if (nodeId === "rerank") setRerankEnabled(enabled);
    if (nodeId === "dense") {
      setRetrievalChannels((current) => ({ ...current, dense: enabled }));
    }
    if (nodeId === "sparse") {
      setRetrievalChannels((current) => ({ ...current, sparse: enabled }));
    }
    if (nodeId === "graph") {
      setRetrievalChannels((current) => ({ ...current, graph: enabled }));
    }
    setHasUnsavedChanges(true);
  }

  function handleIllegalOperation(operation: string) {
    setFeedback({
      variant: "warning",
      title: "该操作被编排规则阻止",
      message: operation,
    });
  }

  return (
    <div className="flex h-full flex-col space-y-6 overflow-hidden p-8">
      <PageHeader
        title="Configuration Center"
        description="以受约束 Pipeline Designer 定义知识库默认检索链路、模型策略与 revision 生效关系。"
        actions={
          <>
            <Button variant="outline" onClick={() => setIsRevisionDrawerOpen(true)}>
              <History className="mr-2 h-4 w-4" /> 查看 Revisions
            </Button>
            <Button variant="outline" onClick={() => handleIllegalOperation("验证会带着当前草稿跳转到 P09，P09 只做单次运行覆盖，不修改正式拓扑。")}>
              <PlayCircle className="mr-2 h-4 w-4" /> 验证此 Pipeline
            </Button>
            <Button variant="primary" disabled={!isPipelineValid} onClick={handleSaveRevision}>
              <Save className="mr-2 h-4 w-4" /> 保存为新 Revision
            </Button>
          </>
        }
        contextLabels={
          <>
            <Badge variant="success">Active Revision: {activeRevision}</Badge>
            <Badge variant={isPipelineValid ? "success" : "error"}>
              {isPipelineValid ? "Valid Pipeline" : "Invalid Pipeline"}
            </Badge>
            {hasUnsavedChanges && <Badge variant="warning">Unsaved Changes</Badge>}
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

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-6 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
        <aside className="space-y-4 overflow-y-auto">
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="flex items-center gap-2 text-sm" serif={false}>
                <Layers className="h-4 w-4 text-terracotta" /> Pipeline Templates
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-4">
              {[
                "Standard Hybrid (Default)",
                "High Recall Mode",
                "Strict Citation Mode",
                "Graph-heavy Mode",
              ].map((template) => (
                <button
                  key={template}
                  type="button"
                  className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                    selectedTemplate === template
                      ? "border-terracotta/40 bg-parchment text-terracotta"
                      : "border-border-cream bg-ivory text-near-black hover:bg-parchment"
                  }`}
                  onClick={() => handleTemplateSelect(template)}
                >
                  {template}
                </button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="py-3">
              <CardTitle className="flex items-center gap-2 text-sm" serif={false}>
                <Database className="h-4 w-4 text-terracotta" /> Node Library
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-4 text-xs">
              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="mb-2 font-medium text-near-black">可配置节点</p>
                <p className="text-stone-gray">Query Rewrite、Dense、Sparse、Graph、Rerank 可调参数或开关。</p>
              </div>
              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="mb-2 flex items-center gap-2 font-medium text-near-black">
                  <Lock className="h-3 w-3" /> 系统锁定节点
                </p>
                <p className="text-stone-gray">Input、Fusion、Permission Filter、Citation、Trace 不允许删除。</p>
              </div>
              <div className="rounded-lg border border-dashed border-border-warm bg-ivory p-3">
                <p className="mb-2 font-medium text-near-black">未来扩展</p>
                <p className="text-stone-gray">HTTP Tool、自定义 Python 节点暂不进入 V1，避免工作流失控。</p>
              </div>
            </CardContent>
          </Card>
        </aside>

        <Card className="flex min-h-0 flex-col overflow-hidden">
          <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex min-h-0 flex-1 flex-col">
            <CardHeader className="border-b border-border-cream pb-0">
              <Tabs.List className="flex gap-6">
                <Tabs.Trigger value="designer" className="pb-3 text-sm font-medium text-stone-gray transition-all hover:text-near-black data-[state=active]:border-b-2 data-[state=active]:border-terracotta data-[state=active]:text-terracotta">
                  Constrained Pipeline Designer
                </Tabs.Trigger>
                <Tabs.Trigger value="diff" className="pb-3 text-sm font-medium text-stone-gray transition-all hover:text-near-black data-[state=active]:border-b-2 data-[state=active]:border-terracotta data-[state=active]:text-terracotta">
                  Diff (vs {activeRevision})
                </Tabs.Trigger>
              </Tabs.List>
            </CardHeader>

            <CardContent className="min-h-0 flex-1 overflow-auto p-5">
              <Tabs.Content value="designer" className="outline-none">
                <div className="mb-4 rounded-xl border border-border-cream bg-parchment p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="font-serif text-lg text-near-black">受约束检索工作流</h2>
                      <p className="mt-1 text-sm text-stone-gray">
                        视觉上采用工作流画布，但连线和阶段由系统生成，用户只能在合法节点内配置。
                      </p>
                    </div>
                    <Badge variant="info">No free-form DAG</Badge>
                  </div>
                </div>

                <div className="space-y-4">
                  {PIPELINE_STAGES.map((stage, index) => {
                    const stageNodes = pipelineNodes.filter((node) => node.stageId === stage.id);

                    return (
                      <section key={stage.id} className="relative">
                        {index < PIPELINE_STAGES.length - 1 && (
                          <div className="absolute left-6 top-[calc(100%-4px)] h-4 w-px bg-border-warm" />
                        )}
                        <div className="rounded-2xl border border-border-cream bg-[#fffdfa] p-4">
                          <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                            <div className="flex gap-3">
                              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-parchment text-sm font-bold text-terracotta">
                                {index + 1}
                              </div>
                              <div>
                                <h3 className="font-medium text-near-black">{stage.title}</h3>
                                <p className="text-xs text-stone-gray">{stage.summary}</p>
                              </div>
                            </div>
                            <Badge variant="default">Stage locked</Badge>
                          </div>
                          <div className="grid grid-cols-1 gap-3 2xl:grid-cols-3">
                            {stageNodes.map((node) => (
                              <NodeCard
                                key={node.id}
                                node={node}
                                isSelected={selectedNode.id === node.id}
                                onSelect={() => setSelectedNodeId(node.id)}
                              />
                            ))}
                          </div>
                        </div>
                      </section>
                    );
                  })}
                </div>
              </Tabs.Content>

              <Tabs.Content value="diff" className="outline-none">
                <div className="rounded-lg border border-border-cream bg-[#fffdfa] p-4 font-mono text-sm space-y-1">
                  <div className="text-stone-gray">@@ pipelineDefinition.constraintsVersion @@</div>
                  <div className="pl-4 text-near-black">"mode": "constrained-stage-pipeline"</div>
                  <div className="pl-4 text-near-black">"stages": ["preprocess", "retrieval", "fusion", "generation", "diagnostics"]</div>
                  <div className="bg-success-green/10 pl-4 text-success-green">+ "queryRewrite.before": "retrieval"</div>
                  <div className="bg-success-green/10 pl-4 text-success-green">+ "permissionFilter.locked": true</div>
                  <div className="bg-success-green/10 pl-4 text-success-green">+ "graph.mustResolveTo": "authorizedChunk"</div>
                  <div className="bg-error-red/10 pl-4 text-error-red line-through">- "freeFormEdges": true</div>
                </div>
              </Tabs.Content>
            </CardContent>
          </Tabs.Root>
        </Card>

        <aside className="space-y-4 overflow-y-auto">
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="flex items-center gap-2 text-sm" serif={false}>
                <SlidersHorizontal className="h-4 w-4 text-terracotta" /> Node Inspector
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 p-4">
              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="font-medium text-near-black">{selectedNode.label}</span>
                  {selectedNode.locked && <Badge variant="info">Locked</Badge>}
                  <Badge variant={selectedNode.enabled ? "success" : "inactive"}>
                    {selectedNode.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
                <p className="text-sm leading-relaxed text-stone-gray">{selectedNode.description}</p>
              </div>

              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="mb-2 text-xs font-medium text-near-black">约束规则</p>
                <p className="text-xs leading-relaxed text-stone-gray">{selectedNode.rule}</p>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-medium text-stone-gray">核心参数</p>
                {selectedNode.params.map((param) => (
                  <div key={param} className="rounded-md border border-border-cream bg-parchment px-3 py-2 text-xs text-near-black">
                    {param}
                  </div>
                ))}
              </div>

              <div className="space-y-2">
                <label className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment p-3 text-sm">
                  <span className="text-near-black">启用节点</span>
                  <input
                    type="checkbox"
                    className="rounded text-terracotta"
                    checked={selectedNode.enabled}
                    disabled={selectedNode.locked}
                    onChange={(event) => handleNodeToggle(selectedNode.id, event.target.checked)}
                  />
                </label>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-warning-amber"
                  onClick={() =>
                    handleIllegalOperation(
                      selectedNode.locked
                        ? `${selectedNode.label} 是系统锁定节点，不允许删除。`
                        : "原型阶段不提供自由删除节点，只允许通过启用状态和模板控制编排。",
                    )
                  }
                >
                  <Lock className="mr-2 h-4 w-4" /> 尝试删除节点
                </Button>
              </div>

              <div className="rounded-lg border border-border-cream bg-[#fffdfa] p-3">
                <p className="mb-2 text-xs font-medium text-near-black">运行预览</p>
                <p className="text-xs leading-relaxed text-stone-gray">
                  该节点会在 P09 的 Executed Pipeline Trace 中以实际运行结果展示；P09 只允许临时覆盖参数，不修改正式拓扑。
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="py-3">
              <CardTitle className="flex items-center gap-2 text-sm" serif={false}>
                <AlertTriangle className="h-4 w-4 text-terracotta" /> Validation
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-4">
              {validationRules.map((rule) => (
                <div key={rule.label} className="flex items-start gap-2 rounded-lg border border-border-cream bg-parchment p-2">
                  {rule.valid ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success-green" />
                  ) : (
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-error-red" />
                  )}
                  <span className={`text-xs leading-relaxed ${rule.valid ? "text-stone-gray" : "text-error-red"}`}>
                    {rule.label}
                  </span>
                </div>
              ))}
              <div className="pt-2 text-xs text-stone-gray">
                前端只提供交互护栏；后端保存和执行时仍必须二次校验 pipelineDefinition。
              </div>
            </CardContent>
          </Card>
        </aside>
      </div>

      <Drawer
        isOpen={isRevisionDrawerOpen}
        onClose={() => setIsRevisionDrawerOpen(false)}
        title="Revision History"
        width="640px"
      >
        <DrawerSection title="Revisions">
          <div className="space-y-3">
            {revisions.map((revision) => (
              <div
                key={revision.id}
                className="rounded-xl border border-border-cream bg-parchment p-4 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-near-black">{revision.id}</p>
                      {revision.active && <Badge variant="success">Active</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-stone-gray">
                      {revision.createdBy} · {revision.createdAt}
                    </p>
                  </div>
                  <StatusBadge status={revision.status} />
                </div>
                <p className="text-sm text-stone-gray">{revision.note}</p>
                <div className="flex justify-end gap-2">
                  {!revision.active && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-terracotta"
                      onClick={() => requestActivate(revision.id)}
                    >
                      设为 Active
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </DrawerSection>
      </Drawer>

      <Dialog open={isActivationDialogOpen} onOpenChange={setIsActivationDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认切换 Active Revision</DialogTitle>
            <DialogDescription>
              配置切换后会影响后续 QA 调试与历史比对结果。目标 revision 内保存的是受约束 pipelineDefinition。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-border-cream bg-parchment p-4 text-sm text-near-black">
            当前生效：{activeRevision}
            <br />
            目标版本：{pendingActivation}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsActivationDialogOpen(false)}>
              取消
            </Button>
            <Button variant="primary" onClick={handleConfirmActivation}>
              确认切换
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
