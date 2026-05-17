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
    "listRagAppApiKeys",
    "createRagAppApiKey",
    "revokeRagAppApiKey",
    "listRagAppInvocations",
    "getRagAppInvocationStats",
    "getRagAppConversationDetail",
  ]) {
    assert(source.includes(`function ${exportName}`), `ragAppService 必须导出 ${exportName}。`);
  }
  assert(source.includes("apiGet") && source.includes("apiPostJson") && source.includes("apiPatchJson"), "服务必须复用现有 apiClient。");
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
  assert(app.defaultRevisionLabel === "跟随知识库 active revision", "缺省默认配置应显示跟随知识库 active revision。");

  const key = toRagAppApiKeyViewModel({
    apiKeyId: "key-1",
    appId: "app-1",
    keyPrefix: "rlak_xxxxxxxx",
    status: "revoked",
    expiresAt: null,
    lastUsedAt: null,
    createdAt: "2026-05-15T00:00:00Z",
    revokedAt: "2026-05-15T00:00:00Z",
  });
  assert(key.statusLabel === "已撤销", "撤销 Key 应显示为已撤销。");
  assert(key.expiresAtLabel === "永不过期", "无过期时间应显示为永不过期。");

  const invocation = toAppInvocationViewModel({
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
  });
  assert(invocation.statusLabel === "失败", "失败调用应显示为失败。");
  assert(invocation.errorLabel === "RAG_APP_DISABLED", "错误码必须保留原始 code。");

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
  assert(layoutSource.includes("RAG 应用"), "平台导航必须包含 RAG 应用入口。");
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

await verifyServiceContract();
await verifyAdapterBehavior();
if (existsSync(pagePath)) {
  await verifyRouteAndPage();
  await verifyPlaintextKeyGuard();
  await verifyRuntimeTrialPanel();
  await verifyQARunDeepLink();
  await verifyConversationDetailPanel();
}
console.log("RAG App management UI verification passed.");
