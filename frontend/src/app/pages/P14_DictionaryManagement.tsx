import { useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, Save, Search } from "lucide-react";
import { Alert } from "../components/rag/Alert";
import { Button } from "../components/rag/Button";
import { Input } from "../components/rag/Input";
import { PageHeader } from "../components/rag/PageHeader";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/rag/Table";
import {
  createDictionaryItem,
  fetchDictionaryItems,
  SYSTEM_DICTIONARY_FALLBACKS,
  SYSTEM_DICTIONARY_TYPES,
  updateDictionaryItem,
} from "../services/dictionaryService";
import type { DictionaryItemDTO, DictionaryStatus, DictionaryTypeCode } from "../types/dictionary";

interface ItemForm {
  code: string;
  name: string;
  description: string;
  sortOrder: string;
  status: DictionaryStatus;
}

const EMPTY_FORM: ItemForm = {
  code: "",
  name: "",
  description: "",
  sortOrder: "0",
  status: "active",
};

function typeName(typeCode: DictionaryTypeCode): string {
  return SYSTEM_DICTIONARY_TYPES.find((type) => type.code === typeCode)?.name ?? typeCode;
}

/**
 * 平台字典管理页。
 * 仅维护运营字典的展示名、排序、状态和少量新增项，权限契约类 code 仍由后端白名单保护。
 */
