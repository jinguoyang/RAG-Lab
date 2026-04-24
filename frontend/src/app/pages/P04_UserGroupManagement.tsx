import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Search, Plus } from "lucide-react";

export function UserGroupManagement() {
  const groups = [
    { id: "grp-001", name: "Finance Team", members: 12, created: "2026-01-15" },
    { id: "grp-002", name: "HR Department", members: 8, created: "2026-02-20" },
    { id: "grp-003", name: "Engineering - Frontend", members: 24, created: "2026-03-05" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="User Groups"
        description="Manage groups of users to easily assign bulk permissions."
        actions={
          <Button variant="primary">
            <Plus className="w-4 h-4 mr-2" />
            Create Group
          </Button>
        }
      />

      <div className="flex items-center gap-4">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input placeholder="Search groups..." className="pl-9" />
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Group Name</TableHead>
            <TableHead>Members Count</TableHead>
            <TableHead>Created Date</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.map((group) => (
            <TableRow key={group.id}>
              <TableCell>
                <div className="font-medium text-near-black">{group.name}</div>
                <div className="text-xs text-stone-gray font-mono">{group.id}</div>
              </TableCell>
              <TableCell>{group.members} users</TableCell>
              <TableCell>{group.created}</TableCell>
              <TableCell>
                <Button variant="ghost" size="sm">Manage Members</Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
