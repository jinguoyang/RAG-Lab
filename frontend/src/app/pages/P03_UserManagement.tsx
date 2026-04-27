import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import { ChevronLeft, ChevronRight, RefreshCw, Search, UserPlus } from "lucide-react";
import { createUser, disableUser, fetchUsers } from "../services/userGroupService";
import type { PlatformRole, UserSummary } from "../types/userGroup";

const PAGE_SIZE = 10;

const ROLE_LABELS: Record<PlatformRole, string> = {
  platform_admin: "平台管理员",
  platform_user: "平台用户",
};

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
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [keyword, setKeyword] = useState("");
  const [queryKeyword, setQueryKeyword] = useState("");
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
  });

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    try {
      const page = await fetchUsers({ keyword: queryKeyword, pageNo, pageSize: PAGE_SIZE });
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
  }, [pageNo, queryKeyword]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const handleSearch = () => {
    const nextKeyword = keyword.trim();
    setPageNo(1);
    setQueryKeyword(nextKeyword);
    if (pageNo === 1 && queryKeyword === nextKeyword) {
      void loadUsers();
    }
  };

  const handleCreateUser = async () => {
    if (!newUser.username.trim() || !newUser.displayName.trim()) {
      setFeedback({ variant: "error", title: "用户信息不完整", message: "用户名和显示名称不能为空。" });
      return;
    }

    setIsSaving(true);
    try {
      await createUser({
        username: newUser.username.trim(),
        displayName: newUser.displayName.trim(),
        email: newUser.email.trim() || null,
        platformRole: newUser.platformRole,
        securityLevel: "public",
      });
      setNewUser({ username: "", displayName: "", email: "", platformRole: "platform_user" });
      setPageNo(1);
      setQueryKeyword("");
      setKeyword("");
      setFeedback({ variant: "success", title: "用户已创建", message: "新用户已写入平台用户表。" });
      if (pageNo === 1 && !queryKeyword) {
        await loadUsers();
      }
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

  const handleDisableUser = async (user: UserSummary) => {
    if (!window.confirm(`禁用用户 ${user.displayName}？`)) return;

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

      <div className="grid grid-cols-1 xl:grid-cols-[180px_220px_minmax(240px,1fr)_180px_auto] gap-3 rounded-lg border border-border-cream bg-ivory p-4">
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
          <option value="platform_user">平台用户</option>
          <option value="platform_admin">平台管理员</option>
        </select>
        <Button variant="primary" onClick={handleCreateUser} disabled={isSaving}>
          <UserPlus className="w-4 h-4 mr-2" /> 新增
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <div className="relative w-80 max-w-full">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") handleSearch();
            }}
            placeholder="按姓名、用户名或邮箱搜索..."
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
                  {ROLE_LABELS[user.platformRole]}
                </Badge>
              </TableCell>
              <TableCell>{user.securityLevel}</TableCell>
              <TableCell>
                <Badge variant={user.status === "active" ? "success" : "inactive"}>
                  {user.status === "active" ? "启用" : "禁用"}
                </Badge>
              </TableCell>
              <TableCell>{formatDate(user.updatedAt)}</TableCell>
              <TableCell>
                {user.status === "active" ? (
                  <Button variant="ghost" size="sm" disabled={isSaving} onClick={() => void handleDisableUser(user)}>
                    禁用
                  </Button>
                ) : (
                  <span className="text-sm text-stone-gray">已禁用</span>
                )}
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
  );
}
