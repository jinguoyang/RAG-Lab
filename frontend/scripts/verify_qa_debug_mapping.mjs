import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import * as esbuild from "esbuild";

const rootDir = path.resolve(import.meta.dirname, "..");
const adapterPath = path.join(rootDir, "src", "app", "adapters", "qaRunAdapter.ts");
const qaDebugPagePath = path.join(rootDir, "src", "app", "pages", "P09_QADebug.tsx");
const qaHistoryPagePath = path.join(rootDir, "src", "app", "pages", "P10_QAHistory.tsx");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * 编译 QA adapter 纯函数，验证 P09 页面展示口径不依赖运行中的浏览器环境。
 */
async function importTypescriptModule(sourcePath) {
  const bundled = await esbuild.build({
    entryPoints: [sourcePath],
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
  });
  const tempDir = await mkdtemp(path.join(tmpdir(), "rag-lab-qa-debug-"));
  const outputPath = path.join(tempDir, "module.mjs");
  await writeFile(outputPath, bundled.outputFiles[0].text, "utf8");
  return import(pathToFileURL(outputPath).href);
}

function makeDetail() {
  return {
    runId: "f9f0bee1-fadf-45dd-ac96-9999d9a31b2a",
    sourceRunId: null,
    status: "success",
    kbId: "ab06d48e-6e5e-491f-9b2b-329cc7372aa7",
    configRevisionId: "ebf7c195-f9b2-45e3-ab5e-556d4a99fcff",
    query: "采购职责由哪些组织负责",
    rewrittenQuery: "采购职责由哪些部门负责",
    answer: "采购职责由物资采购部负责。",
    retrievalDiagnostics: {
      denseCount: 0,
      sparseCount: 15,
      graphCount: 0,
      fusedCount: 15,
      droppedByPermission: 0,
      pipelineParams: {
        retrievalTopK: { dense: 20, sparse: 15, graph: 50 },
        retrievalScoreThreshold: { dense: 0.75, sparse: 0.2, graph: 0 },
      },
    },
    overrideSnapshot: {},
    pipelineSnapshot: {},
    nodeParamSnapshot: {},
    feedbackStatus: "unrated",
    feedbackNote: null,
    failureType: null,
    candidates: [
      {
        candidateId: "candidate-1",
        chunkId: "b397dcc0-e389-4ea9-95fd-34d88880ebe5",
        sourceType: "sparse",
        rawScore: 0.77343,
        rerankScore: 0.77343,
        rankNo: 1,
        isAuthorized: true,
        dropReason: null,
        metadata: {
          documentId: "26b2436f-e3d1-4e8a-8e54-7af5f0166ffa",
          documentName: "劳动保护用品管理办法.md",
          chunkIndex: 24,
          section: "第三章 劳动保护用品工作流程",
          contentPreview: "物资采购部依据《物资采购管理制度》的要求进行采购。",
          fusedScore: 2.0000613,
          retrievalScores: { sparse: 6.666871 },
        },
      },
    ],
    evidence: [
      {
        evidenceId: "evidence-1",
        chunkId: "b397dcc0-e389-4ea9-95fd-34d88880ebe5",
        candidateId: "candidate-1",
        contentSnapshot: "物资采购部依据《物资采购管理制度》的要求进行采购。",
        sourceSnapshot: {},
        redactionStatus: "none",
      },
    ],
    citations: [
      {
        citationId: "citation-1",
        evidenceId: "evidence-1",
        label: "sparse#1",
        locationSnapshot: {
          documentId: "26b2436f-e3d1-4e8a-8e54-7af5f0166ffa",
          documentName: "劳动保护用品管理办法.md",
          chunkId: "b397dcc0-e389-4ea9-95fd-34d88880ebe5",
          chunkIndex: 24,
          section: "第三章 劳动保护用品工作流程",
        },
      },
    ],
    trace: [
      {
        stepKey: "multiQuery",
        status: "success",
        inputSummary: {},
        outputSummary: {
          queries: [
            "采购职责通常由哪些部门或机构负责",
            "采购职责由哪些组织负责",
          ],
          mergeStrategy: "rrf",
        },
        metrics: { actualQueryCount: 2 },
        errorCode: null,
        errorMessage: null,
      },
      {
        stepKey: "denseRetrieval",
        status: "success",
        inputSummary: {},
        outputSummary: { candidateCount: 0, droppedByScoreThreshold: 20 },
        metrics: { topK: 20, scoreThreshold: 0.75 },
        errorCode: null,
        errorMessage: null,
      },
      {
        stepKey: "sparseRetrieval",
        status: "success",
        inputSummary: {},
        outputSummary: { candidateCount: 15, droppedByScoreThreshold: 0 },
        metrics: { topK: 15, scoreThreshold: 0.2 },
        errorCode: null,
        errorMessage: null,
      },
      {
        stepKey: "fusion",
        status: "success",
        inputSummary: { inputCandidates: 15 },
        outputSummary: { candidateCount: 15, dedupedCandidates: 0 },
        metrics: {},
        errorCode: null,
        errorMessage: null,
      },
      {
        stepKey: "rerank",
        status: "success",
        inputSummary: { inputCandidates: 15 },
        outputSummary: { candidateCount: 5 },
        metrics: {},
        errorCode: null,
        errorMessage: null,
      },
      {
        stepKey: "permissionFilter",
        status: "success",
        inputSummary: { inputCandidates: 5 },
        outputSummary: { authorizedCandidates: 5, droppedCandidates: 0 },
        metrics: {},
        errorCode: null,
        errorMessage: null,
      },
      {
        stepKey: "contextPacking",
        status: "success",
        inputSummary: { authorizedEvidenceCount: 5 },
        outputSummary: { contextCandidateCount: 5, maxContextTokens: 6000 },
        metrics: {},
        errorCode: null,
        errorMessage: null,
      },
    ],
    metrics: { latencyMs: 54782 },
    createdAt: "2026-05-12T00:56:59.777004+08:00",
  };
}

