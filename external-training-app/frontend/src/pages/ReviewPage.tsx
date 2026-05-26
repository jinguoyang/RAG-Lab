import { useState, useEffect } from "react";
import { listReviews, generatePlanDraft, submitReview } from "../services/reviewService";
import type { ReviewTask } from "../types/review";

export function ReviewPage() {
  const [tasks, setTasks] = useState<ReviewTask[]>([]);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listReviews("plan").then(setTasks).catch(() => {});
  }, []);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await generatePlanDraft(jobTitle, jobDesc);
      setTasks(await listReviews("plan"));
      setJobTitle("");
      setJobDesc("");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(taskId: string, decision: "approved" | "rejected") {
    try {
      await submitReview(taskId, { decision, notes: "" });
      setTasks(await listReviews("plan"));
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">学习计划审核</h1>
      <form onSubmit={handleGenerate} className="space-y-4 mb-8 p-4 border rounded">
        <h2 className="text-lg font-semibold">生成学习计划草稿</h2>
        <div>
          <label className="block text-sm font-medium mb-1">岗位名称</label>
          <input type="text" value={jobTitle} onChange={(e) => setJobTitle(e.target.value)}
            className="w-full border rounded px-3 py-2" required />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">岗位描述</label>
          <textarea value={jobDesc} onChange={(e) => setJobDesc(e.target.value)}
            className="w-full border rounded px-3 py-2 h-24" required />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button type="submit" disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50">
          {loading ? "生成中..." : "生成草稿"}
        </button>
      </form>
      <h2 className="text-lg font-semibold mb-3">审核任务列表</h2>
      {tasks.length === 0 ? <p className="text-gray-500">暂无审核任务</p> : (
        <div className="space-y-4">
          {tasks.map((t) => (
            <div key={t.id} className="border rounded p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <span className="text-sm text-gray-500">{t.reviewType}</span>
                  <span className={`ml-2 px-2 py-0.5 text-xs rounded ${
                    t.status === "pending" ? "bg-yellow-100 text-yellow-800" :
                    t.status === "approved" ? "bg-green-100 text-green-800" :
                    "bg-red-100 text-red-800"
                  }`}>{t.status}</span>
                </div>
                <span className="text-xs text-gray-400">{new Date(t.createdAt).toLocaleString()}</span>
              </div>
              {t.submittedPayload && Object.keys(t.submittedPayload).length > 0 && (
                <pre className="bg-gray-50 p-3 rounded text-sm overflow-auto max-h-48 mb-3">
                  {JSON.stringify(t.submittedPayload, null, 2)}
                </pre>
              )}
              {t.status === "pending" && (
                <div className="flex gap-2">
                  <button onClick={() => handleReview(t.id, "approved")}
                    className="bg-green-600 text-white px-3 py-1 rounded text-sm">通过</button>
                  <button onClick={() => handleReview(t.id, "rejected")}
                    className="bg-red-600 text-white px-3 py-1 rounded text-sm">驳回</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
