import { describe, expect, it } from "vitest";
import type { PipelineDefinition } from "../types/config";
import { createPipelineDiffItems, getPipelineNode, mergeNodeParams } from "./pipelineDiff";

/**
 * 构造最小 PipelineDefinition，保证测试只关注差异计算本身。
 */
function createPipelineDefinition(): PipelineDefinition {
  return {
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
}

describe("pipelineDiff", () => {
  it("按节点 ID 生成字段级差异并忽略未变化参数", () => {
    const activePipeline = createPipelineDefinition();
    const editedPipeline: PipelineDefinition = {
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

    const paths = createPipelineDiffItems(activePipeline, editedPipeline).map((item) => item.path);

    expect(paths).toContain("nodes.dense.enabled");
    expect(paths).toContain("nodes.dense.params.topK");
    expect(paths).not.toContain("nodes.graph.params.graphDepth");
  });

  it("支持按节点 ID 读取节点并合并 Revision 参数", () => {
    const activePipeline = createPipelineDefinition();

    expect(getPipelineNode(activePipeline, "dense")?.params?.topK).toBe(20);
    expect(
      mergeNodeParams(
        { dense: { topK: 20, fusionWeight: 0.4, scoreThreshold: 0.75 } },
        activePipeline,
      ).dense,
    ).toEqual({ topK: 20, fusionWeight: 0.4, scoreThreshold: 0.75 });
  });
});
