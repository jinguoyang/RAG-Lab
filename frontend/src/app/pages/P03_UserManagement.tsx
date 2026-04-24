import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { StatusBadge } from "../components/rag/Badge";
import { Search, UserPlus } from "lucide-react";

export function UserManagement() {
  const users = [
    { id: "usr-001", username: "admin", name: "管理员用户", email: "admin@example.com", role: "平台管理员", status: "active" },
    { id: "usr-002", username: "jdoe", name: "John Doe", email: "jdoe@example.com", role: "KB Editor", status: "active" },
    { id: "usr-003", username: "asmith", name: "Alice Smith", email: "asmith@example.com", role: "QA Operator", status: "inactive" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="用户管理"
        description="管理平台用户、角色和访问状态。"
        actions={
          <Button variant="primary">
            <UserPlus className="w-4 h-4 mr-2" />
            新增用户
          </Button>
        }
      />

      <div className="flex items-center gap-4">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input placeholder="按姓名或邮箱搜索用户..." className="pl-9" />
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>用户</TableHead>
            <TableHead>邮箱</TableHead>
            <TableHead>角色</TableHead>
            <TableHead>状态</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => (
            <TableRow key={user.id}>
              <TableCell>
                <div className="font-medium text-near-black">{user.name}</div>
                <div className="text-xs text-stone-gray">@{user.username}</div>
              </TableCell>
              <TableCell>{user.email}</TableCell>
              <TableCell>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-border-cream text-olive-gray">
                  {user.role}
                </span>
              </TableCell>
              <TableCell><StatusBadge status={user.status as any} /></TableCell>
              <TableCell>
                <Button variant="ghost" size="sm">编辑</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
