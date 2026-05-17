import { readFile, mkdtemp, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import * as esbuild from "esbuild";

const rootDir = path.resolve(import.meta.dirname, "..");
const servicePath = path.join(rootDir, "src", "app", "services", "appRuntimeService.ts");
const typePath = path.join(rootDir, "src", "app", "types", "appRuntime.ts");

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
  const tempDir = await mkdtemp(path.join(tmpdir(), "rag-lab-app-runtime-service-"));
  const outputPath = path.join(tempDir, "module.mjs");
  await writeFile(outputPath, bundled.outputFiles[0].text, "utf8");
  return import(pathToFileURL(outputPath).href);
}

async function verifySourceShape() {
  assert(existsSync(servicePath), "必须创建 appRuntimeService.ts。");
  assert(existsSync(typePath), "必须创建 appRuntime.ts 类型文件。");
  const source = await readFile(servicePath, "utf8");
  for (const exportName of [
    "chatWithAppRuntime",
    "streamChatWithAppRuntime",
    "submitAppRuntimeFeedback",
    "parseAppRuntimeSse",
  ]) {
    assert(source.includes(`function ${exportName}`), `appRuntimeService 必须导出 ${exportName}。`);
  }
  assert(source.includes("Authorization") && source.includes("Bearer"), "Runtime 调用必须使用 Bearer API Key。");
  assert(!source.includes("localStorage") && !source.includes("sessionStorage"), "服务层不得持久化 App API Key。");
}

async function verifyBehavior() {
  const {
    chatWithAppRuntime,
    parseAppRuntimeSse,
    streamChatWithAppRuntime,
    submitAppRuntimeFeedback,
  } = await importTypescriptModule(servicePath);

  const calls = [];
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    if (String(url).endsWith("/chat-messages") && init.body?.includes('"streaming"')) {
      return new Response("event: done\ndata: {\"runId\":\"run-1\"}\n\n", {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    return Response.json({
      answer: "ok",
      conversationId: "conv-1",
      messageId: "msg-1",
      runId: "run-1",
      citations: [],
      usage: { citationCount: 0 },
      metadata: { responseMode: "blocking" },
    });
  };

  const blocking = await chatWithAppRuntime("rlak_test", { query: "真实问题" });
  assert(blocking.runId === "run-1", "blocking 响应必须返回 runId。");
  assert(calls[0].url === "/api/v1/app-runtime/chat-messages", "blocking 必须调用 App Runtime chat endpoint。");
  assert(calls[0].init.headers.Authorization === "Bearer rlak_test", "blocking 必须携带 Bearer API Key。");

  const streamResponse = await streamChatWithAppRuntime("rlak_test", { query: "真实问题" });
  assert(streamResponse instanceof Response, "streaming 调用应返回原始 Response 供页面读取 SSE。");
  assert(calls[1].init.body.includes('"responseMode":"streaming"'), "streaming 请求必须显式设置 responseMode。");

  await submitAppRuntimeFeedback("rlak_test", "msg-1", {
    feedbackStatus: "wrong",
    createEvaluationSample: true,
  });
  assert(calls[2].url === "/api/v1/app-runtime/messages/msg-1/feedback", "反馈必须调用 message feedback endpoint。");

  const events = parseAppRuntimeSse("event: done\ndata: {\"runId\":\"run-1\"}\n\n");
  assert(events.length === 1 && events[0].event === "done", "SSE 解析必须保留事件名和 JSON data。");
}

await verifySourceShape();
await verifyBehavior();
console.log("App Runtime service verification passed.");
