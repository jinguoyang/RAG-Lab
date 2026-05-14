import { useEffect, useMemo, useState } from "react";
import { PageHeader } from "../components/rag/PageHeader";
import { Alert } from "../components/rag/Alert";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "../components/rag/Table";
import { Button } from "../components/rag/Button";
import { StatusBadge } from "../components/rag/Badge";
import { AlertTriangle, FileWarning, PlayCircle, ShieldCheck, Upload, Settings } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { fetchKnowledgeBase } from "../services/knowledgeBaseService";
import type { KnowledgeBase } from "../types/knowledgeBase";
import { fetchDocumentQualitySummary } from "../services/documentService";
import type { DocumentQualityIssueDTO, DocumentQualitySummaryDTO } from "../types/document";
import { createEvaluationRun, fetchEvaluationRuns } from "../services/qaRunService";
import type { EvaluationRunDTO } from "../types/qaRun";
import { fetchAuditLogs } from "../services/auditService";
import type { AuditLogDTO } from "../types/audit";
import { formatDateTime } from "../adapters/documentAdapter";

function isGovernanceAudit(action: string): boolean {
  return ["governance", "batch", "reparse", "index_sync"].some((keyword) => action.includes(keyword));
}

function governanceActionLabel(action: string): string {
  const labels: Record<string, string> = {
    "chunk.governance_update": "Chunk 治理标记",
    "document.batch_disable": "批量停用文档",
    "document.batch_rebuild_index": "批量重建索引",
    "document.reparse": "文档重解析",
    "index_sync.rebuild": "索引重建",
  };
  return labels[action] ?? action;
}

type RetrievalIndexRow = {
  channel: string;
  provider: string;
  status: "active" | "inactive";
};

/**
 * 构造检索与索引的统一展示行，确保 Dense 与 Milvus 始终绑定呈现。
 */
function buildRetrievalIndexRows(knowledgeBase: KnowledgeBase | null): RetrievalIndexRow[] {
  return [
    { channel: "Dense", provider: "Milvus", status: "active" },
    {
      channel: "Sparse",
      provider: "OpenSearch",
      status: knowledgeBase?.sparseIndexEnabled ? "active" : "inactive",
    },
    {
      channel: "Graph",
      provider: "Neo4j",
      status: knowledgeBase?.graphIndexEnabled ? "active" : "inactive",
    },
  ];
}

