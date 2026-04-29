import { useEffect, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Alert } from "../components/rag/Alert";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Button } from "../components/rag/Button";
import { StatusBadge } from "../components/rag/Badge";
import { AlertTriangle, FileWarning, ShieldCheck, Upload, Settings, RefreshCw } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { fetchKnowledgeBase } from "../services/knowledgeBaseService";
import type { KnowledgeBase } from "../types/knowledgeBase";
import { fetchDocumentQualitySummary } from "../services/documentService";
import type { DocumentQualitySummaryDTO } from "../types/document";

export function KBOverview() {
  const navigate = useNavigate();
  const { kbId } = useParams();
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [qualitySummary, setQualitySummary] = useState<DocumentQualitySummaryDTO | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const governanceTodoCount = qualitySummary
    ? qualitySummary.failedVersionCount
      + qualitySummary.emptyChunkCount
      + qualitySummary.duplicateChunkGroupCount
      + qualitySummary.permissionAnomalyCount
    : 0;

  useEffect(() => {
    if (!kbId) {
      setErrorMessage("缺少知识库 ID。");
      setIsLoading(false);
      return;
    }

    let ignore = false;
    setIsLoading(true);
    setErrorMessage(null);
    Promise.all([fetchKnowledgeBase(kbId), fetchDocumentQualitySummary(kbId)])
      .then(([kb, quality]) => {
        if (!ignore) {
          setKnowledgeBase(kb);
          setQualitySummary(quality);
        }
      })
      .catch(() => {
        if (!ignore) {
          setErrorMessage("知识库治理概览读取失败，请确认该知识库仍可访问。");
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
            <div className="text-3xl font-serif text-near-black">{qualitySummary?.documentCount ?? "-"}</div>
            <p className="text-sm text-stone-gray mt-1">来自文档质量检查接口</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>有效 Chunk</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">{qualitySummary?.activeChunkCount ?? "-"}</div>
            <p className="text-sm text-stone-gray mt-1">排除治理标记前的 active 真值</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>治理待办</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-serif text-near-black">{qualitySummary ? governanceTodoCount : "-"}</div>
            <p className="text-sm text-stone-gray mt-1">解析、Chunk、权限摘要异常</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>质量状态</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {governanceTodoCount > 0 ? (
                <AlertTriangle className="w-5 h-5 text-warning-amber" />
              ) : (
                <ShieldCheck className="w-5 h-5 text-success-green" />
              )}
              <span className="text-lg font-medium text-near-black">{governanceTodoCount > 0 ? "需治理" : "健康"}</span>
            </div>
            <p className="text-sm text-stone-gray mt-2">
              {qualitySummary ? `${qualitySummary.issues.length} 条诊断样例` : "等待诊断结果"}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="col-span-2">
          <h2 className="font-serif text-xl mb-4">治理待办</h2>
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>类型</TableHead>
                  <TableHead>级别</TableHead>
                  <TableHead>数量</TableHead>
                  <TableHead>说明</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(qualitySummary?.issues ?? []).slice(0, 6).map((issue, index) => (
                  <TableRow key={`${issue.issueType}-${issue.chunkId ?? issue.versionId ?? index}`}>
                    <TableCell>{issue.issueType}</TableCell>
                    <TableCell>
                      <StatusBadge status={issue.severity === "high" ? "failed" : issue.severity === "medium" ? "running" : "success"} />
                    </TableCell>
                    <TableCell>{issue.count}</TableCell>
                    <TableCell>{issue.message}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" className="text-terracotta" onClick={() => navigate(`/kb/${kbId}/docs`)}>
                        <FileWarning className="w-3 h-3 mr-1" /> 查看
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {qualitySummary?.issues.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>暂无治理待办。</TableCell>
                  </TableRow>
                )}
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
              <Button variant="outline" className="w-full" onClick={() => navigate(`/kb/${kbId}/docs`)}>
                <RefreshCw className="w-4 h-4 mr-2" /> 文档治理
              </Button>
            </CardContent>
           </Card>
        </div>
      </div>
    </div>
  );
}
