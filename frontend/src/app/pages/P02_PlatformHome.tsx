import { FormEvent, MouseEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { Alert } from "../components/rag/Alert";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { StatusBadge } from "../components/rag/Badge";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Edit3, Power, Plus, Search } from "lucide-react";
import { toKnowledgeBaseCard } from "../adapters/knowledgeBaseAdapter";
import {
  createKnowledgeBase,
  disableKnowledgeBase,
  fetchKnowledgeBases,
  updateKnowledgeBase,
} from "../services/knowledgeBaseService";
import type { KnowledgeBase, KnowledgeBaseCreateRequest } from "../types/knowledgeBase";

interface KnowledgeBaseFormState {
  name: string;
  description: string;
  ownerId: string;
  defaultSecurityLevel: string;
  sparseIndexEnabled: boolean;
  graphIndexEnabled: boolean;
  sparseRequiredForActivation: boolean;
  graphRequiredForActivation: boolean;
}

type KnowledgeBaseDialogMode = "create" | "edit";

const EMPTY_FORM: KnowledgeBaseFormState = {
  name: "",
  description: "",
  ownerId: "",
  defaultSecurityLevel: "public",
  sparseIndexEnabled: false,
  graphIndexEnabled: false,
  sparseRequiredForActivation: false,
  graphRequiredForActivation: false,
};

function toFormState(kb: KnowledgeBase): KnowledgeBaseFormState {
  return {
    name: kb.name,
    description: kb.description ?? "",
    ownerId: kb.ownerId,
    defaultSecurityLevel: kb.defaultSecurityLevel,
    sparseIndexEnabled: kb.sparseIndexEnabled,
    graphIndexEnabled: kb.graphIndexEnabled,
    sparseRequiredForActivation: kb.requiredForActivation.sparse,
    graphRequiredForActivation: kb.requiredForActivation.graph,
  };
}

function buildRequestPayload(form: KnowledgeBaseFormState): KnowledgeBaseCreateRequest {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    ownerId: form.ownerId.trim() || null,
    defaultSecurityLevel: form.defaultSecurityLevel.trim() || "public",
    sparseIndexEnabled: form.sparseIndexEnabled,
    graphIndexEnabled: form.graphIndexEnabled,
    requiredForActivation: {
      dense: true,
      sparse: form.sparseRequiredForActivation,
      graph: form.graphRequiredForActivation,
    },
  };
}

