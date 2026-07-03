import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { Ban, ChevronLeft, ChevronRight, Edit, Pencil, Power, RefreshCw, Save, Search, UserPlus, X } from "lucide-react";
import { chooseActiveDictionaryValue, dictionaryItemsToOptions, dictionaryLabel, fetchDictionaryBundle } from "../services/dictionaryService";
import { createUser, disableUser, fetchUsers, updateUser, updateUserStatus } from "../services/userGroupService";
import type { PlatformRole, UserSummary } from "../types/userGroup";
import type { DictionaryItemDTO } from "../types/dictionary";

const PAGE_SIZE = 10;

const ROLE_LABELS: Record<PlatformRole, string> = {
  platform_admin: "平台管理员",
  platform_user: "平台用户",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isValidOptionalEmail(value: string): boolean {
  const email = value.trim();
  return !email || EMAIL_PATTERN.test(email);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function UserManagement() {
  const confirmDialog = useConfirmDialog();
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [keyword, setKeyword] = useState("");
  const [pageNo, setPageNo] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ variant: "success" | "error"; title: string; message: string } | null>(null);
  const [newUser, setNewUser] = useState({
    username: "",
    displayName: "",
    email: "",
    platformRole: "platform_user" as PlatformRole,
    securityLevel: "public",
  });
  const [editingUser, setEditingUser] = useState<UserSummary | null>(null);
  const [userEditForm, setUserEditForm] = useState({
    displayName: "",
    email: "",
    platformRole: "platform_user" as PlatformRole,
    securityLevel: "public",
  });
  const [platformRoleItems, setPlatformRoleItems] = useState<DictionaryItemDTO[]>([]);
  const [securityLevelItems, setSecurityLevelItems] = useState<DictionaryItemDTO[]>([]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const platformRoleOptions = dictionaryItemsToOptions(platformRoleItems);
  const securityLevelOptions = dictionaryItemsToOptions(securityLevelItems);

  const loadUsers = useCallback(async (nextKeyword = keyword, nextPageNo = pageNo) => {
    setIsLoading(true);
    try {
      const page = await fetchUsers({ keyword: nextKeyword.trim(), pageNo: nextPageNo, pageSize: PAGE_SIZE });
      setUsers(page.items);
      setTotal(page.total);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户列表加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务状态。",
      });
    } finally {
      setIsLoading(false);
    }
  }, [keyword, pageNo]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadUsers();
    }, 250);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [loadUsers]);

  useEffect(() => {
    void fetchDictionaryBundle(["platform_role", "security_level"]).then((bundle) => {
      setPlatformRoleItems(bundle.platform_role);
      setSecurityLevelItems(bundle.security_level);
      setNewUser((current) => ({
        ...current,
        platformRole: chooseActiveDictionaryValue(bundle.platform_role, current.platformRole, "platform_user") as PlatformRole,
        securityLevel: chooseActiveDictionaryValue(bundle.security_level, current.securityLevel, "public"),
      }));
      setUserEditForm((current) => ({
        ...current,
        platformRole: chooseActiveDictionaryValue(bundle.platform_role, current.platformRole, "platform_user") as PlatformRole,
        securityLevel: chooseActiveDictionaryValue(bundle.security_level, current.securityLevel, "public"),
      }));
    });
  }, []);

  const handleCreateUser = async () => {
    if (!newUser.username.trim() || !newUser.displayName.trim()) {
      setFeedback({ variant: "error", title: "用户信息不完整", message: "用户名和显示名称不能为空。" });
      return;
    }
    if (!isValidOptionalEmail(newUser.email)) {
      setFeedback({ variant: "error", title: "邮箱格式不正确", message: "请输入类似 user@example.com 的邮箱地址，或留空。" });
      return;
    }

    const email = newUser.email.trim();
    setIsSaving(true);
    try {
      await createUser({
        username: newUser.username.trim(),
        displayName: newUser.displayName.trim(),
        email: email || null,
        platformRole: newUser.platformRole,
        securityLevel: newUser.securityLevel,
      });
      setNewUser({
        username: "",
        displayName: "",
        email: "",
        platformRole: chooseActiveDictionaryValue(platformRoleItems, "platform_user", "platform_user") as PlatformRole,
        securityLevel: chooseActiveDictionaryValue(securityLevelItems, "public", "public"),
      });
      setPageNo(1);
      setKeyword("");
      setFeedback({ variant: "success", title: "用户已创建", message: "新用户已写入平台用户表。" });
      await loadUsers("", 1);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户创建失败",
        message: error instanceof Error ? error.message : "请检查用户名是否重复。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const startEditUser = (user: UserSummary) => {
    setEditingUser(user);
    setUserEditForm({
      displayName: user.displayName,
      email: user.email ?? "",
      platformRole: chooseActiveDictionaryValue(platformRoleItems, user.platformRole, "platform_user") as PlatformRole,
      securityLevel: chooseActiveDictionaryValue(securityLevelItems, user.securityLevel, "public"),
    });
    setFeedback(null);
  };

  const handleSaveUser = async () => {
    if (!editingUser) return;
    if (!userEditForm.displayName.trim() || !userEditForm.securityLevel.trim()) {
      setFeedback({ variant: "error", title: "用户信息不完整", message: "显示名称和密级不能为空。" });
      return;
    }
    if (!isValidOptionalEmail(userEditForm.email)) {
      setFeedback({ variant: "error", title: "邮箱格式不正确", message: "请输入类似 user@example.com 的邮箱地址，或留空。" });
      return;
    }

    const email = userEditForm.email.trim();
    setIsSaving(true);
    try {
      await updateUser(editingUser.userId, {
        displayName: userEditForm.displayName.trim(),
        email: email || null,
        platformRole: userEditForm.platformRole,
        securityLevel: userEditForm.securityLevel.trim(),
      });
      await loadUsers();
      setEditingUser(null);
      setFeedback({ variant: "success", title: "用户已更新", message: `${userEditForm.displayName.trim()} 的资料已保存。` });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "用户更新失败",
        message: error instanceof Error ? error.message : "请检查输入后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleDisableUser = async (user: UserSummary) => {
    const confirmed = await confirmDialog({
      title: "确认禁用用户",
      description: "禁用后，该用户将无法作为 active 主体参与后续授权，请确认这是预期操作。",
      detail: (
        <>
          用户：{user.displayName}
          <br />
          账号：@{user.username}
        </>
      ),
      confirmText: "确认禁用",
      variant: "destructive",
    });

    if (!confirmed) return;

    setIsSaving(true);
    try {
      await disableUser(user.userId);
      await loadUsers();
      setFeedback({ variant: "success", title: "用户已禁用", message: `${user.displayName} 已无法作为 active 主体参与授权。` });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "禁用失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleEnableUser = async (user: UserSummary) => {
    setIsSaving(true);
    try {
      await updateUserStatus(user.userId, "active");
      await loadUsers();
      setFeedback({ variant: "success", title: "用户已恢复", message: `${user.displayName} 已恢复为启用状态。` });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "恢复失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <PageHeader
        title="用户管理"
        description="管理平台用户、角色和访问状态。"
        actions={
          <Button variant="outline" onClick={() => void loadUsers()} disabled={isLoading}>
            <RefreshCw className="w-4 h-4 mr-2" /> 刷新
          </Button>
        }
      />

      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
        </Alert>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[160px_200px_minmax(220px,1fr)_160px_140px_auto] gap-3 rounded-lg border border-border-cream bg-ivory p-4">
        <Input
          value={newUser.username}
          onChange={(event) => setNewUser((current) => ({ ...current, username: event.target.value }))}
          placeholder="用户名"
          className="bg-white"
        />
        <Input
          value={newUser.displayName}
          onChange={(event) => setNewUser((current) => ({ ...current, displayName: event.target.value }))}
          placeholder="显示名称"
          className="bg-white"
        />
        <Input
          value={newUser.email}
          onChange={(event) => setNewUser((current) => ({ ...current, email: event.target.value }))}
          placeholder="邮箱"
          className="bg-white"
        />
        <select
          value={newUser.platformRole}
          onChange={(event) => setNewUser((current) => ({ ...current, platformRole: event.target.value as PlatformRole }))}
          className="h-10 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
        >
          {platformRoleOptions.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.label}
            </option>
          ))}
        </select>
        <select
          value={newUser.securityLevel}
          onChange={(event) => setNewUser((current) => ({ ...current, securityLevel: event.target.value }))}
          className="h-10 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
        >
          {securityLevelOptions.map((option) => (
            <option key={option.value} value={option.value} disabled={option.disabled}>
              {option.label}
            </option>
          ))}
        </select>
        <Button variant="primary" onClick={handleCreateUser} disabled={isSaving}>
          <UserPlus className="w-4 h-4 mr-2" /> 新建
        </Button>
      </div>

      {editingUser && (
        <div className="rounded-lg border border-border-warm bg-ivory p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs text-stone-gray">编辑用户</p>
              <h2 className="font-serif text-xl text-near-black">@{editingUser.username}</h2>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setEditingUser(null)} disabled={isSaving}>
              <X className="w-4 h-4 mr-1" /> 取消
            </Button>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-[220px_minmax(240px,1fr)_180px_160px_auto] gap-3">
            <Input
              value={userEditForm.displayName}
              onChange={(event) => setUserEditForm((current) => ({ ...current, displayName: event.target.value }))}
              placeholder="显示名称"
              className="bg-white"
            />
            <Input
              value={userEditForm.email}
              onChange={(event) => setUserEditForm((current) => ({ ...current, email: event.target.value }))}
              placeholder="邮箱"
              className="bg-white"
            />
            <select
              value={userEditForm.platformRole}
              onChange={(event) => setUserEditForm((current) => ({ ...current, platformRole: event.target.value as PlatformRole }))}
              className="h-10 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
            >
              {platformRoleOptions.map((option) => (
                <option key={option.value} value={option.value} disabled={option.disabled}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              value={userEditForm.securityLevel}
              onChange={(event) => setUserEditForm((current) => ({ ...current, securityLevel: event.target.value }))}
              className="h-10 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
            >
              {securityLevelOptions.map((option) => (
                <option key={option.value} value={option.value} disabled={option.disabled}>
                  {option.label}
                </option>
              ))}
            </select>
            <Button variant="primary" onClick={() => void handleSaveUser()} disabled={isSaving}>
              <Save className="w-4 h-4 mr-2" /> 保存
            </Button>
          </div>
        </div>
      )}

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
            placeholder="按姓名、用户名或邮箱搜索..."
            className="pl-9"
          />
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>用户</TableHead>
            <TableHead>邮箱</TableHead>
            <TableHead>平台角色</TableHead>
            <TableHead>密级</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>更新时间</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading && (
            <TableRow>
              <TableCell colSpan={7} className="text-stone-gray">加载中...</TableCell>
            </TableRow>
          )}
          {!isLoading && users.length === 0 && (
            <TableRow>
              <TableCell colSpan={7} className="text-stone-gray">暂无用户</TableCell>
            </TableRow>
          )}
          {!isLoading && users.map((user) => (
            <TableRow key={user.userId}>
              <TableCell>
                <div className="font-medium text-near-black">{user.displayName}</div>
                <div className="text-xs text-stone-gray">@{user.username}</div>
              </TableCell>
              <TableCell>{user.email || "-"}</TableCell>
              <TableCell>
                <Badge variant={user.platformRole === "platform_admin" ? "active" : "default"}>
                  {dictionaryLabel(platformRoleItems, user.platformRole, ROLE_LABELS[user.platformRole])}
                </Badge>
              </TableCell>
              <TableCell>{dictionaryLabel(securityLevelItems, user.securityLevel, user.securityLevel)}</TableCell>
              <TableCell>
                <Badge variant={user.status === "active" ? "success" : "inactive"}>
                  {user.status === "active" ? "启用" : "禁用"}
                </Badge>
              </TableCell>
              <TableCell>{formatDate(user.updatedAt)}</TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-2">
                  <Button variant="ghost" size="sm" disabled={isSaving} title="编辑" onClick={() => startEditUser(user)}>
                    <Edit className="w-4 h-4 mr-1" />
                  </Button>
                  {user.status === "active" ? (
                    <Button variant="ghost" size="sm" disabled={isSaving} title="禁用" onClick={() => void handleDisableUser(user)}>
                     <Ban className="w-4 h-4 mr-1" />
                    </Button>
                  ) : (
                    <Button variant="ghost" size="sm" disabled={isSaving} title="启用" onClick={() => void handleEnableUser(user)}>
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
        <span>共 {total} 个用户</span>
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
    </div>
  );
}
