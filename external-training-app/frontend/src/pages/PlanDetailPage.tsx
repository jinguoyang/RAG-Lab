import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import {
  ArrowLeft,
  BookOpen,
  CircleAlert,
  FileQuestion,
  GraduationCap,
  Loader2,
} from "lucide-react";
import { getPlan, type TrainingDocument, type TrainingPlan } from "../services/planService";
import { getQuestionCountByDocument } from "../services/questionService";

const DIFFICULTY_LABELS: Record<string, string> = {
  basic: "基础",
  normal: "普通",
  advanced: "进阶",
};

function documentAbilityGroup(document: TrainingDocument) {
  // 新计划使用 abilityGroup；旧数据可能仍保存为 category。
  return document.abilityGroup || document.category || "";
}

function difficultyLabel(value?: string | null) {
  return value ? DIFFICULTY_LABELS[value] || value : "";
}

export function PlanDetailPage() {
  const { planId } = useParams<{ planId: string }>();
  const navigate = useNavigate();
  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [questionCounts, setQuestionCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!planId) return;
    const pid = planId;
    let mounted = true;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const [planData, counts] = await Promise.all([
          getPlan(pid),
          getQuestionCountByDocument(pid).catch(() => ({})),
        ]);
        if (!mounted) return;
        setPlan(planData);
        setQuestionCounts(counts);
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [planId]);

  function handleStudy(doc: TrainingDocument) {
    navigate(`/plans/${planId}/classroom?documentId=${encodeURIComponent(doc.documentId)}`);
  }

  function handleQuiz(doc: TrainingDocument) {
    navigate(`/plans/${planId}/classroom?documentId=${encodeURIComponent(doc.documentId)}&action=quiz`);
  }

  if (loading) {
    return (
      <section className="page-stack">
        <div className="empty-state">
          <Loader2 size={28} className="animate-spin" aria-hidden="true" />
          <h3>加载中...</h3>
        </div>
      </section>
    );
  }

  if (error || !plan) {
    return (
      <section className="page-stack">
        <div className="notice danger">
          <CircleAlert size={18} aria-hidden="true" />
          <span>{error || "计划不存在"}</span>
        </div>
        <button className="button secondary" onClick={() => navigate("/reviews")}>
          <ArrowLeft size={17} aria-hidden="true" />
          返回计划列表
        </button>
      </section>
    );
  }

  const documents = (plan.documents || []) as TrainingDocument[];

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Plan Detail</p>
          <h2>{plan.planName || plan.jobTitle}</h2>
          <p>{plan.jobTitle}{plan.jobDescription ? ` · ${plan.jobDescription}` : ""}</p>
        </div>
        <button className="button ghost" onClick={() => navigate("/reviews")}>
          <ArrowLeft size={17} aria-hidden="true" />
          返回
        </button>
      </header>

      <section className="work-surface">
        <div className="section-title">
          <BookOpen size={20} aria-hidden="true" />
          <h3>文档列表 ({documents.length})</h3>
        </div>

        {documents.length === 0 ? (
          <div className="empty-state">
            <FileQuestion size={28} aria-hidden="true" />
            <h3>暂无文档</h3>
            <p>请先在学习计划中添加文档。</p>
          </div>
        ) : (
          <div className="plan-doc-list">
            {documents.map((doc, index) => {
              const qCount = questionCounts[doc.documentId] || 0;
              return (
                <article key={doc.documentId} className="plan-doc-item">
                  <div className="plan-doc-info">
                    <span className="plan-doc-index">{index + 1}</span>
                    <div className="plan-doc-text">
                      <h4>{doc.title || doc.documentId}</h4>
                      <div className="plan-doc-meta">
                        {documentAbilityGroup(doc) && <span className="tag">{documentAbilityGroup(doc)}</span>}
                        {doc.difficulty && <span className="tag">{difficultyLabel(doc.difficulty)}</span>}
                        <span className="tag">
                          {qCount > 0 ? `${qCount} 道题目` : "暂无题目"}
                        </span>
                      </div>
                      {doc.summary && <p className="plan-doc-summary">{doc.summary}</p>}
                    </div>
                  </div>
                  <div className="plan-doc-actions">
                    <button className="button primary" onClick={() => handleStudy(doc)}>
                      <GraduationCap size={16} aria-hidden="true" />
                      学习
                    </button>
                    {qCount > 0 && (
                      <button className="button secondary" onClick={() => handleQuiz(doc)}>
                        <FileQuestion size={16} aria-hidden="true" />
                        答题
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </section>
  );
}
