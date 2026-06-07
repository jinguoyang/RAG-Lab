import { useEffect, useMemo, useState } from "react";
import { CircleAlert, FileQuestion, Pencil, RefreshCw, Trash2 } from "lucide-react";

import { deleteQuestion, listQuestions, updateQuestion } from "../services/questionService";
import { listPlans, type TrainingPlan } from "../services/planService";
import type { QuestionOption, TrainingQuestion } from "../types/question";
import { QuestionEditor } from "./QuestionReviewPage";

function formatQuestionType(type: string) {
  const labels: Record<string, string> = {
    single_choice: "单选题",
    true_false: "判断题",
    subjective: "主观题",
    certification: "认证题",
  };
  return labels[type] || type;
}

function formatCorrectAnswer(questionType: string, answer: string | null | undefined): string {
  if (!answer) return "未返回";
  if (questionType === "true_false") {
    return answer === "true" ? "对" : "不对";
  }
  return answer;
}

function formatRubric(rubric: Record<string, unknown> | null | undefined): string | null {
  if (!rubric || !Array.isArray(rubric.criteria)) return null;
  const criteria = rubric.criteria as { name?: string; score?: number; description?: string }[];
  if (criteria.length === 0) return null;
  return criteria
    .map((c, i) => `${i + 1}. ${c.name || "考点" + (i + 1)}（${c.score ?? 1}分）`)
    .join("\n");
}

function renderOption(option: QuestionOption, index: number) {
  const label = option.label || option.value || String.fromCharCode(65 + index);
  const text = option.text || option.value || JSON.stringify(option);
  return (
    <li key={`${label}-${index}`}>
      <strong>{label}.</strong>
      <span>{text}</span>
    </li>
  );
}

export function QuestionBankPage() {
  const [questions, setQuestions] = useState<TrainingQuestion[]>([]);
  const [plans, setPlans] = useState<TrainingPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [editingQuestionId, setEditingQuestionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(true);
  const [error, setError] = useState("");

  const displayedQuestions = useMemo(
    () => questions.filter((question) => question.status === "published"),
    [questions]
  );

  async function loadQuestions(planId?: string) {
    setRefreshing(true);
    setError("");
    try {
      setQuestions(await listQuestions(planId, "published"));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    async function init() {
      try {
        const [planData, questionData] = await Promise.all([
          listPlans(),
          listQuestions(undefined, "published"),
        ]);
        if (!mounted) return;
        setPlans(planData);
        setQuestions(questionData);
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (mounted) setRefreshing(false);
      }
    }
    init();
    return () => {
      mounted = false;
    };
  }, []);

  async function handleEditSave(
    questionId: string,
    data: { content: string; options?: QuestionOption[]; correctAnswer: string; explanation: string }
  ) {
    setLoading(true);
    setError("");
    try {
      await updateQuestion(questionId, data);
      setQuestions((prev) =>
        prev.map((item) => (item.questionId === questionId ? { ...item, ...data } : item))
      );
      setEditingQuestionId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(questionId: string) {
    if (!window.confirm("确定要从题库中永久删除这道题吗？")) return;
    setError("");
    try {
      await deleteQuestion(questionId);
      setQuestions((prev) => prev.filter((item) => item.questionId !== questionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Question Bank</p>
          <h2>题库</h2>
          <p>查看、修改和删除已通过审核的正式题目。</p>
        </div>
        <button className="button ghost" onClick={() => loadQuestions(selectedPlanId || undefined)}>
          <RefreshCw size={17} aria-hidden="true" />
          刷新
        </button>
      </header>

      <section className="work-surface two-column">
        <div className="form-panel">
          <label>
            <span>学习计划</span>
            <select value={selectedPlanId} onChange={(event) => {
              const planId = event.target.value;
              setSelectedPlanId(planId);
              loadQuestions(planId || undefined);
            }}>
              <option value="">全部计划</option>
              {plans.map((plan) => (
                <option key={plan.planId} value={plan.planId}>
                  {plan.planName || plan.jobTitle}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="summary-panel">
          <p className="eyebrow">Published Questions</p>
          <strong>{refreshing ? "..." : displayedQuestions.length}</strong>
          <span>题库题目</span>
        </div>
      </section>

      {error && (
        <div className="notice danger">
          <CircleAlert size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <section className="list-section">
        {displayedQuestions.length === 0 ? (
          <div className="empty-state">
            <FileQuestion size={28} aria-hidden="true" />
            <h3>题库暂无题目</h3>
            <p>题目草稿审核通过后会直接进入这里。</p>
          </div>
        ) : (
          displayedQuestions.map((question) => (
            <article key={question.questionId} className="question-item">
              <div className="item-top">
                <div>
                  <span className="tag">{formatQuestionType(question.questionType)}</span>
                  <span className="status published">已发布</span>
                </div>
                <time>{new Date(question.createdAt).toLocaleString()}</time>
              </div>

              {editingQuestionId === question.questionId ? (
                <QuestionEditor
                  question={question}
                  onSave={(data) => handleEditSave(question.questionId, data)}
                  onCancel={() => setEditingQuestionId(null)}
                  loading={loading}
                />
              ) : (
                <>
                  <h3>{question.content}</h3>
                  {question.questionType !== "true_false" && question.options && question.options.length > 0 && (
                    <ol className="option-list">{question.options.map(renderOption)}</ol>
                  )}
                  <div className="answer-grid">
                    <div>
                      <span>标准答案</span>
                      {question.questionType === "subjective" && formatRubric(question.rubric) ? (
                        <pre className="rubric-text">{formatRubric(question.rubric)}</pre>
                      ) : (
                        <strong>{formatCorrectAnswer(question.questionType, question.correctAnswer)}</strong>
                      )}
                    </div>
                  </div>
                  {question.explanation && <p className="explanation">{question.explanation}</p>}
                </>
              )}

              <div className="item-actions">
                {editingQuestionId !== question.questionId && (
                  <button className="button secondary" onClick={() => setEditingQuestionId(question.questionId)}>
                    <Pencil size={16} aria-hidden="true" />
                    修改
                  </button>
                )}
                <button className="button reject" onClick={() => handleDelete(question.questionId)}>
                  <Trash2 size={16} aria-hidden="true" />
                  删除
                </button>
              </div>
            </article>
          ))
        )}
      </section>
    </section>
  );
}
