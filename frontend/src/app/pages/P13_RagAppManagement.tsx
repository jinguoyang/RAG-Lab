import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router";
import {
  Copy,
  Eye,
  KeyRound,
  Pencil,
  PlayCircle,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldOff,
  X,
} from "lucide-react";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import { Button } from "../components/rag/Button";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { Input } from "../components/rag/Input";
import { PageHeader } from "../components/rag/PageHeader";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/rag/Table";
import {
  groupInvocationsByConversation,
  shortId,
  toAppInvocationViewModel,
  toAppMessageViewModel,
  toRagAppApiKeyViewModel,
  toRagAppViewModel,
} from "../adapters/ragAppAdapter";
import { fetchConfigRevisions } from "../services/configService";
import { fetchKnowledgeBases } from "../services/knowledgeBaseService";
import {
  chatWithAppRuntime,
  parseAppRuntimeSse,
  streamChatWithAppRuntime,
  submitAppRuntimeFeedback,
} from "../services/appRuntimeService";
import {
  createRagApp,
  createRagAppApiKey,
  getRagAppConversationDetail,
  getRagAppInvocationStats,
  listRagAppApiKeys,
  listRagAppInvocations,
  listRagApps,
  revokeRagAppApiKey,
  updateRagApp,
} from "../services/ragAppService";
import type { ConfigRevisionDTO } from "../types/config";
import type { KnowledgeBase } from "../types/knowledgeBase";
import type { AppRuntimeChatResponse, AppRuntimeSseEvent } from "../types/appRuntime";
import type {
  AppInvocationDTO,
  AppInvocationStatsDTO,
  AppInvocationStatus,
  AppConversationDetailDTO,
  RagAppApiKeyDTO,
  RagAppDTO,
  RagAppStatus,
} from "../types/ragApp";

const PAGE_SIZE = 10;
const INVOCATION_PAGE_SIZE = 20;

type DetailTab = "overview" | "keys" | "invocations" | "conversations";
type Feedback = { variant: "success" | "error"; title: string; message: string };

const STATUS_OPTIONS: Array<{ value: "" | RagAppStatus; label: string }> = [
  { value: "", label: "全部状态" },
  { value: "active", label: "启用" },
  { value: "disabled", label: "停用" },
  { value: "archived", label: "已归档" },
];

const INVOCATION_STATUS_OPTIONS: Array<{ value: "" | AppInvocationStatus; label: string }> = [
  { value: "", label: "全部调用" },
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
];

const EMPTY_APP_FORM = {
  name: "",
  description: "",
  kbId: "",
  defaultConfigRevisionId: "",
  status: "active" as RagAppStatus,
};

function statusBadgeVariant(status: string): "success" | "inactive" | "warning" | "error" {
  if (status === "active" || status === "success") return "success";
  if (status === "disabled" || status === "revoked") return "inactive";
  if (status === "failed") return "error";
  return "warning";
}

function toNullableText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function selectedKnowledgeBaseName(knowledgeBases: KnowledgeBase[], kbId: string | null | undefined): string {
  if (!kbId) return "-";
  return knowledgeBases.find((kb) => kb.kbId === kbId)?.name ?? shortId(kbId, 12);
}

function revisionLabel(revision: ConfigRevisionDTO): string {
  return `v${revision.revisionNo} · ${revision.status} · ${shortId(revision.configRevisionId, 8)}`;
}

function buildQARunHistoryLink(kbId: string, runId: string): string {
  return `/kb/${kbId}/history?runId=${encodeURIComponent(runId)}`;
}

