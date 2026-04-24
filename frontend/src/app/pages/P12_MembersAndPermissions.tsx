import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Input } from "../components/rag/Input";
import { Search, UserPlus, ShieldAlert } from "lucide-react";

export function MembersAndPermissions() {
  const members = [
    { id: "bind-01", principal: "管理员用户", type: "用户", role: "知识库管理员", source: "直接绑定", updated: "2026-04-20" },
    { id: "bind-02", principal: "财务团队", type: "用户组", role: "知识库编辑", source: "用户组绑定", updated: "2026-04-21" },
    { id: "bind-03", principal: "Alice Smith", type: "用户", role: "QA 操作员", source: "直接绑定", updated: "2026-04-22" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="成员与权限"
        description="管理谁可以在该知识库中读取、编辑和执行 QA。"
        actions={
          <Button variant="primary">
            <UserPlus className="w-4 h-4 mr-2" /> 添加成员或用户组
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

      <div className="flex items-center gap-4 shrink-0">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input placeholder="按名称搜索..." className="pl-9" />
        </div>
        <select className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none">
          <option value="">全部角色</option>
          <option value="admin">知识库管理员</option>
          <option value="editor">知识库编辑</option>
          <option value="qa">QA 操作员</option>
          <option value="reader">知识库读者</option>
        </select>
      </div>

      <div className="flex-1 overflow-auto border border-border-cream rounded-xl">
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
            {members.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-medium text-near-black">{m.principal}</TableCell>
                <TableCell>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${m.type === '用户组' ? 'bg-focus-blue/10 text-focus-blue' : 'bg-border-cream text-olive-gray'}`}>
                    {m.type}
                  </span>
                </TableCell>
                <TableCell>{m.role}</TableCell>
                <TableCell className="text-stone-gray">{m.source}</TableCell>
                <TableCell>{m.updated}</TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" className="text-terracotta hover:bg-terracotta/10">
                    移除
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
