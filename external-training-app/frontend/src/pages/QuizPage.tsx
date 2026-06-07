import { useState, useEffect } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router";
import { ArrowLeft, CheckCircle2, CircleAlert, GraduationCap, Play } from "lucide-react";
import {
  createPostQuiz,
  createSession,
  submitPostQuiz,
  type PostQuiz,
  type PostQuizSubmission,
} from "../services/classroomService";
import { appealQuestion } from "../services/questionService";
import { getPlan, type TrainingPlan } from "../services/planService";

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function QuizPage() {
  const { planId } = useParams<{ planId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const documentId = searchParams.get("documentId");

  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [postQuiz, setPostQuiz] = useState<PostQuiz | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, string>>({});
  const [quizResult, setQuizResult] = useState<PostQuizSubmission | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 加载计划信息
  useEffect(() => {
    if (!planId) return;
    let mounted = true;
    getPlan(planId)
      .then((data) => {
        if (mounted) setPlan(data);
      })
      .catch((err) => {
        if (mounted) setError(extractErrorMessage(err));
      });
    return () => {
      mounted = false;
    };
  }, [planId]);

  // 自动开始测验
  useEffect(() => {
    if (!planId || !documentId) return;
    handleStartQuiz();
  }, [planId, documentId]);

  async function handleStartQuiz() {
    if (!planId || !documentId) return;
    setLoading(true);
    setError("");
    try {
      // 创建临时 session（后端 API 要求）
      const session = await createSession("demo-user", planId);
      // 创建测验
      const quiz = await createPostQuiz({
        sessionId: session.localSessionId || session.sessionId,
        endUserId: "demo-user",
        documentId,
        planId,
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

  async function handleSubmitQuiz() {
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

  const allAnswered = postQuiz?.questions.every((q) => quizAnswers[q.questionId]);

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Quiz</p>
          <h2>答题</h2>
          {plan && <p className="text-sm opacity-60">计划：{plan.planName || plan.jobTitle}</p>}
        </div>
        <button className="button ghost" onClick={() => navigate(`/plans/${planId}`)}>
          <ArrowLeft size={17} aria-hidden="true" />
          返回计划
        </button>
      </header>

      {loading && !postQuiz && (
        <div className="start-panel">
          <div className="start-icon">
            <GraduationCap size={34} aria-hidden="true" />
          </div>
          <h3>正在加载题目...</h3>
          <p>请稍候</p>
        </div>
      )}

      {!loading && !postQuiz && !error && (
        <div className="start-panel">
          <div className="start-icon">
            <GraduationCap size={34} aria-hidden="true" />
          </div>
          <h3>准备答题</h3>
          <p>点击下方按钮开始测验</p>
          <button onClick={handleStartQuiz} disabled={loading} className="button primary">
            <Play size={17} aria-hidden="true" />
            {loading ? "加载中..." : "开始测验"}
          </button>
        </div>
      )}

      {postQuiz && (
        <section className="quiz-panel">
          <div className="section-title">
            <GraduationCap size={20} aria-hidden="true" />
            <h3>测验题目</h3>
          </div>

          {postQuiz.questions.map((question, index) => (
            <article key={question.questionId} className="quiz-question">
              <p>
                <strong>{index + 1}.</strong> {question.content}
              </p>
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
                      <span>
                        {option.label}. {option.text}
                      </span>
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
              onClick={handleSubmitQuiz}
              disabled={loading || !allAnswered}
            >
              提交测验
            </button>
          ) : (
            <div className={`notice ${quizResult.passed ? "success" : "warning"}`}>
              <CheckCircle2 size={18} aria-hidden="true" />
              <span>
                总分 {quizResult.score}，{quizResult.passed ? "已通过" : "未通过"}
              </span>
            </div>
          )}
        </section>
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
