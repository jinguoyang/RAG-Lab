import type { PermissionSource } from "../types/knowledgeBase";

type BadgeVariant = "default" | "success" | "error" | "warning" | "info" | "queued" | "running" | "draft" | "saved" | "active" | "inactive";
type ProductLayer = "library" | "knowledgeBase" | "app";

const CHUNK_REVISION_LABELS: Record<string, string> = {
  building: "构建中",
  active: "已激活",
  retired: "已退役",
  failed: "构建失败",
};

const CHUNK_REVISION_VARIANTS: Record<string, BadgeVariant> = {
  building: "running",
  active: "success",
  retired: "inactive",
  failed: "error",
};

const LAYER_LABELS: Record<ProductLayer, string> = {
  library: "文档库",
  knowledgeBase: "知识库",
  app: "智能应用",
};

/**
 * 将后端 ChunkRevision 状态转换为稳定展示文案。
 * 未识别状态保持原样，便于发现后端新增状态而不是静默吞掉。
 */
export function chunkRevisionStatusLabel(status: string | null | undefined): string {
  if (!status) return "未创建";
  return CHUNK_REVISION_LABELS[status] ?? status;
}

/**
 * 将 ChunkRevision 状态映射到现有 Badge 变体，避免页面各自定义颜色。
 */
export function chunkRevisionStatusVariant(status: string | null | undefined): BadgeVariant {
  if (!status) return "queued";
  return CHUNK_REVISION_VARIANTS[status] ?? "default";
}

export function layerLabel(layer: ProductLayer): string {
  return LAYER_LABELS[layer];
}

/**
 * 解释权限来源，统一区分平台角色、直接资源角色和用户组继承。
 */
export function permissionSourceLabel(source: Pick<PermissionSource, "sourceType" | "sourceName" | "roleCode" | "effect">): string {
  const role = source.roleCode ?? "未知角色";
  let label: string;
  if (source.sourceType === "platformRole") {
    label = `平台角色：${role}`;
  } else if (source.sourceType === "groupKbRole") {
    label = `用户组继承：${source.sourceName ?? "未命名用户组"} / ${role}`;
  } else if (source.sourceType === "directKbRole") {
    label = `直接授权：${role}`;
  } else {
    label = `${source.sourceName ?? source.sourceType}：${role}`;
  }
  return source.effect === "deny" ? `Deny：${label}` : label;
}
