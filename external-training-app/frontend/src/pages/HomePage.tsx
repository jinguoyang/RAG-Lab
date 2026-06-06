import { useEffect, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  ClipboardCheck,
  FileQuestion,
} from "lucide-react";
import { Link } from "react-router";
import { listPlans } from "../services/planService";
import { listQuestions } from "../services/questionService";

interface HomeStats {
  planCount: number;
  questionDraftCount: number;
}

export function HomePage() {
  const [stats, setStats] = useState<HomeStats>({
    planCount: 0,
    questionDraftCount: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      try {
        const [plans, questions] = await Promise.all([
          listPlans(),
          listQuestions(),
        ]);
        if (!mounted) return;
        setStats({
          planCount: plans.filter((p) => p.status === "saved").length,
          questionDraftCount: questions.filter((item) => item.status === "draft").length,
        });
      } catch (err) {
        if (mounted) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      mounted = false;
    };
  }, []);

  const steps = [
    {
      title: "学习计划管理",
      desc: "创建学习计划，管理文档和员工绑定，保存后自动生成题目。",
      href: "/reviews",
      icon: ClipboardCheck,
      status: `${stats.planCount} 个计划`,
    },
    {
      title: "题库管理",
      desc: "审核题目草稿、手动录入题目、发布题目入题库。",
      href: "/questions",
      icon: FileQuestion,
      status: `${stats.questionDraftCount} 道待审`,
    },
  ];

  return (
    <section className="page-stack">
      <header className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">Training Operations Portal</p>
          <h2>学习计划与题库管理平台</h2>
          <p>
            创建学习计划并管理文档，系统自动生成题目。审核、编辑和发布题目后，
            员工可通过计划详情页进入课堂学习和答题。
          </p>
          <div className="hero-actions">
            <Link className="button primary" to="/reviews">
              <ClipboardCheck size={18} aria-hidden="true" />
              管理学习计划
            </Link>
            <Link className="button secondary" to="/questions">
              <FileQuestion size={18} aria-hidden="true" />
              管理题库
            </Link>
          </div>
        </div>
        <div className="hero-signal" aria-label="接入状态摘要">
          <div>
            <span>已保存计划</span>
            <strong>{loading ? "..." : stats.planCount}</strong>
          </div>
          <div>
            <span>题目待审</span>
            <strong>{loading ? "..." : stats.questionDraftCount}</strong>
          </div>
        </div>
      </header>

      {error && (
        <div className="notice warning">
          <CircleAlert size={18} aria-hidden="true" />
          <span>首页摘要加载失败：{error}</span>
        </div>
      )}

      <div className="workflow-grid">
        {steps.map((step, index) => (
          <Link key={step.href} to={step.href} className="workflow-item">
            <div className="workflow-icon">
              <step.icon size={20} aria-hidden="true" />
            </div>
            <div>
              <span className="step-index">0{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.desc}</p>
            </div>
            <div className="workflow-status">
              <span>{step.status}</span>
              <ArrowRight size={18} aria-hidden="true" />
            </div>
          </Link>
        ))}
      </div>

      <section className="split-section">
        <div>
          <p className="eyebrow">使用流程</p>
          <h3>从计划创建到员工学习的完整闭环</h3>
          <p>
            管理员创建学习计划并选择文档 → 系统自动生成题目 → 审核并发布题目 →
            员工从计划详情页进入课堂学习和答题。
          </p>
        </div>
        <ul className="check-list">
          <li>
            <CheckCircle2 size={17} aria-hidden="true" />
            学习计划：创建、编辑、删除，支持文档排序和元数据调整。
          </li>
          <li>
            <CheckCircle2 size={17} aria-hidden="true" />
            题库管理：自动/手动录入，草稿→审核→发布三步流程。
          </li>
          <li>
            <CheckCircle2 size={17} aria-hidden="true" />
            员工学习：从计划详情页进入课堂，完成学习和课后测验。
          </li>
        </ul>
      </section>
    </section>
  );
}
