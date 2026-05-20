import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, Plus, Trash2, Edit } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import {
  fetchLibraryDetail,
  fetchLibraryMembers,
  addLibraryMember,
  updateLibraryMember,
  removeLibraryMember,
} from "../services/libraryService";
import type { LibraryDTO, LibraryMemberDTO, LibraryMemberPermissionLevel } from "../types/library";

function permissionLabel(level: LibraryMemberPermissionLevel) {
  return level === "read_only" ? "只读" : "文档管理";
}

function permissionVariant(level: LibraryMemberPermissionLevel) {
  return level === "read_only" ? "default" : "info";
}

export function LibraryMembers() {
  const navigate = useNavigate();
  const confirm = useConfirmDialog();
  const { libraryId = "" } = useParams();
  const [library, setLibrary] = useState<LibraryDTO | null>(null);
  const [members, setMembers] = useState<LibraryMemberDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);

  // 添加成员表单
  const [addOpen, setAddOpen] = useState(false);
  const [newSubjectType, setNewSubjectType] = useState<"user" | "group">("user");
  const [newSubjectId, setNewSubjectId] = useState("");
  const [newPermissionLevel, setNewPermissionLevel] = useState<LibraryMemberPermissionLevel>("read_only");
  const [submitting, setSubmitting] = useState(false);

  // 编辑成员
  const [editingBindingId, setEditingBindingId] = useState<string | null>(null);
  const [editPermissionLevel, setEditPermissionLevel] = useState<LibraryMemberPermissionLevel>("read_only");

  async function loadData() {
    setLoading(true);
    try {
      const [libData, membersData] = await Promise.all([
        fetchLibraryDetail(libraryId),
        fetchLibraryMembers(libraryId),
      ]);
      setLibrary(libData);
      setMembers(membersData);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务。",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, [libraryId]);

  async function handleAddMember() {
    if (!newSubjectId.trim()) {
      setFeedback({ variant: "warning", title: "请输入 ID", message: "用户/组 ID 不能为空。" });
      return;
    }
    setSubmitting(true);
    try {
      await addLibraryMember(libraryId, {
        subjectType: newSubjectType,
        subjectId: newSubjectId.trim(),
        permissionLevel: newPermissionLevel,
      });
      setFeedback({ variant: "success", title: "添加成功", message: "成员已添加。" });
      setAddOpen(false);
      setNewSubjectId("");
      await loadData();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "添加失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUpdateMember(bindingId: string) {
    try {
      await updateLibraryMember(libraryId, bindingId, { permissionLevel: editPermissionLevel });
      setFeedback({ variant: "success", title: "更新成功", message: "权限已更新。" });
      setEditingBindingId(null);
      await loadData();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "更新失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    }
  }

  async function handleRemoveMember(bindingId: string) {
    const ok = await confirm({
      title: "移除成员",
      description: "确定要移除此成员吗？移除后该成员将无法访问此文档库。",
      variant: "destructive",
      confirmLabel: "移除",
    });
    if (!ok) return;
    try {
      await removeLibraryMember(libraryId, bindingId);
      setFeedback({ variant: "success", title: "移除成功", message: "成员已移除。" });
      await loadData();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "移除失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    }
  }

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title={`成员管理 - ${library?.name ?? ""}`}
        breadcrumbs={[
          { label: "文档库", href: "/library" },
          { label: library?.name ?? "...", href: `/library/${libraryId}` },
          { label: "成员管理" },
        ]}
        actions={
          <Button onClick={() => setAddOpen(true)}>
            <Plus className="w-4 h-4 mr-2" /> 添加成员
          </Button>
        }
      />

      <div className="flex-1 min-h-0 overflow-auto p-8 space-y-6 max-w-7xl mx-auto w-full">
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        {/* 说明 */}
        <div className="p-4 bg-ivory border border-border-cream rounded-lg text-sm text-stone-gray">
          <p>部分可见性文档库的成员可以访问库中的文档。</p>
          <p className="mt-1"><strong>只读</strong>：可查看文档列表和详情。<strong>文档管理</strong>：可查看、上传、编辑和删除文档。</p>
        </div>

        {/* 成员列表 */}
        {loading ? (
          <div className="text-center py-12 text-stone-gray">加载中...</div>
        ) : members.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-stone-gray">暂无成员</p>
            <p className="text-sm text-stone-gray mt-1">点击"添加成员"授予访问权限</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>主体类型</TableHead>
                <TableHead>主体 ID</TableHead>
                <TableHead>权限级别</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.bindingId}>
                  <TableCell>
                    <Badge variant={member.subjectType === "user" ? "default" : "info"}>
                      {member.subjectType === "user" ? "用户" : "用户组"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-near-black font-mono">{member.subjectId}</span>
                  </TableCell>
                  <TableCell>
                    {editingBindingId === member.bindingId ? (
                      <div className="flex items-center gap-2">
                        <select
                          className="border border-border-cream rounded px-2 py-1 text-sm bg-white"
                          value={editPermissionLevel}
                          onChange={(e) => setEditPermissionLevel(e.target.value as LibraryMemberPermissionLevel)}
                        >
                          <option value="read_only">只读</option>
                          <option value="document_manage">文档管理</option>
                        </select>
                        <Button size="sm" onClick={() => void handleUpdateMember(member.bindingId)}>
                          保存
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditingBindingId(null)}>
                          取消
                        </Button>
                      </div>
                    ) : (
                      <Badge variant={permissionVariant(member.permissionLevel)}>
                        {permissionLabel(member.permissionLevel)}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-stone-gray">
                      {new Date(member.createdAt).toLocaleString("zh-CN")}
                    </span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setEditingBindingId(member.bindingId);
                          setEditPermissionLevel(member.permissionLevel);
                        }}
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700"
                        onClick={() => void handleRemoveMember(member.bindingId)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* 添加成员抽屉 */}
      {addOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/30" onClick={() => setAddOpen(false)} />
          <div className="ml-auto w-[420px] bg-ivory border-l border-border-cream flex flex-col shadow-xl">
            <div className="p-6 border-b border-border-cream">
              <h2 className="text-lg font-serif text-near-black">添加成员</h2>
            </div>
            <div className="flex-1 p-6 space-y-4 overflow-auto">
              <div>
                <label className="block text-sm font-medium text-near-black mb-2">主体类型</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="subjectType"
                      value="user"
                      checked={newSubjectType === "user"}
                      onChange={() => setNewSubjectType("user")}
                      className="accent-terracotta"
                    />
                    <span className="text-sm text-near-black">用户</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="subjectType"
                      value="group"
                      checked={newSubjectType === "group"}
                      onChange={() => setNewSubjectType("group")}
                      className="accent-terracotta"
                    />
                    <span className="text-sm text-near-black">用户组</span>
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-near-black mb-1">
                  {newSubjectType === "user" ? "用户 ID" : "用户组 ID"}
                </label>
                <Input
                  value={newSubjectId}
                  onChange={(e) => setNewSubjectId(e.target.value)}
                  placeholder={`输入${newSubjectType === "user" ? "用户" : "用户组"} ID`}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-near-black mb-2">权限级别</label>
                <div className="space-y-2">
                  {(["read_only", "document_manage"] as LibraryMemberPermissionLevel[]).map((level) => (
                    <label
                      key={level}
                      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                        newPermissionLevel === level
                          ? "border-terracotta bg-terracotta/5"
                          : "border-border-cream hover:border-stone-gray"
                      }`}
                    >
                      <input
                        type="radio"
                        name="permissionLevel"
                        value={level}
                        checked={newPermissionLevel === level}
                        onChange={() => setNewPermissionLevel(level)}
                        className="mt-0.5 accent-terracotta"
                      />
                      <div>
                        <div className="text-sm font-medium text-near-black">{permissionLabel(level)}</div>
                        <div className="text-xs text-stone-gray mt-0.5">
                          {level === "read_only" && "可查看文档列表和详情"}
                          {level === "document_manage" && "可查看、上传、编辑和删除文档"}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <div className="p-6 border-t border-border-cream flex items-center gap-3">
              <Button variant="secondary" className="flex-1" onClick={() => setAddOpen(false)}>
                取消
              </Button>
              <Button className="flex-1" disabled={submitting} onClick={() => void handleAddMember()}>
                {submitting ? "添加中..." : "添加"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