const { toQADebugResult, toQARewriteTrace } = await importTypescriptModule(adapterPath);
const viewModel = toQADebugResult(makeDetail());
const rewriteTrace = toQARewriteTrace(makeDetail());

assert(viewModel.retrievalCards[0].summary.includes("阈值过滤 20 条"), "Dense 0 条候选应解释阈值过滤原因。");
assert(viewModel.retrievalCards[1].summary.includes("2 个 query × topK 15"), "Sparse 多 query 时应解释为什么候选数可能超过单 query topK。");
assert(viewModel.diagnostics.recalled === "15", "总召回量应来自 trace/fusion 输入，而不是候选列表长度。");
assert(viewModel.diagnostics.finalContext === "5", "最终上下文大小应来自 contextPacking，而不是 evidence 条数。");
assert(viewModel.diagnostics.filtered === "0", "权限过滤为 0 时不应显示 -0。");
assert(viewModel.candidates[0].title.includes("#24"), "候选标题应包含 Chunk 位置信息。");
assert(viewModel.candidates[0].snippet.includes("物资采购部"), "候选应显示正文预览。");
assert(viewModel.citations[0].documentId === "26b2436f-e3d1-4e8a-8e54-7af5f0166ffa", "Citation 应保留真实 documentId 用于跳转。");
assert(rewriteTrace.originalQuery === "采购职责由哪些组织负责", "问题改写视图应保留原始问题。");
assert(rewriteTrace.rewrittenQuery === "采购职责由哪些部门负责", "问题改写视图应展示改写后问题。");
assert(rewriteTrace.statusLabel === "已改写", "问题改写成功时应显示已改写状态。");
assert(rewriteTrace.providerLabel === "-", "没有 provider 信息时应显示占位。");

const qaDebugPageSource = await readFile(qaDebugPagePath, "utf8");
const qaHistoryPageSource = await readFile(qaHistoryPagePath, "utf8");
assert(qaDebugPageSource.includes("原始问题") && qaDebugPageSource.includes("改写后问题"), "QA 调试 Trace 应展示原始问题和改写后问题。");
assert(qaHistoryPageSource.includes("DrawerSection title=\"问题改写\""), "QA 历史详情 Drawer 应包含问题改写区。");
assert(qaHistoryPageSource.includes("toQARewriteTrace(selectedDetail)"), "QA 历史详情应复用问题改写视图模型。");

console.log("QA debug mapping verification passed.");
