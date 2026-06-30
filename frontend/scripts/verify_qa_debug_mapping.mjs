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
    answerBlocks: [
      {
        text: "采购职责由物资采购部负责。",
        citationEvidenceIds: ["evidence-1"],
      },
    ],
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

function makeExpandedDetail() {
  const detail = makeDetail();
  return {
    ...detail,
    answer: "杭州18号线列车数量为42辆。资源计算中按44辆预估。",
    answerBlocks: [
      { text: "杭州18号线列车数量为42辆。", citationEvidenceIds: ["evidence-1"] },
      { text: "资源计算中按44辆预估。", citationEvidenceIds: ["evidence-3"] },
    ],
    evidence: [
      ...detail.evidence,
      {
        evidenceId: "evidence-2",
        chunkId: "expanded-chunk",
        candidateId: "candidate-1",
        contentSnapshot: "相邻上下文，不是答案直接引用。",
        sourceSnapshot: { expandedContext: true },
        redactionStatus: "none",
      },
      {
        evidenceId: "evidence-3",
        chunkId: "resource-chunk",
        candidateId: "candidate-2",
        contentSnapshot: "资源计算表中18号线按44辆预估。",
        sourceSnapshot: {},
        redactionStatus: "none",
      },
    ],
    citations: [
      ...detail.citations,
      {
        citationId: "citation-2",
        evidenceId: "evidence-2",
        label: "dense#2",
        locationSnapshot: { chunkId: "expanded-chunk", chunkIndex: 25 },
      },
      {
        citationId: "citation-3",
        evidenceId: "evidence-3",
        label: "dense#3",
        locationSnapshot: { chunkId: "resource-chunk", chunkIndex: 26 },
      },
    ],
    trace: detail.trace.map((step) => {
      if (step.stepKey === "permissionFilter") {
        return { ...step, outputSummary: { authorizedCandidates: 5, droppedCandidates: 0 } };
      }
      if (step.stepKey === "contextPacking") {
        return {
          ...step,
          inputSummary: { authorizedEvidenceCount: 10 },
          outputSummary: { contextCandidateCount: 17, expandedContextCandidates: 7, maxContextTokens: 6000 },
        };
      }
      return step;
    }),
  };
}

const { toQADebugResult, toQARewriteTrace } = await importTypescriptModule(adapterPath);
const viewModel = toQADebugResult(makeDetail());
const expandedViewModel = toQADebugResult(makeExpandedDetail());
const rewriteTrace = toQARewriteTrace(makeDetail());

assert(viewModel.retrievalCards[0].summary.includes("阈值过滤 20 条"), "Dense 0 条候选应解释阈值过滤原因。");
assert(viewModel.retrievalCards[0].summary.includes("原始候选"), "检索卡片应明确候选数属于通道原始候选。");
assert(viewModel.retrievalCards[1].summary.includes("2 个 query × topK 15"), "Sparse 多 query 时应解释为什么候选数可能超过单 query topK。");
assert(viewModel.diagnostics.recalled === "15", "总召回量应来自 trace/fusion 输入，而不是候选列表长度。");
assert(viewModel.diagnostics.finalContext === "5", "最终上下文大小应来自 contextPacking，而不是 evidence 条数。");
assert(viewModel.diagnostics.filtered === "0", "权限过滤为 0 时不应显示 -0。");
assert(viewModel.candidates[0].title.includes("#24"), "候选标题应包含 Chunk 位置信息。");
assert(viewModel.candidates[0].decision.includes("Evidence [1]"), "候选应展示与 Evidence 编号的对应关系。");
assert(viewModel.candidates[0].snippet.includes("物资采购部"), "候选应显示正文预览。");
assert(viewModel.citations[0].documentId === "26b2436f-e3d1-4e8a-8e54-7af5f0166ffa", "Citation 应保留真实 documentId 用于跳转。");
assert(viewModel.citations[0].evidenceId === "evidence-1", "Citation 应保留 evidenceId 供答案内联引用定位。");
assert(viewModel.answerBlocks[0].citationIds[0] === "evidence-1", "答案块应保留句级 evidenceId 引用。");
assert(expandedViewModel.citations.length === 2, "Evidence 与引用页应只展示答案实际引用的证据。");
assert(expandedViewModel.citations.every((citation) => citation.evidenceId !== "evidence-2"), "未被答案引用的扩展上下文不应显示为最终引用证据。");
assert(expandedViewModel.diagnostics.rerankSummary.includes("chunkWindow 扩展 7 条"), "漏斗摘要应单独解释 chunkWindow 扩展数量。");
assert(expandedViewModel.diagnostics.rerankSummary.includes("答案实际引用 2 条"), "漏斗摘要应区分实际引用证据和生成上下文。");
assert(rewriteTrace.originalQuery === "采购职责由哪些组织负责", "问题改写视图应保留原始问题。");
assert(rewriteTrace.rewrittenQuery === "采购职责由哪些部门负责", "问题改写视图应展示改写后问题。");
assert(rewriteTrace.statusLabel === "已改写", "问题改写成功时应显示已改写状态。");
assert(rewriteTrace.providerLabel === "-", "没有 provider 信息时应显示占位。");

const qaDebugPageSource = await readFile(qaDebugPagePath, "utf8");
const qaHistoryPageSource = await readFile(qaHistoryPagePath, "utf8");
assert(qaDebugPageSource.includes("原始问题") && qaDebugPageSource.includes("改写后问题"), "QA 调试 Trace 应展示原始问题和改写后问题。");
assert(qaDebugPageSource.includes("阶段口径"), "QA 调试页应解释检索候选、最终上下文和 Evidence 的阶段关系。");
assert(qaDebugPageSource.includes("handleAnswerCitationClick"), "QA 调试页应支持点击答案引用定位 Evidence。");
assert(qaHistoryPageSource.includes("DrawerSection title=\"问题改写\""), "QA 历史详情 Drawer 应包含问题改写区。");
assert(qaHistoryPageSource.includes("toQARewriteTrace(selectedDetail)"), "QA 历史详情应复用问题改写视图模型。");

console.log("QA debug mapping verification passed.");
