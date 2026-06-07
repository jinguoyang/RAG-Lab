import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router";
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  GraduationCap,
  MessageSquare,
  Play,
  Send,
} from "lucide-react";
import {
  createPostQuiz,
  createSession,
  submitEvent,
  submitPostQuiz,
  type PostQuiz,
  type PostQuizSubmission,
} from "../services/classroomService";
import { appealQuestion } from "../services/questionService";
import { getPlan, type TrainingPlan } from "../services/planService";
import { ChoiceQuestion } from "../components/ChoiceQuestion";
import type { ClassroomMessage, ClassroomUiAction, ClassroomEventResponse } from "../types/classroom";

let messageCounter = 0;

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function ClassroomPage() {
  const { planId } = useParams<{ planId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const documentId = searchParams.get("documentId");
  const action = searchParams.get("action");

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<(ClassroomMessage & { _key: number })[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentState, setCurrentState] = useState("INIT");
  const [uiActions, setUiActions] = useState<ClassroomUiAction[]>([]);
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [postQuiz, setPostQuiz] = useState<PostQuiz | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [quizResult, setQuizResult] = useState<PostQuizSubmission | null>(null);
  const [autoStarted, setAutoStarted] = useState(false);
  const [autoQuizStarted, setAutoQuizStarted] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const pushMessage = useCallback((msg: ClassroomMessage) => {
    setMessages((prev) => [...prev, { ...msg, _key: ++messageCounter }]);
  }, []);

  // 加载计划信息
  useEffect(() => {
    if (!planId) return;
    let mounted = true;
    getPlan(planId)
      .then((data) => { if (mounted) setPlan(data); })
      .catch((err) => { if (mounted) setError(extractErrorMessage(err)); });
    return () => { mounted = false; };
  }, [planId]);

  // 自动创建会话
  useEffect(() => {
    if (!planId || autoStarted) return;
    setAutoStarted(true);
    handleStartSession();
  }, [planId]);

  async function handleStartSession() {
    setLoading(true);
    setError("");
    try {
      const result = await createSession("demo-user", planId || undefined, documentId || undefined);
      setSessionId(result.localSessionId || result.sessionId);
      setCurrentState(result.currentState);
      const planText = result.planId ? `已关联学习计划 ${result.planId}。` : "未选择学习计划，将使用平台检索兜底。";
      pushMessage({ role: "system", content: `课堂会话已创建。${planText} 点击「开始学习」进入课程。` });

    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleEvent(eventType: string, payload?: Record<string, unknown>, query?: string) {
    if (!sessionId) return;
    setLoading(true);
    setError("");
    try {
      if (query) {
        pushMessage({ role: "user", content: query });
      }

      const result: ClassroomEventResponse = await submitEvent(sessionId, eventType, payload, query);

      setCurrentState(result.classroomState);
      setUiActions(result.uiActions || []);

      if (result.visibleContent) {
        pushMessage({
          role: "assistant",
          content: result.visibleContent,
          uiActions: result.uiActions,
        });
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleQuery() {
    if (!input.trim()) return;
    const query = input.trim();
    setInput("");
    handleEvent("query", {}, query);
  }

  function handleStructuredAnswer(action: ClassroomUiAction, answer: string) {
    handleEvent("submit_answer", {
      questionId: String(action.data.questionId || ""),
      questionType: action.actionType,
      answer,
    });
    // uiActions 在 handleEvent 成功后由 setCurrentState 和 setUiActions 更新
    // 这里不清除，避免 API 失败后用户无法重试
  }

  async function handleStartPostQuiz() {
    if (!sessionId || !documentId) return;
    setLoading(true);
    setError("");
    try {
      const quiz = await createPostQuiz({
        sessionId,
        endUserId: "demo-user",
        documentId,
        planId: planId || undefined,
      });
      setPostQuiz(quiz);
      setQuizResult(null);
      setQuizAnswers({});
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (action !== "quiz" || autoQuizStarted || currentState !== "COMPLETED" || !documentId) {
      return;
    }
    setAutoQuizStarted(true);
    handleStartPostQuiz();
  }, [action, autoQuizStarted, currentState, documentId]);

  async function handleSubmitPostQuiz() {
    if (!postQuiz) return;
    setLoading(true);
    setError("");
    try {
      const result = await submitPostQuiz(postQuiz.quizId, {
        endUserId: "demo-user",
        answers: postQuiz.questions.map((question) => ({
          questionId: question.questionId,
          answer: quizAnswers[question.questionId] || "",
        })),
      });
      setQuizResult(result);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleAppeal(questionId: string) {
    const reason = window.prompt("异议说明", "我认为这道题的答案或解析需要复核。");
    if (!reason) return;
    setError("");
    try {
      await appealQuestion(questionId, { endUserId: "demo-user", reason });
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  }

  function getFallbackActions() {
    if (uiActions.length > 0) return [];
    const actions: { state: string; label: string; eventType: string; className?: string }[] = [
      { state: "INIT", label: "开始学习计划", eventType: "start", className: "primary" },
      { state: "PLAN", label: "进入教学", eventType: "continue", className: "primary" },
      { state: "TEACH", label: "确认理解", eventType: "continue", className: "secondary" },
      { state: "CHECK_UNDERSTAND", label: "进入测验", eventType: "continue", className: "secondary" },
      { state: "GRADE", label: "查看结果", eventType: "continue", className: "secondary" },
      { state: "REVIEW", label: "课程总结", eventType: "continue", className: "secondary" },
    ];
    return actions.filter((action) => action.state === currentState);
  }

  function renderAction(action: ClassroomUiAction, index: number) {
    if (action.actionType === "button_group") {
      const buttons = (action.data.buttons as { label: string; eventType: string; payload?: Record<string, unknown> }[]) || [];
      return (
        <div key={`action-${index}`} className="flex gap-2 flex-wrap">
          {buttons.map((button) => (
            <button
              key={`${button.eventType}-${button.label}`}
              onClick={() => handleEvent(button.eventType, button.payload || {})}
              disabled={loading}
              className="button primary compact-button"
            >
              {button.label}
            </button>
          ))}
        </div>
      );
    }

    if (action.actionType === "single_choice" || action.actionType === "true_false") {
      return (
        <ChoiceQuestion
          key={`action-${index}`}
          question={String(action.data.content || action.data.question || "请选择")}
          options={(action.data.options as { label: string; text: string }[]) || []}
          onAnswer={(answer) => handleStructuredAnswer(action, answer)}
          disabled={loading}
        />
      );
    }

    if (action.actionType === "subjective") {
      return (
        <div key={`action-${index}`} className="choice-question">
          <p className="font-medium">{String(action.data.content || "请输入答案")}</p>
          <textarea
            className="subjective-input"
            disabled={loading}
            placeholder="输入你的回答..."
            onBlur={(event) => {
              const value = event.currentTarget.value.trim();
              if (value) handleStructuredAnswer(action, value);
            }}
          />
        </div>
      );
    }

    return null;
  }

  return (
    <section className="page-stack classroom-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Interactive Classroom</p>
          <h2>员工课堂</h2>
          <p>课堂状态由平台控制；外部应用只渲染消息、结构化动作和答题组件。</p>
        </div>
        {sessionId && <span className="state-pill">状态：{currentState}</span>}
        <button className="button ghost" onClick={() => navigate(`/plans/${planId}`)}>
          <ArrowLeft size={17} aria-hidden="true" />
          返回计划
        </button>
      </header>

      {!sessionId ? (
        <div className="start-panel">
          <div className="start-icon">
            <GraduationCap size={34} aria-hidden="true" />
          </div>
          <h3>创建课堂会话</h3>
          <p>正在自动创建课堂会话...</p>
          {plan && <p className="text-xs opacity-60">计划：{plan.planName || plan.jobTitle}</p>}
          {documentId && <p className="text-xs opacity-60">文档：{documentId}</p>}
          <button
            onClick={handleStartSession}
            disabled={loading}
            className="button primary"
          >
            <Play size={17} aria-hidden="true" />
            {loading ? "创建中..." : "开始学习"}
          </button>
        </div>
      ) : (
        <>
          <div className="classroom-surface">
            <div className="message-stream">
            {messages.map((msg) => (
              <div
                key={msg._key}
                className={`message-bubble ${msg.role}`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}

              <div className="action-zone">
                {uiActions.map((action, i) => renderAction(action, i))}
                {uiActions.length === 0 && currentState === "QUIZ" && (
                  <div className="notice warning compact">
                    <CircleAlert size={17} aria-hidden="true" />
                    <span>当前处于测验阶段，请等待平台返回题目动作后再答题。</span>
                  </div>
                )}
              </div>

            <div ref={messagesEndRef} />
            </div>
          </div>

          <div className="classroom-controls">
            {getFallbackActions().map((action) => (
              <button
                key={`${action.state}-${action.eventType}`}
                onClick={() => handleEvent(action.eventType, {})}
                disabled={loading}
                className={`button ${action.className || "secondary"}`}
              >
                <CheckCircle2 size={17} aria-hidden="true" />
                {action.label}
              </button>
            ))}
          {currentState === "SUMMARY" && (
              <>
                <button onClick={() => handleEvent("next_section", {})}
                  disabled={loading} className="button secondary">
                  下一节
                </button>
                <button onClick={() => handleEvent("complete", {})}
                  disabled={loading} className="button primary">
                  完成课程
                </button>
              </>
            )}
            {currentState === "COMPLETED" && documentId && !postQuiz && (
              <button onClick={handleStartPostQuiz} disabled={loading} className="button primary">
                开始课后测验
              </button>
            )}
          </div>

          {postQuiz && (
            <section className="quiz-panel">
              <div className="section-title">
                <GraduationCap size={20} aria-hidden="true" />
                <h3>课后测验</h3>
              </div>
              {postQuiz.questions.map((question, index) => (
                <article key={question.questionId} className="quiz-question">
                  <p><strong>{index + 1}.</strong> {question.content}</p>
                  {question.options && question.options.length > 0 ? (
                    <div className="quiz-options">
                      {question.options.map((option) => (
                        <label key={`${question.questionId}-${option.label}`} className="quiz-option">
                          <input
                            type="radio"
                            name={question.questionId}
                            value={option.label}
                            checked={quizAnswers[question.questionId] === option.label}
                            onChange={(event) =>
                              setQuizAnswers({ ...quizAnswers, [question.questionId]: event.target.value })
                            }
                            disabled={!!quizResult}
                          />
                          <span>{option.label}. {option.text}</span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <textarea
                      className="subjective-input"
                      value={quizAnswers[question.questionId] || ""}
                      onChange={(event) =>
                        setQuizAnswers({ ...quizAnswers, [question.questionId]: event.target.value })
                      }
                      disabled={!!quizResult}
                      placeholder="输入主观题答案"
                    />
                  )}
                  {quizResult && (
                    <div className="quiz-result-row">
                      <span>
                        得分 {quizResult.results.find((item) => item.questionId === question.questionId)?.score ?? 0}
                      </span>
                      <button className="button secondary" onClick={() => handleAppeal(question.questionId)}>
                        上报异议
                      </button>
                    </div>
                  )}
                </article>
              ))}
              {!quizResult ? (
                <button
                  className="button primary"
                  onClick={handleSubmitPostQuiz}
                  disabled={loading || postQuiz.questions.some((question) => !quizAnswers[question.questionId])}
                >
                  提交测验
                </button>
              ) : (
                <div className={`notice ${quizResult.passed ? "success" : "warning"}`}>
                  <CheckCircle2 size={18} aria-hidden="true" />
                  <span>总分 {quizResult.score}，{quizResult.passed ? "已通过" : "未通过"}</span>
                </div>
              )}
            </section>
          )}

          {currentState !== "COMPLETED" && currentState !== "INIT" && currentState !== "PLAN" && (
            <div className="query-bar">
              <MessageSquare size={18} aria-hidden="true" />
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                placeholder="输入问题..."
                disabled={loading}
              />
              <button
                onClick={handleQuery}
                disabled={loading || !input.trim()}
                className="button primary icon-only"
                title="提问"
                aria-label="提问"
              >
                <Send size={17} aria-hidden="true" />
              </button>
            </div>
          )}
        </>
      )}

      {error && (
        <div className="notice danger">
          <CircleAlert size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}
    </section>
  );
}
