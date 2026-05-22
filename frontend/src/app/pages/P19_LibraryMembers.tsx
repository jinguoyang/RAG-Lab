import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, Plus, Trash2, Edit, Database, ShieldCheck, KeyRound } from "lucide-react";
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
import { SubjectSearchDropdown } from "../components/rag/SubjectSearchDropdown";
import type { LibraryDTO, LibraryMemberDTO, LibraryMemberPermissionLevel } from "../types/library";

function permissionLabel(level: LibraryMemberPermissionLevel) {
  const labels: Record<LibraryMemberPermissionLevel, string> = {
    read_only: "只读（旧）",
    document_manage: "文档管理（旧）",
    library_viewer: "查看者",
    library_binder: "绑定者",
    library_editor: "编辑者",
    library_manager: "管理员",
  };
  return labels[level] ?? level;
}

function permissionVariant(level: LibraryMemberPermissionLevel) {
  if (level === "library_manager") return "success";
  if (level === "library_editor" || level === "document_manage") return "info";
  return "default";
}

const LIBRARY_ROLES: LibraryMemberPermissionLevel[] = [
  "library_viewer",
  "library_binder",
  "library_editor",
  "library_manager",
];
const ALL_PERMISSION_LEVELS: LibraryMemberPermissionLevel[] = ["read_only", "document_manage", ...LIBRARY_ROLES];

function permissionDescription(level: LibraryMemberPermissionLevel) {
  const descriptions: Record<LibraryMemberPermissionLevel, string> = {
    read_only: "旧权限值：可查看文档列表和详情",
    document_manage: "旧权限值：可查看、上传、编辑和删除文档",
    library_viewer: "可查看、预览和下载文档",
    library_binder: "可查看、预览、下载，并绑定到知识库",
    library_editor: "可上传、更新、重解析、版本管理、删除和绑定",
    library_manager: "可管理文档、版本、成员和文档库配置",
  };
  return descriptions[level] ?? "";
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
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);
  const [selectedSubjectLabel, setSelectedSubjectLabel] = useState<string>("");
  const [newPermissionLevel, setNewPermissionLevel] = useState<LibraryMemberPermissionLevel>("library_viewer");
  const [submitting, setSubmitting] = useState(false);

  // 编辑成员
  const [editingBindingId, setEditingBindingId] = useState<string | null>(null);
  const [editPermissionLevel, setEditPermissionLevel] = useState<LibraryMemberPermissionLevel>("library_viewer");

  const excludedSubjectIds = useMemo(
    () => new Set(members.filter((m) => m.subjectType === newSubjectType).map((m) => m.subjectId)),
    [members, newSubjectType],
  );

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
    if (!selectedSubjectId) {
      setFeedback({ variant: "warning", title: "请选择成员", message: "请搜索并选择一个用户或用户组。" });
      return;
    }
    setSubmitting(true);
    try {
      await addLibraryMember(libraryId, {
        subjectType: newSubjectType,
        subjectId: selectedSubjectId,
        permissionLevel: newPermissionLevel,
      });
      setFeedback({ variant: "success", title: "添加成功", message: "成员已添加。" });
      setAddOpen(false);
      setSelectedSubjectId(null);
      setSelectedSubjectLabel("");
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
    <div className="flex-1 overflow-auto">
      <div className="p-8 max-w-7xl mx-auto space-y-6">
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
        {feedback && (
          <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
            {feedback.message}
          </Alert>
        )}

        {/* 说明 */}
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-border-cream bg-ivory p-4 text-sm">
            <div className="flex items-center gap-2 font-medium text-near-black">
              <ShieldCheck className="h-4 w-4 text-terracotta" /> 文档库权限
            </div>
            <p className="mt-2 text-stone-gray">成员只控制当前文档库的查看、上传、编辑和删除。</p>
          </div>
          <div className="rounded-lg border border-border-cream bg-ivory p-4 text-sm">
            <div className="flex items-center gap-2 font-medium text-near-black">
              <Database className="h-4 w-4 text-terracotta" /> 知识库权限
            </div>
            <p className="mt-2 text-stone-gray">绑定后的检索、成员角色和管理权限在知识库成员页维护。</p>
          </div>
          <div className="rounded-lg border border-border-cream bg-ivory p-4 text-sm">
            <div className="flex items-center gap-2 font-medium text-near-black">
              <KeyRound className="h-4 w-4 text-terracotta" /> 应用调用权限
            </div>
            <p className="mt-2 text-stone-gray">外部调用由应用状态、所属知识库状态和 API Key 共同决定。</p>
          </div>
        </div>
        <div className="p-4 bg-ivory border border-border-cream rounded-lg text-sm text-stone-gray">
          <p><strong>查看者</strong>：查看、预览、下载。<strong>绑定者</strong>：可将文档带入知识库。<strong>编辑者</strong>：可管理文档和版本。<strong>管理员</strong>：可管理成员和文档库配置。</p>
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
                          {ALL_PERMISSION_LEVELS.map((role) => (
                            <option key={role} value={role}>{permissionLabel(role)}</option>
                          ))}
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
          <div className="relative ml-auto w-[420px] bg-ivory border-l border-border-cream flex flex-col shadow-xl">
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
                      onChange={() => {
                        setNewSubjectType("user");
                        setSelectedSubjectId(null);
                        setSelectedSubjectLabel("");
                      }}
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
                      onChange={() => {
                        setNewSubjectType("group");
                        setSelectedSubjectId(null);
                        setSelectedSubjectLabel("");
                      }}
                      className="accent-terracotta"
                    />
                    <span className="text-sm text-near-black">用户组</span>
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-near-black mb-1">
                  {newSubjectType === "user" ? "搜索用户" : "搜索用户组"}
                </label>
                <SubjectSearchDropdown
                  subjectType={newSubjectType}
                  excludedIds={excludedSubjectIds}
                  excludedLabel="已是成员"
                  onSelect={(id, label) => {
                    setSelectedSubjectId(id);
                    setSelectedSubjectLabel(label);
                  }}
                />
                {selectedSubjectId && (
                  <p className="mt-1 text-xs text-stone-gray">
                    已选择：{selectedSubjectLabel} ({selectedSubjectId})
                  </p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-near-black mb-2">权限级别</label>
                <div className="space-y-2">
                  {LIBRARY_ROLES.map((level) => (
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
                          {permissionDescription(level)}
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
