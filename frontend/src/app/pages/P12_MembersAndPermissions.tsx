import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Search, UserPlus, ShieldAlert, RefreshCw, Trash2 } from "lucide-react";
import {
  createKbMember,
  deleteKbMember,
  fetchKbMembers,
  fetchKbPermissionSummary,
  updateKbMemberRole,
} from "../services/knowledgeBaseService";
import type { KbMemberBinding, KbMemberSubjectType, KbRole, PermissionSummary } from "../types/knowledgeBase";

const ROLE_LABELS: Record<KbRole, string> = {
  kb_owner: "知识库管理员",
  kb_editor: "知识库编辑",
  kb_operator: "QA 操作员",
  kb_viewer: "知识库读者",
};

const SUBJECT_TYPE_LABELS: Record<KbMemberSubjectType, string> = {
  user: "用户",
  group: "用户组",
};

const ROLE_OPTIONS = Object.entries(ROLE_LABELS) as Array<[KbRole, string]>;

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function MembersAndPermissions() {
  const { kbId } = useParams();
  const [members, setMembers] = useState<KbMemberBinding[]>([]);
  const [summary, setSummary] = useState<PermissionSummary | null>(null);
  const [keyword, setKeyword] = useState("");
  const [roleFilter, setRoleFilter] = useState<KbRole | "">("");
  const [subjectType, setSubjectType] = useState<KbMemberSubjectType>("user");
  const [subjectId, setSubjectId] = useState("");
  const [kbRole, setKbRole] = useState<KbRole>("kb_viewer");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const canManageMembers = summary?.permissions.includes("kb.member.manage") ?? false;

  const visibleMembers = useMemo(() => {
    return members.filter((member) => !roleFilter || member.kbRole === roleFilter);
  }, [members, roleFilter]);

  const loadMembers = async () => {
    if (!kbId) {
      setErrorMessage("缺少知识库 ID。");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [memberPage, permissionSummary] = await Promise.all([
        fetchKbMembers(kbId, keyword),
        fetchKbPermissionSummary(kbId),
      ]);
      setMembers(memberPage.items);
      setSummary(permissionSummary);
    } catch {
      setErrorMessage("成员与权限读取失败，请确认当前账号仍可访问该知识库。");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadMembers();
  }, [kbId]);

  const handleSearch = () => {
    void loadMembers();
  };

  const handleCreateMember = async () => {
    if (!kbId || !subjectId.trim()) {
      setErrorMessage("请填写有效的主体 ID。");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await createKbMember(kbId, {
        subjectType,
        subjectId: subjectId.trim(),
        kbRole,
      });
      setSubjectId("");
      await loadMembers();
    } catch {
      setErrorMessage("成员添加失败，请检查主体 ID、角色和是否已存在有效绑定。");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRoleChange = async (member: KbMemberBinding, nextRole: KbRole) => {
    if (!kbId || nextRole === member.kbRole) {
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      const updated = await updateKbMemberRole(kbId, member.bindingId, { kbRole: nextRole });
      setMembers((current) => current.map((item) => (item.bindingId === updated.bindingId ? updated : item)));
    } catch {
      setErrorMessage("角色更新失败，请刷新后重试。");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemove = async (member: KbMemberBinding) => {
    if (!kbId || !window.confirm(`移除 ${member.subjectName} 的知识库角色？`)) {
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await deleteKbMember(kbId, member.bindingId);
      setMembers((current) => current.filter((item) => item.bindingId !== member.bindingId));
    } catch {
      setErrorMessage("成员移除失败，请刷新后重试。");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="成员与权限"
        description="管理谁可以在该知识库中读取、编辑和执行 QA。"
        actions={
          <Button variant="outline" onClick={handleSearch} disabled={isLoading}>
            <RefreshCw className="w-4 h-4 mr-2" /> 刷新
          </Button>
        }
      />

      <div className="bg-warning-amber/10 border border-warning-amber/20 rounded-lg p-4 flex gap-3 text-warning-amber text-sm mb-4">
        <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-near-black">重要安全提示</p>
          <p className="mt-1">角色绑定修改会立即生效。被移出“知识库读者”或“QA 操作员”角色的用户将失去运行诊断查询的权限。</p>
        </div>
      </div>

      {errorMessage && (
        <Alert variant="error" title="操作失败">
          {errorMessage}
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 shrink-0">
        <div className="bg-ivory border border-border-cream rounded-lg p-4">
          <p className="text-xs text-stone-gray mb-1">当前角色</p>
          <p className="text-sm font-medium text-near-black">{summary?.roles.map((role) => ROLE_LABELS[role as KbRole] || role).join(" / ") || "无"}</p>
        </div>
        <div className="bg-ivory border border-border-cream rounded-lg p-4">
          <p className="text-xs text-stone-gray mb-1">成员管理</p>
          <p className="text-sm font-medium text-near-black">{canManageMembers ? "可管理" : "只读"}</p>
        </div>
        <div className="bg-ivory border border-border-cream rounded-lg p-4 lg:col-span-2">
          <p className="text-xs text-stone-gray mb-1">权限摘要</p>
          <p className="text-sm text-near-black truncate">{summary?.permissions.join("、") || "暂无权限"}</p>
        </div>
      </div>

      {canManageMembers && (
        <div className="flex flex-wrap items-center gap-3 shrink-0 bg-ivory border border-border-cream rounded-lg p-4">
          <select
            value={subjectType}
            onChange={(event) => setSubjectType(event.target.value as KbMemberSubjectType)}
            className="px-3 py-2 bg-white border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          >
            <option value="user">用户</option>
            <option value="group">用户组</option>
          </select>
          <Input
            value={subjectId}
            onChange={(event) => setSubjectId(event.target.value)}
            placeholder="主体 UUID"
            className="w-96 max-w-full"
          />
          <select
            value={kbRole}
            onChange={(event) => setKbRole(event.target.value as KbRole)}
            className="px-3 py-2 bg-white border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          >
            {ROLE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <Button variant="primary" onClick={handleCreateMember} disabled={isSaving}>
            <UserPlus className="w-4 h-4 mr-2" /> 添加
          </Button>
        </div>
      )}

      <div className="flex items-center gap-4 shrink-0">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSearch();
              }
            }}
            placeholder="按名称搜索..."
            className="pl-9"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(event) => setRoleFilter(event.target.value as KbRole | "")}
          className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
        >
          <option value="">全部角色</option>
          {ROLE_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <Button variant="outline" onClick={handleSearch} disabled={isLoading}>
          <Search className="w-4 h-4 mr-2" /> 查询
        </Button>
      </div>

      <div className="flex-1 overflow-auto border border-border-cream rounded-xl">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>主体（用户 / 用户组）</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>角色</TableHead>
              <TableHead>来源</TableHead>
              <TableHead>更新时间</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} className="text-stone-gray">加载中...</TableCell>
              </TableRow>
            )}
            {!isLoading && visibleMembers.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-stone-gray">暂无成员绑定</TableCell>
              </TableRow>
            )}
            {!isLoading && visibleMembers.map((member) => (
              <TableRow key={member.bindingId}>
                <TableCell className="font-medium text-near-black">
                  <div>{member.subjectName}</div>
                  <div className="text-xs text-stone-gray font-normal">{member.subjectId}</div>
                </TableCell>
                <TableCell>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${member.subjectType === "group" ? "bg-focus-blue/10 text-focus-blue" : "bg-border-cream text-olive-gray"}`}>
                    {SUBJECT_TYPE_LABELS[member.subjectType]}
                  </span>
                </TableCell>
                <TableCell>
                  {canManageMembers ? (
                    <select
                      value={member.kbRole}
                      onChange={(event) => handleRoleChange(member, event.target.value as KbRole)}
                      disabled={isSaving}
                      className="px-2 py-1 bg-white border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
                    >
                      {ROLE_OPTIONS.map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  ) : (
                    ROLE_LABELS[member.kbRole]
                  )}
                </TableCell>
                <TableCell className="text-stone-gray">{member.subjectType === "group" ? "用户组绑定" : "直接绑定"}</TableCell>
                <TableCell>{formatDate(member.updatedAt)}</TableCell>
                <TableCell>
                  {canManageMembers ? (
                    <Button variant="ghost" size="sm" className="text-terracotta hover:bg-terracotta/10" onClick={() => handleRemove(member)} disabled={isSaving}>
                      <Trash2 className="w-3 h-3 mr-1" /> 移除
                    </Button>
                  ) : (
                    <span className="text-stone-gray text-sm">只读</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
