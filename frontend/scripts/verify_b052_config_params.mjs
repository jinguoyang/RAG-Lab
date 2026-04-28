import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const pagePath = resolve("src/app/pages/P08_ConfigCenter.tsx");
const source = readFileSync(pagePath, "utf8");

function assertContains(needle, message) {
  if (!source.includes(needle)) {
    throw new Error(message);
  }
}

assertContains("NODE_PARAMETER_FIELDS", "P08 缺少可配置节点参数字段定义。");
assertContains("DEFAULT_NODE_PARAMS", "P08 缺少节点默认参数。");
assertContains("nodeParams[node.id]", "P08 保存 pipelineDefinition 时未写入结构化节点参数。");
assertContains("handleNodeParamChange", "P08 缺少参数编辑状态更新入口。");
assertContains("mustFallbackToChunk", "Graph Retrieval 必须保留回落授权 Chunk 的可见参数。");
assertContains("hybridWeight", "检索节点缺少混合召回权重配置。");
assertContains("temperature", "LLM Generation 缺少生成温度配置。");
assertContains("citationPolicy", "Citation Builder 缺少引用策略配置。");

if (source.includes("Object.fromEntries(node.params.map")) {
  throw new Error("P08 仍在把展示文案 param1/param2 保存为后端 params。");
}

console.log("B-052 config params verification passed.");
