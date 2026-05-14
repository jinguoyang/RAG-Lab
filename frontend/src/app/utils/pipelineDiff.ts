import type { PipelineDefinition, PipelineDefinitionNode } from "../types/config";

export type PipelineDiffKind = "added" | "removed" | "changed";

export interface PipelineDiffItem {
  path: string;
  beforeValue: string;
  afterValue: string;
  kind: PipelineDiffKind;
}

type FlatValueMap = Record<string, unknown>;

/**
 * 按节点 ID 读取 Pipeline 节点，避免数组顺序变化导致差异对比错位。
 */
export function getPipelineNode(
  pipelineDefinition: PipelineDefinition | null | undefined,
  nodeId: string,
): PipelineDefinitionNode | undefined {
  return pipelineDefinition?.nodes.find((node) => node.id === nodeId);
}

/**
 * 将默认参数与 Revision 中保存的参数合并，用于从 active Revision 恢复编辑态。
 */
export function mergeNodeParams<T extends Record<string, Record<string, unknown>>>(
  defaultParams: T,
  pipelineDefinition: PipelineDefinition | null | undefined,
): T {
  const mergedParams = Object.fromEntries(
    Object.entries(defaultParams).map(([nodeId, params]) => [nodeId, { ...params }]),
  ) as T;

  pipelineDefinition?.nodes.forEach((node) => {
    if (!node.params) return;
    mergedParams[node.id as keyof T] = {
      ...(mergedParams[node.id as keyof T] ?? {}),
      ...node.params,
    } as T[keyof T];
  });

  return mergedParams;
}

/**
 * 生成当前编辑态相对基线 Pipeline 的字段级差异，供配置中心差异 tab 展示。
 */
export function createPipelineDiffItems(
  basePipelineDefinition: PipelineDefinition | null | undefined,
  currentPipelineDefinition: PipelineDefinition,
): PipelineDiffItem[] {
  const baseFlatValues = flattenPipelineDefinition(basePipelineDefinition);
  const currentFlatValues = flattenPipelineDefinition(currentPipelineDefinition);
  const paths = Array.from(
    new Set([...Object.keys(baseFlatValues), ...Object.keys(currentFlatValues)]),
  ).sort();

  return paths
    .filter((path) => stringifyValue(baseFlatValues[path]) !== stringifyValue(currentFlatValues[path]))
    .map((path) => {
      const hasBefore = Object.prototype.hasOwnProperty.call(baseFlatValues, path);
      const hasAfter = Object.prototype.hasOwnProperty.call(currentFlatValues, path);
      return {
        path,
        beforeValue: formatDiffValue(baseFlatValues[path]),
        afterValue: formatDiffValue(currentFlatValues[path]),
        kind: !hasBefore ? "added" : !hasAfter ? "removed" : "changed",
      };
    });
}

function flattenPipelineDefinition(
  pipelineDefinition: PipelineDefinition | null | undefined,
): FlatValueMap {
  if (!pipelineDefinition) return {};

  const flatValues: FlatValueMap = {
    version: pipelineDefinition.version,
    constraintsVersion: pipelineDefinition.constraintsVersion,
    mode: pipelineDefinition.mode,
    templateId: pipelineDefinition.templateId ?? null,
  };

  pipelineDefinition.stages.forEach((stage, index) => {
    flatValues[`stages.${index}`] = stage;
  });

  pipelineDefinition.nodes.forEach((node) => {
    flattenNode(node, `nodes.${node.id}`, flatValues);
  });

  return flatValues;
}

function flattenNode(node: PipelineDefinitionNode, path: string, flatValues: FlatValueMap) {
  flatValues[`${path}.type`] = node.type;
  flatValues[`${path}.stage`] = node.stage;
  flatValues[`${path}.enabled`] = node.enabled;
  flatValues[`${path}.locked`] = Boolean(node.locked);
  flattenObject(node.params ?? {}, `${path}.params`, flatValues);
}

function flattenObject(value: unknown, path: string, flatValues: FlatValueMap) {
  if (!isPlainObject(value)) {
    flatValues[path] = value;
    return;
  }

  Object.entries(value)
    .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
    .forEach(([key, childValue]) => {
      flattenObject(childValue, `${path}.${key}`, flatValues);
    });
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringifyValue(value: unknown): string {
  return JSON.stringify(value);
}

function formatDiffValue(value: unknown): string {
  if (value === undefined) return "未设置";
  if (value === null) return "null";
  if (typeof value === "string") return `"${value}"`;
  return String(value);
}
