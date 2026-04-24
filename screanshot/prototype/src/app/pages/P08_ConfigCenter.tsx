import { useMemo, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
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
  Save,
  History,
  Code2,
  AlertTriangle,
  Layers,
  Target,
  Wand2,
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

/**
 * 配置中心原型页。
 * 这里优先补“保存新 revision”“查看 revision 历史”“切换 active revision”三种评审必须看见的交互。
 */
export function ConfigCenter() {
  const [activeTab, setActiveTab] = useState("editor");
  const [revisions, setRevisions] = useState(INITIAL_REVISIONS);
  const [selectedTemplate, setSelectedTemplate] = useState("Standard Hybrid (Default)");
  const [isRevisionDrawerOpen, setIsRevisionDrawerOpen] = useState(false);
  const [pendingActivation, setPendingActivation] = useState<string | null>(null);
  const [isActivationDialogOpen, setIsActivationDialogOpen] = useState(false);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning";
    title: string;
    message: string;
  } | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(true);

  const activeRevision = useMemo(
    () => revisions.find((revision) => revision.active)?.id ?? "rev_042",
    [revisions],
  );

  function handleTemplateSelect(templateName: string) {
    setSelectedTemplate(templateName);
    setHasUnsavedChanges(true);
  }

  /**
   * 原型阶段这里不要求真实保存配置字段，
   * 但必须明确“保存即生成新 revision”的产品语义。
   */
  function handleSaveRevision() {
    const nextId = `rev_0${43 + revisions.length - INITIAL_REVISIONS.length}`;
    const nextRevision: RevisionRecord = {
      id: nextId,
      createdBy: "current_user",
      createdAt: "刚刚",
      note: `基于 ${selectedTemplate} 保存的新草稿 revision`,
      status: "queued",
      active: false,
    };

    setRevisions((current) => [nextRevision, ...current]);
    setHasUnsavedChanges(false);
    setFeedback({
      variant: "success",
      title: "已生成新 Revision",
      message: `${nextId} 已创建但尚未生效。原型阶段重点是把“保存”和“激活”明确区分开。`,
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
      message: `后续 QA 调试将基于 ${pendingActivation} 执行。`,
    });
    setIsActivationDialogOpen(false);
    setPendingActivation(null);
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="Configuration Center"
        description="定义知识库默认管线、模型、检索策略与 revision 生效关系。"
        actions={
          <>
            <Button variant="outline" onClick={() => setIsRevisionDrawerOpen(true)}>
              <History className="w-4 h-4 mr-2" /> 查看 Revisions
            </Button>
            <Button variant="primary" onClick={handleSaveRevision}>
              <Save className="w-4 h-4 mr-2" /> 保存为新 Revision
            </Button>
          </>
        }
        contextLabels={
          <>
            <Badge variant="success">Active Revision: {activeRevision}</Badge>
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

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 flex-1 min-h-0">
        <div className="lg:col-span-1 space-y-4">
          <div className="p-4 bg-ivory border border-border-cream rounded-xl">
            <h3 className="font-medium mb-3 text-sm text-stone-gray flex items-center">
              <Layers className="w-4 h-4 mr-2" /> Templates
            </h3>
            <ul className="space-y-2 text-sm">
              {[
                "Standard Hybrid (Default)",
                "High Recall Mode",
                "Strict Citation Mode",
                "Graph-heavy Mode",
              ].map((template) => (
                <li
                  key={template}
                  className={`p-2 rounded cursor-pointer transition-colors ${
                    selectedTemplate === template
                      ? "bg-parchment border border-terracotta/30 text-terracotta font-medium"
                      : "hover:bg-border-cream/50 text-near-black"
                  }`}
                  onClick={() => handleTemplateSelect(template)}
                >
                  {template}
                </li>
              ))}
            </ul>
          </div>

          <div className="p-4 bg-ivory border border-border-cream rounded-xl">
            <h3 className="font-medium mb-3 text-sm text-stone-gray flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2" /> Validation
            </h3>
            <p className="text-xs text-success-green flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-success-green inline-block"></span>
              No conflicts detected.
            </p>
            <p className="text-xs text-stone-gray mt-2 leading-relaxed">
              原型阶段只需要把关键校验原则露出来，字段级校验和错误码可留到详细设计说明书。
            </p>
          </div>
        </div>

        <Card className="lg:col-span-3 flex flex-col h-full overflow-hidden">
          <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
            <CardHeader className="border-b border-border-cream pb-0">
              <Tabs.List className="flex gap-6">
                <Tabs.Trigger value="editor" className="pb-3 text-sm font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all text-stone-gray">
                  Pipeline Editor
                </Tabs.Trigger>
                <Tabs.Trigger value="diff" className="pb-3 text-sm font-medium hover:text-near-black data-[state=active]:text-terracotta data-[state=active]:border-b-2 data-[state=active]:border-terracotta transition-all text-stone-gray">
                  Diff (vs {activeRevision})
                </Tabs.Trigger>
              </Tabs.List>
            </CardHeader>

            <CardContent className="flex-1 overflow-auto p-6 space-y-8">
              <Tabs.Content value="editor" className="space-y-8 outline-none">
                <section>
                  <h3 className="font-serif text-lg text-near-black flex items-center gap-2 mb-4">
                    <Wand2 className="w-5 h-5 text-terracotta" /> Query Pre-processing
                  </h3>
                  <div className="grid grid-cols-2 gap-4 bg-parchment p-4 rounded-lg border border-border-cream">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-near-black">Query Rewrite</label>
                      <select
                        className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm"
                        onChange={() => setHasUnsavedChanges(true)}
                      >
                        <option>Enabled (LLM Prompt v2)</option>
                        <option>Disabled</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-near-black">Retain Original Query</label>
                      <select
                        className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm"
                        onChange={() => setHasUnsavedChanges(true)}
                      >
                        <option>Yes, append to rewritten</option>
                        <option>No, replace entirely</option>
                      </select>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="font-serif text-lg text-near-black flex items-center gap-2 mb-4">
                    <Target className="w-5 h-5 text-terracotta" /> Retrieval & Fusion
                  </h3>
                  <div className="bg-parchment p-4 rounded-lg border border-border-cream space-y-6">
                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                      <div className="p-3 border border-terracotta/30 bg-ivory rounded shadow-sm relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-1 h-full bg-terracotta"></div>
                        <h4 className="text-sm font-bold text-near-black mb-2">Dense Retrieval</h4>
                        <div className="space-y-3">
                          <Input label="Top K" defaultValue="20" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                          <Input label="Min Score" defaultValue="0.75" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                          <Input label="Weight" defaultValue="0.4" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                        </div>
                      </div>
                      <div className="p-3 border border-border-cream bg-ivory rounded shadow-sm relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-1 h-full bg-success-green"></div>
                        <h4 className="text-sm font-bold text-near-black mb-2">Sparse Retrieval (BM25)</h4>
                        <div className="space-y-3">
                          <Input label="Top K" defaultValue="15" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                          <Input label="Min Score" defaultValue="12.5" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                          <Input label="Weight" defaultValue="0.3" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                        </div>
                      </div>
                      <div className="p-3 border border-border-cream bg-ivory rounded shadow-sm relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-1 h-full bg-focus-blue"></div>
                        <h4 className="text-sm font-bold text-near-black mb-2">Graph Retrieval</h4>
                        <div className="space-y-3">
                          <Input label="Hop Depth" defaultValue="2" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                          <Input label="Max Nodes" defaultValue="50" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                          <Input label="Weight" defaultValue="0.3" className="bg-transparent" onChange={() => setHasUnsavedChanges(true)} />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-near-black">Fusion Algorithm</label>
                        <select className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm" onChange={() => setHasUnsavedChanges(true)}>
                          <option>Reciprocal Rank Fusion (RRF)</option>
                          <option>Linear Combination</option>
                          <option>Max Score</option>
                        </select>
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-near-black">Rerank Model</label>
                        <select className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm" onChange={() => setHasUnsavedChanges(true)}>
                          <option>bge-reranker-v2-m3</option>
                          <option>cohere-rerank-english-v3.0</option>
                          <option>Disabled</option>
                        </select>
                      </div>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="font-serif text-lg text-near-black flex items-center gap-2 mb-4">
                    <Code2 className="w-5 h-5 text-terracotta" /> Generation
                  </h3>
                  <div className="grid grid-cols-2 gap-4 bg-parchment p-4 rounded-lg border border-border-cream">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-near-black">LLM Model</label>
                      <select className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm" onChange={() => setHasUnsavedChanges(true)}>
                        <option>claude-3-5-sonnet-20241022</option>
                        <option>claude-3-haiku-20240307</option>
                        <option>gpt-4o-2024-05-13</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-near-black">Temperature</label>
                      <Input type="number" defaultValue="0.1" step="0.1" min="0" max="1" onChange={() => setHasUnsavedChanges(true)} />
                    </div>
                  </div>
                </section>
              </Tabs.Content>

              <Tabs.Content value="diff" className="outline-none">
                <div className="rounded-lg border border-border-cream bg-[#fffdfa] p-4 font-mono text-sm space-y-1">
                  <div className="text-stone-gray">@@ -15,7 +15,7 @@</div>
                  <div className="text-near-black pl-4">"retrieval": {"{"}</div>
                  <div className="text-near-black pl-8">"dense": {"{"}</div>
                  <div className="text-error-red bg-error-red/10 pl-12 line-through">- "weight": 0.5</div>
                  <div className="text-success-green bg-success-green/10 pl-12">+ "weight": 0.4</div>
                  <div className="text-near-black pl-8">{"}"},</div>
                  <div className="text-near-black pl-8">"graph": {"{"}</div>
                  <div className="text-error-red bg-error-red/10 pl-12 line-through">- "weight": 0.2</div>
                  <div className="text-success-green bg-success-green/10 pl-12">+ "weight": 0.3</div>
                  <div className="text-near-black pl-8">{"}"}</div>
                  <div className="text-near-black pl-4">{"}"}</div>
                </div>
              </Tabs.Content>
            </CardContent>
          </Tabs.Root>
        </Card>
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
              配置切换后会影响后续 QA 调试与历史比对结果，这类行为建议在原型阶段就做成明确确认。
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
