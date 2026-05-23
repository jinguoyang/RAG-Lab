import { useMemo, useState } from "react";
import { Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "../components/rag/Button";
import { Input } from "../components/rag/Input";
import { chatWithAppRuntime, retrieveWithAppRuntime, submitAppRuntimeFeedback } from "../services/appRuntimeService";
import type { AppRuntimeChatResponse, AppRuntimeRetrievedEvidenceDTO } from "../types/appRuntime";

function useEmbedToken(): string {
  return useMemo(() => new URLSearchParams(window.location.search).get("token")?.trim() ?? "", []);
}

export function EmbeddedRuntime() {
  const token = useEmbedToken();
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<AppRuntimeChatResponse | null>(null);
  const [evidences, setEvidences] = useState<AppRuntimeRetrievedEvidenceDTO[]>([]);
  const [feedback, setFeedback] = useState<{ variant: "success" | "error"; message: string } | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  async function runChat() {
    if (!token || !query.trim()) {
      setFeedback({ variant: "error", message: token ? "请输入问题。" : "缺少短期 Embed Token。" });
      return;
    }
    setIsRunning(true);
    setFeedback(null);
    setAnswer(null);
    setEvidences([]);
    try {
      const [chatResponse, retrieveResponse] = await Promise.all([
        chatWithAppRuntime(token, { query: query.trim(), responseMode: "blocking" }),
        retrieveWithAppRuntime(token, { query: query.trim(), topK: 3 }),
      ]);
      setAnswer(chatResponse);
      setEvidences(retrieveResponse.evidences);
    } catch (error) {
      setFeedback({ variant: "error", message: error instanceof Error ? error.message : "问答运行失败。" });
    } finally {
      setIsRunning(false);
    }
  }

  async function submitFeedback(feedbackStatus: "correct" | "wrong") {
    if (!answer) return;
    setIsRunning(true);
    try {
      await submitAppRuntimeFeedback(token, answer.messageId, {
        feedbackStatus,
        failureType: feedbackStatus === "wrong" ? "embedded_runtime_feedback" : null,
        feedbackNote: "嵌入页用户反馈。",
      });
      setFeedback({ variant: "success", message: "反馈已提交。" });
    } catch (error) {
      setFeedback({ variant: "error", message: error instanceof Error ? error.message : "反馈提交失败。" });
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main className="min-h-screen bg-ivory text-near-black">
      <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-6">
        <header className="border-b border-border-cream pb-4">
          <h1 className="font-serif text-2xl">知识库问答助手</h1>
          <p className="mt-1 text-sm text-stone-gray">基于当前应用授权范围回答问题，并展示可追溯引用。</p>
        </header>

        <section className="flex-1 space-y-4 overflow-auto py-5">
          {feedback && (
            <div className={`rounded-md border px-3 py-2 text-sm ${feedback.variant === "success" ? "border-success-green/40 bg-success-green/10 text-success-green" : "border-error-red/40 bg-error-red/10 text-error-red"}`}>
              {feedback.message}
            </div>
          )}
          {!answer && (
            <div className="rounded-md border border-border-cream bg-parchment p-4 text-sm text-stone-gray">
              输入问题后，助手会返回回答和证据摘要。嵌入页只使用短期 Token，不持有 App API Key。
            </div>
          )}
          {answer && (
            <article className="space-y-3 rounded-md border border-border-cream bg-white p-4">
              <p className="whitespace-pre-wrap text-sm leading-6">{answer.answer || "未生成回答。"}</p>
              <div className="flex flex-wrap items-center gap-2 text-xs text-stone-gray">
                <span>QARun {answer.runId.slice(0, 8)}</span>
                <span>Citation {answer.citations.length}</span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={isRunning} onClick={() => void submitFeedback("correct")}>
                  <ThumbsUp className="mr-1 h-3 w-3" /> 有帮助
                </Button>
                <Button variant="outline" size="sm" disabled={isRunning} onClick={() => void submitFeedback("wrong")}>
                  <ThumbsDown className="mr-1 h-3 w-3" /> 需改进
                </Button>
              </div>
            </article>
          )}
          {evidences.length > 0 && (
            <section className="space-y-2">
              <h2 className="text-sm font-medium">证据摘要</h2>
              {evidences.map((item) => (
                <div key={item.evidenceId} className="rounded-md border border-border-cream bg-parchment p-3 text-xs">
                  <div className="mb-1 font-mono text-stone-gray">{item.label} · {item.chunkId.slice(0, 8)}</div>
                  <p className="text-near-black">{item.summary || "无摘要"}</p>
                </div>
              ))}
            </section>
          )}
        </section>

        <footer className="border-t border-border-cream pt-4">
          <div className="flex gap-2">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void runChat();
              }}
              placeholder="输入你的问题"
              className="bg-white"
            />
            <Button variant="primary" disabled={isRunning} onClick={() => void runChat()}>
              <Send className="mr-2 h-4 w-4" /> 发送
            </Button>
          </div>
        </footer>
      </div>
    </main>
  );
}
