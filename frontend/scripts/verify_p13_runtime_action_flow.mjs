import { readFile } from "node:fs/promises";
import path from "node:path";

const rootDir = path.resolve(import.meta.dirname, "..");
const pagePath = path.join(rootDir, "src", "app", "pages", "P13_RagAppManagement.tsx");
const ragAppServicePath = path.join(rootDir, "src", "app", "services", "ragAppService.ts");
const appRuntimeServicePath = path.join(rootDir, "src", "app", "services", "appRuntimeService.ts");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function assertIncludes(source, needle, message) {
  assert(source.includes(needle), message);
}

const pageSource = await readFile(pagePath, "utf8");
const ragAppServiceSource = await readFile(ragAppServicePath, "utf8");
const appRuntimeServiceSource = await readFile(appRuntimeServicePath, "utf8");

for (const [needle, message] of [
  ["createRagApp", "P13 创建应用动作必须调用 RAG App 管理服务。"],
  ["deleteRagApp", "P13 删除应用动作必须调用 RAG App 管理服务。"],
  ["createRagAppApiKey", "P13 生成 Key 动作必须调用 API Key 创建接口。"],
  ["deleteRagAppApiKey", "P13 删除 Key 动作必须调用 API Key 删除接口。"],
  ["chatWithAppRuntime", "P13 blocking 试运行必须调用 App Runtime 接口。"],
  ["streamChatWithAppRuntime", "P13 streaming 试运行必须调用 App Runtime 接口。"],
  ["submitAppRuntimeFeedback", "P13 反馈动作必须调用 Runtime 反馈接口。"],
  ["getRagAppConversationDetail", "P13 会话详情必须调用只读详情接口。"],
  ["buildQARunHistoryLink", "P13 调用记录必须能跳转到 P10 QARun 详情。"],
]) {
  assertIncludes(pageSource, needle, message);
}

for (const label of ["创建应用", "生成 Key", "试运行", "提交负反馈并加入评估集", "删除 Key", "删除应用", "查看详情"]) {
  assertIncludes(pageSource, label, `P13 必须提供 ${label} 前端动作。`);
}

for (const label of ["调用文档", "运行中", "并发拒绝"]) {
  assertIncludes(pageSource, label, `P13 必须提供 ${label} 运行治理信息。`);
}

for (const forbidden of ["撤销", "未填写描述", "默认配置", "跟随知识库 active revision"]) {
  assert(!pageSource.includes(forbidden), `P13 不应继续展示旧文案 ${forbidden}。`);
}

assertIncludes(ragAppServiceSource, "apiDelete", "RAG App service 删除动作必须复用 apiDelete。");

for (const endpoint of [
  "/rag-apps",
  "/api-keys",
  "/invocations",
  "/stats",
  "/conversations/",
]) {
  assertIncludes(ragAppServiceSource, endpoint, `RAG App service 必须覆盖 ${endpoint} 真实接口。`);
}

for (const endpoint of [
  "/app-runtime/chat-messages",
  "/app-runtime/messages/",
]) {
  assertIncludes(appRuntimeServiceSource, endpoint, `App Runtime service 必须覆盖 ${endpoint} 真实接口。`);
}

for (const forbidden of ["mockApps", "demoApps", "sampleInvocations", "fakeRuntime", "hardcodedAnswer"]) {
  assert(!pageSource.includes(forbidden), `P13 不应包含演示数据标识 ${forbidden}。`);
}

assert(!pageSource.includes("localStorage") && !pageSource.includes("sessionStorage"), "P13 不得持久化 API Key 明文。");

console.log("P13 runtime action flow contract verification passed.");