export function RagAppManagement() {
  const confirmDialog = useConfirmDialog();
  const [apps, setApps] = useState<RagAppDTO[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [configRevisions, setConfigRevisions] = useState<ConfigRevisionDTO[]>([]);
  const [selectedApp, setSelectedApp] = useState<RagAppDTO | null>(null);
  const [apiKeys, setApiKeys] = useState<RagAppApiKeyDTO[]>([]);
  const [invocations, setInvocations] = useState<AppInvocationDTO[]>([]);
  const [invocationStats, setInvocationStats] = useState<AppInvocationStatsDTO | null>(null);
  const [selectedConversationDetail, setSelectedConversationDetail] = useState<AppConversationDetailDTO | null>(null);
  const [keyword, setKeyword] = useState("");
  const [queryKeyword, setQueryKeyword] = useState("");
  const [kbFilter, setKbFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | RagAppStatus>("");
  const [invocationStatusFilter, setInvocationStatusFilter] = useState<"" | AppInvocationStatus>("");
  const [pageNo, setPageNo] = useState(1);
  const [totalApps, setTotalApps] = useState(0);
  const [isLoadingApps, setIsLoadingApps] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [isAppFormOpen, setIsAppFormOpen] = useState(false);
  const [editingAppId, setEditingAppId] = useState<string | null>(null);
  const [appForm, setAppForm] = useState(EMPTY_APP_FORM);
  const [createdPlainApiKey, setCreatedPlainApiKey] = useState<string | null>(null);
  const [keyExpiresAt, setKeyExpiresAt] = useState("");
  const [runtimeApiKey, setRuntimeApiKey] = useState("");
  const [runtimeQuery, setRuntimeQuery] = useState("");
  const [runtimeMode, setRuntimeMode] = useState<"blocking" | "streaming">("blocking");
  const [runtimeResult, setRuntimeResult] = useState<AppRuntimeChatResponse | null>(null);
  const [runtimeEvents, setRuntimeEvents] = useState<AppRuntimeSseEvent[]>([]);
  const [runtimeFeedbackNote, setRuntimeFeedbackNote] = useState("");
  const [isRuntimeRunning, setIsRuntimeRunning] = useState(false);

  const appRows = useMemo(() => apps.map(toRagAppViewModel), [apps]);
  const selectedAppView = selectedApp ? toRagAppViewModel(selectedApp) : null;
  const keyRows = useMemo(() => apiKeys.map(toRagAppApiKeyViewModel), [apiKeys]);
  const invocationRows = useMemo(() => invocations.map(toAppInvocationViewModel), [invocations]);
  const conversationRows = useMemo(() => groupInvocationsByConversation(invocations), [invocations]);
  const conversationMessageRows = useMemo(
    () => selectedConversationDetail?.messages.map(toAppMessageViewModel) ?? [],
    [selectedConversationDetail],
  );
  const totalPages = Math.max(1, Math.ceil(totalApps / PAGE_SIZE));

  const loadApps = useCallback(async () => {
    setIsLoadingApps(true);
    try {
      const [kbPage, appPage] = await Promise.all([
        fetchKnowledgeBases(),
        listRagApps({
          pageNo,
          pageSize: PAGE_SIZE,
          keyword: queryKeyword,
          kbId: kbFilter || undefined,
          status: statusFilter,
        }),
      ]);
      setKnowledgeBases(kbPage.items);
      setApps(appPage.items);
      setTotalApps(appPage.total);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "RAG 应用列表加载失败",
        message: error instanceof Error ? error.message : "请检查后端服务状态。",
      });
    } finally {
      setIsLoadingApps(false);
    }
  }, [kbFilter, pageNo, queryKeyword, statusFilter]);

  const loadAppDetail = useCallback(async (app: RagAppDTO) => {
    setIsLoadingDetail(true);
    try {
      const [keys, invocationPage, revisions, stats] = await Promise.all([
        listRagAppApiKeys(app.appId),
        listRagAppInvocations(app.appId, {
          pageNo: 1,
          pageSize: INVOCATION_PAGE_SIZE,
          status: invocationStatusFilter,
        }),
        fetchConfigRevisions(app.kbId).catch(() => ({ items: [] as ConfigRevisionDTO[], pageNo: 1, pageSize: 50, total: 0 })),
        getRagAppInvocationStats(app.appId),
      ]);
      setApiKeys(keys);
      setInvocations(invocationPage.items);
      setConfigRevisions(revisions.items);
      setInvocationStats(stats);
      setSelectedConversationDetail(null);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "应用详情加载失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsLoadingDetail(false);
    }
  }, [invocationStatusFilter]);

  useEffect(() => {
    void loadApps();
  }, [loadApps]);

  useEffect(() => {
    if (selectedApp) {
      void loadAppDetail(selectedApp);
    } else {
      setApiKeys([]);
      setInvocations([]);
      setConfigRevisions([]);
      setInvocationStats(null);
      setSelectedConversationDetail(null);
    }
  }, [loadAppDetail, selectedApp]);

  useEffect(() => {
    if (!appForm.kbId) {
      setConfigRevisions([]);
      return;
    }
    let ignore = false;
    fetchConfigRevisions(appForm.kbId)
      .then((page) => {
        if (!ignore) setConfigRevisions(page.items);
      })
      .catch(() => {
        if (!ignore) setConfigRevisions([]);
      });
    return () => {
      ignore = true;
    };
  }, [appForm.kbId]);

  const handleSearch = () => {
    setPageNo(1);
    setQueryKeyword(keyword.trim());
  };

  const openCreateForm = () => {
    setEditingAppId(null);
    setAppForm({
      ...EMPTY_APP_FORM,
      kbId: kbFilter || knowledgeBases[0]?.kbId || "",
    });
    setFeedback(null);
    setIsAppFormOpen(true);
  };

  const openEditForm = (app: RagAppDTO) => {
    setEditingAppId(app.appId);
    setAppForm({
      name: app.name,
      description: app.description ?? "",
      kbId: app.kbId,
      defaultConfigRevisionId: app.defaultConfigRevisionId ?? "",
      status: app.status,
    });
    setFeedback(null);
    setIsAppFormOpen(true);
  };

  const closeAppForm = () => {
    setIsAppFormOpen(false);
    setEditingAppId(null);
    setAppForm(EMPTY_APP_FORM);
  };

  const handleSaveApp = async () => {
    if (!appForm.name.trim() || !appForm.kbId) {
      setFeedback({ variant: "error", title: "应用信息不完整", message: "应用名称和知识库不能为空。" });
      return;
    }
    setIsSaving(true);
    try {
      const payload = {
        name: appForm.name.trim(),
        description: toNullableText(appForm.description),
        defaultConfigRevisionId: appForm.defaultConfigRevisionId || null,
      };
      const savedApp = editingAppId
        ? await updateRagApp(editingAppId, { ...payload, status: appForm.status })
        : await createRagApp({ ...payload, kbId: appForm.kbId });
      setFeedback({
        variant: "success",
        title: editingAppId ? "应用已更新" : "应用已创建",
        message: `${savedApp.name} 已保存。`,
      });
      closeAppForm();
      setSelectedApp(savedApp);
      await loadApps();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: editingAppId ? "应用更新失败" : "应用创建失败",
        message: error instanceof Error ? error.message : "请检查知识库和配置版本是否可用。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleAppStatus = async (app: RagAppDTO) => {
    const nextStatus: RagAppStatus = app.status === "active" ? "disabled" : "active";
    const confirmed = await confirmDialog({
      title: nextStatus === "disabled" ? "确认停用应用" : "确认启用应用",
      description: nextStatus === "disabled"
        ? "停用后，外部 App Runtime 调用会被拒绝。"
        : "启用后，仍需有效 API Key 和可运行配置才能被外部调用。",
      detail: app.name,
      confirmText: nextStatus === "disabled" ? "停用应用" : "启用应用",
      variant: nextStatus === "disabled" ? "destructive" : "default",
    });
    if (!confirmed) return;

    setIsSaving(true);
    try {
      const updated = await updateRagApp(app.appId, { status: nextStatus });
      setSelectedApp(updated);
      setFeedback({ variant: "success", title: "应用状态已更新", message: `${updated.name} 当前为${nextStatus === "active" ? "启用" : "停用"}。` });
      await loadApps();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "状态更新失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateApiKey = async () => {
    if (!selectedApp) return;
    setIsSaving(true);
    try {
      const response = await createRagAppApiKey(selectedApp.appId, {
        expiresAt: keyExpiresAt ? new Date(keyExpiresAt).toISOString() : null,
      });
      setCreatedPlainApiKey(response.apiKey);
      setKeyExpiresAt("");
      setFeedback({ variant: "success", title: "API Key 已生成", message: "明文只显示一次，请立即保存到外部应用安全配置中。" });
      await loadAppDetail(selectedApp);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "API Key 生成失败",
        message: error instanceof Error ? error.message : "请稍后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleClosePlainKey = () => {
    setCreatedPlainApiKey(null);
  };

  const handleRevokeApiKey = async (key: RagAppApiKeyDTO) => {
    if (!selectedApp) return;
    const confirmed = await confirmDialog({
      title: "确认撤销 API Key",
      description: "撤销后使用该 Key 的外部调用将返回 APP_API_KEY_INVALID。",
      detail: `Key 前缀：${key.keyPrefix}`,
      confirmText: "撤销 Key",
      variant: "destructive",
    });
    if (!confirmed) return;

    setIsSaving(true);
    try {
      await revokeRagAppApiKey(selectedApp.appId, key.apiKeyId);
      setFeedback({ variant: "success", title: "API Key 已撤销", message: `${key.keyPrefix} 已不可用于外部调用。` });
      await loadAppDetail(selectedApp);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "撤销失败",
        message: error instanceof Error ? error.message : "请刷新后重试。",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const copyPlainKey = async () => {
    if (!createdPlainApiKey) return;
    try {
      await navigator.clipboard.writeText(createdPlainApiKey);
      setFeedback({ variant: "success", title: "已复制", message: "API Key 已复制到剪贴板。" });
    } catch {
      setFeedback({ variant: "error", title: "复制失败", message: "当前浏览器不允许访问剪贴板，请手动选择文本。" });
    }
  };

  const handleRunRuntimeTrial = async () => {
    if (!selectedApp || !runtimeApiKey.trim() || !runtimeQuery.trim()) {
      setFeedback({ variant: "error", title: "试运行信息不完整", message: "请输入 App API Key 和真实问题。" });
      return;
    }
    setIsRuntimeRunning(true);
    setRuntimeResult(null);
    setRuntimeEvents([]);
    try {
      if (runtimeMode === "streaming") {
        const response = await streamChatWithAppRuntime(runtimeApiKey, { query: runtimeQuery.trim() });
        const text = await response.text();
        const events = parseAppRuntimeSse(text);
        setRuntimeEvents(events);
        const doneEvent = events.find((event) => event.event === "done");
        setFeedback({
          variant: "success",
          title: "Streaming 试运行完成",
          message: doneEvent ? "已收到 done 事件，可在调用记录中查看关联 QARun。" : "已收到 SSE 响应，请查看事件列表。",
        });
      } else {
        const response = await chatWithAppRuntime(runtimeApiKey, { query: runtimeQuery.trim() });
        setRuntimeResult(response);
        setFeedback({ variant: "success", title: "Blocking 试运行完成", message: `已生成 QARun ${shortId(response.runId)}。` });
      }
      await loadAppDetail(selectedApp);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "Runtime 试运行失败",
        message: error instanceof Error ? error.message : "请检查 API Key、应用状态和后端服务。",
      });
    } finally {
      setIsRuntimeRunning(false);
    }
  };

  const handleSubmitRuntimeFeedback = async () => {
    if (!runtimeResult || !runtimeApiKey.trim()) return;
    setIsRuntimeRunning(true);
    try {
      const response = await submitAppRuntimeFeedback(runtimeApiKey, runtimeResult.messageId, {
        feedbackStatus: "wrong",
        failureType: "manual_review_required",
        feedbackNote: runtimeFeedbackNote || "P13 试运行人工反馈：需要复核。",
        createEvaluationSample: true,
      });
      setFeedback({
        variant: "success",
        title: "反馈已回流",
        message: response.evaluationSampleId
          ? `已更新 QARun 并创建评估样本 ${shortId(response.evaluationSampleId)}。`
          : "已更新关联 QARun 反馈状态。",
      });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "反馈提交失败",
        message: error instanceof Error ? error.message : "请检查 API Key 和 messageId 是否仍有效。",
      });
    } finally {
      setIsRuntimeRunning(false);
    }
  };

  const handleOpenConversationDetail = async (conversationId: string) => {
    if (!selectedApp) return;
    setIsLoadingConversation(true);
    try {
      const detail = await getRagAppConversationDetail(selectedApp.appId, conversationId);
      setSelectedConversationDetail(detail);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "会话详情加载失败",
        message: error instanceof Error ? error.message : "请确认会话仍属于当前应用。",
      });
    } finally {
      setIsLoadingConversation(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PageHeader
        title="RAG 应用管理"
        description="将治理后的知识库和配置版本发布为外部可调用应用。"
        actions={
          <>
            <Button variant="outline" onClick={() => void loadApps()} disabled={isLoadingApps}>
              <RefreshCw className="mr-2 h-4 w-4" /> 刷新
            </Button>
            <Button variant="primary" onClick={openCreateForm}>
              <Plus className="mr-2 h-4 w-4" /> 创建应用
            </Button>
          </>
        }
      />

      <div className="flex-1 overflow-auto p-8">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 xl:grid-cols-[minmax(520px,1fr)_440px]">
          <section className="space-y-4">
            {feedback && (
              <Alert variant={feedback.variant} title={feedback.title} onClose={() => setFeedback(null)}>
                {feedback.message}
              </Alert>
            )}

            <div className="grid grid-cols-1 gap-3 rounded-lg border border-border-cream bg-ivory p-4 lg:grid-cols-[220px_180px_minmax(240px,1fr)_auto]">
              <select
                value={kbFilter}
                onChange={(event) => {
                  setKbFilter(event.target.value);
                  setPageNo(1);
                }}
                className="h-10 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
              >
                <option value="">全部知识库</option>
                {knowledgeBases.map((kb) => (
                  <option key={kb.kbId} value={kb.kbId}>{kb.name}</option>
                ))}
              </select>
              <select
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.target.value as "" | RagAppStatus);
                  setPageNo(1);
                }}
                className="h-10 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
              >
                {STATUS_OPTIONS.map((item) => (
                  <option key={item.value || "all"} value={item.value}>{item.label}</option>
                ))}
              </select>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-gray" />
                <Input
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") handleSearch();
                  }}
                  placeholder="搜索应用名称或描述..."
                  className="bg-white pl-9"
                />
              </div>
              <Button variant="outline" onClick={handleSearch} disabled={isLoadingApps}>
                <Search className="mr-2 h-4 w-4" /> 查询
              </Button>
            </div>

            <Table tableClassName="min-w-[900px]">
              <TableHeader>
                <TableRow>
                  <TableHead>应用</TableHead>
                  <TableHead>知识库</TableHead>
                  <TableHead>默认配置</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>更新时间</TableHead>
                  <TableHead>操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoadingApps && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-stone-gray">加载中...</TableCell>
                  </TableRow>
                )}
                {!isLoadingApps && appRows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-stone-gray">暂无 RAG 应用</TableCell>
                  </TableRow>
                )}
                {!isLoadingApps && appRows.map((app) => (
                  <TableRow key={app.id} onClick={() => setSelectedApp(apps.find((item) => item.appId === app.id) ?? null)}>
                    <TableCell>
                      <div className="font-medium text-near-black">{app.name}</div>
                      <div className="max-w-[260px] truncate text-xs text-stone-gray" title={app.description}>{app.description}</div>
                    </TableCell>
                    <TableCell>{selectedKnowledgeBaseName(knowledgeBases, app.kbId)}</TableCell>
                    <TableCell className="max-w-[180px] truncate" title={app.defaultRevisionLabel}>{app.defaultRevisionLabel}</TableCell>
                    <TableCell>
                      <Badge variant={statusBadgeVariant(app.status)}>{app.statusLabel}</Badge>
                    </TableCell>
                    <TableCell>{app.updatedAtLabel}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="sm" onClick={(event) => {
                          event.stopPropagation();
                          setSelectedApp(apps.find((item) => item.appId === app.id) ?? null);
                        }}>
                          <Eye className="mr-1 h-3 w-3" /> 查看
                        </Button>
                        <Button variant="ghost" size="sm" onClick={(event) => {
                          event.stopPropagation();
                          const sourceApp = apps.find((item) => item.appId === app.id);
                          if (sourceApp) openEditForm(sourceApp);
                        }}>
                          <Pencil className="mr-1 h-3 w-3" /> 编辑
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-stone-gray">
              <span>共 {totalApps} 个应用</span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={isLoadingApps || pageNo <= 1} onClick={() => setPageNo((current) => current - 1)}>
                  上一页
                </Button>
                <span className="min-w-20 text-center text-near-black">{pageNo} / {totalPages}</span>
                <Button variant="outline" size="sm" disabled={isLoadingApps || pageNo >= totalPages} onClick={() => setPageNo((current) => current + 1)}>
                  下一页
                </Button>
              </div>
            </div>
          </section>

          <aside className="space-y-4">
            {!selectedApp || !selectedAppView ? (
              <div className="rounded-lg border border-border-cream bg-ivory p-6 text-sm text-stone-gray">
                从左侧列表选择一个 RAG 应用，查看 API Key、调用记录和会话摘要。
              </div>
            ) : (
              <>
                <div className="rounded-lg border border-border-cream bg-ivory p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="truncate font-serif text-xl text-near-black" title={selectedApp.name}>{selectedApp.name}</h2>
                      <p className="mt-1 text-xs text-stone-gray">
                        {selectedKnowledgeBaseName(knowledgeBases, selectedApp.kbId)} / {selectedAppView.defaultRevisionLabel}
                      </p>
                      <p className="mt-1 font-mono text-xs text-stone-gray">appId: {selectedApp.appId}</p>
                    </div>
                    <Badge variant={statusBadgeVariant(selectedApp.status)}>{selectedAppView.statusLabel}</Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEditForm(selectedApp)}>
                      <Pencil className="mr-1 h-3 w-3" /> 编辑
                    </Button>
                    <Button
                      variant={selectedApp.status === "active" ? "destructive" : "primary"}
                      size="sm"
                      disabled={isSaving}
                      onClick={() => void handleToggleAppStatus(selectedApp)}
                    >
                      {selectedApp.status === "active" ? <ShieldOff className="mr-1 h-3 w-3" /> : <RotateCcw className="mr-1 h-3 w-3" />}
                      {selectedApp.status === "active" ? "停用应用" : "启用应用"}
                    </Button>
                  </div>
                </div>

                <div className="rounded-lg border border-border-cream bg-ivory">
                  <div className="grid grid-cols-4 border-b border-border-cream text-sm">
                    {[
                      ["overview", "概览"],
                      ["keys", "API Keys"],
                      ["invocations", "调用记录"],
                      ["conversations", "会话"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setActiveTab(value as DetailTab)}
                        className={`h-11 border-r border-border-cream last:border-r-0 ${activeTab === value ? "bg-parchment text-terracotta" : "text-near-black hover:bg-parchment"}`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="max-h-[560px] overflow-auto p-4">
                    {isLoadingDetail && <p className="text-sm text-stone-gray">详情加载中...</p>}
                    {!isLoadingDetail && activeTab === "overview" && (
                      <div className="space-y-3 text-sm">
                        <div>
                          <p className="text-xs text-stone-gray">描述</p>
                          <p className="mt-1 text-near-black">{selectedApp.description || "未填写描述"}</p>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">API Key</p>
                            <p className="mt-1 text-lg font-medium text-near-black">{apiKeys.length}</p>
                          </div>
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">最近调用</p>
                            <p className="mt-1 text-lg font-medium text-near-black">{invocationRows[0]?.createdAtLabel ?? "-"}</p>
                          </div>
                        </div>
                        <div className="rounded-lg border border-border-cream bg-parchment p-3">
                          <p className="text-xs text-stone-gray">调用统计</p>
                          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-stone-gray">
                            <span>总调用：{invocationStats?.totalInvocations ?? 0}</span>
                            <span>成功：{invocationStats?.successInvocations ?? 0}</span>
                            <span>失败：{invocationStats?.failedInvocations ?? 0}</span>
                            <span>平均延迟：{invocationStats?.averageLatencyMs == null ? "-" : `${invocationStats.averageLatencyMs}ms`}</span>
                            <span>无证据率：{(((invocationStats?.noEvidenceRate ?? 0) * 100)).toFixed(1)}%</span>
                            <span>限流：{invocationStats?.quotaExceededInvocations ?? 0}</span>
                          </div>
                        </div>
                        <div className="space-y-3 rounded-lg border border-border-cream bg-parchment p-3">
                          <div>
                            <p className="text-xs text-stone-gray">真实 Runtime 试运行</p>
                            <p className="mt-1 text-xs text-stone-gray">API Key 只保存在当前页面状态，关闭或刷新后不会保留。</p>
                          </div>
                          <Input
                            value={runtimeApiKey}
                            onChange={(event) => setRuntimeApiKey(event.target.value)}
                            placeholder="粘贴 rlak_ 开头的 App API Key"
                            className="bg-white"
                          />
                          <textarea
                            value={runtimeQuery}
                            onChange={(event) => setRuntimeQuery(event.target.value)}
                            rows={3}
                            placeholder="输入真实问题..."
                            className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm text-near-black focus:outline-none"
                          />
                          <div className="flex items-center justify-between gap-3">
                            <select
                              value={runtimeMode}
                              onChange={(event) => setRuntimeMode(event.target.value as "blocking" | "streaming")}
                              className="h-9 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
                            >
                              <option value="blocking">blocking</option>
                              <option value="streaming">streaming</option>
                            </select>
                            <Button variant="primary" size="sm" disabled={isRuntimeRunning} onClick={() => void handleRunRuntimeTrial()}>
                              <PlayCircle className="mr-1 h-3 w-3" /> 试运行
                            </Button>
                          </div>
                          {runtimeResult && (
                            <div className="space-y-2 rounded-lg border border-border-cream bg-white p-3 text-xs">
                              <div className="text-near-black">{runtimeResult.answer || "无回答内容"}</div>
                              <div className="font-mono text-stone-gray">runId: {runtimeResult.runId}</div>
                              <div className="text-stone-gray">Citation：{runtimeResult.citations.length} · messageId：{shortId(runtimeResult.messageId)}</div>
                              <textarea
                                value={runtimeFeedbackNote}
                                onChange={(event) => setRuntimeFeedbackNote(event.target.value)}
                                rows={2}
                                placeholder="反馈备注..."
                                className="w-full rounded-md border border-border-cream bg-parchment px-2 py-1 text-xs text-near-black focus:outline-none"
                              />
                              <Button variant="outline" size="sm" disabled={isRuntimeRunning} onClick={() => void handleSubmitRuntimeFeedback()}>
                                提交负反馈并加入评估集
                              </Button>
                            </div>
                          )}
                          {runtimeEvents.length > 0 && (
                            <div className="max-h-36 overflow-auto rounded-lg border border-border-cream bg-white p-3 text-xs">
                              {runtimeEvents.map((event, index) => (
                                <div key={`${event.event}-${index}`} className="font-mono text-stone-gray">
                                  {event.event}: {JSON.stringify(event.data)}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    {!isLoadingDetail && activeTab === "keys" && (
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center justify-end gap-2">
                          <label className="text-xs text-stone-gray">
                            过期时间
                            <input
                              type="datetime-local"
                              value={keyExpiresAt}
                              onChange={(event) => setKeyExpiresAt(event.target.value)}
                              className="ml-2 h-9 rounded-md border border-border-cream bg-white px-2 text-sm text-near-black focus:outline-none"
                            />
                          </label>
                          <Button variant="primary" size="sm" onClick={() => void handleCreateApiKey()} disabled={isSaving}>
                            <KeyRound className="mr-1 h-3 w-3" /> 生成 Key
                          </Button>
                        </div>
                        <Table tableClassName="min-w-[680px]">
                          <TableHeader>
                            <TableRow>
                              <TableHead>前缀</TableHead>
                              <TableHead>状态</TableHead>
                              <TableHead>过期时间</TableHead>
                              <TableHead>最近使用</TableHead>
                              <TableHead>操作</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {keyRows.length === 0 && (
                              <TableRow>
                                <TableCell colSpan={5} className="text-stone-gray">暂无 API Key</TableCell>
                              </TableRow>
                            )}
                            {keyRows.map((key) => (
                              <TableRow key={key.id}>
                                <TableCell mono>{key.keyPrefix}</TableCell>
                                <TableCell><Badge variant={statusBadgeVariant(key.status)}>{key.statusLabel}</Badge></TableCell>
                                <TableCell>{key.expiresAtLabel}</TableCell>
                                <TableCell>{key.lastUsedAtLabel}</TableCell>
                                <TableCell>
                                  {key.status === "active" ? (
                                    <Button variant="ghost" size="sm" disabled={isSaving} onClick={() => {
                                      const sourceKey = apiKeys.find((item) => item.apiKeyId === key.id);
                                      if (sourceKey) void handleRevokeApiKey(sourceKey);
                                    }}>
                                      撤销
                                    </Button>
                                  ) : (
                                    <span className="text-stone-gray">-</span>
                                  )}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                    {!isLoadingDetail && activeTab === "invocations" && (
                      <div className="space-y-3">
                        <div className="flex justify-between gap-3">
                          <select
                            value={invocationStatusFilter}
                            onChange={(event) => setInvocationStatusFilter(event.target.value as "" | AppInvocationStatus)}
                            className="h-9 rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
                          >
                            {INVOCATION_STATUS_OPTIONS.map((item) => (
                              <option key={item.value || "all"} value={item.value}>{item.label}</option>
                            ))}
                          </select>
                          <Button variant="outline" size="sm" onClick={() => void loadAppDetail(selectedApp)}>
                            <RefreshCw className="mr-1 h-3 w-3" /> 刷新
                          </Button>
                        </div>
                        <Table tableClassName="min-w-[760px]">
                          <TableHeader>
                            <TableRow>
                              <TableHead>时间</TableHead>
                              <TableHead>状态</TableHead>
                              <TableHead>延迟</TableHead>
                              <TableHead>会话</TableHead>
                              <TableHead>QARun</TableHead>
                              <TableHead>摘要</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {invocationRows.length === 0 && (
                              <TableRow>
                                <TableCell colSpan={6} className="text-stone-gray">暂无调用记录</TableCell>
                              </TableRow>
                            )}
                            {invocationRows.map((invocation) => (
                              <TableRow key={invocation.id}>
                                <TableCell>{invocation.createdAtLabel}</TableCell>
                                <TableCell>
                                  <Badge variant={statusBadgeVariant(invocation.status)}>{invocation.statusLabel}</Badge>
                                  {invocation.errorLabel !== "-" && <div className="mt-1 text-xs text-error-red">{invocation.errorLabel}</div>}
                                </TableCell>
                                <TableCell>{invocation.latencyLabel}</TableCell>
                                <TableCell mono>{shortId(invocation.conversationId)}</TableCell>
                                <TableCell>
                                  {invocation.qaRunId ? (
                                    <NavLink className="text-terracotta hover:underline" to={buildQARunHistoryLink(selectedApp.kbId, invocation.qaRunId)}>
                                      {shortId(invocation.qaRunId)}
                                    </NavLink>
                                  ) : "-"}
                                </TableCell>
                                <TableCell className="max-w-[240px] truncate" title={`${invocation.requestSummaryLabel} / ${invocation.responseSummaryLabel}`}>
                                  {invocation.responseSummaryLabel !== "-" ? invocation.responseSummaryLabel : invocation.requestSummaryLabel}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                    {!isLoadingDetail && activeTab === "conversations" && (
                      <div className="space-y-4">
                        <Table tableClassName="min-w-[700px]">
                          <TableHeader>
                            <TableRow>
                              <TableHead>会话</TableHead>
                              <TableHead>调用</TableHead>
                              <TableHead>成功/失败</TableHead>
                              <TableHead>最近调用</TableHead>
                              <TableHead>QARun</TableHead>
                              <TableHead>操作</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {conversationRows.length === 0 && (
                              <TableRow>
                                <TableCell colSpan={6} className="text-stone-gray">暂无可聚合会话</TableCell>
                              </TableRow>
                            )}
                            {conversationRows.map((conversation) => (
                              <TableRow key={conversation.conversationId}>
                                <TableCell mono>{shortId(conversation.conversationId, 12)}</TableCell>
                                <TableCell>{conversation.invocationCount}</TableCell>
                                <TableCell>{conversation.successCount} / {conversation.failedCount}</TableCell>
                                <TableCell>{conversation.lastCalledAtLabel}</TableCell>
                                <TableCell>
                                  {conversation.lastQaRunId ? (
                                    <NavLink className="text-terracotta hover:underline" to={buildQARunHistoryLink(selectedApp.kbId, conversation.lastQaRunId)}>
                                      {shortId(conversation.lastQaRunId)}
                                    </NavLink>
                                  ) : "-"}
                                </TableCell>
                                <TableCell>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    disabled={isLoadingConversation}
                                    onClick={() => void handleOpenConversationDetail(conversation.conversationId)}
                                  >
                                    查看详情
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                        {selectedConversationDetail && (
                          <div className="rounded-lg border border-border-cream bg-parchment p-3 text-xs">
                            <div className="flex flex-wrap justify-between gap-2 text-stone-gray">
                              <span>conversationId：{selectedConversationDetail.conversationId}</span>
                              <span>endUserId：{selectedConversationDetail.endUserId || "-"}</span>
                            </div>
                            <div className="mt-3 space-y-2">
                              {conversationMessageRows.map((message) => (
                                <div key={message.id} className="rounded-md border border-border-cream bg-white p-3">
                                  <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-stone-gray">
                                    <span>{message.roleLabel} · {message.createdAtLabel}</span>
                                    {message.qaRunId ? (
                                      <NavLink className="text-terracotta hover:underline" to={buildQARunHistoryLink(selectedApp.kbId, message.qaRunId)}>
                                        QARun {shortId(message.qaRunId)}
                                      </NavLink>
                                    ) : (
                                      <span>{message.status}</span>
                                    )}
                                  </div>
                                  <p className="whitespace-pre-wrap text-near-black">{message.content}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </aside>
        </div>
      </div>

      {isAppFormOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-2xl rounded-lg border border-border-warm bg-ivory shadow-[0_24px_80px_rgba(20,20,19,0.18)]">
            <div className="flex items-center justify-between border-b border-border-cream p-5">
              <div>
                <h2 className="font-serif text-xl text-near-black">{editingAppId ? "编辑 RAG 应用" : "创建 RAG 应用"}</h2>
                <p className="mt-1 text-sm text-stone-gray">应用只保存知识库和配置绑定，不复制 Pipeline。</p>
              </div>
              <Button variant="ghost" size="sm" onClick={closeAppForm} disabled={isSaving}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <div className="space-y-4 p-5">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <label className="space-y-2 text-sm">
                  <span className="text-stone-gray">应用名称</span>
                  <Input value={appForm.name} onChange={(event) => setAppForm((current) => ({ ...current, name: event.target.value }))} className="bg-white" />
                </label>
                <label className="space-y-2 text-sm">
                  <span className="text-stone-gray">知识库</span>
                  <select
                    value={appForm.kbId}
                    onChange={(event) => setAppForm((current) => ({ ...current, kbId: event.target.value, defaultConfigRevisionId: "" }))}
                    disabled={Boolean(editingAppId)}
                    className="h-10 w-full rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none disabled:bg-parchment"
                  >
                    <option value="">请选择知识库</option>
                    {knowledgeBases.map((kb) => (
                      <option key={kb.kbId} value={kb.kbId}>{kb.name}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="block space-y-2 text-sm">
                <span className="text-stone-gray">描述</span>
                <textarea
                  value={appForm.description}
                  onChange={(event) => setAppForm((current) => ({ ...current, description: event.target.value }))}
                  rows={3}
                  className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm text-near-black focus:outline-none"
                />
              </label>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <label className="space-y-2 text-sm">
                  <span className="text-stone-gray">默认配置版本</span>
                  <select
                    value={appForm.defaultConfigRevisionId}
                    onChange={(event) => setAppForm((current) => ({ ...current, defaultConfigRevisionId: event.target.value }))}
                    className="h-10 w-full rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
                  >
                    <option value="">跟随知识库 active revision</option>
                    {configRevisions.map((revision) => (
                      <option key={revision.configRevisionId} value={revision.configRevisionId}>
                        {revisionLabel(revision)}
                      </option>
                    ))}
                  </select>
                </label>
                {editingAppId && (
                  <label className="space-y-2 text-sm">
                    <span className="text-stone-gray">状态</span>
                    <select
                      value={appForm.status}
                      onChange={(event) => setAppForm((current) => ({ ...current, status: event.target.value as RagAppStatus }))}
                      className="h-10 w-full rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
                    >
                      <option value="active">启用</option>
                      <option value="disabled">停用</option>
                      <option value="archived">已归档</option>
                    </select>
                  </label>
                )}
              </div>
            </div>
            <div className="flex justify-end gap-3 border-t border-border-cream p-5">
              <Button variant="ghost" onClick={closeAppForm} disabled={isSaving}>取消</Button>
              <Button variant="primary" onClick={() => void handleSaveApp()} disabled={isSaving}>
                {editingAppId ? "保存修改" : "创建应用"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {createdPlainApiKey && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
          <div className="w-full max-w-xl rounded-lg border border-border-warm bg-ivory p-6 shadow-[0_24px_80px_rgba(20,20,19,0.18)]">
            <h2 className="font-serif text-xl text-near-black">API Key 已生成</h2>
            <p className="mt-2 text-sm text-stone-gray">明文只显示一次，关闭后页面不会保留。请立即保存到外部应用的安全配置中。</p>
            <div className="mt-4 rounded-lg border border-border-cream bg-parchment p-4 font-mono text-sm text-near-black break-all">
              {createdPlainApiKey}
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="outline" onClick={() => void copyPlainKey()}>
                <Copy className="mr-2 h-4 w-4" /> 复制
              </Button>
              <Button variant="primary" onClick={handleClosePlainKey}>我已保存</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
