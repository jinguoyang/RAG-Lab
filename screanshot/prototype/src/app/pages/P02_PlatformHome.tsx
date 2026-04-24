import { useNavigate } from "react-router";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { StatusBadge } from "../components/rag/Badge";
import { Search, Plus } from "lucide-react";

export function PlatformHome() {
  const navigate = useNavigate();

  const kbs = [
    { id: "kb-001", name: "Financial Q3 Reports", desc: "Internal financial reports and statements.", status: "active", updated: "2026-04-22 10:30" },
    { id: "kb-002", name: "HR Policies", desc: "Company guidelines and employee handbooks.", status: "active", updated: "2026-04-21 15:45" },
    { id: "kb-003", name: "Product Specs 2026", desc: "Technical product specifications and roadmaps.", status: "inactive", updated: "2026-04-10 09:12" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <PageHeader
        title="Knowledge Bases"
        description="Select a knowledge base to enter the workspace or create a new one."
        actions={
          <Button variant="primary">
            <Plus className="w-4 h-4 mr-2" />
            Create Knowledge Base
          </Button>
        }
      />

      <div className="mt-8 mb-6 flex items-center gap-4">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input placeholder="Search knowledge bases..." className="pl-9" />
        </div>
        <div className="text-sm text-stone-gray ml-auto">
          Showing {kbs.length} Knowledge Bases
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {kbs.map((kb) => (
          <Card key={kb.id} className="hover:border-terracotta cursor-pointer transition-colors" onClick={() => navigate(`/kb/${kb.id}`)}>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <CardTitle>{kb.name}</CardTitle>
                <StatusBadge status={kb.status as any} />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-stone-gray mb-4 line-clamp-2 h-10">{kb.desc}</p>
              <div className="text-xs font-mono text-olive-gray">ID: {kb.id}</div>
              <div className="text-xs text-stone-gray mt-1">Updated: {kb.updated}</div>
            </CardContent>
            <CardFooter className="pt-2">
              <Button variant="ghost" size="sm" className="w-full justify-center">
                Enter Workspace
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
