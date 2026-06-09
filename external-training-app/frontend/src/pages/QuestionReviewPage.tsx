import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import {
  CheckCircle2,
  CircleAlert,
  FileQuestion,
  Pencil,
  Plus,
  RefreshCw,
  X,
  XCircle,
} from "lucide-react";
import { useTaskContext } from "../contexts/TaskContext";
import {
  createQuestion,
  generateQuestionDrafts,
  listQuestions,
  reviewQuestion,
  updateQuestion,
} from "../services/questionService";
import { listPlans, type TrainingPlan } from "../services/planService";
import type { QuestionOption, TrainingQuestion } from "../types/question";

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

function getStatusLabel(status: string) {
  const labels: Record<string, string> = {
    draft: "草稿",
    approved: "已审核",
    published: "已发布",
    rejected: "已驳回",
  };
  return labels[status] || status;
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

// ── 内联编辑组件 ──

export function QuestionEditor({
  question,
  onSave,
  onCancel,
  loading,
}: {
  question: TrainingQuestion;
  onSave: (data: { content: string; options?: QuestionOption[]; correctAnswer: string; explanation: string }) => void;
  onCancel: () => void;
  loading: boolean;
}) {
  const [content, setContent] = useState(question.content);
  const [correctAnswer, setCorrectAnswer] = useState(question.correctAnswer || "");
  const [explanation, setExplanation] = useState(question.explanation || "");
  const [options, setOptions] = useState<QuestionOption[]>(question.options || []);

  function updateOption(index: number, field: "label" | "text", value: string) {
    setOptions((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }

  function addOption() {
    setOptions((prev) => [...prev, { label: String.fromCharCode(65 + prev.length), text: "" }]);
  }

  function removeOption(index: number) {
    setOptions((prev) => prev.filter((_, i) => i !== index));
  }

  return (
    <div className="question-editor">
      <label>
        <span>题干</span>
        <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={3} />
      </label>

      {question.questionType === "true_false" ? (
        <div className="editor-options">
          <label>
            <span>标准答案</span>
            <select value={correctAnswer} onChange={(e) => setCorrectAnswer(e.target.value)}>
              <option value="true">对</option>
              <option value="false">不对</option>
            </select>
          </label>
        </div>
      ) : question.questionType !== "subjective" ? (
        <div className="editor-options">
          <span>选项</span>
          {options.map((opt, i) => (
            <div key={i} className="editor-option-row">
              <input
                value={opt.label || ""}
                onChange={(e) => updateOption(i, "label", e.target.value)}
                placeholder="标签"
                style={{ width: 48 }}
              />
              <input
                value={opt.text || ""}
                onChange={(e) => updateOption(i, "text", e.target.value)}
                placeholder="选项内容"
              />
              <button type="button" className="icon-button" onClick={() => removeOption(i)}>
                <X size={14} />
              </button>
            </div>
          ))}
          <button type="button" className="button secondary compact" onClick={addOption}>
            <Plus size={14} /> 添加选项
          </button>
          <label>
            <span>标准答案</span>
            <input value={correctAnswer} onChange={(e) => setCorrectAnswer(e.target.value)} />
          </label>
        </div>
      ) : null}
      <label>
        <span>解析</span>
        <textarea value={explanation} onChange={(e) => setExplanation(e.target.value)} rows={2} />
      </label>

      <div className="editor-actions">
        <button
          className="button primary"
          onClick={() => {
            const finalOptions = question.questionType === "true_false"
              ? [{ label: "true", text: "对" }, { label: "false", text: "不对" }]
              : options.length > 0 ? options : undefined;
            onSave({ content, options: finalOptions, correctAnswer, explanation });
          }}
          disabled={loading}
        >
          保存
        </button>
        <button className="button ghost" onClick={onCancel}>取消</button>
      </div>
    </div>
  );
}

// ── 手动录入表单 ──

function ManualQuestionForm({
  planId,
  documentId,
  onCreated,
}: {
  planId: string;
  documentId?: string;
  onCreated: () => void;
}) {
  const [questionType, setQuestionType] = useState("single_choice");
  const [content, setContent] = useState("");
  const [options, setOptions] = useState<{ label: string; text: string }[]>([
    { label: "A", text: "" },
    { label: "B", text: "" },
  ]);
  const [correctAnswer, setCorrectAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function updateOption(index: number, field: "label" | "text", value: string) {
    setOptions((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }

  function addOption() {
    setOptions((prev) => [...prev, { label: String.fromCharCode(65 + prev.length), text: "" }]);
  }

  function removeOption(index: number) {
    setOptions((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!content.trim() || !planId) return;
    setLoading(true);
    setError("");
    try {
      await createQuestion({
        planId,
        documentId: documentId || undefined,
        questionType,
        content,
        options: questionType !== "subjective" ? options.filter((o) => o.text.trim()) : undefined,
        correctAnswer: correctAnswer || undefined,
        explanation: explanation || undefined,
      });
      setContent("");
      setOptions([
        { label: "A", text: "" },
        { label: "B", text: "" },
      ]);
      setCorrectAnswer("");
      setExplanation("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="manual-question-form">
      <div className="section-title">
        <Plus size={20} aria-hidden="true" />
        <h3>手动录入题目</h3>
      </div>

      {error && (
        <div className="notice danger compact">
          <CircleAlert size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="form-row">
        <label>
          <span>题型</span>
          <select value={questionType} onChange={(e) => setQuestionType(e.target.value)}>
            <option value="single_choice">单选题</option>
            <option value="true_false">判断题</option>
            <option value="subjective">主观题</option>
          </select>
        </label>
      </div>

      <label>
        <span>题干</span>
        <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={2} required />
      </label>

      {questionType !== "subjective" && (
        <div className="editor-options">
          <span>选项</span>
          {options.map((opt, i) => (
            <div key={i} className="editor-option-row">
              <input
                value={opt.label}
                onChange={(e) => updateOption(i, "label", e.target.value)}
                style={{ width: 48 }}
              />
              <input
                value={opt.text}
                onChange={(e) => updateOption(i, "text", e.target.value)}
                placeholder="选项内容"
              />
              <button type="button" className="icon-button" onClick={() => removeOption(i)}>
                <X size={14} />
              </button>
            </div>
          ))}
          <button type="button" className="button secondary compact" onClick={addOption}>
            <Plus size={14} /> 添加选项
          </button>
        </div>
      )}

      <label>
        <span>标准答案</span>
        <input value={correctAnswer} onChange={(e) => setCorrectAnswer(e.target.value)} />
      </label>
      <label>
        <span>解析</span>
        <textarea value={explanation} onChange={(e) => setExplanation(e.target.value)} rows={2} />
      </label>

      <button type="submit" className="button primary" disabled={loading || !content.trim()}>
        <Plus size={17} aria-hidden="true" />
        {loading ? "提交中..." : "录入题目"}
      </button>
    </form>
  );
}

// ── 主页面 ──

export function QuestionReviewPage() {
  const navigate = useNavigate();
  const { addTask } = useTaskContext();
  const [questions, setQuestions] = useState<TrainingQuestion[]>([]);
  const [plans, setPlans] = useState<TrainingPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [filterDocumentId, setFilterDocumentId] = useState("");
  const [editingQuestionId, setEditingQuestionId] = useState<string | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(true);
  const [error, setError] = useState("");

  // 从当前计划中提取文档列表
  const planDocuments = useMemo(() => {
    const plan = plans.find((p) => p.planId === selectedPlanId);
    return (plan?.documents || []) as { documentId: string; title: string }[];
  }, [plans, selectedPlanId]);

  // 按文档筛选题目
  const filteredQuestions = useMemo(() => {
    if (!filterDocumentId) return questions;
    return questions.filter((q) => q.documentId === filterDocumentId);
  }, [questions, filterDocumentId]);

  const draftCount = useMemo(
    () => filteredQuestions.filter((item) => item.status === "draft").length,
    [filteredQuestions]
  );
  const selectedPlan = useMemo(
    () => plans.find((p) => p.planId === selectedPlanId),
    [plans, selectedPlanId]
  );

  async function loadQuestions(planId?: string) {
    setRefreshing(true);
    setError("");
    try {
      setQuestions(await listQuestions(planId, "draft"));
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
        const [planData, questionData] = await Promise.all([listPlans(), listQuestions(undefined, "draft")]);
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
    return () => { mounted = false; };
  }, []);

  // 选择计划后重新加载题目（跳过首次渲染）
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    loadQuestions(selectedPlanId || undefined);
  }, [selectedPlanId]);

  async function handleGenerateForDocument() {
    if (!selectedPlan || !filterDocumentId) return;
    setLoading(true);
    setError("");
    try {
      const abilityGroups = (selectedPlan.abilityGroups || []).map((group) => {
        if (typeof group === "string") return group;
        if (group && typeof group === "object" && "name" in group) {
          return String((group as { name?: unknown }).name || "");
        }
        return "";
      }).filter(Boolean);
      const task = await generateQuestionDrafts({
        planId: selectedPlan.planId,
        jobTitle: selectedPlan.jobTitle,
        abilityGroups,
        count: 10,
        documentIds: [filterDocumentId],
      });
      addTask({
        ...task,
        logs: [],
        status: task.status as "pending" | "running" | "completed" | "failed" | "cancelled",
      });
      navigate(`/tasks/${task.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(questionId: string, decision: "approved" | "rejected") {
    setError("");
    try {
      await reviewQuestion(questionId, { decision, notes: "" });
      setQuestions((prev) => prev.filter((item) => item.questionId !== questionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleEditSave(questionId: string, data: { content: string; options?: QuestionOption[]; correctAnswer: string; explanation: string }) {
    setLoading(true);
    setError("");
    try {
      await updateQuestion(questionId, data);
      setQuestions((prev) =>
        prev.map((item) =>
          item.questionId === questionId
            ? { ...item, ...data }
            : item
        )
      );
      setEditingQuestionId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Question Review</p>
          <h2>题目审核</h2>
          <p>审核并编辑题目草稿。审核通过后直接进入题库，未通过则删除。</p>
        </div>
        <div className="flex gap-2">
          <button className="button secondary" onClick={() => setShowManualForm(!showManualForm)}>
            <Plus size={17} aria-hidden="true" />
            手动录入
          </button>
          <button className="button ghost" onClick={() => loadQuestions(selectedPlanId || undefined)}>
            <RefreshCw size={17} aria-hidden="true" />
            刷新
          </button>
        </div>
      </header>

      <section className="work-surface two-column">
        <div className="form-panel">
          <div className="section-title">
            <FileQuestion size={20} aria-hidden="true" />
            <h3>筛选</h3>
          </div>
          <label>
            <span>学习计划</span>
            <select
              value={selectedPlanId}
              onChange={(e) => {
                setSelectedPlanId(e.target.value);
                setFilterDocumentId("");
              }}
            >
              <option value="">全部计划</option>
              {plans.map((p) => (
                <option key={p.planId} value={p.planId}>
                  {p.planName || p.jobTitle}
                </option>
              ))}
            </select>
          </label>
          {planDocuments.length > 0 && (
            <label>
              <span>文档筛选</span>
              <select value={filterDocumentId} onChange={(e) => setFilterDocumentId(e.target.value)}>
                <option value="">请选择文档</option>
                {planDocuments.map((d) => (
                  <option key={d.documentId} value={d.documentId}>
                    {d.title || d.documentId}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            className="button secondary"
            onClick={handleGenerateForDocument}
            disabled={loading || !selectedPlanId || !filterDocumentId}
          >
            <RefreshCw size={17} aria-hidden="true" />
            为当前文档生成题目
          </button>
        </div>

        <div className="summary-panel">
          <p className="eyebrow">Review Queue</p>
          <strong>{refreshing ? "..." : filteredQuestions.length}</strong>
          <span>题目总数</span>
          <div className="summary-row">
            <span>待审核</span>
            <b>{draftCount}</b>
          </div>
        </div>
      </section>

      {error && (
        <div className="notice danger">
          <CircleAlert size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {showManualForm && selectedPlanId && (
        <ManualQuestionForm
          planId={selectedPlanId}
          onCreated={() => {
            loadQuestions(selectedPlanId);
            setShowManualForm(false);
          }}
        />
      )}

      <section className="list-section">
        {filteredQuestions.length === 0 ? (
          <div className="empty-state">
            <FileQuestion size={28} aria-hidden="true" />
            <h3>暂无题目</h3>
            <p>选择计划后保存即可自动生成题目，或使用手动录入。</p>
          </div>
        ) : (
          filteredQuestions.map((question) => (
            <article key={question.questionId} className="question-item">
              <div className="item-top">
                <div>
                  <span className="tag">{formatQuestionType(question.questionType)}</span>
                  <span className={`status ${question.status}`}>{getStatusLabel(question.status)}</span>
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
                {question.status === "draft" && (
                  <>
                    <button className="button approve" onClick={() => handleReview(question.questionId, "approved")}>
                      <CheckCircle2 size={17} aria-hidden="true" />
                      审核通过
                    </button>
                    <button className="button reject" onClick={() => handleReview(question.questionId, "rejected")}>
                      <XCircle size={17} aria-hidden="true" />
                      不通过并删除
                    </button>
                  </>
                )}
              </div>
            </article>
          ))
        )}
      </section>
    </section>
  );
}
