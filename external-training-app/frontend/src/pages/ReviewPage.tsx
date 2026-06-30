import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import {
  ArrowDown,
  ArrowUp,
  CircleAlert,
  FileSearch,
  Loader2,
  Pencil,
  Plus,
  Save,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {
  deletePlan,
  generatePlanDraft,
  listPlans,
  listTrainingDocuments,
  savePlan,
  updatePlan,
  type TrainingDocument,
  type TrainingPlan,
  type TrainingSection,
} from "../services/planService";
import { useTaskContext } from "../contexts/TaskContext";

const MOCK_EMPLOYEES = [
  { id: "emp-001", name: "张三", department: "检修车间" },
  { id: "emp-002", name: "李四", department: "供电车间" },
  { id: "emp-003", name: "王五", department: "工务段" },
  { id: "emp-004", name: "赵六", department: "电务段" },
  { id: "emp-005", name: "钱七", department: "车辆段" },
];

const DIFFICULTY_OPTIONS = [
  { value: "basic", label: "基础" },
  { value: "normal", label: "普通" },
  { value: "advanced", label: "进阶" },
];

const DIFFICULTY_ALIASES: Record<string, string> = {
  初级: "basic",
  基础: "basic",
  中级: "normal",
  普通: "normal",
  高级: "advanced",
  进阶: "advanced",
};

function documentTitle(document: TrainingDocument) {
  return document.title || document.documentId;
}

function documentAbilityGroup(document: TrainingDocument) {
  // 兼容历史候选文档的 category，新生成计划优先使用平台返回的 abilityGroup。
  return document.abilityGroup || document.category || "";
}

function difficultyLabel(value?: string | null) {
  const normalized = normalizeDifficulty(value);
  return DIFFICULTY_OPTIONS.find((item) => item.value === normalized)?.label || value || "";
}

function normalizeDifficulty(value?: string | null, index = 0) {
  if (!value) return index === 0 ? "basic" : "normal";
  return DIFFICULTY_OPTIONS.some((item) => item.value === value) ? value : DIFFICULTY_ALIASES[value] || "normal";
}

function abilityGroupName(group: unknown) {
  if (typeof group === "string") return group;
  if (group && typeof group === "object" && "name" in group) {
    const name = (group as { name?: unknown }).name;
    return typeof name === "string" ? name : "";
  }
  return "";
}

function normalizeTrainingDocument(
  document: TrainingDocument,
  index = 0,
  abilityGroups: unknown[] = []
) {
  // 平台草稿和历史本地数据字段略有差异，进入表单前统一成页面编辑契约。
  return {
    ...document,
    difficulty: normalizeDifficulty(document.difficulty, index),
    abilityGroup: documentAbilityGroup(document) || abilityGroupName(abilityGroups[index]) || "",
    sections: document.sections || [],
  };
}

function normalizeTrainingDocuments(documents: TrainingDocument[] = [], abilityGroups: unknown[] = []) {
  return documents.map((document, index) => normalizeTrainingDocument(document, index, abilityGroups));
}

interface DraftPlan {
  taskId: string;
  planName: string;
  jobTitle: string;
  createdAt: string;
}

export function ReviewPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { tasks, addTask, getTask, subscribeToTask } = useTaskContext();
  const [draftPlans, setDraftPlans] = useState<DraftPlan[]>([]);

  // 从导航状态中读取草稿计划（从编辑器跳转过来时携带）
  useEffect(() => {
    const draft = (location.state as { draft?: DraftPlan } | null)?.draft;
    if (draft) {
      setDraftPlans((prev) => {
        if (prev.some((d) => d.taskId === draft.taskId)) return prev;
        return [...prev, draft];
      });
      // 清除导航状态，避免刷新页面时重复添加
      navigate(location.pathname, { replace: true, state: null });
    }
  }, []);
  const draftCleanupRef = useRef<Map<string, () => void>>(new Map());
  const [plans, setPlans] = useState<TrainingPlan[]>([]);
  const [viewMode, setViewMode] = useState<"list" | "editor">("list");
  const [editingPlan, setEditingPlan] = useState<TrainingPlan | null>(null);
  const [selectedDocs, setSelectedDocs] = useState<TrainingDocument[]>([]);
  const [candidateDocs, setCandidateDocs] = useState<TrainingDocument[]>([]);
  const [appliedDocumentQuery, setAppliedDocumentQuery] = useState("");
  const [form, setForm] = useState({
    planName: "",
    jobTitle: "",
    jobDescription: "",
    documentQuery: "",
  });
  const [selectedEmployeeIds, setSelectedEmployeeIds] = useState<string[]>([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    planName: "",
    jobTitle: "",
    jobDescription: "",
  });
  const [loading, setLoading] = useState(false);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [error, setError] = useState("");

  const savedPlans = useMemo(
    () => plans.filter((item) => item.status === "saved"),
    [plans]
  );

  const platformPlanDrafts = useMemo(
    () => plans.filter((item) => item.status === "draft"),
    [plans]
  );

  const recoveredPlanDrafts = useMemo(() => {
    const savedPlanIds = new Set(plans.map((item) => item.planId));
    const trackedTaskIds = new Set(draftPlans.map((item) => item.taskId));

    return Array.from(tasks.values()).flatMap((task) => {
      if (
        task.type !== "plan_generation"
        || task.status !== "completed"
        || trackedTaskIds.has(task.id)
      ) {
        return [];
      }
      const result = task.result as TrainingPlan | undefined;
      if (!result?.planId || savedPlanIds.has(result.planId)) return [];
      return [{ task, plan: result }];
    });
  }, [draftPlans, plans, tasks]);

  const filteredCandidateDocs = useMemo(() => {
    const query = form.documentQuery.trim().toLowerCase();
    if (!query || query === appliedDocumentQuery.toLowerCase()) return candidateDocs;
    return candidateDocs.filter((document) =>
      [
        documentTitle(document),
        document.summary,
        documentAbilityGroup(document),
        difficultyLabel(document.difficulty),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query)
    );
  }, [appliedDocumentQuery, candidateDocs, form.documentQuery]);

  async function refreshPlans() {
    const data = await listPlans();
    setPlans(data);
  }

  const loadCandidateDocuments = useCallback(async (query = "") => {
    setLoadingDocuments(true);
    setError("");
    try {
      setCandidateDocs(await listTrainingDocuments(query));
      setAppliedDocumentQuery(query.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingDocuments(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    listPlans()
      .then((data) => {
        if (!cancelled) setPlans(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 为每个生成中的草稿订阅 SSE，任务完成后自动刷新列表
  useEffect(() => {
    for (const draft of draftPlans) {
      if (draftCleanupRef.current.has(draft.taskId)) continue;
      const unsubscribe = subscribeToTask(draft.taskId);
      draftCleanupRef.current.set(draft.taskId, unsubscribe);
    }
    // 清理已移除的草稿订阅
    for (const [taskId, cleanup] of draftCleanupRef.current) {
      if (!draftPlans.some((d) => d.taskId === taskId)) {
        cleanup();
        draftCleanupRef.current.delete(taskId);
      }
    }
  }, [draftPlans, subscribeToTask]);

  // 组件卸载时清理所有草稿订阅
  useEffect(() => {
    return () => {
      for (const cleanup of draftCleanupRef.current.values()) {
        cleanup();
      }
      draftCleanupRef.current.clear();
    };
  }, []);

  // 监听任务状态变化，完成后用 result 打开编辑器
  useEffect(() => {
    for (const draft of draftPlans) {
      const task = getTask(draft.taskId);
      if (!task) continue;
      if (task.status === "completed") {
        setDraftPlans((prev) => prev.filter((d) => d.taskId !== draft.taskId));
        const planResult = task.result as TrainingPlan | undefined;
        if (planResult && planResult.planId) {
          // 用平台返回的草稿数据打开编辑器，用户审核后手动保存
          openEditor(planResult);
        } else {
          void refreshPlans();
        }
      }
      // failed 状态保留在列表中，用户可手动关闭
    }
    // getTask 随 tasks Map 变化而重建，已隐式依赖 tasks 更新
  }, [draftPlans, getTask]);

  function resetEditor() {
    setViewMode("list");
    setEditingPlan(null);
    setSelectedDocs([]);
    setCandidateDocs([]);
    setAppliedDocumentQuery("");
    setSelectedEmployeeIds([]);
    setForm({ planName: "", jobTitle: "", jobDescription: "", documentQuery: "" });
  }

  function openEditor(plan?: TrainingPlan) {
    if (plan) {
      setEditingPlan(plan);
      setForm({
        planName: plan.planName || plan.jobTitle,
        jobTitle: plan.jobTitle,
        jobDescription: plan.jobDescription || "",
        documentQuery: "",
      });
      setSelectedDocs(normalizeTrainingDocuments((plan.documents || []) as TrainingDocument[], plan.abilityGroups || []));
      setSelectedEmployeeIds(plan.employeeIds || []);
    } else {
      setEditingPlan(null);
      setForm({ planName: "", jobTitle: "", jobDescription: "", documentQuery: "" });
      setSelectedDocs([]);
      setSelectedEmployeeIds([]);
    }
    setCandidateDocs([]);
    setAppliedDocumentQuery("");
    setViewMode("editor");
    void loadCandidateDocuments();
  }

  async function handleGenerateRecommendations() {
    const planName = createForm.planName.trim();
    const jobTitle = createForm.jobTitle.trim();
    if (!planName || !jobTitle) return;
    setLoading(true);
    setError("");
    try {
      const task = await generatePlanDraft({
        planName,
        jobTitle,
        jobDescription: createForm.jobDescription.trim(),
      });
      // 添加任务到上下文
      addTask({
        ...task,
        logs: [],
        status: task.status as 'pending' | 'running' | 'completed' | 'failed' | 'cancelled',
      });
      // 携带草稿信息导航到学习计划列表页
      const draft: DraftPlan = {
        taskId: task.id,
        planName,
        jobTitle,
        createdAt: task.createdAt,
      };
      setCreateModalOpen(false);
      setCreateForm({ planName: "", jobTitle: "", jobDescription: "" });
      navigate("/reviews", { state: { draft } });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  function addDocument(document: TrainingDocument) {
    setSelectedDocs((prev) => {
      if (prev.some((item) => item.documentId === document.documentId)) return prev;
      const normalized = normalizeTrainingDocument(document, prev.length);
      return [...prev, {
        ...normalized,
        sections: normalized.sections.length > 0 ? normalized.sections : [{
          sectionId: `section-${document.documentId}-${Date.now()}`,
          title: documentTitle(document),
          learningObjective: `掌握《${documentTitle(document)}》的关键要求`,
          evidenceChunkIds: [],
          keyPoints: [],
          checkpointCriteria: ["能够说明本小节的关键要求"],
          estimatedMinutes: 8,
          required: true,
        }],
      }];
    });
  }

  function removeDocument(documentId: string) {
    setSelectedDocs((prev) => prev.filter((item) => item.documentId !== documentId));
  }

  function moveDocument(index: number, direction: -1 | 1) {
    setSelectedDocs((prev) => {
      const next = [...prev];
      const target = index + direction;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function updateDocMetadata(index: number, field: "abilityGroup" | "difficulty", value: string) {
    setSelectedDocs((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  }

  function updateSection(documentIndex: number, sectionIndex: number, patch: Partial<TrainingSection>) {
    setSelectedDocs((prev) => prev.map((document, itemIndex) => (
      itemIndex === documentIndex
        ? {
            ...document,
            sections: document.sections.map((section, index) => (
              index === sectionIndex ? { ...section, ...patch } : section
            )),
          }
        : document
    )));
  }

  function moveSection(documentIndex: number, sectionIndex: number, direction: -1 | 1) {
    setSelectedDocs((prev) => prev.map((document, itemIndex) => {
      if (itemIndex !== documentIndex) return document;
      const sections = [...document.sections];
      const target = sectionIndex + direction;
      if (target < 0 || target >= sections.length) return document;
      [sections[sectionIndex], sections[target]] = [sections[target], sections[sectionIndex]];
      return { ...document, sections };
    }));
  }

  async function handleSave() {
    if (!editingPlan) return;
    setLoading(true);
    setError("");
    try {
      const planName = form.planName || editingPlan.planName || editingPlan.jobTitle;
      if (editingPlan.status === "saved") {
        // 编辑已有计划
        await updatePlan(editingPlan.planId, {
          planName,
          documents: selectedDocs,
          employeeIds: selectedEmployeeIds,
        });
      } else {
        // 新建计划
        await savePlan(editingPlan.planId, {
          planName,
          appId: editingPlan.appId || "local",
          jobTitle: form.jobTitle || editingPlan.jobTitle,
          jobDescription: form.jobDescription || editingPlan.jobDescription,
          abilityGroups: editingPlan.abilityGroups || [],
          documents: selectedDocs,
          evidenceChunkIds: [],
          recommendReason: editingPlan.recommendReason || null,
          employeeIds: selectedEmployeeIds,
          version: 1,
        });
      }
      await refreshPlans();
      resetEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(planId: string) {
    if (!confirm("确定删除该学习计划？")) return;
    setError("");
    try {
      await deletePlan(planId);
      await refreshPlans();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  // ── 列表视图 ──
  if (viewMode === "list") {
    return (
      <section className="page-stack">
        <header className="page-header">
          <div>
            <p className="eyebrow">Plan Management</p>
            <h2>学习计划管理</h2>
            <p>创建、编辑和管理学习计划。保存计划时将自动生成题目。</p>
          </div>
          <button
            className="button primary"
            onClick={() => {
              setError("");
              setCreateModalOpen(true);
            }}
          >
            <Plus size={17} aria-hidden="true" />
            新建计划
          </button>
        </header>

        {error && (
          <div className="notice danger">
            <CircleAlert size={18} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <section className="list-section">
          {draftPlans.map((draft) => {
            const task = getTask(draft.taskId);
            const isFailed = task?.status === "failed";
            return (
              <article key={`draft-${draft.taskId}`} className={`plan-item draft${isFailed ? " draft-failed" : ""}`}>
                <div className="item-top">
                  <div>
                    <span className="tag">{isFailed ? "生成失败" : "生成中"}</span>
                    <span className={`status ${isFailed ? "rejected" : "pending"}`}>
                      {isFailed ? (
                        <><CircleAlert size={14} aria-hidden="true" /> 失败</>
                      ) : (
                        <><Loader2 size={14} className="spinning" aria-hidden="true" /> 生成中</>
                      )}
                    </span>
                  </div>
                  <time>{new Date(draft.createdAt).toLocaleString()}</time>
                </div>
                <h3>{draft.planName}</h3>
                <div className="answer-grid">
                  <div>
                    <span>岗位</span>
                    <strong>{draft.jobTitle}</strong>
                  </div>
                </div>
                {isFailed && (
                  <button
                    className="button ghost"
                    onClick={() => setDraftPlans((prev) => prev.filter((d) => d.taskId !== draft.taskId))}
                  >
                    <X size={14} aria-hidden="true" />
                    关闭
                  </button>
                )}
              </article>
            );
          })}
          {recoveredPlanDrafts.map(({ task, plan }) => (
            <article key={`recovered-${task.id}`} className="plan-item draft">
              <div className="item-top">
                <div>
                  <span className="tag">平台草稿</span>
                  <span className="status pending">待保存</span>
                </div>
                <time>{new Date(task.completedAt || task.createdAt).toLocaleString()}</time>
              </div>
              <h3>{plan.planName || plan.jobTitle}</h3>
              {plan.recommendReason && <p className="explanation">{plan.recommendReason}</p>}
              <div className="answer-grid">
                <div>
                  <span>文档</span>
                  <strong>{plan.documents?.length || 0} 份</strong>
                </div>
                <div>
                  <span>岗位</span>
                  <strong>{plan.jobTitle}</strong>
                </div>
                <div>
                  <span>任务 ID</span>
                  <strong className="text-xs">{task.id.slice(0, 8)}...</strong>
                </div>
              </div>
              <div className="item-actions">
                <button className="button primary" onClick={() => openEditor(plan)}>
                  <Pencil size={16} aria-hidden="true" />
                  继续编辑并保存
                </button>
                <button className="button reject" onClick={() => handleDelete(plan.planId)}>
                  <Trash2 size={16} aria-hidden="true" />
                  删除
                </button>
              </div>
            </article>
          ))}
          {platformPlanDrafts.map((plan) => (
            <article key={`platform-${plan.planId}`} className="plan-item draft">
              <div className="item-top">
                <div>
                  <span className="tag">平台草稿</span>
                  <span className="status pending">待保存</span>
                </div>
                <time>{new Date(plan.createdAt).toLocaleString()}</time>
              </div>
              <h3>{plan.planName || plan.jobTitle}</h3>
              {plan.recommendReason && <p className="explanation">{plan.recommendReason}</p>}
              <div className="answer-grid">
                <div>
                  <span>文档</span>
                  <strong>{plan.documents?.length || 0} 份</strong>
                </div>
                <div>
                  <span>岗位</span>
                  <strong>{plan.jobTitle}</strong>
                </div>
                <div>
                  <span>计划 ID</span>
                  <strong className="text-xs">{plan.planId.slice(0, 8)}...</strong>
                </div>
              </div>
              <div className="item-actions">
                <button className="button primary" onClick={() => openEditor(plan)}>
                  <Pencil size={16} aria-hidden="true" />
                  继续编辑并保存
                </button>
                <button className="button reject" onClick={() => handleDelete(plan.planId)}>
                  <Trash2 size={16} aria-hidden="true" />
                  删除
                </button>
              </div>
            </article>
          ))}
          {draftPlans.length === 0
            && recoveredPlanDrafts.length === 0
            && platformPlanDrafts.length === 0
            && savedPlans.length === 0 ? (
            <div className="empty-state">
              <FileSearch size={28} aria-hidden="true" />
              <h3>暂无学习计划</h3>
              <p>点击「新建计划」开始创建第一个学习计划。</p>
            </div>
          ) : (
            savedPlans.map((plan) => (
              <article key={plan.planId} className="plan-item">
                <div className="item-top">
                  <div>
                    <span className="tag">{plan.status}</span>
                    <span className="status saved">已保存</span>
                  </div>
                  <time>{new Date(plan.createdAt).toLocaleString()}</time>
                </div>
                <h3>{plan.planName || plan.jobTitle}</h3>
                {plan.recommendReason && <p className="explanation">{plan.recommendReason}</p>}
                <div className="answer-grid">
                  <div>
                    <span>文档</span>
                    <strong>{plan.documents?.length || 0} 份</strong>
                  </div>
                  <div>
                    <span>岗位</span>
                    <strong>{plan.jobTitle}</strong>
                  </div>
                  <div>
                    <span>计划 ID</span>
                    <strong className="text-xs">{plan.planId.slice(0, 8)}...</strong>
                  </div>
                </div>
                <div className="item-actions">
                  <button className="button secondary" onClick={() => openEditor(plan)}>
                    <Pencil size={16} aria-hidden="true" />
                    编辑
                  </button>
                  <button className="button primary" onClick={() => navigate(`/plans/${plan.planId}`)}>
                    查看详情
                  </button>
                  <button className="button reject" onClick={() => handleDelete(plan.planId)}>
                    <Trash2 size={16} aria-hidden="true" />
                    删除
                  </button>
                </div>
              </article>
            ))
          )}
        </section>
        {createModalOpen && (
          <div className="modal-backdrop" role="presentation">
            <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="create-plan-title">
              <header className="modal-header">
                <div>
                  <p className="eyebrow">New Plan</p>
                  <h2 id="create-plan-title">新建计划</h2>
                </div>
                <button
                  type="button"
                  className="icon-button"
                  title="关闭"
                  onClick={() => setCreateModalOpen(false)}
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </header>
              <div className="modal-body">
                <label>
                  <span>计划名称</span>
                  <input
                    value={createForm.planName}
                    onChange={(event) => setCreateForm({ ...createForm, planName: event.target.value })}
                    placeholder="例如：财务岗位培训计划"
                    autoFocus
                    required
                  />
                </label>
                <label>
                  <span>岗位名称</span>
                  <input
                    value={createForm.jobTitle}
                    onChange={(event) => setCreateForm({ ...createForm, jobTitle: event.target.value })}
                    placeholder="例如：财务"
                    required
                  />
                </label>
                <label>
                  <span>岗位简介</span>
                  <textarea
                    value={createForm.jobDescription}
                    onChange={(event) => setCreateForm({ ...createForm, jobDescription: event.target.value })}
                    placeholder="描述岗位职责、技能要求和培训目标"
                  />
                </label>
                {error && (
                  <div className="notice danger">
                    <CircleAlert size={18} aria-hidden="true" />
                    <span>{error}</span>
                  </div>
                )}
              </div>
              <footer className="modal-actions">
                <button type="button" className="button ghost" onClick={() => setCreateModalOpen(false)}>
                  取消
                </button>
                <button
                  type="button"
                  className="button primary"
                  onClick={handleGenerateRecommendations}
                  disabled={loading || !createForm.planName.trim() || !createForm.jobTitle.trim()}
                >
                  <Sparkles size={17} aria-hidden="true" />
                  {loading ? "生成中..." : "生成学习计划"}
                </button>
              </footer>
            </section>
          </div>
        )}
      </section>
    );
  }

  // ── 编辑器视图 ──
  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Edit Plan</p>
          <h2>编辑学习计划</h2>
          <p>填写岗位信息，查询并选择知识库文档，保存后系统将自动生成题目。</p>
        </div>
        <button className="button ghost" onClick={resetEditor}>
          <X size={17} aria-hidden="true" />
          返回列表
        </button>
      </header>

      {error && (
        <div className="notice danger">
          <CircleAlert size={18} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      <section className="work-surface two-column">
        <div className="form-panel">
          <div className="section-title">
            <Sparkles size={20} aria-hidden="true" />
            <h3>基本信息</h3>
          </div>
          <label>
            <span>计划名称</span>
            <input
              value={form.planName}
              onChange={(event) => setForm({ ...form, planName: event.target.value })}
              placeholder="例如：现场安全员入职计划"
            />
          </label>
          <label>
            <span>岗位名称</span>
            <input
              value={form.jobTitle}
              onChange={(event) => setForm({ ...form, jobTitle: event.target.value })}
              placeholder="例如：车辆检修工程师"
              required
            />
          </label>
          <label>
            <span>岗位简介</span>
            <textarea
              value={form.jobDescription}
              onChange={(event) => setForm({ ...form, jobDescription: event.target.value })}
              placeholder="描述岗位职责、技能要求和培训目标"
              required
            />
          </label>
        </div>

        <div className="form-panel">
          <div className="section-title">
            <FileSearch size={20} aria-hidden="true" />
            <h3>知识库文档 ({candidateDocs.length})</h3>
          </div>
          <label>
            <span>筛选文档</span>
            <input
              value={form.documentQuery}
              onChange={(event) => setForm({ ...form, documentQuery: event.target.value })}
              placeholder="按标题、摘要、分类筛选；留空显示全部"
            />
          </label>
          <button
            type="button"
            className="button secondary"
            onClick={() => void loadCandidateDocuments(form.documentQuery)}
            disabled={loadingDocuments}
          >
            <FileSearch size={17} aria-hidden="true" />
            {loadingDocuments
              ? "加载中..."
              : form.documentQuery.trim()
                ? "搜索知识库"
                : "刷新文档列表"}
          </button>
          <div className="mini-list">
            {!loadingDocuments && candidateDocs.length === 0 && (
              <p className="text-xs opacity-60" style={{ padding: "8px 0" }}>
                当前知识库暂无可选文档。
              </p>
            )}
            {!loadingDocuments && candidateDocs.length > 0 && filteredCandidateDocs.length === 0 && (
              <p className="text-xs opacity-60" style={{ padding: "8px 0" }}>
                没有符合当前筛选条件的文档。
              </p>
            )}
            {filteredCandidateDocs.map((document) => {
              const alreadyAdded = selectedDocs.some((d) => d.documentId === document.documentId);
              return (
                <button
                  type="button"
                  className={`mini-row${alreadyAdded ? " added" : ""}`}
                  key={document.documentId}
                  onClick={() => addDocument(document)}
                  disabled={alreadyAdded}
                >
                  <span className="mini-row-title">
                    <strong>{documentTitle(document)}</strong>
                    <span className={`selection-status${alreadyAdded ? " selected" : ""}`}>
                      {alreadyAdded ? "已选择" : "点击选择"}
                    </span>
                  </span>
                  <span>{documentAbilityGroup(document) || "未分组"} · {difficultyLabel(document.difficulty) || "未分级"}</span>
                  {document.summary && <span className="mini-row-summary">{document.summary}</span>}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className="work-surface two-column">
        <div className="form-panel">
          <div className="section-title">
            <Save size={20} aria-hidden="true" />
            <h3>文档列表 ({selectedDocs.length})</h3>
          </div>
          <ol className="compact-list editable-list">
            {selectedDocs.map((document, index) => (
              <li key={document.documentId} className="doc-edit-row">
                <div className="doc-edit-main">
                  <span className="doc-edit-title" title={documentTitle(document)}>
                    {index + 1}. {documentTitle(document)}
                  </span>
                  <div className="doc-edit-controls">
                    <button type="button" className="icon-button" onClick={() => moveDocument(index, -1)} disabled={index === 0} title="上移">
                      <ArrowUp size={14} aria-hidden="true" />
                    </button>
                    <button type="button" className="icon-button" onClick={() => moveDocument(index, 1)} disabled={index === selectedDocs.length - 1} title="下移">
                      <ArrowDown size={14} aria-hidden="true" />
                    </button>
                    <button type="button" className="icon-button" onClick={() => removeDocument(document.documentId)} title="移除">
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                </div>
                <div className="doc-meta-row">
                  <select
                    value={normalizeDifficulty(document.difficulty, index)}
                    onChange={(e) => updateDocMetadata(index, "difficulty", e.target.value)}
                  >
                    <option value="">难度</option>
                    {DIFFICULTY_OPTIONS.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                  <input
                    value={documentAbilityGroup(document)}
                    onChange={(e) => updateDocMetadata(index, "abilityGroup", e.target.value)}
                    placeholder="能力组"
                  />
                </div>
                <details className="document-sections" open>
                  <summary className="section-title document-sections-summary">
                    <Sparkles size={16} aria-hidden="true" />
                    <h3>文档内小节 ({document.sections.length})</h3>
                  </summary>
                  <ol className="compact-list editable-list section-edit-list">
                    {document.sections.map((section, sectionIndex) => (
                      <li key={section.sectionId} className="section-edit-item">
                        <div className="section-editor">
                          <div className="section-editor-summary">
                            <span className="section-index">{sectionIndex + 1}.</span>
                            <input
                              className="section-title-input"
                              aria-label={`第 ${sectionIndex + 1} 个小节标题`}
                              value={section.title}
                              onChange={(event) => updateSection(index, sectionIndex, { title: event.target.value })}
                            />
                            <div className="doc-edit-controls">
                              <button
                                type="button"
                                className="icon-button"
                                onClick={() => moveSection(index, sectionIndex, -1)}
                                disabled={sectionIndex === 0}
                                title="上移小节"
                              >
                                <ArrowUp size={14} aria-hidden="true" />
                              </button>
                              <button
                                type="button"
                                className="icon-button"
                                onClick={() => moveSection(index, sectionIndex, 1)}
                                disabled={sectionIndex === document.sections.length - 1}
                                title="下移小节"
                              >
                                <ArrowDown size={14} aria-hidden="true" />
                              </button>
                            </div>
                          </div>
                          <div className="section-editor-body">
                            <label>
                              <span>学习目标</span>
                              <textarea
                                value={section.learningObjective}
                                onChange={(event) => updateSection(index, sectionIndex, { learningObjective: event.target.value })}
                              />
                            </label>
                            <p className="section-criteria">
                              小节标准：{section.checkpointCriteria.join("、")}
                            </p>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ol>
                </details>
              </li>
            ))}
          </ol>
        </div>

        <div className="form-panel">
          <div className="section-title">
            <h3>绑定员工</h3>
          </div>
          <div className="employee-select">
            {MOCK_EMPLOYEES.map((emp) => (
              <label key={emp.id} className="employee-option">
                <input
                  type="checkbox"
                  checked={selectedEmployeeIds.includes(emp.id)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedEmployeeIds((prev) => [...prev, emp.id]);
                    } else {
                      setSelectedEmployeeIds((prev) => prev.filter((id) => id !== emp.id));
                    }
                  }}
                />
                <span>{emp.name}</span>
                <span className="text-xs opacity-60">{emp.department}</span>
              </label>
            ))}
          </div>

          <button
            type="button"
            className="button primary"
            onClick={handleSave}
            disabled={loading || !editingPlan || selectedDocs.length === 0}
          >
            <Save size={17} aria-hidden="true" />
            {loading ? "保存中..." : "保存计划"}
          </button>
          <p className="text-xs opacity-60 mt-2">
            保存后系统将自动为每个文档生成 10 道题目。
          </p>
        </div>
      </section>
    </section>
  );
}
