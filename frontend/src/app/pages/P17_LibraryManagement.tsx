import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Plus, Search, Trash2, Edit, ChevronLeft, ChevronRight, FileText, Users } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import {
  fetchLibraries,
  createLibrary,
  updateLibrary,
  deleteLibrary,
} from "../services/libraryService";
import type { LibraryDTO } from "../types/library";

const PAGE_SIZE = 20;

export function LibraryManagement() {
  const navigate = useNavigate();
  const confirm = useConfirmDialog();
  const [libraries, setLibraries] = useState<LibraryDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [pageNo, setPageNo] = useState(1);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  // 创建/编辑抽屉状态
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editingLibrary, setEditingLibrary] = useState<LibraryDTO | null>(null);
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async (keyword = searchTerm, nextPageNo = pageNo) => {
    setLoading(true);
    try {
      const page = await fetchLibraries({ keyword, pageNo: nextPageNo, pageSize: PAGE_SIZE });
      setLibraries(page.items);
      setTotal(page.total);
      setPageNo(page.pageNo);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务。",
      });
    } finally {
      setLoading(false);
    }
  }, [searchTerm, pageNo]);

  useEffect(() => {
    void loadData("", 1);
  }, []);

  async function handleSearchSubmit() {
    await loadData(searchTerm, 1);
  }

  function openCreateDrawer() {
    setEditingLibrary(null);
    setFormName("");
    setFormDescription("");
    setDrawerOpen(true);
  }

  function openEditDrawer(lib: LibraryDTO) {
    setEditingLibrary(lib);
    setFormName(lib.name);
    setFormDescription(lib.description ?? "");
    setDrawerOpen(true);
  }

  async function handleSubmit() {
    if (!formName.trim()) {
      setFeedback({ variant: "warning", title: "请输入名称", message: "文档库名称不能为空。" });
      return;
    }
    setSubmitting(true);
    try {
      if (editingLibrary) {
        await updateLibrary(editingLibrary.libraryId, {
          name: formName.trim(),
          description: formDescription.trim() || undefined,
        });
        setFeedback({ variant: "success", title: "更新成功", message: "文档库已更新。" });
      } else {
        await createLibrary({
          name: formName.trim(),
          description: formDescription.trim() || undefined,
        });
        setFeedback({ variant: "success", title: "创建成功", message: "文档库已创建。" });
      }
      setDrawerOpen(false);
      await loadData(searchTerm, 1);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: editingLibrary ? "更新失败" : "创建失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(lib: LibraryDTO) {
    const ok = await confirm({
      title: "删除文档库",
      description: `确定要删除文档库"${lib.name}"吗？库内所有文档将被一并删除。`,
      variant: "destructive",
      confirmLabel: "删除",
    });
    if (!ok) return;
    try {
      await deleteLibrary(lib.libraryId);
      setFeedback({ variant: "success", title: "删除成功", message: "文档库已删除。" });
      await loadData(searchTerm, pageNo);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "删除失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          title="文档库"
          description="管理文档库，上传的文档归属于文档库中。"
          actions={
            <Button onClick={openCreateDrawer}>
              <Plus className="w-4 h-4 mr-2" /> 创建文档库
            </Button>
          }
        />
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        {/* 搜索 */}
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-gray pointer-events-none" />
            <Input
              className="pl-9"
              placeholder="搜索文档库名称..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSearchSubmit()}
            />
          </div>
          <Button variant="secondary" onClick={() => void handleSearchSubmit()}>
            搜索
          </Button>
        </div>

        {/* 文档库列表 */}
        {loading ? (
          <div className="text-center py-12 text-stone-gray">加载中...</div>
        ) : libraries.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
            <p className="text-stone-gray">暂无文档库</p>
            <p className="text-sm text-stone-gray mt-1">点击"创建文档库"开始使用</p>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>文档数</TableHead>
                  <TableHead>负责人</TableHead>
                  <TableHead>最近更新</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {libraries.map((lib) => (
                  <TableRow
                    key={lib.libraryId}
                    className="cursor-pointer"
                    onClick={() => navigate(`/library/${lib.libraryId}`)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-stone-gray" />
                        <span className="font-medium text-near-black truncate max-w-[300px]">{lib.name}</span>
                      </div>
                      {lib.description && (
                        <p className="text-xs text-stone-gray mt-1 truncate max-w-[400px]">{lib.description}</p>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="text-near-black">{lib.documentCount}</span>
                    </TableCell>
                    <TableCell>
                      <span className="text-stone-gray text-sm">{lib.ownerName || "-"}</span>
                    </TableCell>
                    <TableCell>
                      <span className="text-stone-gray text-sm">
                        {new Date(lib.updatedAt).toLocaleString("zh-CN")}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          title="成员权限"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/library/${lib.libraryId}/members`);
                          }}
                        >
                          <Users className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            openEditDrawer(lib);
                          }}
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:text-red-700"
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleDelete(lib);
                          }}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* 分页 */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-stone-gray">共 {total} 个文档库</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={pageNo <= 1}
                    onClick={() => void loadData(searchTerm, pageNo - 1)}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <span className="text-sm text-near-black">{pageNo} / {totalPages}</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={pageNo >= totalPages}
                    onClick={() => void loadData(searchTerm, pageNo + 1)}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* 创建/编辑弹出层 */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDrawerOpen(false)} />
          <div className="relative w-[420px] bg-ivory border border-border-cream rounded-lg shadow-xl">
            <div className="p-6 border-b border-border-cream">
              <h2 className="text-lg font-serif text-near-black">
                {editingLibrary ? "编辑文档库" : "创建文档库"}
              </h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-near-black mb-1">名称</label>
                <Input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="输入文档库名称"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-near-black mb-1">描述</label>
                <textarea
                  className="w-full border border-border-cream rounded-md px-3 py-2 text-sm bg-white resize-none"
                  rows={3}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="可选，输入文档库描述"
                />
              </div>
            </div>
            <div className="p-6 border-t border-border-cream flex items-center gap-3">
              <Button variant="secondary" className="flex-1" onClick={() => setDrawerOpen(false)}>
                取消
              </Button>
              <Button className="flex-1" disabled={submitting} onClick={() => void handleSubmit()}>
                {submitting ? "提交中..." : editingLibrary ? "保存" : "创建"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
