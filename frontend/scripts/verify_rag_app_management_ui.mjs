import { readFile, mkdtemp, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import * as esbuild from "esbuild";

const rootDir = path.resolve(import.meta.dirname, "..");
const servicePath = path.join(rootDir, "src", "app", "services", "ragAppService.ts");
const adapterPath = path.join(rootDir, "src", "app", "adapters", "ragAppAdapter.ts");
const routePath = path.join(rootDir, "src", "app", "routes.tsx");
const layoutPath = path.join(rootDir, "src", "app", "layouts", "PlatformLayout.tsx");
const pagePath = path.join(rootDir, "src", "app", "pages", "P13_RagAppManagement.tsx");
const qaHistoryPagePath = path.join(rootDir, "src", "app", "pages", "P10_QAHistory.tsx");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function importTypescriptModule(sourcePath) {
  const bundled = await esbuild.build({
    entryPoints: [sourcePath],
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
  });
  const tempDir = await mkdtemp(path.join(tmpdir(), "rag-lab-rag-app-ui-"));
  const outputPath = path.join(tempDir, "module.mjs");
  await writeFile(outputPath, bundled.outputFiles[0].text, "utf8");
  return import(pathToFileURL(outputPath).href);
}

async function verifyServiceContract() {
  const source = await readFile(servicePath, "utf8");
  for (const exportName of [
    "listRagApps",
    "createRagApp",
    "updateRagApp",
    "deleteRagApp",
    "listRagAppApiKeys",
    "createRagAppApiKey",
    "deleteRagAppApiKey",
    "listRagAppInvocations",
    "getRagAppInvocationStats",
    "getRagAppConversationDetail",
  ]) {
    assert(source.includes(`function ${exportName}`), `ragAppService 必须导出 ${exportName}。`);
  }
  assert(source.includes("apiGet") && source.includes("apiPostJson") && source.includes("apiPatchJson") && source.includes("apiDelete"), "服务必须复用现有 apiClient。");
  assert(!source.includes("localStorage") && !source.includes("sessionStorage"), "服务层不得持久化 API Key 明文。");
}

async function verifyAdapterBehavior() {
  const {
    groupInvocationsByConversation,
    toAppInvocationViewModel,
    toRagAppApiKeyViewModel,
    toRagAppViewModel,
  } = await importTypescriptModule(adapterPath);

  const app = toRagAppViewModel({
    appId: "app-1",
    kbId: "kb-1",
    defaultConfigRevisionId: null,
    name: "客服助手",
    description: null,
    status: "active",
    outputPolicy: {},
    metadata: {},
    createdAt: "2026-05-15T00:00:00Z",
    updatedAt: "2026-05-15T00:00:00Z",
  });
  assert(app.statusLabel === "启用", "RAG App active 状态应显示为启用。");
  assert(app.defaultRevisionLabel === "跟随知识库", "缺省检索配置应显示跟随知识库。");
  assert(app.description === "", "未填写描述时不应生成占位描述。");

  const key = toRagAppApiKeyViewModel({
    apiKeyId: "key-1",
    appId: "app-1",
    keyPrefix: "rlak_xxxxxxxx",
    status: "active",
    expiresAt: null,
    lastUsedAt: null,
    createdAt: "2026-05-15T00:00:00Z",
    revokedAt: null,
  });
  assert(key.statusLabel === "启用", "活跃 Key 应显示为启用。");
  assert(key.expiresAtLabel === "永不过期", "无过期时间应显示为永不过期。");

  const invocationDto = {
    invocationId: "inv-1",
    appId: "app-1",
    apiKeyId: "key-1",
    conversationId: "conv-1",
    messageId: "msg-1",
    qaRunId: "run-1",
    status: "failed",
    errorCode: "RAG_APP_DISABLED",
    latencyMs: 12,
    requestSummary: { queryLength: 12 },
    responseSummary: {},
    createdAt: "2026-05-15T00:00:00Z",
  };
  const invocation = toAppInvocationViewModel(invocationDto);
  assert(invocation.statusLabel === "失败", "失败调用应显示为失败。");
  assert(invocation.errorLabel === "RAG_APP_DISABLED", "错误码必须保留原始 code。");

  const runningInvocation = toAppInvocationViewModel({
    ...invocationDto,
    invocationId: "inv-running",
    status: "running",
    errorCode: null,
    latencyMs: null,
  });
  assert(runningInvocation.statusLabel === "运行中", "运行中调用应显示为运行中。");
  assert(runningInvocation.latencyLabel === "运行中", "运行中调用延迟应提示运行中。");

  const conversations = groupInvocationsByConversation([
    { ...invocation, status: "failed", invocationId: "inv-1" },
    { ...invocation, status: "success", invocationId: "inv-2" },
  ]);
  assert(conversations.length === 1 && conversations[0].invocationCount === 2, "会话摘要应按 conversationId 聚合。");
}

async function verifyRouteAndPage() {
  const routeSource = await readFile(routePath, "utf8");
  const layoutSource = await readFile(layoutPath, "utf8");
  assert(existsSync(pagePath), "必须创建 P13_RagAppManagement.tsx。");
  assert(routeSource.includes("P13_RagAppManagement"), "路由必须注册 P13_RagAppManagement。");
  assert(routeSource.includes('path: "rag-apps"'), "平台路由必须包含 /rag-apps。");
  assert(layoutSource.includes("应用中心"), "平台导航必须显示应用中心入口。");
  assert(layoutSource.includes("DropdownMenuTrigger"), "平台侧边栏用户栏必须作为账户菜单触发器。");
  assert(layoutSource.includes("DropdownMenuItem"), "账户菜单必须使用菜单项承载退出登录等操作。");
  assert(layoutSource.includes("个人中心"), "账户菜单应预留个人中心入口，便于后续扩展。");
  assert(!layoutSource.includes('<Button variant="ghost" className="w-full justify-start text-stone-gray hover:text-error-red">'), "退出登录不应作为侧边栏底部常驻按钮。");
}

async function verifyPlaintextKeyGuard() {
  if (!existsSync(pagePath)) return;
  const pageSource = await readFile(pagePath, "utf8");
  assert(pageSource.includes("createdPlainApiKey"), "页面必须使用单独状态保存一次性明文 Key。");
  assert(pageSource.includes("setCreatedPlainApiKey(null)"), "关闭创建成功弹窗时必须清理明文 Key。");
  assert(!pageSource.includes("localStorage") && !pageSource.includes("sessionStorage"), "页面不得持久化 API Key 明文。");
}

async function verifyRuntimeTrialPanel() {
  if (!existsSync(pagePath)) return;
  const pageSource = await readFile(pagePath, "utf8");
  assert(pageSource.includes("chatWithAppRuntime"), "P13 必须接入 App Runtime blocking 试运行服务。");
  assert(pageSource.includes("streamChatWithAppRuntime"), "P13 必须接入 App Runtime streaming 试运行服务。");
  assert(pageSource.includes("submitAppRuntimeFeedback"), "P13 必须支持从试运行结果提交 Runtime 反馈。");
  assert(pageSource.includes("runtimeApiKey"), "P13 试运行 API Key 必须只保存在页面内存状态。");
  assert(pageSource.includes("keyExpiresAt"), "P13 生成 API Key 时必须支持过期时间输入。");
  assert(pageSource.includes("调用统计"), "P13 必须展示应用级调用统计。");
  assert(pageSource.includes("runningInvocations"), "P13 调用统计必须展示运行中调用数量。");
  assert(pageSource.includes("concurrencyExceededInvocations"), "P13 调用统计必须展示并发拒绝次数。");
  assert(pageSource.includes("调用文档"), "P13 必须在页头提供调用文档入口。");
  assert(pageSource.includes("isApiDocDrawerOpen"), "P13 必须使用弹出层状态展示 API 调用文档。");
  assert(pageSource.includes("RAG_APP_CONCURRENCY_EXCEEDED"), "P13 API 文档必须说明并发超限错误。");
  assert(pageSource.includes("删除应用"), "P13 必须提供删除应用动作。");
  assert(pageSource.includes("删除 Key"), "P13 必须提供物理删除 Key 动作。");
  assert(!pageSource.includes("未填写描述"), "P13 不应展示未填写描述占位文案。");
  assert(!pageSource.includes("默认配置"), "P13 展示文案应改为检索配置。");
  assert(!pageSource.includes("跟随知识库 active revision"), "P13 应使用跟随知识库短文案。");
  assert(!pageSource.includes("撤销"), "P13 不应保留 API Key 撤销文案。");
}

async function verifyQARunDeepLink() {
  assert(existsSync(qaHistoryPagePath), "必须存在 P10_QAHistory.tsx。");
  const pageSource = await readFile(pagePath, "utf8");
  const qaHistorySource = await readFile(qaHistoryPagePath, "utf8");
  assert(pageSource.includes("buildQARunHistoryLink"), "P13 必须集中生成带 runId 的 QA 历史链接。");
  assert(pageSource.includes("runId="), "P13 调用记录跳转必须携带 runId 查询参数。");
  assert(qaHistorySource.includes("useLocation"), "P10 必须读取 URL 查询参数。");
  assert(qaHistorySource.includes("targetRunId"), "P10 必须维护目标 runId 自动打开状态。");
  assert(qaHistorySource.includes("openRun(matchedRun"), "P10 必须在历史加载后自动打开匹配 QARun。");
}

async function verifyConversationDetailPanel() {
  const pageSource = await readFile(pagePath, "utf8");
  assert(pageSource.includes("getRagAppConversationDetail"), "P13 会话页必须调用真实会话详情接口。");
  assert(pageSource.includes("selectedConversationDetail"), "P13 必须维护当前会话详情状态。");
  assert(pageSource.includes("conversationMessageRows"), "P13 必须将 App Message 转为可展示行。");
  assert(pageSource.includes("endUserId"), "P13 会话详情必须展示外部用户线索。");
  assert(pageSource.includes("查看详情"), "P13 会话列表必须提供查看详情动作。");
}

async function verifyFilterLayoutGuard() {
  const pageSource = await readFile(pagePath, "utf8");
  assert(pageSource.includes("flex flex-wrap items-center"), "P13 筛选栏必须允许控件换行，避免查询按钮越界。");
  assert(pageSource.includes("w-[128px]"), "P13 状态筛选下拉栏应收窄到够展示状态文字。");
  assert(pageSource.includes("whitespace-nowrap"), "P13 查询按钮文字必须保持水平排列。");
  assert(!pageSource.includes('tableClassName="min-w-[900px]"'), "P13 应用列表不得强制 900px 最小宽度造成横向滚动。");
  assert(pageSource.includes('tableClassName="table-fixed"'), "P13 应用列表应使用固定布局在当前容器内完整展示。");
  assert(pageSource.includes("w-[28px]"), "P13 应用列表多选列应收窄，缩短多选框与应用名距离。");
  assert(!pageSource.includes("<TableHead>检索配置</TableHead>"), "P13 应用列表空间不足时不展示检索配置列。");
}

await verifyServiceContract();
await verifyAdapterBehavior();
if (existsSync(pagePath)) {
  await verifyRouteAndPage();
  await verifyPlaintextKeyGuard();
  await verifyRuntimeTrialPanel();
  await verifyQARunDeepLink();
  await verifyConversationDetailPanel();
  await verifyFilterLayoutGuard();
}
console.log("RAG App management UI verification passed.");
