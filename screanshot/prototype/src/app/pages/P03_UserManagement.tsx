import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { StatusBadge } from "../components/rag/Badge";
import { Search, UserPlus } from "lucide-react";

export function UserManagement() {
  const users = [
    { id: "usr-001", username: "admin", name: "Admin User", email: "admin@example.com", role: "Platform Admin", status: "active" },
    { id: "usr-002", username: "jdoe", name: "John Doe", email: "jdoe@example.com", role: "KB Editor", status: "active" },
    { id: "usr-003", username: "asmith", name: "Alice Smith", email: "asmith@example.com", role: "QA Operator", status: "inactive" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="User Management"
        description="Manage platform users, roles, and access status."
        actions={
          <Button variant="primary">
            <UserPlus className="w-4 h-4 mr-2" />
            Add User
          </Button>
        }
      />

      <div className="flex items-center gap-4">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input placeholder="Search users by name or email..." className="pl-9" />
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>User</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Actions</TableHead>
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
                <Button variant="ghost" size="sm">Edit</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
