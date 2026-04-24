import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Search, Plus } from "lucide-react";

export function UserGroupManagement() {
  const groups = [
    { id: "grp-001", name: "财务团队", members: 12, created: "2026-01-15" },
    { id: "grp-002", name: "人力资源部", members: 8, created: "2026-02-20" },
    { id: "grp-003", name: "前端工程组", members: 24, created: "2026-03-05" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="用户组"
        description="管理用户分组，便于批量分配权限。"
        actions={
          <Button variant="primary">
            <Plus className="w-4 h-4 mr-2" />
            新建用户组
          </Button>
        }
      />

      <div className="flex items-center gap-4">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input placeholder="搜索用户组..." className="pl-9" />
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>组名</TableHead>
            <TableHead>成员数</TableHead>
            <TableHead>创建日期</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.map((group) => (
            <TableRow key={group.id}>
              <TableCell>
                <div className="font-medium text-near-black">{group.name}</div>
                <div className="text-xs text-stone-gray font-mono">{group.id}</div>
              </TableCell>
              <TableCell>{group.members} 人</TableCell>
              <TableCell>{group.created}</TableCell>
              <TableCell>
                <Button variant="ghost" size="sm">管理成员</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
