import { ReactNode, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
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
import { toRevisionRecord } from "../adapters/configAdapter";
import {
  activateConfigRevision,
  fetchConfigRevisions,
  saveConfigRevision,
  validatePipeline,
} from "../services/configService";
import type {
  PipelineDefinition,
  PipelineValidationResultDTO,
  RevisionRecordViewModel,
} from "../types/config";

interface PipelineNode {
  id: string;
  type: string;
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

const PIPELINE_STAGES: PipelineStage[] = [
  {
    id: "preprocess",
    title: "1. 输入与问题预处理",
    summary: "输入与 Query Rewrite 固定发生在检索之前。",
  },
  {
    id: "retrieval",
    title: "2. 并行召回",
    summary: "Dense / Sparse / Graph 通道可开关，但至少保留一路。",
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
              {node.locked && <Badge variant="info">已锁定</Badge>}
              {!node.enabled && <Badge variant="inactive">已禁用</Badge>}
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
  const { kbId = "" } = useParams();
  const [activeTab, setActiveTab] = useState("designer");
  const [revisions, setRevisions] = useState<RevisionRecordViewModel[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState("标准混合（默认）");
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
  const [loadingRevisions, setLoadingRevisions] = useState(false);
  const [savingRevision, setSavingRevision] = useState(false);
  const [activatingRevision, setActivatingRevision] = useState(false);
  const [serverValidation, setServerValidation] = useState<PipelineValidationResultDTO | null>(null);
  const [queryRewriteEnabled, setQueryRewriteEnabled] = useState(true);
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const [retrievalChannels, setRetrievalChannels] = useState({
    dense: true,
    sparse: true,
    graph: true,
  });

  const activeRevision = useMemo(
    () => revisions.find((revision) => revision.active)?.revisionNo ?? "暂无生效版本",
    [revisions],
  );

  async function loadRevisions() {
    if (!kbId) return;
    setLoadingRevisions(true);
    try {
      const page = await fetchConfigRevisions(kbId);
      setRevisions(page.items.map(toRevisionRecord));
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "版本历史加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务和数据库连接。",
      });
    } finally {
      setLoadingRevisions(false);
    }
  }

  useEffect(() => {
    void loadRevisions();
  }, [kbId]);

  const pipelineNodes = useMemo<PipelineNode[]>(
    () => [
      {
        id: "input",
        type: "input",
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
        type: "queryRewrite",
        label: "问题改写",
        stageId: "preprocess",
        description: "对原始问题做改写、扩展和保留原问策略。",
        enabled: queryRewriteEnabled,
        icon: <Wand2 className="h-4 w-4" />,
        params: ["Prompt v2", "保留原始问题", "输出 rewrittenQuery"],
        rule: "如果启用，必须位于任何检索节点之前。",
      },
      {
        id: "dense",
        type: "denseRetrieval",
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
        type: "sparseRetrieval",
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
        type: "graphRetrieval",
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
        type: "fusion",
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
        type: "permissionFilter",
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
        type: "rerank",
        label: "Rerank",
        stageId: "fusion",
        description: "对融合候选做精排，并记录淘汰原因。",
        enabled: rerankEnabled,
        icon: <Target className="h-4 w-4" />,
        params: ["bge-reranker-v2-m3", "topN=5", "保留淘汰解释"],
        rule: "只能处理已融合且已标准化的候选列表。",
      },
      {
        id: "contextBuilder",
        type: "contextBuilder",
        label: "Context Builder",
        stageId: "generation",
        description: "将权限过滤后的 Evidence 组织成进入 LLM 的上下文。",
        locked: true,
        enabled: true,
        icon: <Layers className="h-4 w-4" />,
        params: ["maxContextTokens=6000", "evidenceOnly", "preserve citation anchors"],
        rule: "只能读取权限过滤后的候选和 Evidence。",
      },
      {
        id: "generation",
        type: "generation",
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
        type: "citation",
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
        type: "output",
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
      label: "问题改写如果启用，必须位于检索前。",
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

  function buildPipelineDefinition(): PipelineDefinition {
    return {
      version: "1.0",
      constraintsVersion: "1.0",
      mode: "constrained-stage-pipeline",
      stages: PIPELINE_STAGES.map((stage) => stage.id),
      templateId: selectedTemplate,
      nodes: pipelineNodes.map((node) => ({
        id: node.id,
        type: node.type,
        stage: node.stageId,
        enabled: node.enabled,
        locked: Boolean(node.locked),
        params: Object.fromEntries(node.params.map((param, index) => [`param${index + 1}`, param])),
      })),
    };
  }

  async function handleValidatePipeline() {
    if (!kbId) return;
    try {
      const result = await validatePipeline(kbId, buildPipelineDefinition());
      setServerValidation(result);
      setFeedback({
        variant: result.valid ? "success" : "error",
        title: result.valid ? "后端校验通过" : "后端校验未通过",
        message: result.valid
          ? "当前 pipelineDefinition 已通过服务端二次校验。"
          : result.errors.map((error) => error.message).join("；"),
      });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "Pipeline 校验请求失败",
        message: error instanceof Error ? error.message : "请检查后端服务状态。",
      });
    }
  }

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
  async function handleSaveRevision() {
    if (!isPipelineValid) {
      setFeedback({
        variant: "error",
        title: "Pipeline 校验未通过",
        message: "请至少启用一路检索通道，并修复右侧 Validation 中的错误后再保存。",
      });
      return;
    }

    setSavingRevision(true);
    try {
      const response = await saveConfigRevision(
        kbId,
        buildPipelineDefinition(),
        `基于 ${selectedTemplate} 保存的新 Pipeline revision`,
      );
      setHasUnsavedChanges(false);
      setFeedback({
        variant: "success",
        title: "已生成新 Revision",
        message: `rev_${String(response.revisionNo).padStart(3, "0")} 已创建但尚未生效。保存的是受约束 pipelineDefinition，激活仍需二次确认。`,
      });
      setIsRevisionDrawerOpen(true);
      await loadRevisions();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "保存 Revision 失败",
        message: error instanceof Error ? error.message : "请根据校验结果修复后重试。",
      });
    } finally {
      setSavingRevision(false);
    }
  }

  function requestActivate(revisionId: string) {
    setPendingActivation(revisionId);
    setIsActivationDialogOpen(true);
  }

  async function handleConfirmActivation() {
    if (!pendingActivation) return;

    setActivatingRevision(true);
    try {
      await activateConfigRevision(kbId, pendingActivation);
      await loadRevisions();
      setFeedback({
        variant: "warning",
        title: "生效版本已切换",
        message: "后续 QA 调试将基于新的 active ConfigRevision 执行。",
      });
      setIsActivationDialogOpen(false);
      setPendingActivation(null);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "激活 Revision 失败",
        message: error instanceof Error ? error.message : "请确认目标版本仍可激活。",
      });
    } finally {
      setActivatingRevision(false);
    }
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
        title="配置中心"
        description="以受约束 Pipeline Designer 定义知识库默认检索链路、模型策略与 revision 生效关系。"
        actions={
          <>
            <Button variant="outline" onClick={() => setIsRevisionDrawerOpen(true)}>
              <History className="mr-2 h-4 w-4" /> 查看版本历史
            </Button>
            <Button variant="outline" onClick={() => void handleValidatePipeline()}>
              <PlayCircle className="mr-2 h-4 w-4" /> 后端校验
            </Button>
            <Button
              variant="primary"
              disabled={!isPipelineValid || savingRevision}
              onClick={() => void handleSaveRevision()}
            >
              <Save className="mr-2 h-4 w-4" /> {savingRevision ? "保存中..." : "保存为新版本"}
            </Button>
          </>
        }
        contextLabels={
          <>
            <Badge variant="success">生效版本：{activeRevision}</Badge>
            <Badge variant={isPipelineValid ? "success" : "error"}>
              {isPipelineValid ? "Pipeline 合法" : "Pipeline 非法"}
            </Badge>
            {hasUnsavedChanges && <Badge variant="warning">有未保存修改</Badge>}
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
                <Layers className="h-4 w-4 text-terracotta" /> Pipeline 模板
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 p-4">
              {[
                "标准混合（默认）",
                "高召回模式",
                "严格引用模式",
                "图谱增强模式",
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
                <Database className="h-4 w-4 text-terracotta" /> 节点库
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 p-4 text-xs">
              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="mb-2 font-medium text-near-black">可配置节点</p>
                <p className="text-stone-gray">问题改写、Dense、Sparse、Graph、Rerank 支持参数调整或开关控制。</p>
              </div>
              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="mb-2 flex items-center gap-2 font-medium text-near-black">
                  <Lock className="h-3 w-3" /> 系统锁定节点
                </p>
                <p className="text-stone-gray">输入、融合、权限过滤、引用、Trace 不允许删除。</p>
              </div>
              <div className="rounded-lg border border-dashed border-border-warm bg-ivory p-3">
                <p className="mb-2 font-medium text-near-black">未来扩展</p>
                <p className="text-stone-gray">HTTP 工具、自定义 Python 节点暂不进入 V1，避免工作流失控。</p>
              </div>
            </CardContent>
          </Card>
        </aside>

        <Card className="flex min-h-0 flex-col overflow-hidden">
          <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex min-h-0 flex-1 flex-col">
            <CardHeader className="border-b border-border-cream pb-0">
              <Tabs.List className="flex gap-6">
                <Tabs.Trigger value="designer" className="pb-3 text-sm font-medium text-stone-gray transition-all hover:text-near-black data-[state=active]:border-b-2 data-[state=active]:border-terracotta data-[state=active]:text-terracotta">
                  受约束 Pipeline 设计器
                </Tabs.Trigger>
                <Tabs.Trigger value="diff" className="pb-3 text-sm font-medium text-stone-gray transition-all hover:text-near-black data-[state=active]:border-b-2 data-[state=active]:border-terracotta data-[state=active]:text-terracotta">
                  差异对比（相对 {activeRevision}）
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
                    <Badge variant="info">不支持自由 DAG</Badge>
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
                            <Badge variant="default">阶段已锁定</Badge>
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
                <SlidersHorizontal className="h-4 w-4 text-terracotta" /> 节点检查器
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 p-4">
              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="font-medium text-near-black">{selectedNode.label}</span>
                  {selectedNode.locked && <Badge variant="info">已锁定</Badge>}
                  <Badge variant={selectedNode.enabled ? "success" : "inactive"}>
                    {selectedNode.enabled ? "已启用" : "已禁用"}
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
                <AlertTriangle className="h-4 w-4 text-terracotta" /> 校验结果
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
              {serverValidation && (
                <div className="rounded-lg border border-border-cream bg-[#fffdfa] p-3 text-xs">
                  <p className="mb-2 font-medium text-near-black">
                    后端校验：{serverValidation.valid ? "通过" : "未通过"}
                  </p>
                  {(serverValidation.errors.length > 0
                    ? serverValidation.errors
                    : serverValidation.warnings
                  ).map((item) => (
                    <p key={`${item.code}-${item.field}`} className="leading-relaxed text-stone-gray">
                      {item.code}：{item.message}
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>

      <Drawer
        isOpen={isRevisionDrawerOpen}
        onClose={() => setIsRevisionDrawerOpen(false)}
        title="版本历史"
        width="640px"
      >
        <DrawerSection title="版本列表">
          <div className="space-y-3">
            {loadingRevisions && (
              <div className="rounded-xl border border-border-cream bg-parchment p-4 text-sm text-stone-gray">
                正在加载真实 Revision 列表...
              </div>
            )}
            {!loadingRevisions && revisions.length === 0 && (
              <div className="rounded-xl border border-dashed border-border-warm bg-parchment p-4 text-sm text-stone-gray">
                暂无配置版本。保存当前 Pipeline 后会生成第一个 saved Revision。
              </div>
            )}
            {revisions.map((revision) => (
              <div
                key={revision.id}
                className="rounded-xl border border-border-cream bg-parchment p-4 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-near-black">{revision.id}</p>
                      {revision.active && <Badge variant="success">当前生效</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-stone-gray">
                      {revision.revisionNo} · {revision.createdBy} · {revision.createdAt}
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
                      设为生效版本
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
            <DialogTitle>确认切换生效版本</DialogTitle>
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
            <Button variant="primary" disabled={activatingRevision} onClick={() => void handleConfirmActivation()}>
              {activatingRevision ? "切换中..." : "确认切换"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
