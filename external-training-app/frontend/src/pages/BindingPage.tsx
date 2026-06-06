import { useState, useEffect } from "react";
import { CheckCircle2, CircleAlert, KeyRound, Link2, Plus, Settings } from "lucide-react";
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
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Platform Binding</p>
          <h2>平台绑定配置</h2>
          <p>外部应用后端使用 App API Key 调用平台，浏览器端不持有长期密钥。</p>
        </div>
      </header>

      <section className="work-surface two-column">
        <form onSubmit={handleSubmit} className="form-panel">
          <div className="section-title">
            <Settings size={20} aria-hidden="true" />
            <h3>新增绑定</h3>
          </div>
          <label>
            <span>平台地址</span>
            <div className="input-with-icon">
              <Link2 size={17} aria-hidden="true" />
              <input
                type="text"
                value={form.platformBaseUrl}
                onChange={(e) => setForm({ ...form, platformBaseUrl: e.target.value })}
                placeholder="http://localhost:8000/api/v1"
                required
              />
            </div>
          </label>
          <label>
            <span>API Key</span>
            <div className="input-with-icon">
              <KeyRound size={17} aria-hidden="true" />
              <input
                type="password"
                value={form.platformApiKey}
                onChange={(e) => setForm({ ...form, platformApiKey: e.target.value })}
                required
              />
            </div>
          </label>
          {error && (
            <div className="notice danger compact">
              <CircleAlert size={17} aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}
          <button type="submit" disabled={loading} className="button primary">
            <Plus size={17} aria-hidden="true" />
            {loading ? "保存中..." : "保存绑定"}
          </button>
        </form>

        <div className="summary-panel">
          <p className="eyebrow">Connection</p>
          <strong>{bindings.length}</strong>
          <span>已保存绑定</span>
          <p>如需切换平台环境，可新增绑定记录；真实调用仍以服务端配置为准。</p>
        </div>
      </section>

      <section className="list-section">
        {bindings.length === 0 ? (
          <div className="empty-state">
            <KeyRound size={28} aria-hidden="true" />
            <h3>暂无绑定</h3>
            <p>配置平台地址和 App API Key 后，学习计划、题库和课堂接口才能联通平台。</p>
          </div>
        ) : (
          bindings.map((binding) => (
            <article key={binding.id} className="binding-item">
              <div className="item-top">
                <div>
                  <span className="tag">平台 API</span>
                  <span className={`status ${binding.status}`}>{binding.status}</span>
                </div>
                <time>{new Date(binding.createdAt).toLocaleString()}</time>
              </div>
              <h3>{binding.platformBaseUrl}</h3>
              <p>
                <CheckCircle2 size={16} aria-hidden="true" />
                API Key 已由后端保存，前端仅展示连接摘要。
              </p>
            </article>
          ))
        )}
      </section>
    </section>
  );
}
