import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { Ban, ChevronLeft, ChevronRight, Edit, Pencil, Plus, Power, RefreshCw, Save, Search, Trash2, Users, X } from "lucide-react";
import {
  addUsersToGroup,
  createUserGroup,
  fetchUserGroup,
  fetchUserGroups,
  removeUserFromGroup,
  updateUserGroup,
} from "../services/userGroupService";
import type { GroupMember, GroupStatus, UserGroupDetail, UserGroupSummary } from "../types/userGroup";
import { SubjectSearchDropdown } from "../components/rag/SubjectSearchDropdown";

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
  const confirmDialog = useConfirmDialog();
  const [groups, setGroups] = useState<UserGroupSummary[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<UserGroupDetail | null>(null);
  const [keyword, setKeyword] = useState("");
  const [pageNo, setPageNo] = useState(1);
  const [total, setTotal] = useState(0);
  const [newGroup, setNewGroup] = useState({ name: "", description: "" });
  const [editingGroup, setEditingGroup] = useState<UserGroupSummary | UserGroupDetail | null>(null);
  const [groupEditForm, setGroupEditForm] = useState({ name: "", description: "" });
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [selectedUserLabel, setSelectedUserLabel] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ variant: "success" | "error"; title: string; message: string } | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const isSelectedGroupActive = selectedGroup?.status === "active";

  const loadGroups = useCallback(async (nextKeyword = keyword, nextPageNo = pageNo) => {
    setIsLoading(true);
    try {
      const page = await fetchUserGroups({ keyword: nextKeyword.trim(), pageNo: nextPageNo, pageSize: PAGE_SIZE });
      setGroups(page.items);
      setTotal(page.total);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户组加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务状态。",
      });
    } finally {
      setIsLoading(false);
    }
  }, [keyword, pageNo]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadGroups();
    }, 250);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadGroups]);

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
      setKeyword("");
      setSelectedGroup(await fetchUserGroup(group.groupId));
      setFeedback({ variant: "success", title: "用户组已创建", message: "可以继续在右侧添加组成员。" });
      await loadGroups("", 1);
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
      setSelectedUserId(null);
      setSelectedUserLabel("");
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

  const startEditGroup = (group: UserGroupSummary | UserGroupDetail) => {
    setEditingGroup(group);
    setGroupEditForm({
      name: group.name,
      description: group.description ?? "",
    });
    setFeedback(null);
  };

  const handleSaveGroup = async () => {
    if (!editingGroup) return;
    if (!groupEditForm.name.trim()) {
      setFeedback({ variant: "error", title: "用户组信息不完整", message: "用户组名称不能为空。" });
      return;
    }

    setIsSaving(true);
    try {
      const updated = await updateUserGroup(editingGroup.groupId, {
        name: groupEditForm.name.trim(),
        description: groupEditForm.description.trim() || null,
      });
      if (selectedGroup?.groupId === updated.groupId) {
        setSelectedGroup(await fetchUserGroup(updated.groupId));
      }
      await loadGroups();
      setEditingGroup(null);
      setFeedback({ variant: "success", title: "用户组已更新", message: `${updated.name} 的名称和描述已保存。` });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户组更新失败",
        message: error instanceof Error ? error.message : "请检查组名是否重复。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdateGroupStatus = async (group: UserGroupSummary | UserGroupDetail, status: GroupStatus) => {
    const isDisabling = status === "disabled";
    const confirmed = await confirmDialog({
      title: isDisabling ? "确认停用用户组" : "确认恢复用户组",
      description: isDisabling
        ? "停用后，该用户组不再作为 active 权限主体参与后续授权计算，历史成员关系和审计记录会保留。"
        : "恢复后，该用户组会重新作为 active 主体参与后续授权计算。",
      detail: (
        <>
          用户组：{group.name}
          <br />
          当前成员数：{group.memberCount} 人
        </>
      ),
      confirmText: isDisabling ? "确认停用" : "确认恢复",
      variant: isDisabling ? "destructive" : "default",
    });

    if (!confirmed) return;

    setIsSaving(true);
    try {
      const updated = await updateUserGroup(group.groupId, { status });
      if (selectedGroup?.groupId === updated.groupId) {
        setSelectedGroup(await fetchUserGroup(updated.groupId));
      }
      await loadGroups();
      setFeedback({
        variant: "success",
        title: isDisabling ? "用户组已停用" : "用户组已恢复",
        message: `${updated.name} 已${isDisabling ? "停用" : "恢复启用"}。`,
      });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: isDisabling ? "停用用户组失败" : "恢复用户组失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddMember = async () => {
    if (!selectedGroup || !selectedUserId) {
      setFeedback({ variant: "error", title: "未选择成员", message: "请先选择用户组和要加入的用户。" });
      return;
    }
    if (!isSelectedGroupActive) {
      setFeedback({ variant: "error", title: "用户组已停用", message: "请先恢复启用用户组，再添加新成员。" });
      return;
    }

    setIsSaving(true);
    try {
      const detail = await addUsersToGroup(selectedGroup.groupId, [selectedUserId]);
      setSelectedGroup(detail);
      setSelectedUserId(null);
      setSelectedUserLabel("");
      await loadGroups();
      setFeedback({ variant: "success", title: "成员已添加", message: `${selectedUserLabel} 已加入 ${detail.name}。` });
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
    if (!selectedGroup) return;

    const confirmed = await confirmDialog({
      title: "确认移除成员",
      description: "移除后，该用户将不再继承当前用户组的权限。",
      detail: (
        <>
          用户组：{selectedGroup.name}
          <br />
          成员：{user.displayName}
        </>
      ),
      confirmText: "确认移除",
      variant: "destructive",
    });

    if (!confirmed) return;

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

      {editingGroup && (
        <div className="rounded-lg border border-border-warm bg-ivory p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs text-stone-gray">编辑用户组</p>
              <h2 className="font-serif text-xl text-near-black">{editingGroup.name}</h2>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setEditingGroup(null)} disabled={isSaving}>
              <X className="w-4 h-4 mr-1" /> 取消
            </Button>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-[240px_minmax(260px,1fr)_auto] gap-3">
            <Input
              value={groupEditForm.name}
              onChange={(event) => setGroupEditForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="用户组名称"
              className="bg-white"
            />
            <Input
              value={groupEditForm.description}
              onChange={(event) => setGroupEditForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="描述"
              className="bg-white"
            />
            <Button variant="primary" onClick={() => void handleSaveGroup()} disabled={isSaving}>
              <Save className="w-4 h-4 mr-2" /> 保存
            </Button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-6">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative w-80 max-w-full">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
              <Input
                value={keyword}
                onChange={(event) => {
                  setPageNo(1);
                  setKeyword(event.target.value);
                }}
                placeholder="搜索用户组..."
                className="pl-9"
              />
            </div>
          </div>

          <Table tableClassName="min-w-0 table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[42%]">组名</TableHead>
                <TableHead className="w-[72px]">成员数</TableHead>
                <TableHead className="w-[72px]">状态</TableHead>
                <TableHead className="w-[104px]">创建日期</TableHead>
                <TableHead className="w-[168px]">操作</TableHead>
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
                <TableRow
                  key={group.groupId}
                  onClick={() => void handleSelectGroup(group)}
                  className={selectedGroup?.groupId === group.groupId ? "bg-parchment" : ""}
                >
                  <TableCell className="min-w-0">
                    <div className="truncate font-medium text-near-black">{group.name}</div>
                    <div className="truncate text-xs text-stone-gray">{group.description || group.groupId}</div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{group.memberCount} 人</TableCell>
                  <TableCell>
                    <Badge variant={group.status === "active" ? "success" : "inactive"}>
                      {group.status === "active" ? "启用" : "停用"}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">{formatDate(group.createdAt)}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1" onClick={(event) => event.stopPropagation()}>
                      <Button variant="ghost" size="sm" title="编辑" onClick={() => startEditGroup(group)} disabled={isSaving}>
                        <Edit className="w-4 h-4 mr-1" />
                      </Button>
                      {group.status === "active" ? (
                        <Button variant="ghost" size="sm" title="禁用" onClick={() => void handleUpdateGroupStatus(group, "disabled")} disabled={isSaving}>
                          <Ban className="w-4 h-4 mr-1" />
                        </Button>
                      ) : (
                        <Button variant="ghost" size="sm" title="启用" onClick={() => void handleUpdateGroupStatus(group, "active")} disabled={isSaving}>
                          <Power className="w-4 h-4 mr-1" />
                        </Button>
                      )}
                    </div>
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
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <h2 className="font-serif text-xl text-near-black">{selectedGroup?.name || "请选择用户组"}</h2>
                {selectedGroup && (
                  <Badge variant={selectedGroup.status === "active" ? "success" : "inactive"}>
                    {selectedGroup.status === "active" ? "启用" : "停用"}
                  </Badge>
                )}
              </div>
            </div>
            <Users className="w-5 h-5 text-terracotta" />
          </div>

          {selectedGroup ? (
            <>
              {!isSelectedGroupActive && (
                <div className="rounded-lg border border-border-warm bg-parchment p-3 text-sm text-stone-gray">
                  该用户组已停用，不再参与 active 权限计算；仍可移除成员以整理历史关系。
                </div>
              )}
              <SubjectSearchDropdown
                subjectType="user"
                excludedIds={selectedMemberIds}
                excludedLabel="已在组内"
                placeholder="搜索用户加入当前组"
                disabled={!isSelectedGroupActive}
                onSelect={(id, label) => {
                  setSelectedUserId(id);
                  setSelectedUserLabel(label);
                }}
              />
              <Button variant="primary" className="w-full" onClick={handleAddMember} disabled={isSaving || !selectedUserId || !isSelectedGroupActive}>
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
