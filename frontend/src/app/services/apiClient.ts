const API_BASE_URL = "/api/v1";

interface ApiErrorField {
  field?: unknown;
  message?: unknown;
}

interface ApiValidationIssue {
  loc?: unknown;
  msg?: unknown;
  type?: unknown;
}

interface ApiErrorBody {
  error?: {
    message?: unknown;
    detail?: unknown;
    fields?: ApiErrorField[];
  };
  detail?: unknown;
  message?: unknown;
}

const FIELD_LABELS: Record<string, string> = {
  username: "用户名",
  displayName: "显示名称",
  email: "邮箱",
  platformRole: "平台角色",
  securityLevel: "密级",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

function normalizeFieldPath(loc: unknown): string | null {
  if (!Array.isArray(loc)) return null;
  const parts = loc
    .filter((part) => part !== "body" && part !== "query" && part !== "path")
    .map(String);
  return parts.length > 0 ? parts.join(".") : null;
}

function normalizeValidationMessage(field: string | null, issue: ApiValidationIssue): string {
  const message = typeof issue.msg === "string" ? issue.msg : "请求参数不合法。";
  const type = typeof issue.type === "string" ? issue.type : "";
  if (field === "email" && (type.includes("value_error") || message.toLowerCase().includes("email"))) {
    return "邮箱格式不正确，请输入类似 user@example.com 的地址。";
  }
  return field ? `${fieldLabel(field)}：${message}` : message;
}

function formatValidationIssues(detail: unknown): string | null {
  if (!Array.isArray(detail)) return null;
  const messages = detail
    .filter((issue): issue is ApiValidationIssue => isRecord(issue))
    .map((issue) => {
      const field = normalizeFieldPath(issue.loc);
      return normalizeValidationMessage(field, issue);
    });
  return messages.length > 0 ? messages.join("；") : null;
}

// 兼容项目统一错误模型和 FastAPI 默认 422，避免页面只展示 HTTP 状态码。
function formatApiError(status: number, body: unknown): string {
  if (!isRecord(body)) return `API request failed: ${status}`;

  const payload = body as ApiErrorBody;
  const fields = payload.error?.fields
    ?.map((field) => {
      if (typeof field.message !== "string") return null;
      return typeof field.field === "string" ? `${fieldLabel(field.field)}：${field.message}` : field.message;
    })
    .filter((message): message is string => Boolean(message));
  if (fields?.length) return fields.join("；");

  const validationMessage = formatValidationIssues(payload.detail);
  if (validationMessage) return validationMessage;

  for (const message of [payload.error?.detail, payload.error?.message, payload.detail, payload.message]) {
    if (typeof message === "string" && message.trim()) return message;
  }
  return `API request failed: ${status}`;
}

async function throwApiError(response: Response): Promise<never> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // 非 JSON 错误响应只能回退到 HTTP 状态码。
  }
  throw new Error(formatApiError(response.status, body));
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  return response.json() as Promise<T>;
}

export async function apiPostForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  return response.json() as Promise<T>;
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  return response.json() as Promise<T>;
}

export async function apiPatchJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    await throwApiError(response);
  }

  return response.json() as Promise<T>;
}

export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "DELETE",
  });

  if (!response.ok) {
    await throwApiError(response);
  }
}
