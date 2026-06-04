import { useState, useEffect } from "react";
import { createBinding, listBindings } from "../services/bindingService";
import type { BindingResponse } from "../types/binding";

export function BindingPage() {
  const [bindings, setBindings] = useState<BindingResponse[]>([]);
  const [form, setForm] = useState({ platformBaseUrl: "", platformApiKey: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listBindings().then(setBindings).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await createBinding(form);
      setBindings([result, ...bindings]);
      setForm({ platformBaseUrl: "", platformApiKey: "" });
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">平台绑定配置</h1>
      <form onSubmit={handleSubmit} className="space-y-4 mb-8">
        <div>
          <label className="block text-sm font-medium mb-1">平台地址</label>
          <input type="text" value={form.platformBaseUrl}
            onChange={(e) => setForm({ ...form, platformBaseUrl: e.target.value })}
            className="w-full border rounded px-3 py-2" placeholder="http://localhost:8000/api/v1" required />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">API Key</label>
          <input type="password" value={form.platformApiKey}
            onChange={(e) => setForm({ ...form, platformApiKey: e.target.value })}
            className="w-full border rounded px-3 py-2" required />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button type="submit" disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50">
          {loading ? "保存中..." : "保存绑定"}
        </button>
      </form>
      <h2 className="text-lg font-semibold mb-3">已有绑定</h2>
      {bindings.length === 0 ? <p className="text-gray-500">暂无绑定</p> : (
        <div className="space-y-2">
          {bindings.map((b) => (
            <div key={b.id} className="border rounded p-3">
              <p className="font-medium">{b.platformBaseUrl}</p>
              <p className="text-sm text-gray-500">状态: {b.status}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
