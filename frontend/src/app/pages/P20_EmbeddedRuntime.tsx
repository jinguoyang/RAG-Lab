import { useMemo, useState } from "react";
import { FileText, Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { Button } from "../components/rag/Button";
import { Input } from "../components/rag/Input";
import {
  chatWithAppRuntime,
  createStructuredRunWithAppRuntime,
  retrieveWithAppRuntime,
  submitAppRuntimeFeedback,
  submitTrainingQuizWithAppRuntime,
} from "../services/appRuntimeService";
import type {
  AppRuntimeChatResponse,
  AppRuntimeRetrievedEvidenceDTO,
  AppRuntimeStructuredRunResponse,
  AppRuntimeTrainingQuizSubmissionResponse,
} from "../types/appRuntime";

function useEmbedToken(): string {
  return useMemo(() => new URLSearchParams(window.location.search).get("token")?.trim() ?? "", []);
}

export function EmbeddedRuntime() {
  const token = useEmbedToken();
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<AppRuntimeChatResponse | null>(null);
  const [evidences, setEvidences] = useState<AppRuntimeRetrievedEvidenceDTO[]>([]);
  const [trainingRun, setTrainingRun] = useState<AppRuntimeStructuredRunResponse | null>(null);
  const [trainingAnswers, setTrainingAnswers] = useState<Record<string, string>>({});
  const [trainingResult, setTrainingResult] = useState<AppRuntimeTrainingQuizSubmissionResponse | null>(null);
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
    setTrainingRun(null);
    setTrainingResult(null);
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

  async function runTraining(action: "training_explain" | "training_quiz_generate") {
    if (!token || !query.trim()) {
      setFeedback({ variant: "error", message: token ? "请输入培训主题。" : "缺少短期 Embed Token。" });
      return;
    }
    setIsRunning(true);
    setFeedback(null);
    setAnswer(null);
    setEvidences([]);
    setTrainingRun(null);
    setTrainingResult(null);
    setTrainingAnswers({});
    try {
      const response = await createStructuredRunWithAppRuntime(token, {
        action,
        topic: query.trim(),
      });
      setTrainingRun(response);
    } catch (error) {
      setFeedback({ variant: "error", message: error instanceof Error ? error.message : "培训运行失败。" });
    } finally {
      setIsRunning(false);
    }
  }

  async function submitTrainingQuiz() {
    const quiz = trainingRun?.output.quiz;
    if (!token || !trainingRun || !quiz) return;
    setIsRunning(true);
    try {
      const response = await submitTrainingQuizWithAppRuntime(token, {
        conversationId: trainingRun.conversationId,
        quizMessageId: trainingRun.messageId,
        answers: quiz.questions.map((question) => ({
          questionId: question.questionId,
          answer: trainingAnswers[question.questionId] ?? "",
        })),
      });
      setTrainingResult(response);
    } catch (error) {
      setFeedback({ variant: "error", message: error instanceof Error ? error.message : "答题提交失败。" });
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
          <h1 className="font-serif text-2xl">场景助手</h1>
          <p className="mt-1 text-sm text-stone-gray">支持知识问答和员工培训，所有结果都回溯到当前应用授权范围。</p>
        </header>

        <section className="flex-1 space-y-4 overflow-auto py-5">
          {feedback && (
            <div className={`rounded-md border px-3 py-2 text-sm ${feedback.variant === "success" ? "border-success-green/40 bg-success-green/10 text-success-green" : "border-error-red/40 bg-error-red/10 text-error-red"}`}>
              {feedback.message}
            </div>
          )}
          {!answer && !trainingRun && (
            <div className="rounded-md border border-border-cream bg-parchment p-4 text-sm text-stone-gray">
              输入问题或培训主题后，嵌入页只使用短期 Token，不持有 App API Key。
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
          {trainingRun && (
            <article className="space-y-3 rounded-md border border-border-cream bg-white p-4">
              <div className="flex flex-wrap items-center gap-2 text-xs text-stone-gray">
                <span>QARun {trainingRun.runId.slice(0, 8)}</span>
                <span>{trainingRun.action === "training_explain" ? "培训讲解" : "培训测验"}</span>
              </div>
              {trainingRun.output.explanation && (
                <p className="whitespace-pre-wrap text-sm leading-6">{trainingRun.output.explanation.summary}</p>
              )}
              {trainingRun.output.quiz && (
                <div className="space-y-3">
                  {trainingRun.output.quiz.questions.map((question, index) => (
                    <div key={question.questionId} className="space-y-2 rounded-md border border-border-cream bg-parchment p-3 text-sm">
                      <div>{index + 1}. {question.stem}</div>
                      <select
                        value={trainingAnswers[question.questionId] ?? ""}
                        onChange={(event) => setTrainingAnswers((current) => ({ ...current, [question.questionId]: event.target.value }))}
                        className="h-9 w-full rounded-md border border-border-cream bg-white px-2 text-sm text-near-black focus:outline-none"
                      >
                        <option value="">选择答案</option>
                        {question.options.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </div>
                  ))}
                  <Button variant="primary" disabled={isRunning} onClick={() => void submitTrainingQuiz()}>
                    提交答题
                  </Button>
                </div>
              )}
              {trainingResult && (
                <div className="rounded-md border border-border-cream bg-parchment p-3 text-sm">
                  <div className="font-medium">得分 {trainingResult.score} / 100 · {trainingResult.passed ? "已通过" : "未通过"}</div>
                  <div className="mt-2 space-y-1 text-xs text-stone-gray">
                    {trainingResult.results.map((item) => (
                      <div key={item.questionId}>{item.questionId}：{item.isCorrect ? "正确" : "错误"}，正确答案：{item.correctAnswer}</div>
                    ))}
                  </div>
                </div>
              )}
            </article>
          )}
        </section>

        <footer className="border-t border-border-cream pt-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void runChat();
              }}
              placeholder="输入问题或培训主题"
              className="bg-white"
            />
            <Button variant="outline" disabled={isRunning} onClick={() => void runTraining("training_explain")}>
              <FileText className="mr-2 h-4 w-4" /> 讲解
            </Button>
            <Button variant="outline" disabled={isRunning} onClick={() => void runTraining("training_quiz_generate")}>
              测验
            </Button>
            <Button variant="primary" disabled={isRunning} onClick={() => void runChat()}>
              <Send className="mr-2 h-4 w-4" /> 发送
            </Button>
          </div>
        </footer>
      </div>
    </main>
  );
}
