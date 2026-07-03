import { FormEvent, MouseEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { Alert } from "../components/rag/Alert";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { StatusBadge } from "../components/rag/Badge";
import { KbDeleteDialog } from "../components/rag/KbDeleteDialog";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Edit3, Power, Plus, Search, Trash2 } from "lucide-react";
import { toKnowledgeBaseCard } from "../adapters/knowledgeBaseAdapter";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  disableKnowledgeBase,
  enableKnowledgeBase,
  fetchKbDeleteImpact,
  fetchKnowledgeBases,
  updateKnowledgeBase,
} from "../services/knowledgeBaseService";
import { fetchDocuments } from "../services/documentService";
import type { KbDeleteImpact, KnowledgeBase, KnowledgeBaseCreateRequest } from "../types/knowledgeBase";

interface KnowledgeBaseFormState {
  name: string;
  description: string;
  ownerId: string;
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
  const [indexCapabilityLocked, setIndexCapabilityLocked] = useState(false);
  const [indexCapabilityLockLoading, setIndexCapabilityLockLoading] = useState(false);

  const kbCards = useMemo(() => knowledgeBases.map(toKnowledgeBaseCard), [knowledgeBases]);
  const indexCapabilityControlsDisabled = indexCapabilityLocked || indexCapabilityLockLoading;

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
    setIndexCapabilityLocked(false);
    setIndexCapabilityLockLoading(false);
    setIsDialogOpen(true);
  };

  const openEditDialog = (event: MouseEvent<HTMLButtonElement>, kb: KnowledgeBase) => {
    event.stopPropagation();
    setDialogMode("edit");
    setEditingKb(kb);
    setForm(toFormState(kb));
    setIndexCapabilityLocked(false);
    setIndexCapabilityLockLoading(true);
    setIsDialogOpen(true);
    void fetchDocuments(kb.kbId, { pageNo: 1, pageSize: 1 })
      .then((page) => {
        setIndexCapabilityLocked(page.total > 0);
      })
      .catch(() => {
        setIndexCapabilityLocked(true);
      })
      .finally(() => {
        setIndexCapabilityLockLoading(false);
      });
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
      const message = error instanceof Error ? error.message : "知识库停用失败。";
      setErrorMessage(
        message.includes("KB_HAS_ACTIVE_RAG_APPS")
          ? "该知识库仍有关联的启用应用。请先在应用中心停用相关应用，再停用知识库。"
          : message,
      );
    }
  };

  const handleEnable = async (event: MouseEvent<HTMLButtonElement>, kb: KnowledgeBase) => {
    event.stopPropagation();
    const confirmed = await confirm({
      title: "恢复启用知识库",
      description: "恢复后将重新允许上传文档、保存配置和发起 QA 调试，历史数据保持不变。",
      detail: <span className="font-medium text-near-black">{kb.name}</span>,
      confirmText: "恢复启用",
    });
    if (!confirmed) {
      return;
    }

    setErrorMessage(null);
    try {
      await enableKnowledgeBase(kb.kbId);
      await loadKnowledgeBases(keyword);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "知识库启用失败。");
    }
  };

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteImpact, setDeleteImpact] = useState<KbDeleteImpact | null>(null);
  const [deleteImpactLoading, setDeleteImpactLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [kbToDelete, setKbToDelete] = useState<KnowledgeBase | null>(null);

  const handleOpenDeleteDialog = async (event: MouseEvent<HTMLButtonElement>, kb: KnowledgeBase) => {
    event.stopPropagation();
    setKbToDelete(kb);
    setDeleteDialogOpen(true);
    setDeleteImpactLoading(true);
    try {
      const impact = await fetchKbDeleteImpact(kb.kbId);
      setDeleteImpact(impact);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "获取删除影响信息失败。");
      setDeleteDialogOpen(false);
    } finally {
      setDeleteImpactLoading(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!kbToDelete || !deleteImpact) return;
    setDeleting(true);
    try {
      await deleteKnowledgeBase(kbToDelete.kbId, deleteImpact.kbName);
      setDeleteDialogOpen(false);
      setKbToDelete(null);
      await loadKnowledgeBases(keyword);
    } catch (error) {
      const message = error instanceof Error ? error.message : "知识库删除失败。";
      setErrorMessage(
        message.includes("CONFIRM_NAME_MISMATCH")
          ? "名称不匹配，请重新输入。"
          : message.includes("KB_HAS_ACTIVE_RAG_APPS")
            ? "该知识库仍有关联的活跃应用。请先停用相关应用。"
            : message,
      );
    } finally {
      setDeleting(false);
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

      <div className="mt-6 mb-6 flex items-center gap-4">
          <div className="relative w-80 max-w-full">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-gray pointer-events-none" />
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
                    <CardTitle className="line-clamp-2 h-12 min-w-0 flex-1 break-words leading-6">
                      {kbCard.name}
                    </CardTitle>
                    <StatusBadge status={kbCard.status} className="shrink-0" />
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-stone-gray mb-4 line-clamp-2 h-10">{kbCard.description}</p>
                  <div className="text-xs font-mono text-olive-gray">ID: {kbCard.id}</div>
                  <div className="text-xs text-stone-gray mt-1">检索策略：{kbCard.retrievalSummary}</div>
                  <div className="text-xs text-stone-gray mt-1">最近更新：{kbCard.updatedAtLabel}</div>
                </CardContent>
                <CardFooter className="flex gap-1 pt-2">
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
                    title={isDisabled ? "恢复启用知识库" : "停用知识库"}
                    onClick={(event) => isDisabled ? handleEnable(event, kb) : handleDisable(event, kb)}
                  >
                    <Power className="h-4 w-4" />
                    <span className="sr-only">{isDisabled ? "恢复启用" : "停用"}</span>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    title="删除知识库"
                    onClick={(event) => handleOpenDeleteDialog(event, kb)}
                  >
                    <Trash2 className="h-4 w-4" />
                    <span className="sr-only">删除</span>
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
                维护基础信息和索引能力开关。
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

              <label className="grid gap-2 text-sm text-near-black">
                负责人 ID
                <Input value={form.ownerId} onChange={(event) => setForm({ ...form, ownerId: event.target.value })} />
              </label>

              <div className="grid gap-3 rounded-lg border border-border-cream bg-parchment p-4">
                {dialogMode === "edit" && indexCapabilityLocked && (
                  <p className="text-xs text-stone-gray">已有文档后不可变更 OpenSearch / Neo4j 索引能力。</p>
                )}
                <label className="flex items-center justify-between gap-4 text-sm text-near-black">
                  维护 Sparse 文本索引
                  <input
                    type="checkbox"
                    checked={form.sparseIndexEnabled}
                    disabled={indexCapabilityControlsDisabled}
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
                    disabled={indexCapabilityControlsDisabled}
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

      <KbDeleteDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        impact={deleteImpact}
        loading={deleteImpactLoading}
        onConfirm={handleConfirmDelete}
        deleting={deleting}
      />
    </div>
  );
}