export function DictionaryManagement() {
  const [selectedType, setSelectedType] = useState<DictionaryTypeCode>("security_level");
  const [items, setItems] = useState<DictionaryItemDTO[]>(SYSTEM_DICTIONARY_FALLBACKS.security_level);
  const [editingCode, setEditingCode] = useState<string | null>(null);
  const [form, setForm] = useState<ItemForm>(EMPTY_FORM);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [itemSearch, setItemSearch] = useState("");
  const [feedback, setFeedback] = useState<{ variant: "success" | "error" | "warning"; title: string; message: string } | null>(null);

  const selectedTypeMeta = useMemo(
    () => SYSTEM_DICTIONARY_TYPES.find((type) => type.code === selectedType),
    [selectedType],
  );

  const filteredItems = useMemo(() => {
    if (!itemSearch.trim()) return items;
    const q = itemSearch.trim().toLowerCase();
    return items.filter((item) => item.code.toLowerCase().includes(q) || item.name.toLowerCase().includes(q) || (item.description ?? "").toLowerCase().includes(q));
  }, [items, itemSearch]);

  async function loadItems(typeCode = selectedType) {
    setIsLoading(true);
    try {
      const response = await fetchDictionaryItems(typeCode, false);
      setItems(response.length > 0 ? response : SYSTEM_DICTIONARY_FALLBACKS[typeCode]);
      setFeedback(null);
    } catch (error) {
      setItems(SYSTEM_DICTIONARY_FALLBACKS[typeCode]);
      setFeedback({
        variant: "warning",
        title: "使用本地默认字典",
        message: error instanceof Error ? error.message : "字典接口暂不可用，当前展示内置默认值。",
      });
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    setEditingCode(null);
    setForm(EMPTY_FORM);
    void loadItems(selectedType);
  }, [selectedType]);

  function startEdit(item: DictionaryItemDTO) {
    setEditingCode(item.code);
    setForm({
      code: item.code,
      name: item.name,
      description: item.description ?? "",
      sortOrder: String(item.sortOrder),
      status: item.status,
    });
  }

  function startCreate() {
    setEditingCode(null);
    setForm(EMPTY_FORM);
  }

  async function saveItem() {
    const code = form.code.trim();
    const name = form.name.trim();
    if (!code || !name) {
      setFeedback({ variant: "error", title: "字典项不完整", message: "编码和名称不能为空。" });
      return;
    }
    const sortOrder = Number.parseInt(form.sortOrder, 10);
    setIsSaving(true);
    try {
      if (editingCode) {
        await updateDictionaryItem(selectedType, editingCode, {
          name,
          description: form.description.trim() || null,
          sortOrder: Number.isNaN(sortOrder) ? 0 : sortOrder,
          status: form.status,
        });
      } else {
        await createDictionaryItem(selectedType, {
          code,
          name,
          description: form.description.trim() || null,
          sortOrder: Number.isNaN(sortOrder) ? 0 : sortOrder,
          status: form.status,
        });
      }
      await loadItems(selectedType);
      setFeedback({ variant: "success", title: "字典已保存", message: `${typeName(selectedType)} 已更新。` });
      startCreate();
    } catch (error) {
      setFeedback({ variant: "error", title: "保存失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          title="字典管理"
          description="维护密级、来源、角色展示名和反馈标签。"
          actions={
            <Button variant="outline" onClick={() => void loadItems()} disabled={isLoading}>
              <RefreshCw className="mr-2 h-4 w-4" /> 刷新
            </Button>
          }
        />
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        <div className="grid grid-cols-[220px_minmax(0,1fr)] gap-5">
          <aside className="rounded-md border border-border-cream bg-ivory p-3">
            {SYSTEM_DICTIONARY_TYPES.map((type) => (
              <button
                key={type.code}
                type="button"
                className={`mb-1 flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm ${
                  selectedType === type.code ? "bg-parchment text-terracotta" : "text-near-black hover:bg-parchment"
                }`}
                onClick={() => setSelectedType(type.code)}
              >
                <span>{type.name}</span>
                {type.fixedCodes && <span className="text-xs text-stone-gray">固定</span>}
              </button>
            ))}
          </aside>

          <section className="min-w-0 space-y-4">
            <div className="rounded-md border border-border-cream bg-ivory p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-medium text-near-black">{typeName(selectedType)}</h2>
                  <p className="text-xs text-stone-gray">
                    {selectedTypeMeta?.fixedCodes ? "该类型只能维护既有 code 的展示信息。" : "可新增字典项，保存后由后端校验生效。"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="relative w-48">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-gray" />
                    <Input
                      value={itemSearch}
                      onChange={(e) => setItemSearch(e.target.value)}
                      placeholder="搜索字典项..."
                      className="pl-9 bg-white"
                    />
                  </div>
                  <Button variant="outline" onClick={startCreate}>
                    <Plus className="mr-2 h-4 w-4" /> 新增
                  </Button>
                </div>
              </div>
              {isLoading ? (
                <div className="space-y-3">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-12 rounded-lg bg-parchment animate-pulse" />
                  ))}
                </div>
              ) : (
                <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>编码</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>排序</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredItems.map((item) => (
                  <TableRow key={item.code}>
                    <TableCell className="font-mono">{item.code}</TableCell>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>{item.sortOrder}</TableCell>
                    <TableCell>{item.status === "active" ? "启用" : "禁用"}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => startEdit(item)}>
                        编辑
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {filteredItems.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-stone-gray">{itemSearch.trim() ? "无匹配字典项" : "暂无字典项"}</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
              )}
            </div>

          <div className="rounded-md border border-border-cream bg-ivory p-4">
            <h3 className="mb-3 text-sm font-medium text-near-black">{editingCode ? "编辑字典项" : "新增字典项"}</h3>
            <div className="grid grid-cols-2 gap-3">
              <label className="space-y-1 text-sm">
                <span className="text-stone-gray">编码</span>
                <Input value={form.code} disabled={Boolean(editingCode)} onChange={(event) => setForm({ ...form, code: event.target.value })} />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-stone-gray">名称</span>
                <Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-stone-gray">排序</span>
                <Input value={form.sortOrder} onChange={(event) => setForm({ ...form, sortOrder: event.target.value })} />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-stone-gray">状态</span>
                <select
                  className="h-10 w-full rounded-md border border-border-cream bg-white px-3 text-sm"
                  value={form.status}
                  onChange={(event) => setForm({ ...form, status: event.target.value as DictionaryStatus })}
                >
                  <option value="active">启用</option>
                  <option value="disabled">禁用</option>
                </select>
              </label>
              <label className="col-span-2 space-y-1 text-sm">
                <span className="text-stone-gray">说明</span>
                <Input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
              </label>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={() => void saveItem()} disabled={isSaving}>
                <Save className="mr-2 h-4 w-4" /> 保存
              </Button>
            </div>
          </div>
          </section>
        </div>
      </div>
    </div>
  );
}
