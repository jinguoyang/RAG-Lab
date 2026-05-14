import { readFile } from "node:fs/promises";
import path from "node:path";

const rootDir = path.resolve(import.meta.dirname, "..");
const qaHistoryPagePath = path.join(rootDir, "src", "app", "pages", "P10_QAHistory.tsx");
const qaRunServicePath = path.join(rootDir, "src", "app", "services", "qaRunService.ts");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/**
 * 验证 QA 历史页在没有评估样本时不会直接发起评估批次创建。
 */
async function verifyEvaluationSampleGuard() {
  const pageSource = await readFile(qaHistoryPagePath, "utf8");

  assert(
    pageSource.includes("evaluationCount <= 0"),
    "P10 触发评估回归前应先检查当前知识库是否已有评估样本。",
  );
  assert(
    pageSource.includes("请先从历史运行详情中加入评估集"),
    "P10 无评估样本时应提示用户先沉淀回归样本。",
  );
  assert(
    pageSource.includes("disabled={actionLoading === \"evaluation-create\" || evaluationCount <= 0}"),
    "P10 无评估样本时应禁用触发评估回归按钮。",
  );
}

/**
 * 验证 P10 提供评估样本明细查看和移出评估集入口。
 */
async function verifyEvaluationSampleListManagement() {
  const pageSource = await readFile(qaHistoryPagePath, "utf8");
  const serviceSource = await readFile(qaRunServicePath, "utf8");

  assert(
    serviceSource.includes("archiveEvaluationSample"),
    "qaRunService 应提供 archiveEvaluationSample 调用后端归档接口。",
  );
  assert(
    serviceSource.includes("/evaluation-samples/${sampleId}"),
    "archiveEvaluationSample 应调用单条评估样本归档路径。",
  );
  assert(
    pageSource.includes("const [evaluationSamples, setEvaluationSamples]"),
    "P10 应保存评估样本列表，而不是只保存 total。",
  );
  assert(
    pageSource.includes("async function removeEvaluationSample"),
    "P10 应提供移出评估集操作。",
  );
  assert(
    pageSource.includes("const [isEvaluationSamplesDrawerOpen, setEvaluationSamplesDrawerOpen]"),
    "P10 应使用抽屉状态控制评估样本列表展示。",
  );
  assert(
    pageSource.includes("查看评估集"),
    "P10 应提供查看评估集按钮来打开抽屉。",
  );
  assert(
    pageSource.includes("isOpen={isEvaluationSamplesDrawerOpen}"),
    "P10 评估样本列表应通过 Drawer 展示。",
  );
  assert(
    pageSource.includes("title=\"评估样本列表\""),
    "P10 评估样本抽屉标题应为评估样本列表。",
  );
  assert(
    pageSource.includes("移出评估集"),
    "P10 评估样本抽屉应提供移出评估集按钮。",
  );
}

await verifyEvaluationSampleGuard();
await verifyEvaluationSampleListManagement();
console.log("QA history evaluation guard verification passed.");
