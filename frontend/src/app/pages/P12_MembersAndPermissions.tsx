import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Search, UserPlus, ShieldAlert } from "lucide-react";

export function MembersAndPermissions() {
  const members = [
    { id: "bind-01", principal: "Admin User", type: "User", role: "KB Admin", source: "Direct", updated: "2026-04-20" },
    { id: "bind-02", principal: "Finance Team", type: "Group", role: "KB Editor", source: "Group Binding", updated: "2026-04-21" },
    { id: "bind-03", principal: "Alice Smith", type: "User", role: "QA Operator", source: "Direct", updated: "2026-04-22" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="Members & Permissions"
        description="Manage who can read, write, and execute QA within this knowledge base."
        actions={
          <Button variant="primary">
            <UserPlus className="w-4 h-4 mr-2" /> Add Member or Group
          </Button>
        }
      />

      <div className="bg-warning-amber/10 border border-warning-amber/20 rounded-lg p-4 flex gap-3 text-warning-amber text-sm mb-4">
        <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-near-black">Important Security Note</p>
          <p className="mt-1">Changes to role bindings take effect immediately. Users removed from the 'KB Reader' or 'QA Operator' role will lose access to run diagnostic queries.</p>
        </div>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input placeholder="Search by name..." className="pl-9" />
        </div>
        <select className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none">
          <option value="">All Roles</option>
          <option value="admin">KB Admin</option>
          <option value="editor">KB Editor</option>
          <option value="qa">QA Operator</option>
          <option value="reader">KB Reader</option>
        </select>
      </div>

      <div className="flex-1 overflow-auto border border-border-cream rounded-xl">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Principal (User / Group)</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-medium text-near-black">{m.principal}</TableCell>
                <TableCell>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${m.type === 'Group' ? 'bg-focus-blue/10 text-focus-blue' : 'bg-border-cream text-olive-gray'}`}>
                    {m.type}
                  </span>
                </TableCell>
                <TableCell>{m.role}</TableCell>
                <TableCell className="text-stone-gray">{m.source}</TableCell>
                <TableCell>{m.updated}</TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" className="text-terracotta hover:bg-terracotta/10">
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
