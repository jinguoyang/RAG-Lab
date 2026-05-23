import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, useNavigate } from "react-router";
import * as Tabs from "@radix-ui/react-tabs";
import {
  Copy,
  FileText,
  KeyRound,
  Pencil,
  PlayCircle,
  Plus,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldCheck,
  ShieldOff,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { Alert } from "../components/rag/Alert";
import { Badge } from "../components/rag/Badge";
import { Button } from "../components/rag/Button";
import { useConfirmDialog } from "../components/rag/ConfirmDialog";
import { Drawer, DrawerSection } from "../components/rag/Drawer";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
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
  createAppRuntimeEmbedToken,
  parseAppRuntimeSse,
  retrieveWithAppRuntime,
  streamChatWithAppRuntime,
  submitAppRuntimeFeedback,
} from "../services/appRuntimeService";
import { listAgentScenarioTemplates } from "../services/agentScenarioService";
import { chooseActiveDictionaryValue, fetchDictionaryItemsWithFallback } from "../services/dictionaryService";
import {
  createRagApp,
  createRagAppApiKey,
  deleteRagApp,
  deleteRagAppApiKey,
  getRagAppConversationDetail,
  getRagAppInvocationStats,
  listRagAppApiKeys,
  listRagAppInvocations,
  listRagApps,
  updateRagApp,
} from "../services/ragAppService";
import type { ConfigRevisionDTO } from "../types/config";
import type { AgentScenarioTemplateDTO } from "../types/agentScenario";
import type { KnowledgeBase } from "../types/knowledgeBase";
import type { AppRuntimeChatResponse, AppRuntimeRetrieveResponse, AppRuntimeSseEvent } from "../types/appRuntime";
import type { DictionaryItemDTO } from "../types/dictionary";
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
  { value: "running", label: "运行中" },
  { value: "success", label: "成功" },
  { value: "failed", label: "失败" },
];