export function PlatformHome() {
  const navigate = useNavigate();
  const confirm = useConfirmDialog();
  const [keyword, setKeyword] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [dialogMode, setDialogMode] = useState<KnowledgeBaseDialogMode>("create");
  const [editingKb, setEditingKb] = useState<KnowledgeBase | null>(null);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [form, setForm] = useState<KnowledgeBaseFormState>(EMPTY_FORM);

  const kbCards = useMemo(() => knowledgeBases.map(toKnowledgeBaseCard), [knowledgeBases]);

  const loadKnowledgeBases = useCallback((nextKeyword: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    return fetchKnowledgeBases(nextKeyword)
      .then((page) => {
        setKnowledgeBases(page.items);
        setTotal(page.total);
      })
      .catch(() => {
        setErrorMessage("知识库列表读取失败，请确认后端服务和数据库迁移已完成。");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadKnowledgeBases(keyword);
    }, 250);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [keyword, loadKnowledgeBases]);

  const openCreateDialog = () => {
    setDialogMode("create");
    setEditingKb(null);
    setForm(EMPTY_FORM);
    setIsDialogOpen(true);
  };

  const openEditDialog = (event: MouseEvent<HTMLButtonElement>, kb: KnowledgeBase) => {
    event.stopPropagation();
    setDialogMode("edit");
    setEditingKb(kb);
    setForm(toFormState(kb));
    setIsDialogOpen(true);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const payload = buildRequestPayload(form);
    if (!payload.name) {
      setErrorMessage("知识库名称不能为空。");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      if (dialogMode === "edit" && editingKb) {
        await updateKnowledgeBase(editingKb.kbId, payload);
      } else {
        await createKnowledgeBase(payload);
      }
      setIsDialogOpen(false);
      await loadKnowledgeBases(keyword);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "知识库保存失败。");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDisable = async (event: MouseEvent<HTMLButtonElement>, kb: KnowledgeBase) => {
    event.stopPropagation();
    const confirmed = await confirm({
      title: "停用知识库",
      description: "停用后将保留文档、配置和 QA 历史，但不再允许上传文档、保存配置或发起 QA 调试。",
      detail: <span className="font-medium text-near-black">{kb.name}</span>,
      confirmText: "停用",
      variant: "destructive",
    });
    if (!confirmed) {
      return;
    }

    setErrorMessage(null);
    try {
      await disableKnowledgeBase(kb.kbId);
      await loadKnowledgeBases(keyword);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "知识库停用失败。");
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <PageHeader
        title="知识库"
        description="选择一个知识库进入工作区，或新建知识库。"
        actions={
          <Button variant="primary" onClick={openCreateDialog}>
            <Plus className="w-4 h-4 mr-2" />
            新建知识库
          </Button>
        }
      />

      <div className="mt-8 mb-6 flex items-center gap-4">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索知识库..."
            className="pl-9"
          />
        </div>
        <div className="text-sm text-stone-gray ml-auto">共显示 {total} 个知识库</div>
      </div>

      {errorMessage && (
        <Alert variant="error" title="操作失败" className="mb-6">
          {errorMessage}
        </Alert>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[0, 1, 2].map((item) => (
            <Card key={item} className="animate-pulse">
              <CardHeader>
                <div className="h-5 w-2/3 rounded bg-border-warm" />
              </CardHeader>
              <CardContent>
                <div className="h-4 w-full rounded bg-border-cream" />
                <div className="mt-3 h-4 w-1/2 rounded bg-border-cream" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!isLoading && !errorMessage && kbCards.length === 0 && (
        <Card>
          <CardContent>
            <p className="text-sm text-stone-gray">暂无可见知识库。</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {!isLoading &&
          !errorMessage &&
          kbCards.map((kbCard) => {
            const kb = knowledgeBases.find((item) => item.kbId === kbCard.id);
            if (!kb) return null;
            const isDisabled = kb.status === "disabled";

            return (
              <Card
                key={kbCard.id}
                className="hover:border-terracotta cursor-pointer transition-colors"
                onClick={() => navigate(`/kb/${kbCard.id}`)}
              >
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-start gap-3">
                    <CardTitle>{kbCard.name}</CardTitle>
                    <StatusBadge status={kbCard.status} />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-stone-gray mb-4 line-clamp-2 h-10">{kbCard.description}</p>
                  <div className="text-xs font-mono text-olive-gray">ID: {kbCard.id}</div>
                  <div className="text-xs text-stone-gray mt-1">检索策略：{kbCard.retrievalSummary}</div>
                  <div className="text-xs text-stone-gray mt-1">最近更新：{kbCard.updatedAtLabel}</div>
                </CardContent>
                <CardFooter className="pt-2 gap-2">
                  <Button variant="ghost" size="sm" className="flex-1 justify-center">
                    进入工作区
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    title="编辑知识库"
                    disabled={isDisabled}
                    onClick={(event) => openEditDialog(event, kb)}
                  >
                    <Edit3 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    title="停用知识库"
                    disabled={isDisabled}
                    onClick={(event) => handleDisable(event, kb)}
                  >
                    <Power className="h-4 w-4" />
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
      </div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="border-border-warm bg-ivory sm:max-w-[560px]">
          <form onSubmit={handleSubmit} className="space-y-5">
            <DialogHeader>
              <DialogTitle className="font-serif text-2xl font-medium text-near-black">
                {dialogMode === "edit" ? "编辑知识库" : "新建知识库"}
              </DialogTitle>
              <DialogDescription className="text-sm text-olive-gray">
                维护基础信息、默认密级和索引能力开关。
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4">
              <label className="grid gap-2 text-sm text-near-black">
                名称
                <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>

              <label className="grid gap-2 text-sm text-near-black">
                描述
                <textarea
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                  className="min-h-24 rounded-[10px] border border-border-warm bg-white px-3 py-2 text-sm text-near-black outline-none focus:ring-2 focus:ring-focus-blue"
                />
              </label>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <label className="grid gap-2 text-sm text-near-black">
                  负责人 ID
                  <Input value={form.ownerId} onChange={(event) => setForm({ ...form, ownerId: event.target.value })} />
                </label>
                <label className="grid gap-2 text-sm text-near-black">
                  默认密级
                  <Input
                    value={form.defaultSecurityLevel}
                    onChange={(event) => setForm({ ...form, defaultSecurityLevel: event.target.value })}
                  />
                </label>
              </div>

              <div className="grid gap-3 rounded-lg border border-border-cream bg-parchment p-4">
                <label className="flex items-center justify-between gap-4 text-sm text-near-black">
                  维护 Sparse 文本索引
                  <input
                    type="checkbox"
                    checked={form.sparseIndexEnabled}
                    onChange={(event) => setForm({ ...form, sparseIndexEnabled: event.target.checked })}
                    className="h-4 w-4 accent-terracotta"
                  />
                </label>
                <label className="flex items-center justify-between gap-4 text-sm text-near-black">
                  Sparse 完成后才允许激活
                  <input
                    type="checkbox"
                    checked={form.sparseRequiredForActivation}
                    onChange={(event) => setForm({ ...form, sparseRequiredForActivation: event.target.checked })}
                    className="h-4 w-4 accent-terracotta"
                  />
                </label>
                <label className="flex items-center justify-between gap-4 text-sm text-near-black">
                  维护图索引
                  <input
                    type="checkbox"
                    checked={form.graphIndexEnabled}
                    onChange={(event) => setForm({ ...form, graphIndexEnabled: event.target.checked })}
                    className="h-4 w-4 accent-terracotta"
                  />
                </label>
                <label className="flex items-center justify-between gap-4 text-sm text-near-black">
                  图索引完成后才允许激活
                  <input
                    type="checkbox"
                    checked={form.graphRequiredForActivation}
                    onChange={(event) => setForm({ ...form, graphRequiredForActivation: event.target.checked })}
                    className="h-4 w-4 accent-terracotta"
                  />
                </label>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setIsDialogOpen(false)}>
                取消
              </Button>
              <Button type="submit" variant="primary" disabled={isSaving}>
                {isSaving ? "保存中" : "保存"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
