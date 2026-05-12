export type ReplayChannelKey = "dense" | "sparse" | "graph";

export interface QAReplaySeedState {
  overrideParams?: Record<string, unknown>;
  retrievalChannels?: string[];
  retrievalTopK?: Record<string, number>;
  temperature?: number;
  maxContextTokens?: number;
  graphSnapshotId?: string | null;
}

export interface ReplayChannels {
  dense: boolean;
  sparse: boolean;
  graph: boolean;
}

function readBoolean(source: Record<string, unknown> | undefined, key: string, fallback: boolean): boolean {
  const value = source?.[key];
  return typeof value === "boolean" ? value : fallback;
}

function readNestedChannels(source: Record<string, unknown> | undefined): ReplayChannels {
  const channels = source?.channels;
  if (!channels || typeof channels !== "object" || Array.isArray(channels)) {
    return { dense: true, sparse: true, graph: true };
  }
  const typedChannels = channels as Record<string, unknown>;
  return {
    dense: readBoolean(typedChannels, "dense", true),
    sparse: readBoolean(typedChannels, "sparse", true),
    graph: readBoolean(typedChannels, "graph", true),
  };
}

function readPositiveNumber(source: Record<string, number> | undefined, key: ReplayChannelKey): number | undefined {
  const value = source?.[key];
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : undefined;
}

export function readStringNumber(source: Record<string, unknown> | undefined, key: string, fallback: string): string {
  const value = source?.[key];
  return typeof value === "number" || typeof value === "string" ? String(value) : fallback;
}

export function readRewriteEnabled(source: Record<string, unknown> | undefined): boolean {
  return readBoolean(source, "rewriteEnabled", true);
}

/**
 * 根据历史回放上下文恢复检索通道；后端 replay-context 比旧版 overrideSnapshot 更接近原运行事实。
 */
export function resolveReplayChannels(seed: QAReplaySeedState): ReplayChannels {
  if (Array.isArray(seed.retrievalChannels) && seed.retrievalChannels.length > 0) {
    const channelSet = new Set(seed.retrievalChannels);
    return {
      dense: channelSet.has("dense"),
      sparse: channelSet.has("sparse"),
      graph: channelSet.has("graph"),
    };
  }

  return readNestedChannels(seed.overrideParams);
}

/**
 * 将 replay-context 和页面上的本次调整合并为 QARun 创建接口可消费的覆盖参数。
 */
export function buildReplayOverrideParams({
  seed,
  rewriteEnabled,
  channels,
  rerankerTopN,
}: {
  seed: QAReplaySeedState;
  rewriteEnabled: boolean;
  channels: ReplayChannels;
  rerankerTopN: string;
}): Record<string, unknown> {
  const overrideParams: Record<string, unknown> = {
    ...(seed.overrideParams ?? {}),
    rewriteEnabled,
    channels,
    rerankerTopN,
  };

  const denseTopK = readPositiveNumber(seed.retrievalTopK, "dense");
  const sparseTopK = readPositiveNumber(seed.retrievalTopK, "sparse");
  const graphTopK = readPositiveNumber(seed.retrievalTopK, "graph");
  if (denseTopK !== undefined) overrideParams.denseTopK = denseTopK;
  if (sparseTopK !== undefined) overrideParams.sparseTopK = sparseTopK;
  if (graphTopK !== undefined) overrideParams.graphTopK = graphTopK;
  if (typeof seed.temperature === "number") overrideParams.temperature = seed.temperature;
  if (typeof seed.maxContextTokens === "number") overrideParams.maxContextTokens = seed.maxContextTokens;
  if (seed.graphSnapshotId) overrideParams.graphSnapshotId = seed.graphSnapshotId;

  return overrideParams;
}