const EMPTY_APP_FORM = {
  name: "",
  description: "",
  kbId: "",
  defaultConfigRevisionId: "",
  status: "active" as RagAppStatus,
  scenarioTemplateId: "builtin_knowledge_qa_v1",
  scenarioType: "knowledge_qa",
  answerLength: "standard",
  citationCount: 3,
  noEvidencePolicy: "refuse",
  showSuggestedQuestions: true,
  publishApi: true,
  publishEmbed: true,
  embedEnabled: true,
  embedAllowedOrigins: "",
  embedGreeting: "你好，我是知识库问答助手。",
  createRecommendedConfigRevision: true,
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

function templateConfigValue(template: AgentScenarioTemplateDTO | undefined, key: string, fallback: string | number | boolean): string | number | boolean {
  const value = template?.defaultConfig?.[key];
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return value;
  return fallback;
}

export function RagAppManagement() {
  const navigate = useNavigate();
  const confirmDialog = useConfirmDialog();
  const [apps, setApps] = useState<RagAppDTO[]>([]);
  const [scenarioTemplates, setScenarioTemplates] = useState<AgentScenarioTemplateDTO[]>([]);
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
  const [isApiDocDrawerOpen, setIsApiDocDrawerOpen] = useState(false);
  const [editingAppId, setEditingAppId] = useState<string | null>(null);
  const [appForm, setAppForm] = useState(EMPTY_APP_FORM);
  const [createdPlainApiKey, setCreatedPlainApiKey] = useState<string | null>(null);
  const [keyExpiresAt, setKeyExpiresAt] = useState("");
  const [runtimeApiKey, setRuntimeApiKey] = useState("");
  const [runtimeQuery, setRuntimeQuery] = useState("");
  const [runtimeMode, setRuntimeMode] = useState<"blocking" | "streaming">("blocking");
  const [runtimeResult, setRuntimeResult] = useState<AppRuntimeChatResponse | null>(null);
  const [runtimeRetrieveResult, setRuntimeRetrieveResult] = useState<AppRuntimeRetrieveResponse | null>(null);
  const [runtimeEvents, setRuntimeEvents] = useState<AppRuntimeSseEvent[]>([]);
  const [runtimeFeedbackStatus, setRuntimeFeedbackStatus] = useState("wrong");
  const [runtimeFeedbackNote, setRuntimeFeedbackNote] = useState("");
  const [isRuntimeRunning, setIsRuntimeRunning] = useState(false);
  const [feedbackStatusItems, setFeedbackStatusItems] = useState<DictionaryItemDTO[]>([]);
  const [embedTokenPreview, setEmbedTokenPreview] = useState<{ token: string; expiresAt: string } | null>(null);

  const appRows = useMemo(() => apps.map(toRagAppViewModel), [apps]);
  const selectedAppView = selectedApp ? toRagAppViewModel(selectedApp) : null;
  const keyRows = useMemo(() => apiKeys.map(toRagAppApiKeyViewModel), [apiKeys]);
  const activeApiKeyCount = useMemo(
    () => apiKeys.filter((key) => key.status === "active" && (!key.expiresAt || new Date(key.expiresAt) >= new Date())).length,
    [apiKeys],
  );
  const invocationRows = useMemo(() => invocations.map(toAppInvocationViewModel), [invocations]);
  const conversationRows = useMemo(() => groupInvocationsByConversation(invocations), [invocations]);
  const conversationMessageRows = useMemo(
    () => selectedConversationDetail?.messages.map(toAppMessageViewModel) ?? [],
    [selectedConversationDetail],
  );
  const totalPages = Math.max(1, Math.ceil(totalApps / PAGE_SIZE));
  const selectedScenarioTemplate = useMemo(
    () => scenarioTemplates.find((template) => template.templateId === appForm.scenarioTemplateId),
    [appForm.scenarioTemplateId, scenarioTemplates],
  );

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
    void listAgentScenarioTemplates()
      .then(setScenarioTemplates)
      .catch(() => setScenarioTemplates([]));
  }, []);

  useEffect(() => {
    void fetchDictionaryItemsWithFallback("feedback_status").then((items) => {
      setFeedbackStatusItems(items);
      setRuntimeFeedbackStatus((current) => chooseActiveDictionaryValue(items, current, "wrong"));
    });
  }, []);

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
    const template = scenarioTemplates.find((item) => item.scenarioType === "knowledge_qa") ?? scenarioTemplates[0];
    setEditingAppId(null);
    setAppForm({
      ...EMPTY_APP_FORM,
      kbId: kbFilter || knowledgeBases[0]?.kbId || "",
      scenarioTemplateId: template?.templateId ?? EMPTY_APP_FORM.scenarioTemplateId,
      scenarioType: template?.scenarioType ?? EMPTY_APP_FORM.scenarioType,
      answerLength: String(templateConfigValue(template, "answerLength", EMPTY_APP_FORM.answerLength)),
      citationCount: Number(templateConfigValue(template, "citationCount", EMPTY_APP_FORM.citationCount)),
      noEvidencePolicy: String(templateConfigValue(template, "noEvidencePolicy", EMPTY_APP_FORM.noEvidencePolicy)),
      showSuggestedQuestions: Boolean(templateConfigValue(template, "showSuggestedQuestions", EMPTY_APP_FORM.showSuggestedQuestions)),
      publishApi: template?.defaultPublishChannels?.api ?? true,
      publishEmbed: template?.defaultPublishChannels?.embed ?? true,
      embedEnabled: Boolean(template?.defaultEmbedSettings?.enabled ?? true),
      embedGreeting: String(template?.defaultEmbedSettings?.greeting ?? EMPTY_APP_FORM.embedGreeting),
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
      scenarioTemplateId: app.scenarioTemplateId,
      scenarioType: app.scenarioType,
      answerLength: String(app.scenarioConfig.answerLength ?? EMPTY_APP_FORM.answerLength),
      citationCount: Number(app.scenarioConfig.citationCount ?? EMPTY_APP_FORM.citationCount),
      noEvidencePolicy: String(app.scenarioConfig.noEvidencePolicy ?? EMPTY_APP_FORM.noEvidencePolicy),
      showSuggestedQuestions: Boolean(app.scenarioConfig.showSuggestedQuestions ?? EMPTY_APP_FORM.showSuggestedQuestions),
      publishApi: app.publishChannels.api ?? true,
      publishEmbed: app.publishChannels.embed ?? false,
      embedEnabled: Boolean(app.embedSettings.enabled ?? false),
      embedAllowedOrigins: Array.isArray(app.embedSettings.allowedOrigins) ? app.embedSettings.allowedOrigins.join("\n") : "",
      embedGreeting: String(app.embedSettings.greeting ?? EMPTY_APP_FORM.embedGreeting),
      createRecommendedConfigRevision: false,
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
        scenarioType: appForm.scenarioType,
        scenarioTemplateId: appForm.scenarioTemplateId,
        scenarioConfig: {
          answerLength: appForm.answerLength,
          citationCount: Number(appForm.citationCount),
          noEvidencePolicy: appForm.noEvidencePolicy,
          showSuggestedQuestions: appForm.showSuggestedQuestions,
          greeting: appForm.embedGreeting,
        },
        publishChannels: {
          api: appForm.publishApi,
          embed: appForm.publishEmbed,
        },
        embedSettings: {
          enabled: appForm.embedEnabled,
          allowedOrigins: appForm.embedAllowedOrigins.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
          theme: "light",
          greeting: appForm.embedGreeting,
        },
      };
      const savedApp = editingAppId
        ? await updateRagApp(editingAppId, { ...payload, status: appForm.status })
        : await createRagApp({
            ...payload,
            kbId: appForm.kbId,
            createRecommendedConfigRevision: appForm.createRecommendedConfigRevision && !appForm.defaultConfigRevisionId,
          });
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

  const handleDeleteApp = async (app: RagAppDTO) => {
    const confirmed = await confirmDialog({
      title: "确认删除应用",
      description: "删除后，该应用会从列表中移除，外部 App Runtime 调用会被拒绝；历史调用和 QARun 不会被删除。",
      detail: app.name,
      confirmText: "删除应用",
      variant: "destructive",
    });
    if (!confirmed) return;

    setIsSaving(true);
    try {
      await deleteRagApp(app.appId);
      setSelectedApp((current) => (current?.appId === app.appId ? null : current));
      setFeedback({ variant: "success", title: "应用已删除", message: `${app.name} 已从应用列表移除。` });
      await loadApps();
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "应用删除失败",
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

  const handleDeleteApiKey = async (key: RagAppApiKeyDTO) => {
    if (!selectedApp) return;
    const confirmed = await confirmDialog({
      title: "确认删除 API Key",
      description: "删除后使用该 Key 的外部调用将返回 APP_API_KEY_INVALID，调用审计会保留但不再关联该 Key。",
      detail: `Key 前缀：${key.keyPrefix}`,
      confirmText: "删除 Key",
      variant: "destructive",
    });
    if (!confirmed) return;

    setIsSaving(true);
    try {
      await deleteRagAppApiKey(selectedApp.appId, key.apiKeyId);
      setFeedback({ variant: "success", title: "API Key 已删除", message: `${key.keyPrefix} 已不可用于外部调用。` });
      await loadAppDetail(selectedApp);
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "删除失败",
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
    setRuntimeRetrieveResult(null);
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
        const [response, retrieveResponse] = await Promise.all([
          chatWithAppRuntime(runtimeApiKey, { query: runtimeQuery.trim() }),
          retrieveWithAppRuntime(runtimeApiKey, { query: runtimeQuery.trim(), topK: 3 }),
        ]);
        setRuntimeResult(response);
        setRuntimeRetrieveResult(retrieveResponse);
        setFeedback({ variant: "success", title: "Blocking 试运行完成", message: `已生成 QARun ${shortId(response.runId)}。` });
      }
      await loadAppDetail(selectedApp);
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "请检查 API Key、应用状态和后端服务。";
      const friendlyTitle =
        rawMessage.includes("KB_DISABLED") ? "知识库已停用" :
        rawMessage.includes("KB_NOT_FOUND") ? "知识库不存在" :
        rawMessage.includes("APP_DISABLED") ? "应用已停用" :
        rawMessage.includes("KEY_EXPIRED") ? "API Key 已过期" :
        "Runtime 试运行失败";
      const friendlyMessage =
        rawMessage.includes("KB_DISABLED") ? "知识库已停用，请先在知识库管理页面恢复知识库状态。" :
        rawMessage.includes("KB_NOT_FOUND") ? "知识库不存在或已删除，请检查应用配置。" :
        rawMessage.includes("APP_DISABLED") ? "应用已停用，请先启用应用。" :
        rawMessage.includes("KEY_EXPIRED") ? "API Key 已过期，请创建新的 Key。" :
        rawMessage;
      setFeedback({ variant: "error", title: friendlyTitle, message: friendlyMessage });
    } finally {
      setIsRuntimeRunning(false);
    }
  };

  const handleSubmitRuntimeFeedback = async () => {
    if (!runtimeResult || !runtimeApiKey.trim()) return;
    setIsRuntimeRunning(true);
    try {
      const response = await submitAppRuntimeFeedback(runtimeApiKey, runtimeResult.messageId, {
        feedbackStatus: runtimeFeedbackStatus,
        failureType: ["wrong", "citation_error", "no_evidence", "partially_correct"].includes(runtimeFeedbackStatus) ? "manual_review_required" : null,
        feedbackNote: runtimeFeedbackNote || "P13 试运行人工反馈。",
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

  const handleCreateEmbedTokenPreview = async () => {
    if (!selectedApp || !runtimeApiKey.trim()) {
      setFeedback({ variant: "error", title: "无法生成嵌入 Token", message: "请先输入当前应用可用的 App API Key。" });
      return;
    }
    setIsRuntimeRunning(true);
    try {
      const response = await createAppRuntimeEmbedToken(runtimeApiKey, { ttlSeconds: 900 });
      setEmbedTokenPreview({ token: response.embedToken, expiresAt: response.expiresAt });
      setFeedback({ variant: "success", title: "短期 Token 已生成", message: "嵌入页预览链接已刷新，Token 15 分钟后过期。" });
    } catch (error) {
      setFeedback({
        variant: "error",
        title: "短期 Token 生成失败",
        message: error instanceof Error ? error.message : "请检查 API Key 和应用状态。",
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
    <div className="flex-1 overflow-auto">
      <div className="p-8 max-w-7xl mx-auto space-y-6">
        <PageHeader
          title="应用中心"
          description="将治理后的知识库和配置版本发布为外部可调用应用。"
          actions={
            <>
              <Button variant="outline" onClick={() => void loadApps()} disabled={isLoadingApps}>
                <RefreshCw className="mr-2 h-4 w-4" /> 刷新
              </Button>
              <Button variant="outline" onClick={() => setIsApiDocDrawerOpen(true)} disabled={!selectedApp}>
                <FileText className="mr-2 h-4 w-4" /> 调用文档
              </Button>
              <Button variant="primary" onClick={openCreateForm}>
                <Plus className="mr-2 h-4 w-4" /> 创建场景助手
              </Button>
            </>
          }
        />

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(520px,1fr)_440px]">
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

            <Table tableClassName="min-w-[860px]">
              <TableHeader>
                <TableRow>
                  <TableHead>应用</TableHead>
                  <TableHead>场景</TableHead>
                  <TableHead>知识库</TableHead>
                  <TableHead>检索配置</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead>更新时间</TableHead>
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
                      {app.description && (
                        <div className="max-w-[260px] truncate text-xs text-stone-gray" title={app.description}>{app.description}</div>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="space-y-1">
                        <Badge variant="warning">{app.scenarioLabel}</Badge>
                        <div className="text-xs text-stone-gray">{app.publishChannelLabel}</div>
                      </div>
                    </TableCell>
                    <TableCell>{selectedKnowledgeBaseName(knowledgeBases, app.kbId)}</TableCell>
                    <TableCell className="max-w-[180px] truncate" title={app.defaultRevisionLabel}>{app.defaultRevisionLabel}</TableCell>
                    <TableCell>
                      <Badge variant={statusBadgeVariant(app.status)}>{app.statusLabel}</Badge>
                    </TableCell>
                    <TableCell>{app.updatedAtLabel}</TableCell>
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
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <Badge variant={statusBadgeVariant(selectedApp.status)}>{selectedAppView.statusLabel}</Badge>
                      <Badge variant="warning">{selectedAppView.scenarioLabel}</Badge>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => openEditForm(selectedApp)}>
                      <Pencil className="mr-1 h-3 w-3" /> 编辑
                    </Button>
                    <Button
                      variant={selectedApp.status === "active" ? "outline" : "primary"}
                      size="sm"
                      disabled={isSaving}
                      onClick={() => void handleToggleAppStatus(selectedApp)}
                    >
                      {selectedApp.status === "active" ? <ShieldOff className="mr-1 h-3 w-3" /> : <RotateCcw className="mr-1 h-3 w-3" />}
                      {selectedApp.status === "active" ? "停用应用" : "启用应用"}
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={isSaving}
                      onClick={() => void handleDeleteApp(selectedApp)}
                    >
                      <Trash2 className="mr-1 h-3 w-3" /> 删除应用
                    </Button>
                  </div>
                </div>

                {selectedApp.knowledgeBaseName && (
                  <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm mt-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-stone-gray">所属知识库：</span>
                        <span className="text-near-black ml-2">{selectedApp.knowledgeBaseName}</span>
                      </div>
                      <Badge
                        variant={
                          selectedApp.knowledgeBaseStatus === "active" ? "success" :
                          selectedApp.knowledgeBaseStatus === "disabled" ? "warning" :
                          "error"
                        }
                      >
                        {selectedApp.knowledgeBaseStatus === "active" ? "运行中" :
                         selectedApp.knowledgeBaseStatus === "disabled" ? "已停用" :
                         selectedApp.knowledgeBaseStatus}
                      </Badge>
                    </div>
                    {selectedApp.knowledgeBaseStatus === "disabled" && (
                      <Alert variant="warning" title="知识库已停用" className="mt-2">
                        Runtime 调用将被拒绝。请先恢复知识库。
                      </Alert>
                    )}
                  </div>
                )}

                <div className="rounded-lg border border-border-cream bg-ivory p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-serif text-lg text-near-black">权限管理</h3>
                      <p className="mt-1 text-sm text-stone-gray">应用不单独维护成员，访问边界由所属知识库和 API Key 共同决定。</p>
                    </div>
                    <ShieldCheck className="h-5 w-5 text-terracotta" />
                  </div>
                  <div className="mt-4 grid gap-2 text-sm">
                    <div className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment px-3 py-2">
                      <span className="text-stone-gray">应用开关</span>
                      <Badge variant={statusBadgeVariant(selectedApp.status)}>{selectedAppView.statusLabel}</Badge>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment px-3 py-2">
                      <span className="text-stone-gray">知识库访问</span>
                      <Badge
                        variant={
                          selectedApp.knowledgeBaseStatus === "active" ? "success" :
                          selectedApp.knowledgeBaseStatus === "disabled" ? "warning" :
                          "inactive"
                        }
                      >
                        {selectedApp.knowledgeBaseStatus === "active" ? "运行中" :
                         selectedApp.knowledgeBaseStatus === "disabled" ? "已停用" :
                         selectedApp.knowledgeBaseStatus ?? "未知"}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-border-cream bg-parchment px-3 py-2">
                      <span className="text-stone-gray">可用 API Key</span>
                      <Badge variant={activeApiKeyCount > 0 ? "success" : "inactive"}>{activeApiKeyCount}</Badge>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => navigate(`/kb/${selectedApp.kbId}/members`)}>
                      <Users className="mr-1 h-3 w-3" /> 管理知识库权限
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setActiveTab("keys")}>
                      <KeyRound className="mr-1 h-3 w-3" /> 管理 API Key
                    </Button>
                  </div>
                </div>

                <Tabs.Root value={activeTab} onValueChange={(v) => setActiveTab(v as DetailTab)} className="rounded-lg border border-border-cream bg-ivory">
                  <Tabs.List className="flex border-b border-border-cream text-sm">
                    <Tabs.Trigger value="overview" className="flex-1 h-11 border-r border-border-cream text-stone-gray font-medium hover:text-near-black data-[state=active]:bg-parchment data-[state=active]:text-terracotta transition-all">概览</Tabs.Trigger>
                    <Tabs.Trigger value="keys" className="flex-1 h-11 border-r border-border-cream text-stone-gray font-medium hover:text-near-black data-[state=active]:bg-parchment data-[state=active]:text-terracotta transition-all">API Keys</Tabs.Trigger>
                    <Tabs.Trigger value="invocations" className="flex-1 h-11 border-r border-border-cream text-stone-gray font-medium hover:text-near-black data-[state=active]:bg-parchment data-[state=active]:text-terracotta transition-all">调用记录</Tabs.Trigger>
                    <Tabs.Trigger value="conversations" className="flex-1 h-11 text-stone-gray font-medium hover:text-near-black data-[state=active]:bg-parchment data-[state=active]:text-terracotta transition-all">会话</Tabs.Trigger>
                  </Tabs.List>
                  <div className="max-h-[calc(100vh-250px)] overflow-auto p-4">
                    {isLoadingDetail && <p className="text-sm text-stone-gray">详情加载中...</p>}
                    {!isLoadingDetail && activeTab === "overview" && (
                      <div className="space-y-3 text-sm">
                        {selectedApp.description?.trim() && (
                          <div>
                            <p className="text-xs text-stone-gray">描述</p>
                            <p className="mt-1 text-near-black">{selectedApp.description}</p>
                          </div>
                        )}
                        <div className="grid grid-cols-2 gap-3">
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">应用场景</p>
                            <p className="mt-1 text-sm font-medium text-near-black">{selectedAppView.scenarioLabel}</p>
                          </div>
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">发布方式</p>
                            <p className="mt-1 text-sm font-medium text-near-black">{selectedAppView.publishChannelLabel}</p>
                          </div>
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">API Key</p>
                            <p className="mt-1 text-lg font-medium text-near-black">{apiKeys.length}</p>
                          </div>
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">最近调用</p>
                            <p className="mt-1 text-lg font-medium text-near-black">{invocationRows[0]?.createdAtLabel ?? "-"}</p>
                          </div>
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">嵌入页</p>
                            <p className="mt-1 text-sm font-medium text-near-black">{selectedAppView.embedStatusLabel}</p>
                          </div>
                          <div className="rounded-lg border border-border-cream bg-parchment p-3">
                            <p className="text-xs text-stone-gray">场景模板</p>
                            <p className="mt-1 max-w-[160px] truncate font-mono text-xs text-near-black" title={selectedApp.scenarioTemplateId}>
                              {selectedApp.scenarioTemplateId}
                            </p>
                          </div>
                        </div>
                        {selectedApp.knowledgeBaseStatus === "disabled" && (
                          <Alert variant="warning" title="调用统计受影响">
                            知识库已停用，自停用以来无新调用记录。
                          </Alert>
                        )}
                        <div className="rounded-lg border border-border-cream bg-parchment p-3">
                          <p className="text-xs text-stone-gray">调用统计</p>
                          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-stone-gray">
                            <span>总调用：{invocationStats?.totalInvocations ?? 0}</span>
                            <span>运行中：{invocationStats?.runningInvocations ?? 0}</span>
                            <span>成功：{invocationStats?.successInvocations ?? 0}</span>
                            <span>失败：{invocationStats?.failedInvocations ?? 0}</span>
                            <span>平均延迟：{invocationStats?.averageLatencyMs == null ? "-" : `${invocationStats.averageLatencyMs}ms`}</span>
                            <span>无证据率：{(((invocationStats?.noEvidenceRate ?? 0) * 100)).toFixed(1)}%</span>
                            <span>限流：{invocationStats?.quotaExceededInvocations ?? 0}</span>
                            <span>并发拒绝：{invocationStats?.concurrencyExceededInvocations ?? 0}</span>
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
                              {runtimeRetrieveResult && (
                                <div className="space-y-1 rounded-md border border-border-cream bg-parchment p-2">
                                  <div className="text-stone-gray">retrieve 证据摘要：{runtimeRetrieveResult.evidences.length} 条</div>
                                  {runtimeRetrieveResult.evidences.map((item) => (
                                    <div key={item.evidenceId} className="text-near-black">
                                      {item.label}：{item.summary}
                                    </div>
                                  ))}
                                </div>
                              )}
                              <select
                                value={runtimeFeedbackStatus}
                                onChange={(event) => setRuntimeFeedbackStatus(event.target.value)}
                                className="h-8 w-full rounded-md border border-border-cream bg-parchment px-2 text-xs text-near-black focus:outline-none"
                              >
                                {feedbackStatusItems.map((item) => (
                                  <option key={item.code} value={item.code} disabled={item.status !== "active"}>
                                    {item.name}
                                  </option>
                                ))}
                              </select>
                              <textarea
                                value={runtimeFeedbackNote}
                                onChange={(event) => setRuntimeFeedbackNote(event.target.value)}
                                rows={2}
                                placeholder="反馈备注..."
                                className="w-full rounded-md border border-border-cream bg-parchment px-2 py-1 text-xs text-near-black focus:outline-none"
                              />
                              <Button variant="outline" size="sm" disabled={isRuntimeRunning} onClick={() => void handleSubmitRuntimeFeedback()}>
                                提交反馈并加入评估集
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
                          <div className="rounded-lg border border-border-cream bg-white p-3 text-xs">
                            <div className="mb-2 flex items-center justify-between gap-2">
                              <span className="text-stone-gray">嵌入页预览</span>
                              <Button variant="outline" size="sm" disabled={isRuntimeRunning} onClick={() => void handleCreateEmbedTokenPreview()}>
                                生成短期 Token
                              </Button>
                            </div>
                            {embedTokenPreview ? (
                              <div className="space-y-1">
                                <a
                                  className="break-all font-mono text-terracotta hover:underline"
                                  href={`/embed/runtime?token=${encodeURIComponent(embedTokenPreview.token)}`}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  /embed/runtime?token={shortId(embedTokenPreview.token, 24)}
                                </a>
                                <div className="text-stone-gray">过期时间：{new Date(embedTokenPreview.expiresAt).toLocaleString("zh-CN")}</div>
                              </div>
                            ) : (
                              <p className="text-stone-gray">使用当前 API Key 生成短期 Token 后，可打开嵌入页验证问答、Citation 和反馈。</p>
                            )}
                          </div>
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
                              <TableHead>可用性</TableHead>
                              <TableHead>过期时间</TableHead>
                              <TableHead>最近使用</TableHead>
                              <TableHead>操作</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {keyRows.length === 0 && (
                              <TableRow>
                                <TableCell colSpan={6} className="text-stone-gray">暂无 API Key</TableCell>
                              </TableRow>
                            )}
                            {keyRows.map((key) => (
                              <TableRow key={key.id}>
                                <TableCell mono>{key.keyPrefix}</TableCell>
                                <TableCell><Badge variant={statusBadgeVariant(key.status)}>{key.statusLabel}</Badge></TableCell>
                                <TableCell>
                                  {(() => {
                                    if (key.status === "revoked") return <Badge variant="inactive">已撤销</Badge>;
                                    const sourceKey = apiKeys.find((item) => item.apiKeyId === key.id);
                                    if (sourceKey?.expiresAt && new Date(sourceKey.expiresAt) < new Date()) return <Badge variant="inactive">已过期</Badge>;
                                    if (selectedApp.status === "disabled") return <Badge variant="warning">应用已停用</Badge>;
                                    if (selectedApp.knowledgeBaseStatus === "disabled") return <Badge variant="error">知识库已停用</Badge>;
                                    return <Badge variant="success">可用</Badge>;
                                  })()}
                                </TableCell>
                                <TableCell>{key.expiresAtLabel}</TableCell>
                                <TableCell>{key.lastUsedAtLabel}</TableCell>
                                <TableCell>
                                  {key.status === "active" ? (
                                    <Button variant="ghost" size="sm" disabled={isSaving} onClick={() => {
                                      const sourceKey = apiKeys.find((item) => item.apiKeyId === key.id);
                                      if (sourceKey) void handleDeleteApiKey(sourceKey);
                                    }}>
                                      删除 Key
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
                </Tabs.Root>
              </>
            )}
          </aside>
        </div>

      <Drawer
        isOpen={isApiDocDrawerOpen && Boolean(selectedApp)}
        onClose={() => setIsApiDocDrawerOpen(false)}
        title="API 调用文档"
        width="640px"
      >
        {selectedApp && (
          <>
            <DrawerSection title="调用入口">
              <div className="space-y-3 text-sm text-stone-gray">
                <p>当前应用：<span className="font-medium text-near-black">{selectedApp.name}</span></p>
                <p className="font-mono text-xs break-all">appId: {selectedApp.appId}</p>
                <div className="rounded-lg border border-border-cream bg-parchment p-3 font-mono text-xs text-near-black">
                  POST /api/v1/app-runtime/chat-messages
                </div>
                <p>请求头使用 <span className="font-mono">Authorization: Bearer &lt;app_api_key&gt;</span>。API Key 明文只在生成时显示一次，外部应用应保存到服务端安全配置。</p>
              </div>
            </DrawerSection>
            <DrawerSection title="blocking 示例">
              <pre className="overflow-auto rounded-lg border border-border-cream bg-parchment p-3 text-xs text-near-black">
{`$headers = @{ Authorization = "Bearer <app_api_key>" }
$body = @{
  query = "请基于知识库回答这个问题"
  endUserId = "external-user-001"
  responseMode = "blocking"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/app-runtime/chat-messages" -Headers $headers -ContentType "application/json" -Body $body`}
              </pre>
            </DrawerSection>
            <DrawerSection title="streaming 与反馈">
              <div className="space-y-3 text-sm text-stone-gray">
                <p>将 <span className="font-mono">responseMode</span> 设为 <span className="font-mono">streaming</span> 时返回 SSE，事件包括 <span className="font-mono">answer_delta</span>、<span className="font-mono">citation</span>、<span className="font-mono">usage</span> 和 <span className="font-mono">done</span>。</p>
                <div className="rounded-lg border border-border-cream bg-parchment p-3 font-mono text-xs text-near-black">
                  POST /api/v1/app-runtime/messages/&lt;message_id&gt;/feedback
                </div>
                <p>反馈可写回关联 QARun，并可选择沉淀为评估样本；外部响应不会暴露 Trace、Evidence 正文或内部配置。</p>
              </div>
            </DrawerSection>
            <DrawerSection title="返回字段与错误码">
              <div className="space-y-3 text-sm text-stone-gray">
                <p>成功响应包含 <span className="font-mono">answer</span>、<span className="font-mono">citations</span>、<span className="font-mono">conversationId</span>、<span className="font-mono">messageId</span>、<span className="font-mono">runId</span>、<span className="font-mono">usage</span> 和 <span className="font-mono">metadata</span>。</p>
                <div className="grid grid-cols-1 gap-2 text-xs">
                  {[
                    ["APP_API_KEY_INVALID", "401，Key 无效、过期或已删除"],
                    ["RAG_APP_DISABLED", "409，应用已停用"],
                    ["RAG_APP_NO_RUNNABLE_REVISION", "409，应用没有可运行配置"],
                    ["RAG_APP_QUOTA_EXCEEDED", "429，超过短窗口限流或日配额"],
                    ["RAG_APP_CONCURRENCY_EXCEEDED", "429，超过 maxConcurrent 并发上限"],
                  ].map(([code, description]) => (
                    <div key={code} className="rounded-md border border-border-cream bg-parchment p-2">
                      <span className="font-mono text-near-black">{code}</span>
                      <span className="ml-2 text-stone-gray">{description}</span>
                    </div>
                  ))}
                </div>
              </div>
            </DrawerSection>
            <DrawerSection title="运行治理">
              <div className="space-y-2 text-sm text-stone-gray">
                <p>调用进入 Runtime 后会先生成 running 调用记录，完成后更新为成功或失败。P13 的调用记录页可以刷新查看运行中请求。</p>
                <p>应用可通过 <span className="font-mono">metadata.runtimeLimits.maxConcurrent</span> 配置并发上限。V1.9 采用直接打回策略，不排队等待。</p>
              </div>
            </DrawerSection>
          </>
        )}
      </Drawer>

      <Drawer
        isOpen={isAppFormOpen}
        onClose={closeAppForm}
        title={editingAppId ? "编辑场景助手" : "创建场景助手"}
        width="640px"
      >
        {!editingAppId && (
          <DrawerSection title="1. 选择场景">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {scenarioTemplates.map((template) => (
                <button
                  key={template.templateId}
                  type="button"
                  onClick={() => setAppForm((current) => ({
                    ...current,
                    scenarioTemplateId: template.templateId,
                    scenarioType: template.scenarioType,
                    answerLength: String(templateConfigValue(template, "answerLength", current.answerLength)),
                    citationCount: Number(templateConfigValue(template, "citationCount", current.citationCount)),
                    noEvidencePolicy: String(templateConfigValue(template, "noEvidencePolicy", current.noEvidencePolicy)),
                    showSuggestedQuestions: Boolean(templateConfigValue(template, "showSuggestedQuestions", current.showSuggestedQuestions)),
                    publishApi: template.defaultPublishChannels.api ?? current.publishApi,
                    publishEmbed: template.defaultPublishChannels.embed ?? current.publishEmbed,
                    embedEnabled: Boolean(template.defaultEmbedSettings.enabled ?? current.embedEnabled),
                    embedGreeting: String(template.defaultEmbedSettings.greeting ?? current.embedGreeting),
                  }))}
                  className={`rounded-lg border p-3 text-left transition ${appForm.scenarioTemplateId === template.templateId ? "border-terracotta bg-parchment" : "border-border-cream bg-white hover:bg-parchment"}`}
                >
                  <div className="text-sm font-medium text-near-black">{template.name}</div>
                  <div className="mt-1 text-xs text-stone-gray">{template.description}</div>
                </button>
              ))}
            </div>
          </DrawerSection>
        )}
        <DrawerSection title="基本信息">
          <div className="space-y-4">
            <p className="text-sm text-stone-gray">
              {editingAppId ? "调整应用基础信息和场景参数。" : "按场景、知识库、运行配置、参数和发布方式创建业务助手。"}
            </p>
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
                <span className="text-stone-gray">3. 运行配置</span>
                <select
                  value={appForm.defaultConfigRevisionId}
                  onChange={(event) => setAppForm((current) => ({
                    ...current,
                    defaultConfigRevisionId: event.target.value,
                    createRecommendedConfigRevision: !event.target.value,
                  }))}
                  className="h-10 w-full rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
                >
                  <option value="">使用场景推荐配置</option>
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
        </DrawerSection>
        <DrawerSection title="4. 配置参数">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm">
              <span className="text-stone-gray">回答长度</span>
              <select
                value={appForm.answerLength}
                onChange={(event) => setAppForm((current) => ({ ...current, answerLength: event.target.value }))}
                className="h-10 w-full rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
              >
                <option value="short">简短</option>
                <option value="standard">标准</option>
                <option value="detailed">详细</option>
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-stone-gray">引用数量</span>
              <Input
                type="number"
                min={1}
                max={8}
                value={String(appForm.citationCount)}
                onChange={(event) => setAppForm((current) => ({ ...current, citationCount: Number(event.target.value) }))}
                className="bg-white"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-stone-gray">无证据策略</span>
              <select
                value={appForm.noEvidencePolicy}
                onChange={(event) => setAppForm((current) => ({ ...current, noEvidencePolicy: event.target.value }))}
                className="h-10 w-full rounded-md border border-border-cream bg-white px-3 text-sm text-near-black focus:outline-none"
              >
                <option value="refuse">拒答</option>
                <option value="brief">简要说明不足</option>
              </select>
            </label>
            <label className="flex items-center gap-2 pt-7 text-sm text-near-black">
              <input
                type="checkbox"
                checked={appForm.showSuggestedQuestions}
                onChange={(event) => setAppForm((current) => ({ ...current, showSuggestedQuestions: event.target.checked }))}
              />
              显示推荐追问
            </label>
          </div>
          {selectedScenarioTemplate?.scenarioType === "employee_training" && (
            <p className="mt-3 rounded-md border border-border-cream bg-parchment p-3 text-xs text-stone-gray">
              员工培训助手完整讲解、测验和评分流程将在 Sprint 49 接入；本轮先支持模型和创建入口。
            </p>
          )}
        </DrawerSection>
        <DrawerSection title="5. 发布方式">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="flex items-center gap-2 rounded-md border border-border-cream bg-white p-3 text-sm">
              <input type="checkbox" checked={appForm.publishApi} onChange={(event) => setAppForm((current) => ({ ...current, publishApi: event.target.checked }))} />
              API 调用
            </label>
            <label className="flex items-center gap-2 rounded-md border border-border-cream bg-white p-3 text-sm">
              <input type="checkbox" checked={appForm.publishEmbed} onChange={(event) => setAppForm((current) => ({ ...current, publishEmbed: event.target.checked, embedEnabled: event.target.checked }))} />
              嵌入页
            </label>
          </div>
          <div className="mt-3 space-y-3">
            <label className="block space-y-2 text-sm">
              <span className="text-stone-gray">嵌入页欢迎语</span>
              <Input value={appForm.embedGreeting} onChange={(event) => setAppForm((current) => ({ ...current, embedGreeting: event.target.value }))} className="bg-white" />
            </label>
            <label className="block space-y-2 text-sm">
              <span className="text-stone-gray">允许来源，每行一个 Origin</span>
              <textarea
                value={appForm.embedAllowedOrigins}
                onChange={(event) => setAppForm((current) => ({ ...current, embedAllowedOrigins: event.target.value }))}
                rows={2}
                placeholder="https://example.com"
                className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm text-near-black focus:outline-none"
              />
            </label>
          </div>
        </DrawerSection>
        {!editingAppId && (
          <DrawerSection title="6. 创建预览">
            <div className="grid grid-cols-1 gap-2 rounded-md border border-border-cream bg-parchment p-3 text-sm md:grid-cols-2">
              <span>场景：{selectedScenarioTemplate?.name ?? appForm.scenarioType}</span>
              <span>知识库：{selectedKnowledgeBaseName(knowledgeBases, appForm.kbId)}</span>
              <span>运行配置：{appForm.defaultConfigRevisionId ? shortId(appForm.defaultConfigRevisionId) : "场景推荐配置"}</span>
              <span>发布：{[appForm.publishApi ? "API" : null, appForm.publishEmbed ? "嵌入页" : null].filter(Boolean).join(" / ") || "-"}</span>
            </div>
          </DrawerSection>
        )}
        <div className="flex justify-end gap-3 border-t border-border-cream p-5">
          <Button variant="ghost" onClick={closeAppForm} disabled={isSaving}>取消</Button>
          <Button variant="primary" onClick={() => void handleSaveApp()} disabled={isSaving}>
            {editingAppId ? "保存修改" : "创建场景助手"}
          </Button>
        </div>
      </Drawer>

      <Dialog open={Boolean(createdPlainApiKey)} onOpenChange={(open) => { if (!open) handleClosePlainKey(); }}>
        <DialogContent className="sm:max-w-xl bg-ivory border-border-warm">
          <DialogHeader>
            <DialogTitle className="font-serif text-xl text-near-black">API Key 已生成</DialogTitle>
            <DialogDescription className="text-sm text-stone-gray">
              明文只显示一次，关闭后页面不会保留。请立即保存到外部应用的安全配置中。
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-lg border border-border-cream bg-parchment p-4 font-mono text-sm text-near-black break-all">
            {createdPlainApiKey}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => void copyPlainKey()}>
              <Copy className="mr-2 h-4 w-4" /> 复制
            </Button>
            <Button variant="primary" onClick={handleClosePlainKey}>我已保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      </div>
    </div>
  );
}