export function KBOverview() {
  const navigate = useNavigate();
  const { kbId } = useParams();
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [qualitySummary, setQualitySummary] = useState<DocumentQualitySummaryDTO | null>(null);
  const [recentGovernanceActions, setRecentGovernanceActions] = useState<AuditLogDTO[]>([]);
  const [evaluationRuns, setEvaluationRuns] = useState<EvaluationRunDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [validationLoading, setValidationLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    variant: "success" | "info" | "warning" | "error";
    title: string;
    message: string;
  } | null>(null);
  const governanceTodoCount = qualitySummary
    ? qualitySummary.failedVersionCount
      + qualitySummary.emptyChunkCount
      + qualitySummary.duplicateChunkGroupCount
      + qualitySummary.permissionAnomalyCount
    : 0;
  const latestEvaluation = useMemo(() => evaluationRuns[0] ?? null, [evaluationRuns]);

  async function loadGovernanceSideData(currentKbId: string) {
    const [auditResult, evaluationResult] = await Promise.allSettled([
      fetchAuditLogs({ kbId: currentKbId, pageSize: 20 }),
      fetchEvaluationRuns(currentKbId),
    ]);
    if (auditResult.status === "fulfilled") {
      setRecentGovernanceActions(auditResult.value.items.filter((item) => isGovernanceAudit(item.action)).slice(0, 5));
    }
    if (evaluationResult.status === "fulfilled") {
      setEvaluationRuns(evaluationResult.value.items.slice(0, 5));
    }
  }

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
          void loadGovernanceSideData(kbId);
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

  function openGovernanceIssue(issue: DocumentQualityIssueDTO) {
    if (issue.documentId) {
      navigate(`/kb/${kbId}/docs/${issue.documentId}`, {
        state: {
          governanceIssue: {
            issueType: issue.issueType,
            documentId: issue.documentId,
            versionId: issue.versionId,
            chunkId: issue.chunkId || issue.sampleChunkIds[0] || null,
            recommendedAction: issue.recommendedAction,
            targetStore: issue.targetStore,
          },
        },
      });
      return;
    }
    navigate(`/kb/${kbId}/docs`);
  }

  async function handleGovernanceValidation() {
    if (!kbId) return;
    setValidationLoading(true);
    try {
      const run = await createEvaluationRun(kbId, { remark: "P05 治理后验证" });
      await loadGovernanceSideData(kbId);
      setFeedback({
        variant: "success",
        title: "治理验证已触发",
        message: `已创建评估批次 ${run.evaluationRunId.slice(0, 8)}，可到 QA 历史查看详情。`,
      });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "治理验证失败",
        message: error instanceof Error ? error.message : "请确认评估样本已准备且当前账号有权限。",
      });
    } finally {
      setValidationLoading(false);
    }
  }

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
      {feedback && (
        <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
          {feedback.message}
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
                    <TableCell>
                      <div>{issue.message}</div>
                      {issue.sampleChunkIds.length > 0 && (
                        <div className="mt-1 text-xs text-stone-gray">
                          样例 Chunk：{issue.sampleChunkIds.map((item) => item.slice(0, 8)).join("、")}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" className="text-terracotta" onClick={() => openGovernanceIssue(issue)}>
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
                <p className="text-xs text-stone-gray mb-2">检索与索引</p>
                <div className="divide-y divide-border-cream border-y border-border-cream">
                  {buildRetrievalIndexRows(knowledgeBase).map((item) => (
                    <div key={item.channel} className="flex items-center justify-between gap-3 py-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-near-black">{item.channel}</p>
                        <p className="text-xs text-stone-gray">{item.provider}</p>
                      </div>
                      <StatusBadge status={item.status} />
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">默认安全级别</p>
                <p className="text-near-black">{knowledgeBase?.defaultSecurityLevel || "public"}</p>
              </div>
              <div>
                <p className="text-xs text-stone-gray mb-1">状态</p>
                <p className="text-near-black">{knowledgeBase?.status || "active"}</p>
              </div>
            </CardContent>
           </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>治理验证摘要</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="text-xs text-stone-gray">最近批次</p>
                <p className="mt-1 font-medium text-near-black">{latestEvaluation?.evaluationRunId.slice(0, 8) ?? "暂无"}</p>
              </div>
              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="text-xs text-stone-gray">通过率</p>
                <p className="mt-1 font-medium text-near-black">
                  {latestEvaluation ? `${(latestEvaluation.passRate * 100).toFixed(1)}%` : "-"}
                </p>
              </div>
              <div className="rounded-lg border border-border-cream bg-parchment p-3">
                <p className="text-xs text-stone-gray">样本数</p>
                <p className="mt-1 font-medium text-near-black">{latestEvaluation?.totalSamples ?? "-"}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" disabled={validationLoading} onClick={() => void handleGovernanceValidation()}>
                <PlayCircle className="w-4 h-4 mr-2" /> 验证治理效果
              </Button>
              <Button variant="outline" onClick={() => navigate(`/kb/${kbId}/history`)}>
                查看评估批次
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>最近治理动作</CardTitle>
          </CardHeader>
          <CardContent>
            {recentGovernanceActions.length === 0 ? (
              <p className="text-sm text-stone-gray">暂无治理审计记录。</p>
            ) : (
              <div className="space-y-3">
                {recentGovernanceActions.map((action) => (
                  <div key={action.auditLogId} className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-near-black">{governanceActionLabel(action.action)}</span>
                      <span className="text-xs text-stone-gray">{formatDateTime(action.createdAt)}</span>
                    </div>
                    <p className="mt-1 text-xs text-stone-gray">
                      资源：{action.resourceType} / {action.resourceId.slice(0, 8)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
