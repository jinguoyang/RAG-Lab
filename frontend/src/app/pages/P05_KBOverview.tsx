import { useEffect, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Alert } from "../components/rag/Alert";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Button } from "../components/rag/Button";
import { StatusBadge } from "../components/rag/Badge";
import { Upload, Settings, RefreshCw } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { fetchKnowledgeBase } from "../services/knowledgeBaseService";
import type { KnowledgeBase } from "../types/knowledgeBase";

export function KBOverview() {
  const navigate = useNavigate();
  const { kbId } = useParams();
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const recentJobs = [
    { id: "job-1092", type: "文档入库", status: "success", time: "10 分钟前" },
    { id: "job-1091", type: "图谱构建", status: "running", time: "1 小时前" },
    { id: "job-1090", type: "文档入库", status: "failed", time: "2 小时前" },
  ];

  useEffect(() => {
    if (!kbId) {
      setErrorMessage("缺少知识库 ID。");
      setIsLoading(false);
      return;
    }

    let ignore = false;
    setIsLoading(true);
    setErrorMessage(null);
    fetchKnowledgeBase(kbId)
      .then((data) => {
        if (!ignore) {
          setKnowledgeBase(data);
        }
      })
      .catch(() => {
        if (!ignore) {
          setErrorMessage("知识库详情读取失败，请确认该知识库仍可访问。");
        }
      })
      .finally(() => {
        if (!ignore) {
          setIsLoading(false);
        }
      });

    return () => {
      ignore = true;
    };
  }, [kbId]);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <PageHeader
        title={knowledgeBase?.name || "知识库概览"}
        description={knowledgeBase?.description || "查看该知识库的核心指标和最近活动。"}
        actions={
          <>
            <Button variant="outline" onClick={() => navigate(`/kb/${kbId}/config`)}>
              <Settings className="w-4 h-4 mr-2" /> 配置
            </Button>
            <Button variant="primary" onClick={() => navigate(`/kb/${kbId}/docs`)}>
              <Upload className="w-4 h-4 mr-2" /> 上传文档
            </Button>
          </>
        }
      />

      {errorMessage && (
        <Alert variant="error" title="加载失败">
          {errorMessage}
        </Alert>
      )}

      {isLoading && (
        <Card className="animate-pulse">
          <CardContent>
            <div className="h-5 w-64 rounded bg-border-warm" />
            <div className="mt-3 h-4 w-96 rounded bg-border-cream" />
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>文档总数</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">142</div>
            <p className="text-sm text-stone-gray mt-1">12 份待索引</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>有效 Chunk</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">15.2K</div>
            <p className="text-sm text-stone-gray mt-1">平均每篇约 107 个 chunk</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>QA 会话（30 天）</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">1,894</div>
            <p className="text-sm text-stone-gray mt-1">准确率提升 24%</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>系统健康度</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-success-green"></span>
              <span className="text-lg font-medium text-near-black">健康</span>
            </div>
            <p className="text-sm text-stone-gray mt-2">向量与图谱同步正常</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="col-span-2">
          <h2 className="font-serif text-xl mb-4">最近作业</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>作业 ID</TableHead>
                  <TableHead>类型</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>时间</TableHead>
                  <TableHead>操作</TableHead>
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
                          <RefreshCw className="w-3 h-3 mr-1" /> 重试
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
           <h2 className="font-serif text-xl mb-4">当前配置</h2>
           <Card>
            <CardContent className="space-y-4 pt-6">
              <div>
                <p className="text-xs text-stone-gray mb-1">生效版本</p>
                <p className="font-medium text-near-black">{knowledgeBase?.activeConfigRevisionId || "未配置"}</p>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">检索策略</p>
                <p className="text-near-black">
                  Dense
                  {knowledgeBase?.sparseIndexEnabled ? " + Sparse" : ""}
                  {knowledgeBase?.graphIndexEnabled ? " + Graph" : ""}
                </p>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">默认安全级别</p>
                <p className="text-near-black">{knowledgeBase?.defaultSecurityLevel || "public"}</p>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">状态</p>
                <p className="text-near-black">{knowledgeBase?.status || "active"}</p>
              </div>
              <Button variant="outline" className="w-full mt-4" onClick={() => navigate(`/kb/${kbId}/qa`)}>
                测试配置
              </Button>
            </CardContent>
           </Card>
        </div>
      </div>
    </div>
  );
}
