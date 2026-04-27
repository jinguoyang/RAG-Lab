import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import { ChevronLeft, ChevronRight, Plus, RefreshCw, Search, Trash2, Users } from "lucide-react";
import {
  addUsersToGroup,
  createUserGroup,
  fetchUserGroup,
  fetchUserGroups,
  fetchUsers,
  removeUserFromGroup,
} from "../services/userGroupService";
import type { GroupMember, UserGroupDetail, UserGroupSummary, UserSummary } from "../types/userGroup";

const PAGE_SIZE = 10;

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

export function UserGroupManagement() {
  const [groups, setGroups] = useState<UserGroupSummary[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<UserGroupDetail | null>(null);
  const [keyword, setKeyword] = useState("");
  const [queryKeyword, setQueryKeyword] = useState("");
  const [pageNo, setPageNo] = useState(1);
  const [total, setTotal] = useState(0);
  const [newGroup, setNewGroup] = useState({ name: "", description: "" });
  const [memberSearch, setMemberSearch] = useState("");
  const [candidateUsers, setCandidateUsers] = useState<UserSummary[]>([]);
  const [selectedUser, setSelectedUser] = useState<UserSummary | null>(null);
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ variant: "success" | "error"; title: string; message: string } | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const selectedGroupId = selectedGroup?.groupId;

  const loadGroups = useCallback(async () => {
    setIsLoading(true);
    try {
      const page = await fetchUserGroups({ keyword: queryKeyword, pageNo, pageSize: PAGE_SIZE });
      setGroups(page.items);
      setTotal(page.total);
      if (selectedGroupId) {
        const refreshed = page.items.some((group) => group.groupId === selectedGroupId)
          ? await fetchUserGroup(selectedGroupId)
          : null;
        setSelectedGroup(refreshed);
      }
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户组加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务状态。",
      });
    } finally {
      setIsLoading(false);
    }
  }, [pageNo, queryKeyword, selectedGroupId]);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchUsers({ keyword: memberSearch, pageNo: 1, pageSize: 8 })
        .then((page) => setCandidateUsers(page.items.filter((user) => user.status === "active")))
        .catch(() => setCandidateUsers([]));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [memberSearch]);

  const handleSearch = () => {
    const nextKeyword = keyword.trim();
    setPageNo(1);
    setQueryKeyword(nextKeyword);
    if (pageNo === 1 && queryKeyword === nextKeyword) {
      void loadGroups();
    }
  };

  const handleCreateGroup = async () => {
    if (!newGroup.name.trim()) {
      setFeedback({ variant: "error", title: "用户组信息不完整", message: "用户组名称不能为空。" });
      return;
    }

    setIsSaving(true);
    try {
      const group = await createUserGroup({
        name: newGroup.name.trim(),
        description: newGroup.description.trim() || null,
      });
      setNewGroup({ name: "", description: "" });
      setPageNo(1);
      setQueryKeyword("");
      setKeyword("");
      setSelectedGroup(await fetchUserGroup(group.groupId));
      setFeedback({ variant: "success", title: "用户组已创建", message: "可以继续在右侧添加组成员。" });
      if (pageNo === 1 && !queryKeyword) {
        await loadGroups();
      }
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户组创建失败",
        message: error instanceof Error ? error.message : "请检查组名是否重复。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleSelectGroup = async (group: UserGroupSummary) => {
    setIsSaving(true);
    try {
      setSelectedGroup(await fetchUserGroup(group.groupId));
      setSelectedUser(null);
      setMemberSearch("");
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户组详情加载失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddMember = async () => {
    if (!selectedGroup || !selectedUser) {
      setFeedback({ variant: "error", title: "未选择成员", message: "请先选择用户组和要加入的用户。" });
      return;
    }

    setIsSaving(true);
    try {
      const detail = await addUsersToGroup(selectedGroup.groupId, [selectedUser.userId]);
      setSelectedGroup(detail);
      setSelectedUser(null);
      setMemberSearch("");
      await loadGroups();
      setFeedback({ variant: "success", title: "成员已添加", message: `${selectedUser.displayName} 已加入 ${detail.name}。` });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "添加成员失败",
        message: error instanceof Error ? error.message : "请确认用户仍处于启用状态且未重复加入。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveMember = async (user: GroupMember) => {
    if (!selectedGroup || !window.confirm(`从 ${selectedGroup.name} 移除 ${user.displayName}？`)) return;

    setIsSaving(true);
    try {
      await removeUserFromGroup(selectedGroup.groupId, user.userId);
      setSelectedGroup(await fetchUserGroup(selectedGroup.groupId));
      await loadGroups();
      setFeedback({ variant: "success", title: "成员已移除", message: `${user.displayName} 已不再属于该用户组。` });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "移除成员失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const selectedMemberIds = new Set(selectedGroup?.members.map((member) => member.userId) ?? []);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="用户组"
        description="管理用户分组，便于批量分配权限。"
        actions={
          <Button variant="outline" onClick={() => void loadGroups()} disabled={isLoading}>
            <RefreshCw className="w-4 h-4 mr-2" /> 刷新
          </Button>
        }
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
        </Alert>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[240px_minmax(260px,1fr)_auto] gap-3 rounded-lg border border-border-cream bg-ivory p-4">
        <Input
          value={newGroup.name}
          onChange={(event) => setNewGroup((current) => ({ ...current, name: event.target.value }))}
          placeholder="用户组名称"
          className="bg-white"
        />
        <Input
          value={newGroup.description}
          onChange={(event) => setNewGroup((current) => ({ ...current, description: event.target.value }))}
          placeholder="描述"
          className="bg-white"
        />
        <Button variant="primary" onClick={handleCreateGroup} disabled={isSaving}>
          <Plus className="w-4 h-4 mr-2" /> 新建
        </Button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-6">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative w-80 max-w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
              <Input
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") handleSearch();
                }}
                placeholder="搜索用户组..."
                className="pl-9"
              />
            </div>
            <Button variant="outline" onClick={handleSearch} disabled={isLoading}>
              <Search className="w-4 h-4 mr-2" /> 查询
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>组名</TableHead>
                <TableHead>成员数</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建日期</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading && (
                <TableRow>
                  <TableCell colSpan={5} className="text-stone-gray">加载中...</TableCell>
                </TableRow>
              )}
              {!isLoading && groups.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-stone-gray">暂无用户组</TableCell>
                </TableRow>
              )}
              {!isLoading && groups.map((group) => (
                <TableRow key={group.groupId} className={selectedGroup?.groupId === group.groupId ? "bg-parchment" : ""}>
                  <TableCell>
                    <div className="font-medium text-near-black">{group.name}</div>
                    <div className="text-xs text-stone-gray">{group.description || group.groupId}</div>
                  </TableCell>
                  <TableCell>{group.memberCount} 人</TableCell>
                  <TableCell>
                    <Badge variant={group.status === "active" ? "success" : "inactive"}>
                      {group.status === "active" ? "启用" : "禁用"}
                    </Badge>
                  </TableCell>
                  <TableCell>{formatDate(group.createdAt)}</TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" onClick={() => void handleSelectGroup(group)} disabled={isSaving}>
                      管理成员
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-stone-gray">
            <span>共 {total} 个用户组</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled={isLoading || pageNo <= 1} onClick={() => setPageNo((current) => current - 1)}>
                <ChevronLeft className="w-4 h-4 mr-1" /> 上一页
              </Button>
              <span className="min-w-20 text-center text-near-black">{pageNo} / {totalPages}</span>
              <Button variant="outline" size="sm" disabled={isLoading || pageNo >= totalPages} onClick={() => setPageNo((current) => current + 1)}>
                下一页 <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </div>

        <aside className="rounded-xl border border-border-cream bg-ivory p-4 space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs text-stone-gray">成员管理</p>
              <h2 className="mt-1 font-serif text-xl text-near-black">{selectedGroup?.name || "请选择用户组"}</h2>
            </div>
            <Users className="w-5 h-5 text-terracotta" />
          </div>

          {selectedGroup ? (
            <>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-5 -translate-y-1/2 text-stone-gray z-10" />
                <Input
                  value={memberSearch}
                  onChange={(event) => {
                    setMemberSearch(event.target.value);
                    setSelectedUser(null);
                    setIsUserDropdownOpen(true);
                  }}
                  onFocus={() => setIsUserDropdownOpen(true)}
                  onBlur={() => window.setTimeout(() => setIsUserDropdownOpen(false), 120)}
                  placeholder="搜索用户加入当前组"
                  className="pl-9 bg-white"
                />
                {isUserDropdownOpen && (
                  <div className="absolute left-0 right-0 top-12 z-20 max-h-64 overflow-auto rounded-lg border border-border-cream bg-white shadow-lg">
                    {candidateUsers.length === 0 && (
                      <div className="px-3 py-2 text-sm text-stone-gray">没有可选用户</div>
                    )}
                    {candidateUsers.map((user) => (
                      <button
                        key={user.userId}
                        type="button"
                        disabled={selectedMemberIds.has(user.userId)}
                        onMouseDown={(event) => {
                          event.preventDefault();
                          if (selectedMemberIds.has(user.userId)) return;
                          setSelectedUser(user);
                          setMemberSearch(user.displayName);
                          setIsUserDropdownOpen(false);
                        }}
                        className="w-full px-3 py-2 text-left hover:bg-parchment disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-sm font-medium text-near-black">{user.displayName}</span>
                          {selectedMemberIds.has(user.userId) && <span className="text-xs text-stone-gray">已在组内</span>}
                        </div>
                        <div className="text-xs text-stone-gray">@{user.username} · {user.email || "无邮箱"}</div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <Button variant="primary" className="w-full" onClick={handleAddMember} disabled={isSaving || !selectedUser}>
                <Plus className="w-4 h-4 mr-2" /> 添加成员
              </Button>

              <div className="space-y-2">
                {selectedGroup.members.length === 0 && (
                  <div className="rounded-lg border border-dashed border-border-warm bg-parchment p-3 text-sm text-stone-gray">
                    当前用户组暂无成员。
                  </div>
                )}
                {selectedGroup.members.map((member) => (
                  <div key={member.groupMemberId} className="flex items-center justify-between gap-3 rounded-lg border border-border-cream bg-parchment p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-near-black">{member.displayName}</p>
                      <p className="truncate text-xs text-stone-gray">@{member.username} · {member.email || "无邮箱"}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-terracotta hover:bg-terracotta/10"
                      disabled={isSaving}
                      onClick={() => void handleRemoveMember(member)}
                    >
                      <Trash2 className="w-3 h-3 mr-1" /> 移除
                    </Button>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="rounded-lg border border-dashed border-border-warm bg-parchment p-4 text-sm text-stone-gray">
              从左侧选择一个用户组后，可以查看、添加或移除组成员。
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
