# Sprint 55-58: 最小闭环实施计划

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 完成员工培训 Agent 的最小闭环：学习计划 CRUD → 审核 → 题库 CRUD → 审核 → 课堂交互 → 端到端验证。首版 RAG/LLM 集成使用模板数据，后续替换为真实调用。

**Architecture:** 平台侧新增 training_plans 和 training_questions 表及 API；外部培训应用新增课堂页面和答题组件。所有 AI 生成首版使用模板，接口保持与真实集成一致。

---

## Sprint 55: 平台学习计划 CRUD

### Task 1: 学习计划数据库表

在 `backend/app/tables.py` 追加：

```python
training_plans = sa.Table(
    "training_plans", metadata,
    sa.Column("plan_id", UUIDString(), primary_key=True),
    sa.Column("app_id", UUIDString(), nullable=False),
    sa.Column("job_title", sa.String(length=256), nullable=False),
    sa.Column("job_description", sa.Text(), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
    sa.Column("ability_groups", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("documents", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("recommend_reason", sa.Text(), nullable=True),
    sa.Column("reading_order", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", UUIDString(), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", UUIDString(), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_by", UUIDString(), nullable=True),
)
```

创建迁移 `0036_create_training_plans_table.py`。

### Task 2: 学习计划 Schemas + Service + Routes

创建：
- `backend/app/schemas/training_plan.py`
- `backend/app/services/training_plan_service.py`
- `backend/app/api/routes/training_plans.py`

API:
- `POST /api/v1/training/plans/drafts` — 生成学习计划草稿
- `GET /api/v1/training/plans` — 列出学习计划
- `POST /api/v1/training/plans/{plan_id}/review` — 审核学习计划

首版 generate_draft 使用模板数据（不调用 LLM），接口保持一致。

---

## Sprint 56: 题库 CRUD

### Task 3: 题库数据库表

在 `backend/app/tables.py` 追加：

```python
training_questions = sa.Table(
    "training_questions", metadata,
    sa.Column("question_id", UUIDString(), primary_key=True),
    sa.Column("plan_id", UUIDString(), nullable=False),
    sa.Column("app_id", UUIDString(), nullable=False),
    sa.Column("question_type", sa.String(length=32), nullable=False),
    sa.Column("category", sa.String(length=16), nullable=False, server_default="practice"),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("options", sa.JSON(), nullable=True),
    sa.Column("correct_answer", sa.String(length=256), nullable=True),
    sa.Column("explanation", sa.Text(), nullable=True),
    sa.Column("rubric", sa.JSON(), nullable=True),
    sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", UUIDString(), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", UUIDString(), nullable=True),
)
```

创建迁移 `0037_create_training_questions_table.py`。

### Task 4: 题库 Schemas + Service + Routes

创建：
- `backend/app/schemas/training_question.py`
- `backend/app/services/training_question_service.py`
- `backend/app/api/routes/training_questions.py`

API:
- `POST /api/v1/training/questions/drafts` — 生成题库草稿
- `POST /api/v1/training/questions/{question_id}/review` — 审核题目

---

## Sprint 57: 外部培训应用课堂交互

### Task 5: 外部应用课堂 API 接入

在 `external-training-app/backend/app/services/platform_client.py` 中已有课堂方法。

在 `external-training-app/backend/app/api/routes/` 新增 `classroom.py`：
- `POST /classroom/sessions` — 创建课堂会话
- `POST /classroom/sessions/{id}/events` — 提交事件
- `GET /classroom/sessions/{id}` — 查询会话

### Task 6: 外部应用课堂页面

创建前端页面：
- `src/pages/ClassroomPage.tsx` — 多轮对话 + 状态显示 + uiActions 渲染
- `src/components/ChoiceQuestion.tsx` — A/B/C/D 单选题组件
- `src/services/classroomService.ts` — 课堂 API 调用
- `src/types/classroom.ts` — 课堂类型定义

---

## Sprint 58: 端到端验收

### Task 7: 端到端验证脚本

创建 `scripts/e2e-training-flow.py` 验证完整链路：
1. 创建平台绑定
2. 生成学习计划草稿
3. 审核学习计划
4. 生成题库草稿
5. 创建课堂会话
6. 提交课堂事件
7. 验证状态机流转

### Task 8: 文档同步

更新所有 Sprint 文档的执行记录。
