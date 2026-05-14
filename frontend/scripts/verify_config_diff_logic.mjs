import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";

const tempDir = await mkdtemp(join(tmpdir(), "rag-lab-config-diff-"));
const outputFile = join(tempDir, "pipelineDiff.mjs");

try {
  await build({
    entryPoints: ["src/app/utils/pipelineDiff.ts"],
    bundle: true,
    format: "esm",
    platform: "node",
    outfile: outputFile,
    logLevel: "silent",
  });

  const { createPipelineDiffItems, getPipelineNode, mergeNodeParams } = await import(
    pathToFileURL(outputFile).href
  );

  const activePipeline = {
    version: "1.0",
    constraintsVersion: "1.0",
    mode: "constrained-stage-pipeline",
    stages: ["preprocess", "retrieval"],
    templateId: "标准混合（默认）",
    nodes: [
      {
        id: "dense",
        type: "denseRetrieval",
        stage: "retrieval",
        enabled: true,
        locked: false,
        params: { topK: 20, fusionWeight: 0.4 },
      },
      {
        id: "graph",
        type: "graphRetrieval",
        stage: "retrieval",
        enabled: true,
        locked: false,
        params: { graphDepth: 2 },
      },
    ],
  };
  const editedPipeline = {
    ...activePipeline,
    nodes: [
      {
        ...activePipeline.nodes[0],
        enabled: false,
        params: { topK: 12, fusionWeight: 0.4 },
      },
      activePipeline.nodes[1],
    ],
  };

  const diffItems = createPipelineDiffItems(activePipeline, editedPipeline);
  const paths = diffItems.map((item) => item.path);

  if (!paths.includes("nodes.dense.enabled")) {
    throw new Error("差异结果缺少 Dense 启用状态变化。");
  }
  if (!paths.includes("nodes.dense.params.topK")) {
    throw new Error("差异结果缺少 Dense topK 参数变化。");
  }
  if (paths.includes("nodes.graph.params.graphDepth")) {
    throw new Error("未变化的 Graph 参数不应出现在差异结果中。");
  }

  const denseNode = getPipelineNode(activePipeline, "dense");
  if (!denseNode || denseNode.params?.topK !== 20) {
    throw new Error("无法按节点 ID 读取 active pipeline 节点。");
  }

  const mergedParams = mergeNodeParams(
    { dense: { topK: 20, fusionWeight: 0.4, scoreThreshold: 0.75 } },
    activePipeline,
  );
  if (mergedParams.dense.topK !== 20 || mergedParams.dense.scoreThreshold !== 0.75) {
    throw new Error("active pipeline 参数合并结果不正确。");
  }

  console.log("Config diff logic verification passed.");
} finally {
  await rm(tempDir, { recursive: true, force: true });
}
