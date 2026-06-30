import { useState, useEffect, useEffectEvent, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { useParams, useSearchParams, useNavigate } from "react-router";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  CircleAlert,
  GraduationCap,
  MessageSquare,
  Play,
  Send,
} from "lucide-react";
import {
  createPostQuiz,
  createSession,
  getSession,
  submitEvent,
  submitPostQuiz,
  type PostQuiz,
  type PostQuizSubmission,
} from "../services/classroomService";
import { appealQuestion } from "../services/questionService";
import { getPlan, type TrainingPlan } from "../services/planService";
import { ChoiceQuestion } from "../components/ChoiceQuestion";
import type {
  ClassroomEventResponse,
  ClassroomMessage,
  ClassroomSessionDetail,
  ClassroomUiAction,
} from "../types/classroom";

let messageCounter = 0;
const SESSION_STORAGE_VERSION = "v1";
const MARKDOWN_REMARK_PLUGINS = [remarkGfm];

function userVisibleText(value: unknown) {
  // 平台内部仍保留 Checkpoint 术语，ex-app 对用户统一展示为“小节”。
  return String(value ?? "").replace(/Checkpoint/gi, "小节");
}

function renderMessageContent(msg: ClassroomMessage) {
  // 助手和系统消息来自大模型或平台编排，按 GFM Markdown 展示表格、列表等结构。
  const content = userVisibleText(msg.content);
  if (msg.role === "user") {
    return <p className="whitespace-pre-wrap">{content}</p>;
  }
  return (
    <div className="markdown-message">
      <ReactMarkdown remarkPlugins={MARKDOWN_REMARK_PLUGINS}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

function getStoredSessionKey(planId?: string, documentId?: string | null): string {
  return `rag-lab:classroom-session:${SESSION_STORAGE_VERSION}:${planId || "no-plan"}:${documentId || "all"}`;
}

function pendingActionsToUiActions(
  actions: ClassroomSessionDetail["metadata"]["pendingActions"],
): ClassroomUiAction[] {
  if (!actions?.length) return [];
  return [{
    actionType: "button_group",
    data: {
      buttons: actions.map((item) => ({
        label: item.label,
        eventType: item.eventType,
        payload: {},
      })),
    },
  }];
}

function hasAnswerAction(actions?: ClassroomUiAction[]): boolean {
  return Boolean(actions?.some((action) =>
    action.actionType === "single_choice"
    || action.actionType === "true_false"
    || action.actionType === "subjective"
  ));
}

function shouldDisplayRestoredMessage(message: ClassroomMessage): boolean {
  if (message.stateAtTime === "CHECK_UNDERSTAND") return false;
  return !hasAnswerAction(message.metadata?.uiActions);
}

function formatQuizOptionText(questionType: string, option: { label: string; text: string }): string {
  if (questionType === "true_false") {
    return option.text || (option.label === "true" ? "正确" : "错误");
  }
  return `${option.label}. ${option.text}`;
}

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
  const [messages, setMessages] = useState<(ClassroomMessage & { _key: string })[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentState, setCurrentState] = useState("INIT");
  const [currentSectionIndex, setCurrentSectionIndex] = useState(0);
  const [sectionTotal, setSectionTotal] = useState(0);
  const [completedSections, setCompletedSections] = useState(0);
  const [uiActions, setUiActions] = useState<ClassroomUiAction[]>([]);
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [postQuiz, setPostQuiz] = useState<PostQuiz | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [quizResult, setQuizResult] = useState<PostQuizSubmission | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const autoStartedRef = useRef(false);
  const autoQuizStartedRef = useRef(false);
  const onStartSession = useEffectEvent(handleStartSession);
  const onStartPostQuiz = useEffectEvent(handleStartPostQuiz);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const pushMessage = useCallback((msg: ClassroomMessage) => {
    setMessages((prev) => [...prev, { ...msg, _key: `local-${++messageCounter}` }]);
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
    if (!planId || autoStartedRef.current) return;
    autoStartedRef.current = true;
    void onStartSession();
  }, [planId]);

  async function handleStartSession() {
    setLoading(true);
    setError("");
    try {
      const storageKey = getStoredSessionKey(planId, documentId);
      const storedSessionId = window.localStorage.getItem(storageKey);
      if (storedSessionId) {
        try {
          const detail = await getSession(storedSessionId);
          restoreSession(detail);
          return;
        } catch {
          window.localStorage.removeItem(storageKey);
        }
      }

      const result = await createSession("demo-user", planId || undefined, documentId || undefined);
      const createdSessionId = result.localSessionId || result.sessionId;
      window.localStorage.setItem(storageKey, createdSessionId);
      setSessionId(createdSessionId);
      setCurrentState(result.currentState);
      setCurrentSectionIndex(result.currentSectionIndex || 0);
      await advanceOpeningSteps(createdSessionId, result.currentState);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function restoreSession(detail: ClassroomSessionDetail) {
    setSessionId(detail.sessionId);
    setCurrentState(detail.currentState);
    setCurrentSectionIndex(detail.currentSectionIndex || detail.metadata.currentSectionIndex || 0);
    const completedIds = detail.metadata.completedSectionIds || [];
    setCompletedSections(completedIds.length);

    const snapshotSections = (detail.metadata.inputs?.courseSnapshot?.documents || [])
      .flatMap((document) => document.sections || []);
    setSectionTotal(snapshotSections.length);
    const restoredMessages = detail.messages
      .filter(shouldDisplayRestoredMessage)
      .map((message, index) => ({
        ...message,
        _key: message.messageId || `restored-${index}`,
      }));
    setMessages([
      ...restoredMessages,
      {
        role: "system",
        content: `已恢复上次学习进度，当前位于第 ${(detail.currentSectionIndex || 0) + 1} 节。`,
        _key: `restored-notice-${++messageCounter}`,
      },
    ]);

    const lastMessageActions = [...detail.messages]
      .reverse()
      .find((message) => message.metadata?.uiActions?.length)
      ?.metadata?.uiActions;
    setUiActions(lastMessageActions || pendingActionsToUiActions(detail.metadata.pendingActions));

    if (detail.currentState === "INIT" || detail.currentState === "PLAN") {
      void advanceOpeningSteps(detail.sessionId, detail.currentState);
    }
  }

  function applyEventResult(result: ClassroomEventResponse) {
    setCurrentState(result.classroomState);
    setUiActions(result.uiActions || []);
    if (result.progressUpdate?.sectionIndex !== undefined) {
      setCurrentSectionIndex(result.progressUpdate.sectionIndex);
    }
    if (result.progressUpdate?.sectionTotal !== undefined) {
      setSectionTotal(result.progressUpdate.sectionTotal);
    }
    if (result.progressUpdate?.completedSections !== undefined) {
      setCompletedSections(result.progressUpdate.completedSections);
    }
    if (result.visibleContent && !hasAnswerAction(result.uiActions)) {
      pushMessage({
        role: "assistant",
        content: result.visibleContent,
        uiActions: result.uiActions,
      });
    }
  }

  async function advanceOpeningSteps(targetSessionId: string, initialState: string) {
    let state = initialState;
    if (state === "INIT") {
      const planResult = await submitEvent(targetSessionId, "start", {});
      applyEventResult(planResult);
      state = planResult.classroomState;
    }
    if (state === "PLAN") {
      const teachingResult = await submitEvent(targetSessionId, "continue", {});
      applyEventResult(teachingResult);
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

      const sourceState = currentState;
      const result = await submitEvent(sessionId, eventType, payload, query);
      if (sourceState === "TEACH" && eventType === "continue" && result.classroomState === "CHECK_UNDERSTAND") {
        try {
          const checkpointResult = await submitEvent(sessionId, "continue", {});
          applyEventResult(checkpointResult);
        } catch (err) {
          applyEventResult(result);
          throw err;
        }
      } else if (
        sourceState === "GRADE"
        && eventType === "continue"
        && result.classroomState === "REVIEW"
        && result.uiActions.some((action) =>
          (action.data.buttons as Array<{ eventType?: string }> | undefined)
            ?.some((button) => button.eventType === "continue")
        )
      ) {
        if (result.visibleContent) {
          pushMessage({ role: "assistant", content: result.visibleContent });
        }
        const summaryResult = await submitEvent(sessionId, "continue", {});
        applyEventResult(summaryResult);
      } else {
        applyEventResult(result);
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
    if (action !== "quiz" || autoQuizStartedRef.current || currentState !== "COMPLETED" || !documentId) {
      return;
    }
    autoQuizStartedRef.current = true;
    void onStartPostQuiz();
  }, [action, currentState, documentId]);

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
      { state: "TEACH", label: "进入本节练习", eventType: "continue", className: "primary" },
      { state: "CHECK_UNDERSTAND", label: "开始本节练习", eventType: "continue", className: "primary" },
      { state: "GRADE", label: "查看结果", eventType: "continue", className: "secondary" },
      { state: "REVIEW", label: "课程总结", eventType: "continue", className: "secondary" },
    ];
    return actions.filter((action) => action.state === currentState);
  }

  const planSections = (plan?.documents || []).flatMap((document) => document.sections || []);
  const currentSection = planSections[currentSectionIndex];
  const displayedSectionTotal = sectionTotal || planSections.length;
  const progressPercent = displayedSectionTotal > 0
    ? Math.min(100, Math.round((completedSections / displayedSectionTotal) * 100))
    : 0;

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
              {userVisibleText(button.label)}
            </button>
          ))}
        </div>
      );
    }

    if (action.actionType === "single_choice" || action.actionType === "true_false") {
      return (
        <ChoiceQuestion
          key={`action-${index}`}
          question={userVisibleText(action.data.content || action.data.question || "请选择")}
          options={((action.data.options as unknown[]) || []).map((opt, i) =>
            typeof opt === "string"
              ? { label: String.fromCharCode(65 + i), text: opt }
              : (opt as { label: string; text: string })
          )}
          onAnswer={(answer) => handleStructuredAnswer(action, answer)}
          disabled={loading}
        />
      );
    }

    if (action.actionType === "subjective") {
      return (
        <div key={`action-${index}`} className="choice-question">
          <p className="font-medium">{userVisibleText(action.data.content || "请输入答案")}</p>
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
          保存并退出
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
          <section className="classroom-progress-card" aria-label="课堂学习进度">
            <div className="classroom-progress-copy">
              <p className="eyebrow">当前学习小节</p>
              <h3>{currentSection?.title || `第 ${currentSectionIndex + 1} 节`}</h3>
              <p>{currentSection?.learningObjective || "完成本节讲解与练习后记录学习进度。"}</p>
              <div className="classroom-progress-meta">
                <span><BookOpenCheck size={16} /> 已完成 {completedSections}/{displayedSectionTotal || "?"} 节</span>
                {currentSection?.estimatedMinutes ? (
                  <span><Clock3 size={16} /> 预计 {currentSection.estimatedMinutes} 分钟</span>
                ) : null}
                {currentSection?.checkpointCriteria?.length ? (
                  <span>小节标准：{currentSection.checkpointCriteria.join("；")}</span>
                ) : null}
              </div>
            </div>
            <div className="classroom-progress-value" aria-label={`课程进度 ${progressPercent}%`}>
              <strong>{progressPercent}%</strong>
              <div className="classroom-progress-track">
                <span style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
          </section>

          <div className="classroom-surface">
            <div className="message-stream">
            {messages.map((msg) => (
              <div
                key={msg._key}
                className={`message-bubble ${msg.role}`}
              >
                {renderMessageContent(msg)}
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
                          <span>{formatQuizOptionText(question.questionType, option)}</span>
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
