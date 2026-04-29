import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { ChevronLeft, ChevronRight, RefreshCw, Search, ShieldAlert, Trash2, UserPlus } from "lucide-react";
import {
  createKbMember,
  deleteKbMember,
  fetchKbMembers,
  fetchKbPermissionSummary,
  searchKbMemberSubjects,
  simulateEffectivePermission,
  updateKbMemberRole,
} from "../services/knowledgeBaseService";
import type {
  EffectivePermissionSimulationResponse,
  KbMemberBinding,
  KbMemberSubjectOption,
  KbMemberSubjectType,
  KbRole,
  PermissionSummary,
} from "../types/knowledgeBase";

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
const PAGE_SIZE = 10;

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
  const confirmDialog = useConfirmDialog();
  const { kbId } = useParams();
  const [members, setMembers] = useState<KbMemberBinding[]>([]);
  const [totalMembers, setTotalMembers] = useState(0);
  const [summary, setSummary] = useState<PermissionSummary | null>(null);
  const [keyword, setKeyword] = useState("");
  const [queryKeyword, setQueryKeyword] = useState("");
  const [roleFilter, setRoleFilter] = useState<KbRole | "">("");
  const [pageNo, setPageNo] = useState(1);
  const [subjectType, setSubjectType] = useState<KbMemberSubjectType>("user");
  const [subjectSearch, setSubjectSearch] = useState("");
  const [subjectOptions, setSubjectOptions] = useState<KbMemberSubjectOption[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<KbMemberSubjectOption | null>(null);
  const [simulationUserId, setSimulationUserId] = useState("");
  const [simulationPermissionCode, setSimulationPermissionCode] = useState("kb.view");
  const [simulationResult, setSimulationResult] = useState<EffectivePermissionSimulationResponse | null>(null);
  const [isSubjectDropdownOpen, setIsSubjectDropdownOpen] = useState(false);
  const [isSearchingSubjects, setIsSearchingSubjects] = useState(false);
  const [kbRole, setKbRole] = useState<KbRole>("kb_viewer");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const canManageMembers = summary?.permissions.includes("kb.member.manage") ?? false;
  const totalPages = Math.max(1, Math.ceil(totalMembers / PAGE_SIZE));
  const pageStart = totalMembers === 0 ? 0 : (pageNo - 1) * PAGE_SIZE + 1;
  const pageEnd = Math.min(pageNo * PAGE_SIZE, totalMembers);

  const loadMembers = useCallback(async () => {
    if (!kbId) {
      setErrorMessage("缺少知识库 ID。");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [memberPage, permissionSummary] = await Promise.all([
        fetchKbMembers(kbId, {
          keyword: queryKeyword,
          pageNo,
          pageSize: PAGE_SIZE,
          kbRole: roleFilter,
        }),
        fetchKbPermissionSummary(kbId),
      ]);
      setMembers(memberPage.items);
      setTotalMembers(memberPage.total);
      setSummary(permissionSummary);
    } catch {
      setErrorMessage("成员与权限读取失败，请确认当前账号仍可访问该知识库。");
    } finally {
      setIsLoading(false);
    }
  }, [kbId, pageNo, queryKeyword, roleFilter]);

  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  useEffect(() => {
    if (!kbId || !canManageMembers) {
      setSubjectOptions([]);
      return;
    }

    const timer = window.setTimeout(() => {
      setIsSearchingSubjects(true);
      searchKbMemberSubjects(kbId, subjectType, subjectSearch)
        .then(setSubjectOptions)
        .catch(() => setSubjectOptions([]))
        .finally(() => setIsSearchingSubjects(false));
    }, 200);

    return () => window.clearTimeout(timer);
  }, [kbId, canManageMembers, subjectType, subjectSearch]);

  const handleSearch = () => {
    const nextKeyword = keyword.trim();
    setPageNo(1);
    setQueryKeyword(nextKeyword);
    if (pageNo === 1 && queryKeyword === nextKeyword) {
      void loadMembers();
    }
  };

  const handleSubjectTypeChange = (nextType: KbMemberSubjectType) => {
    setSubjectType(nextType);
    setSubjectSearch("");
    setSelectedSubject(null);
    setSubjectOptions([]);
    setIsSubjectDropdownOpen(false);
  };

  const handleSelectSubject = (option: KbMemberSubjectOption) => {
    if (option.isAlreadyBound) {
      return;
    }

    setSelectedSubject(option);
    setSubjectSearch(option.label);
    setIsSubjectDropdownOpen(false);
  };

  const handleCreateMember = async () => {
    if (!kbId || !selectedSubject) {
      setErrorMessage("请先从下拉列表选择要添加的用户或用户组。");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await createKbMember(kbId, {
        subjectType,
        subjectId: selectedSubject.subjectId,
        kbRole,
      });
      setSubjectSearch("");
      setSelectedSubject(null);
      setSubjectOptions([]);
      setPageNo(1);
      if (pageNo === 1) {
        await loadMembers();
      }
    } catch {
      setErrorMessage("成员添加失败，请确认主体仍有效，且当前知识库中不存在有效绑定。");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSimulatePermission = async () => {
    if (!kbId || !simulationUserId.trim()) {
      setErrorMessage("请先输入要模拟的用户 ID。");
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      setSimulationResult(
        await simulateEffectivePermission(kbId, simulationUserId.trim(), simulationPermissionCode.trim() || "kb.view"),
      );
    } catch {
      setSimulationResult(null);
      setErrorMessage("权限解释模拟失败，请确认用户 ID 有效且当前账号可管理成员。");
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
      await updateKbMemberRole(kbId, member.bindingId, { kbRole: nextRole });
      await loadMembers();
    } catch {
      setErrorMessage("角色更新失败，请刷新后重试。");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemove = async (member: KbMemberBinding) => {
    if (!kbId) {
      return;
    }

    const confirmed = await confirmDialog({
      title: "确认移除知识库角色",
      description: "角色绑定修改会立即生效，被移除主体将失去对应知识库权限。",
      detail: (
        <>
          主体：{member.subjectName}
          <br />
          类型：{SUBJECT_TYPE_LABELS[member.subjectType]}
          <br />
          当前角色：{ROLE_LABELS[member.kbRole]}
        </>
      ),
      confirmText: "确认移除",
      variant: "destructive",
    });

    if (!confirmed) {
      return;
    }

    setIsSaving(true);
    setErrorMessage(null);
    try {
      await deleteKbMember(kbId, member.bindingId);
      if (members.length === 1 && pageNo > 1) {
        setPageNo((current) => current - 1);
      } else {
        await loadMembers();
      }
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
          <Button variant="outline" onClick={() => void loadMembers()} disabled={isLoading}>
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
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(240px,1fr)_220px_auto_minmax(300px,1.4fr)] gap-3 shrink-0 bg-ivory border border-border-cream rounded-lg p-4 items-start">
          <div>
            <p className="text-sm font-medium text-near-black mb-2">权限解释</p>
            <Input
              value={simulationUserId}
              onChange={(event) => setSimulationUserId(event.target.value)}
              placeholder="输入用户 ID"
              className="bg-white"
            />
          </div>
          <div>
            <p className="text-sm font-medium text-near-black mb-2">权限码</p>
            <Input
              value={simulationPermissionCode}
              onChange={(event) => setSimulationPermissionCode(event.target.value)}
              className="bg-white"
            />
          </div>
          <Button variant="outline" onClick={() => void handleSimulatePermission()} disabled={isSaving} className="mt-7 h-10">
            模拟
          </Button>
          <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
            {simulationResult ? (
              <>
                <div className="font-medium text-near-black">
                  {simulationResult.allowed ? "允许" : "拒绝"} · {simulationResult.requestedPermissionCode || "全部权限"}
                </div>
                <div className="mt-2 text-stone-gray">
                  来源：{simulationResult.sources.map((source) => `${source.sourceName || source.sourceType}:${source.effect}`).join("、") || "无"}
                </div>
                <div className="mt-1 text-stone-gray">
                  拒绝原因：{simulationResult.deniedReasons.join("、") || "无显式拒绝"}
                </div>
              </>
            ) : (
              <p className="text-stone-gray">输入用户 ID 后可查看有效权限来源和拒绝原因。</p>
            )}
          </div>
        </div>
      )}

      {canManageMembers && (
        <div className="grid grid-cols-1 xl:grid-cols-[140px_minmax(280px,1fr)_220px_auto] gap-3 shrink-0 bg-ivory border border-border-cream rounded-lg p-4 items-start">
          <select
            value={subjectType}
            onChange={(event) => handleSubjectTypeChange(event.target.value as KbMemberSubjectType)}
            className="h-10 px-3 bg-white border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          >
            <option value="user">用户</option>
            <option value="group">用户组</option>
          </select>

          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-5 -translate-y-1/2 text-stone-gray z-10" />
            <Input
              value={subjectSearch}
              onChange={(event) => {
                setSubjectSearch(event.target.value);
                setSelectedSubject(null);
                setIsSubjectDropdownOpen(true);
              }}
              onFocus={() => setIsSubjectDropdownOpen(true)}
              onBlur={() => window.setTimeout(() => setIsSubjectDropdownOpen(false), 120)}
              placeholder={`搜索${SUBJECT_TYPE_LABELS[subjectType]}名称、账号或邮箱`}
              className="pl-9 bg-white"
            />
            {isSubjectDropdownOpen && (
              <div className="absolute left-0 right-0 top-12 z-20 max-h-72 overflow-auto rounded-lg border border-border-cream bg-white shadow-lg">
                {isSearchingSubjects && (
                  <div className="px-3 py-2 text-sm text-stone-gray">搜索中...</div>
                )}
                {!isSearchingSubjects && subjectOptions.length === 0 && (
                  <div className="px-3 py-2 text-sm text-stone-gray">没有可选{SUBJECT_TYPE_LABELS[subjectType]}</div>
                )}
                {!isSearchingSubjects && subjectOptions.map((option) => (
                  <button
                    key={`${option.subjectType}-${option.subjectId}`}
                    type="button"
                    onMouseDown={(event) => {
                      event.preventDefault();
                      handleSelectSubject(option);
                    }}
                    disabled={option.isAlreadyBound}
                    className="w-full px-3 py-2 text-left hover:bg-parchment disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-near-black">{option.label}</span>
                      {option.isAlreadyBound && <span className="text-xs text-stone-gray">已绑定</span>}
                    </div>
                    <div className="mt-0.5 text-xs text-stone-gray truncate">{option.secondaryText || option.subjectId}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <select
            value={kbRole}
            onChange={(event) => setKbRole(event.target.value as KbRole)}
            className="h-10 px-3 bg-white border border-border-cream rounded-md text-sm text-near-black focus:outline-none"
          >
            {ROLE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <Button variant="primary" onClick={handleCreateMember} disabled={isSaving || !selectedSubject} className="h-10">
            <UserPlus className="w-4 h-4 mr-2" /> 添加
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-4 shrink-0">
        <div className="relative w-80 max-w-full">
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
          onChange={(event) => {
            setRoleFilter(event.target.value as KbRole | "");
            setPageNo(1);
          }}
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

      <div className="flex-1 overflow-auto">
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
            {!isLoading && members.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-stone-gray">暂无成员绑定</TableCell>
              </TableRow>
            )}
            {!isLoading && members.map((member) => (
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

      <div className="flex flex-wrap items-center justify-between gap-3 shrink-0 text-sm text-stone-gray">
        <span>
          共 {totalMembers} 条，当前显示 {pageStart}-{pageEnd}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPageNo((current) => Math.max(1, current - 1))}
            disabled={isLoading || pageNo <= 1}
          >
            <ChevronLeft className="w-4 h-4 mr-1" /> 上一页
          </Button>
          <span className="min-w-20 text-center text-near-black">
            {pageNo} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPageNo((current) => Math.min(totalPages, current + 1))}
            disabled={isLoading || pageNo >= totalPages}
          >
            下一页 <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
