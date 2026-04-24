import { PageHeader } from "../components/rag/PageHeader";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Button } from "../components/rag/Button";
import { StatusBadge } from "../components/rag/Badge";
import { Upload, Settings, RefreshCw } from "lucide-react";
import { useNavigate, useParams } from "react-router";

export function KBOverview() {
  const navigate = useNavigate();
  const { kbId } = useParams();

  const recentJobs = [
    { id: "job-1092", type: "Document Ingest", status: "success", time: "10 mins ago" },
    { id: "job-1091", type: "Graph Build", status: "running", time: "1 hour ago" },
    { id: "job-1090", type: "Document Ingest", status: "failed", time: "2 hours ago" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title="Knowledge Base Overview"
        description="Core metrics and recent activity for this knowledge base."
        actions={
          <>
            <Button variant="outline" onClick={() => navigate(`/kb/${kbId}/config`)}>
              <Settings className="w-4 h-4 mr-2" /> Configure
            </Button>
            <Button variant="primary" onClick={() => navigate(`/kb/${kbId}/docs`)}>
              <Upload className="w-4 h-4 mr-2" /> Upload Documents
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Total Documents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">142</div>
            <p className="text-sm text-stone-gray mt-1">12 pending indexing</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Active Chunks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">15.2K</div>
            <p className="text-sm text-stone-gray mt-1">~107 chunks/doc avg</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>QA Sessions (30d)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">1,894</div>
            <p className="text-sm text-stone-gray mt-1">24% accuracy improvement</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>System Health</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-success-green"></span>
              <span className="text-lg font-medium text-near-black">Healthy</span>
            </div>
            <p className="text-sm text-stone-gray mt-2">Vector & Graph sync ok</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="col-span-2">
          <h2 className="font-serif text-xl mb-4">Recent Jobs</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentJobs.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell mono>{job.id}</TableCell>
                    <TableCell>{job.type}</TableCell>
                    <TableCell><StatusBadge status={job.status as any} /></TableCell>
                    <TableCell>{job.time}</TableCell>
                    <TableCell>
                      {job.status === 'failed' && (
                        <Button variant="ghost" size="sm" className="text-terracotta">
                          <RefreshCw className="w-3 h-3 mr-1" /> Retry
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        </div>
        <div>
           <h2 className="font-serif text-xl mb-4">Current Configuration</h2>
           <Card>
            <CardContent className="space-y-4 pt-6">
              <div>
                <p className="text-xs text-stone-gray mb-1">Active Revision</p>
                <p className="font-medium text-near-black">rev_042</p>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">Retrieval Strategy</p>
                <p className="text-near-black">Hybrid (Dense + Sparse) + Graph</p>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">Rerank Model</p>
                <p className="text-near-black">bge-reranker-v2-m3</p>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">Generation Model</p>
                <p className="text-near-black">claude-3-5-sonnet</p>
              </div>
              <Button variant="outline" className="w-full mt-4" onClick={() => navigate(`/kb/${kbId}/qa`)}>
                Test Configuration
              </Button>
            </CardContent>
           </Card>
        </div>
      </div>
    </div>
  );
}
