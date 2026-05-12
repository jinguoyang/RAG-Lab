import { readFile, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import * as esbuild from "esbuild";

const rootDir = path.resolve(import.meta.dirname, "..");
const pagePath = path.join(rootDir, "src", "app", "pages", "P09_QADebug.tsx");
const helperPath = path.join(rootDir, "src", "app", "utils", "qaReplaySeed.ts");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * 将 TypeScript 工具模块临时编译为 ESM，便于在无测试框架的前端工程中做行为验证。
 */
async function importTypescriptModule(sourcePath) {
  const bundled = await esbuild.build({
    entryPoints: [sourcePath],
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
  });
  const tempDir = await mkdtemp(path.join(tmpdir(), "rag-lab-qa-replay-"));
  const outputPath = path.join(tempDir, "module.mjs");
  await writeFile(outputPath, bundled.outputFiles[0].text, "utf8");
  return import(pathToFileURL(outputPath).href);
}

/**
 * 验证历史回放会请求来源运行详情，并且不会因为 query 存在就展示 mock 结果。
 */
async function verifyPageDoesNotShowMockReplay() {
  const pageSource = await readFile(pagePath, "utf8");
  assert(
    !pageSource.includes("useState(Boolean(seed.query))"),
    "P09 不能因为回放 query 存在就直接展示 SCENARIO_MAP mock 结果。",
  );
  assert(
    pageSource.includes("fetchQARunDetail(kbId, seed.sourceRunId)"),
    "P09 回放模式必须先读取来源 run 的详情。",
  );
  assert(
    pageSource.includes("setResultSource(\"source\")"),
    "P09 来源详情加载成功后应标记为 source 结果态。",
  );
  assert(
    pageSource.includes("buildReplayOverrideParams"),
    "P09 创建复跑 QARun 时必须使用 replay-context 构造覆盖参数。",
  );
}

/**
 * 验证 replay-context 能恢复为后端 QARun 创建接口可消费的覆盖参数。
 */
async function verifyReplayOverrideParams() {
  const { buildReplayOverrideParams, resolveReplayChannels } = await importTypescriptModule(helperPath);
  const seed = {
    overrideParams: { rewriteEnabled: false, channels: { dense: true, sparse: false, graph: true } },
    retrievalChannels: ["dense", "graph"],
    retrievalTopK: { dense: 11, sparse: 7, graph: 3 },
  };

  assert(
    JSON.stringify(resolveReplayChannels(seed)) === JSON.stringify({ dense: true, sparse: false, graph: true }),
    "回放检索通道应优先来自历史上下文，而不是退回全 true。",
  );

  const params = buildReplayOverrideParams({
    seed,
    rewriteEnabled: false,
    channels: { dense: true, sparse: false, graph: true },
    rerankerTopN: "9",
  });
  assert(params.denseTopK === 11, "denseTopK 应来自历史回放上下文。");
  assert(params.sparseTopK === 7, "sparseTopK 应来自历史回放上下文。");
  assert(params.graphTopK === 3, "graphTopK 应来自历史回放上下文。");
  assert(params.rerankerTopN === "9", "用户在复跑页调整的 rerankerTopN 应保留。");
}

await verifyPageDoesNotShowMockReplay();
await verifyReplayOverrideParams();
console.log("QA replay context verification passed.");
