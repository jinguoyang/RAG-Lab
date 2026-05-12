import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import * as esbuild from "esbuild";

const rootDir = path.resolve(import.meta.dirname, "..");
const helperPath = path.join(rootDir, "src", "app", "utils", "qaPartialDiagnostics.ts");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * 将 TypeScript 诊断 helper 临时编译为 ESM，便于直接验证纯函数行为。
 */
async function importTypescriptModule(sourcePath) {
  const bundled = await esbuild.build({
    entryPoints: [sourcePath],
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
  });
  const tempDir = await mkdtemp(path.join(tmpdir(), "rag-lab-qa-partial-"));
  const outputPath = path.join(tempDir, "module.mjs");
  await writeFile(outputPath, bundled.outputFiles[0].text, "utf8");
  return import(pathToFileURL(outputPath).href);
}

const { deriveQAPartialDiagnostics } = await importTypescriptModule(helperPath);

function makeDetail(overrides = {}) {
  return {
    runId: "run-1",
    sourceRunId: null,
    status: "partial",
    kbId: "kb-1",
    configRevisionId: "rev-1",
    query: "Graph 为什么缺失？",
    rewrittenQuery: null,
    answer: "答案仍可用，但图侧证据缺失。",
    retrievalDiagnostics: {},
    overrideSnapshot: {},
    pipelineSnapshot: {},
    nodeParamSnapshot: {},
    feedbackStatus: "unrated",
    feedbackNote: null,
    failureType: null,
    candidates: [],
    evidence: [],
    citations: [],
    trace: [],
    metrics: {},
    createdAt: "2026-05-11T00:00:00Z",
    ...overrides,
  };
}

/**
 * 验证 trace 中的部分成功步骤会被转为用户可读的降级原因。
 */
function verifyTraceDiagnostics() {
  const detail = makeDetail({
    retrievalDiagnostics: { providerErrors: ["graphRetrieval"] },
    trace: [
      {
        stepKey: "denseRetrieval",
        status: "success",
        inputSummary: {},
        outputSummary: { count: 8 },
        metrics: {},
        errorCode: null,
        errorMessage: null,
      },
      {
        stepKey: "graphRetrieval",
        status: "partial",
        inputSummary: {},
        outputSummary: { reason: "graphProviderTimeout", provider: "neo4j" },
        metrics: {},
        errorCode: "PROVIDER_ERROR",
        errorMessage: "Neo4j request timed out",
      },
    ],
  });

  const diagnostics = deriveQAPartialDiagnostics(detail);

  assert(diagnostics.hasPartialIssue === true, "partial run 应识别为存在降级详情。");
  assert(diagnostics.affectedSteps.length === 1, "应只提取 partial/failed 的 trace step。");
  assert(diagnostics.affectedSteps[0].stepKey === "graphRetrieval", "应保留降级 stepKey。");
  assert(diagnostics.affectedSteps[0].errorCode === "PROVIDER_ERROR", "应保留错误码。");
  assert(diagnostics.providerErrors.includes("graphRetrieval"), "应暴露 providerErrors。");
  assert(diagnostics.summary.includes("Graph 检索"), "摘要应使用用户可读阶段名。");
  assert(diagnostics.impact.includes("图侧"), "影响描述应说明图侧上下文缺失。");
}

/**
 * 验证没有 trace 明细时仍给出可解释的 fallback，避免页面只显示“部分成功”。
 */
function verifyFallbackDiagnostics() {
  const diagnostics = deriveQAPartialDiagnostics(makeDetail({ failureType: "provider_degraded" }));

  assert(diagnostics.hasPartialIssue === true, "partial fallback 应识别为存在诊断信息。");
  assert(diagnostics.summary.includes("provider_degraded"), "fallback 摘要应包含 failureType。");
  assert(diagnostics.affectedSteps.length === 0, "没有 trace 时不应伪造受影响步骤。");
}

verifyTraceDiagnostics();
verifyFallbackDiagnostics();
console.log("QA partial diagnostics verification passed.");
