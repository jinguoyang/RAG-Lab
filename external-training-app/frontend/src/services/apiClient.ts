const API_BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.text();
    let detail = body;
    try {
      const parsed = JSON.parse(body);
      if (parsed.detail) detail = String(parsed.detail);
    } catch {
      // body 不是 JSON，使用原始文本
    }
    throw new Error(detail);
  }
  return resp.json();
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, data: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(data) });
}
