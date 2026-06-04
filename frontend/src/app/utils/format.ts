/** 格式化文件大小为人类可读字符串。 */
export function formatFileSize(bytes: number | null | undefined): string {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 将解析状态映射为 Badge variant。 */
export function parseStatusVariant(status: string | null | undefined): "success" | "error" | "running" | "queued" {
  if (status === "success" || status === "completed") return "success";
  if (status === "failed") return "error";
  if (status === "running") return "running";
  return "queued";
}
