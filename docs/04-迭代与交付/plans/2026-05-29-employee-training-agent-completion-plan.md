# 员工培训智能体完整化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` before production code changes. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前“员工培训 Agent 可用骨架”完善为产品级完整员工培训智能体，覆盖 AI 学习规划、AI 出题、交互式教学、主观题评分、学习进度闭环、管理员审核发布、安全边界和端到端验收。

**Architecture:** 平台侧继续作为权威 Agent Runtime，负责 RAG、LLM、状态机、Skill、评分、进度、权限、审计和报表；外部培训应用只负责用户体系、审核 UI、课堂 UI 和本地业务镜像。所有新增能力先以员工培训专用服务落地，只有出现两个以上真实场景复用点时再抽象到通用 Agent Runtime。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、PostgreSQL/SQLite 测试库、现有 QARun/AppRuntime、React、Vite、TypeScript、pytest。

---

## 1. 当前基线

当前已具备：

- 平台侧 `training/plans/drafts`、`training/questions/drafts`、`training/classroom/*` API。
- 平台侧课堂状态机、结构化 `uiActions`、Citation、API Key 鉴权。
- 平台侧服务端权威客观题评分、偏题和违规文本拦截、`CHECK_UNDERSTAND` 流程。
- 应用端通过平台课堂 Agent 创建会话、提交事件，并保存本地镜像。
- 前端课堂页能消费平台返回的按钮、选择题、判断题和主观题动作。

当前主要缺口：

- 学习计划和题目生成仍偏规则化，未真正使用 LLM 结构化生成。
- Skill Registry、Skill 调用审计和 ReAct 控制还没有形成清晰内部契约。
- 主观题评分只是基础规则，未按 rubric 使用 LLM 批改。
- 课程进度、完成判定、错题复习、断线续接和报表不完整。
- 管理员审核发布、版本冻结、回滚和题库正式入库闭环不足。
- 会话、计划、题库、员工维度权限隔离和端到端测试仍需补强。

## 2. 文件结构规划

### 平台侧新增或重点修改

- `backend/app/services/training_skill_service.py`：员工培训 Skill Registry、Skill 输入输出 DTO、Skill 调用审计辅助。
- `backend/app/services/training_llm_service.py`：LLM 结构化 JSON 调用、schema 校验、失败回退。
- `backend/app/services/training_plan_service.py`：学习计划 LLM 生成、证据绑定、版本草稿。
- `backend/app/services/training_question_service.py`：单文档题目生成、题型分布、rubric 生成。
- `backend/app/services/training_classroom_service.py`：课堂状态机、追问、测验、复习、章节推进、完成判定。
- `backend/app/services/training_progress_service.py`：员工学习进度、课程完成、错题和薄弱点统计。
- `backend/app/services/training_report_service.py`：培训报表聚合。
- `backend/app/api/routes/training_progress.py`：员工进度与管理员报表 API。
- `backend/app/api/routes/training_plans.py`：计划审核、发布、版本读取 API。
- `backend/app/api/routes/training_questions.py`：题目审核、发布、按文档查询 API。
- `backend/app/schemas/training_skill.py`：Skill DTO。
- `backend/app/schemas/training_progress.py`：进度、完成记录、报表 DTO。
- `backend/app/tables.py`：补充计划版本、题目版本、员工进度、答题记录、Skill 调用审计表。
- `backend/migrations/versions/0040_training_completion_tables.py`：新增完整化表结构。
- `backend/app/tests/integration/test_employee_training_llm_plan.py`
- `backend/app/tests/integration/test_employee_training_question_generation.py`
- `backend/app/tests/integration/test_employee_training_progress.py`
- `backend/app/tests/integration/test_employee_training_e2e.py`

### 应用端新增或重点修改

- `external-training-app/backend/app/services/training_plan_service.py`：接入平台计划审核发布。
- `external-training-app/backend/app/services/training_question_service.py`：接入平台题库审核发布。
- `external-training-app/backend/app/services/training_classroom_service.py`：同步平台进度和答题结果镜像。
- `external-training-app/backend/app/services/platform_client.py`：补充平台计划、题目、进度和报表 API。
- `external-training-app/frontend/src/pages/ReviewPage.tsx`：计划/题库审核 UI 完整化。
- `external-training-app/frontend/src/pages/ClassroomPage.tsx`：断线续接、复习、完成状态展示。
- `external-training-app/frontend/src/services/reviewService.ts`
- `external-training-app/frontend/src/services/classroomService.ts`
- `external-training-app/frontend/src/types/classroom.ts`
- `external-training-app/frontend/src/types/review.ts`

## 3. 里程碑拆分

| 里程碑 | 目标 | 验收口径 |
| --- | --- | --- |
| M1 | LLM 结构化 Skill 基座 | Skill 可注册、可调用、可审计；LLM JSON 输出可校验和回退 |
| M2 | AI 学习计划完整化 | 基于岗位和知识库生成结构化计划，管理员可审核发布 |
| M3 | AI 题库完整化 | 对单文档生成判断、选择、主观题，管理员可审核发布 |
| M4 | 课堂与测验闭环 | 章节进度、答题记录、通过/不通过、错题复习、完成判定 |
| M5 | 记忆与断线续接 | 短期上下文、摘要记忆、业务记忆、恢复待处理动作 |
| M6 | 权限、安全和报表 | 跨应用/跨员工隔离、报表、审计和 E2E 验收 |

---

## Task 1: Training Skill Registry 与调用审计

**Files:**

- Create: `backend/app/schemas/training_skill.py`
- Create: `backend/app/services/training_skill_service.py`
- Modify: `backend/app/tables.py`
- Create: `backend/migrations/versions/0040_training_completion_tables.py`
- Test: `backend/app/tests/unit/test_training_skill_registry.py`

- [ ] **Step 1: 写失败测试，验证 Skill 注册、白名单和调用审计结构**

```python
def test_training_skill_registry_allows_known_skill_only():
    from app.services.training_skill_service import get_training_skill, list_training_skills

    skills = list_training_skills()

    assert "buildLearningPlanDraft" in [item.skillName for item in skills]
    assert get_training_skill("buildLearningPlanDraft").skillName == "buildLearningPlanDraft"
    assert get_training_skill("unknownSkill") is None
```

Run:

```powershell
python -m pytest backend/app/tests/unit/test_training_skill_registry.py -q
```

Expected: FAIL，提示 `app.services.training_skill_service` 不存在。

- [ ] **Step 2: 实现最小 Skill Registry**

Create `backend/app/schemas/training_skill.py`:

```python
"""员工培训 Skill DTO。"""
from typing import Any

from pydantic import BaseModel, Field


class TrainingSkillDTO(BaseModel):
    """平台内置员工培训 Skill 描述。"""

    skillName: str
    description: str
    inputSchema: dict[str, Any] = Field(default_factory=dict)
    outputSchema: dict[str, Any] = Field(default_factory=dict)
```

Create `backend/app/services/training_skill_service.py`:

```python
"""员工培训内置 Skill 注册表。"""
from __future__ import annotations

from app.schemas.training_skill import TrainingSkillDTO


_TRAINING_SKILLS = {
    "buildLearningPlanDraft": TrainingSkillDTO(
        skillName="buildLearningPlanDraft",
        description="基于岗位描述和知识库证据生成学习计划草稿。",
        inputSchema={"required": ["jobTitle", "evidences"]},
        outputSchema={"required": ["abilityGroups", "documents", "readingOrder"]},
    ),
    "generateQuestionDrafts": TrainingSkillDTO(
        skillName="generateQuestionDrafts",
        description="基于单文档证据生成题目草稿。",
        inputSchema={"required": ["documentId", "evidences", "questionTypes"]},
        outputSchema={"required": ["questions"]},
    ),
    "gradeSubjectiveAnswer": TrainingSkillDTO(
        skillName="gradeSubjectiveAnswer",
        description="基于 rubric 辅助评分主观题。",
        inputSchema={"required": ["answer", "rubric", "evidences"]},
        outputSchema={"required": ["score", "reason"]},
    ),
    "classifyIntent": TrainingSkillDTO(
        skillName="classifyIntent",
        description="识别课堂文本输入意图。",
        inputSchema={"required": ["state", "query"]},
        outputSchema={"required": ["intent"]},
    ),
}


def list_training_skills() -> list[TrainingSkillDTO]:
    """返回员工培训模板允许使用的 Skill。"""
    return list(_TRAINING_SKILLS.values())


def get_training_skill(skill_name: str) -> TrainingSkillDTO | None:
    """按名称读取 Skill，不存在时返回 None。"""
    return _TRAINING_SKILLS.get(skill_name)
```

- [ ] **Step 3: 运行测试确认通过**

```powershell
python -m pytest backend/app/tests/unit/test_training_skill_registry.py -q
```

Expected: PASS。

- [ ] **Step 4: 新增 Skill 调用审计表**

在 `backend/app/tables.py` 增加：

```python
training_skill_calls = sa.Table(
    "training_skill_calls",
    metadata,
    sa.Column("skill_call_id", UUIDString(), primary_key=True),
    sa.Column("session_id", UUIDString(), nullable=True),
    sa.Column("app_id", UUIDString(), nullable=False),
    sa.Column("skill_name", sa.String(length=64), nullable=False),
    sa.Column("input_summary", sa.JSON(), nullable=False),
    sa.Column("output_summary", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("error_code", sa.String(length=64), nullable=True),
    sa.Column("latency_ms", sa.Integer(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
```

Create migration `0040_training_completion_tables.py` with the same table. If later tasks add more tables, extend this migration before it is applied in shared environments.

- [ ] **Step 5: 验证编译和迁移脚本语法**

```powershell
python -m py_compile backend/migrations/versions/0040_training_completion_tables.py
python -m compileall backend/app
```

Expected: both commands PASS。

---

## Task 2: LLM 结构化 JSON 服务

**Files:**

- Create: `backend/app/services/training_llm_service.py`
- Test: `backend/app/tests/unit/test_training_llm_service.py`

- [ ] **Step 1: 写失败测试，验证 JSON 清洗和 schema 校验**

```python
def test_parse_training_json_strips_markdown_fence():
    from app.services.training_llm_service import parse_training_json

    result = parse_training_json('```json\n{"ok": true}\n```', required_keys={"ok"})

    assert result == {"ok": True}


def test_parse_training_json_rejects_missing_key():
    import pytest
    from app.services.training_llm_service import TrainingLLMOutputError, parse_training_json

    with pytest.raises(TrainingLLMOutputError):
        parse_training_json('{"ok": true}', required_keys={"questions"})
```

Run:

```powershell
python -m pytest backend/app/tests/unit/test_training_llm_service.py -q
```

Expected: FAIL，提示模块不存在。

- [ ] **Step 2: 实现 JSON 解析与校验**

```python
"""员工培训 LLM 结构化输出工具。"""
from __future__ import annotations

import json
from typing import Any


class TrainingLLMOutputError(ValueError):
    """LLM 结构化输出无法解析或缺少必要字段。"""


def parse_training_json(text: str, required_keys: set[str]) -> dict[str, Any]:
    """解析 LLM JSON 输出，兼容 Markdown fenced code block。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise TrainingLLMOutputError("TRAINING_LLM_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise TrainingLLMOutputError("TRAINING_LLM_JSON_OBJECT_REQUIRED")
    missing = required_keys - payload.keys()
    if missing:
        raise TrainingLLMOutputError(f"TRAINING_LLM_JSON_MISSING_KEYS:{','.join(sorted(missing))}")
    return payload
```

- [ ] **Step 3: 运行测试确认通过**

```powershell
python -m pytest backend/app/tests/unit/test_training_llm_service.py -q
```

Expected: PASS。

---

## Task 3: AI 学习计划生成完整化

**Files:**

- Modify: `backend/app/services/training_plan_service.py`
- Modify: `backend/app/schemas/training_plan.py`
- Test: `backend/app/tests/integration/test_employee_training_llm_plan.py`

- [ ] **Step 1: 写失败测试，验证 LLM 输出优先且保留证据**

```python
def test_plan_draft_uses_llm_structured_output_when_available(db, monkeypatch):
    from app.schemas.training_plan import PlanDraftRequest
    from app.services.training_plan_service import create_plan_draft

    credential, app_id = insert_training_app_with_chunks(db)

    def fake_generate_plan(*args, **kwargs):
        return {
            "abilityGroups": [{"name": "风险识别", "description": "识别现场风险"}],
            "documents": [{"documentId": kwargs["evidences"][0]["documentId"], "title": "现场安全制度", "relevance": 0.99, "abilityGroup": "风险识别", "difficulty": "basic"}],
            "readingOrder": [kwargs["evidences"][0]["documentId"]],
            "recommendReason": "岗位描述与现场安全制度高度相关。",
        }

    monkeypatch.setattr("app.services.training_plan_service.generate_plan_with_llm", fake_generate_plan)

    response = create_plan_draft(
        db,
        credential,
        PlanDraftRequest(appId=app_id, jobTitle="现场安全员", jobDescription="负责风险识别"),
    )

    assert response.abilityGroups[0].name == "风险识别"
    assert response.documents[0].relevance == 0.99
    assert response.evidenceChunkIds
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_llm_plan.py -q
```

Expected: FAIL，提示 `generate_plan_with_llm` 不存在。

- [ ] **Step 2: 新增 `generate_plan_with_llm`，失败时回退现有规则计划**

在 `training_plan_service.py` 增加：

```python
def generate_plan_with_llm(job_title: str, job_description: str, evidences: list[dict]) -> dict | None:
    """调用 LLM 生成学习计划 JSON；异常时返回 None 交给规则回退。"""
    # 首版复用现有 QARun/AppRuntime provider 能力；如果当前 Provider 不支持直接结构化调用，
    # 先保留函数边界，由测试 monkeypatch 注入，生产异常回退规则计划。
    return None
```

修改 `create_plan_draft()`：

```python
evidence_payload = [
    {
        "documentId": str(row["document_id"]),
        "chunkId": str(row["chunk_id"]),
        "title": evidence_title(row),
        "content": evidence_preview(row, 500),
    }
    for row in rows
]
llm_payload = generate_plan_with_llm(request.jobTitle, request.jobDescription, evidence_payload)
if llm_payload:
    groups = [AbilityGroupDTO(**item) for item in llm_payload["abilityGroups"]]
    documents = [DocumentDTO(**item) for item in llm_payload["documents"]]
    reading_order = llm_payload["readingOrder"]
    recommend_reason = llm_payload["recommendReason"]
else:
    # 保留当前规则回退
```

- [ ] **Step 3: 运行测试和既有计划测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_llm_plan.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
```

Expected: PASS。

---

## Task 4: AI 题库生成完整化

**Files:**

- Modify: `backend/app/services/training_question_service.py`
- Modify: `backend/app/schemas/training_question.py`
- Test: `backend/app/tests/integration/test_employee_training_question_generation.py`

- [ ] **Step 1: 写失败测试，验证按单文档生成三类题并绑定 evidence**

```python
def test_question_generation_uses_llm_for_single_document(db, monkeypatch):
    from app.schemas.training_question import QuestionDraftRequest
    from app.services.training_question_service import create_question_drafts

    credential, app_id, document_id = insert_training_app_with_one_document(db)

    def fake_generate_questions(*args, **kwargs):
        return {
            "questions": [
                {"questionType": "single_choice", "content": "应如何处理异常？", "options": [{"label": "A", "text": "停机并记录"}], "correctAnswer": "A", "explanation": "证据要求异常停机。", "rubric": None},
                {"questionType": "true_false", "content": "异常可以不上报。", "options": [{"label": "true", "text": "正确"}, {"label": "false", "text": "错误"}], "correctAnswer": "false", "explanation": "异常必须上报。", "rubric": None},
                {"questionType": "subjective", "content": "说明异常处理流程。", "options": [], "correctAnswer": None, "explanation": "按 rubric 评分。", "rubric": {"totalScore": 100, "criteria": [{"name": "流程", "score": 60}]}},
            ]
        }

    monkeypatch.setattr("app.services.training_question_service.generate_questions_with_llm", fake_generate_questions)

    response = create_question_drafts(
        db,
        credential,
        QuestionDraftRequest(planId=str(uuid4()), appId=app_id, jobTitle="点检员", documentIds=[document_id], count=3),
    )

    assert {item.questionType for item in response} == {"single_choice", "true_false", "subjective"}
    assert all(item.evidenceChunkIds for item in response)
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_question_generation.py -q
```

Expected: FAIL，提示 `generate_questions_with_llm` 不存在。

- [ ] **Step 2: 增加 LLM 题目生成函数和规则回退**

在 `training_question_service.py` 增加：

```python
def generate_questions_with_llm(job_title: str, evidences: list[dict], question_types: list[str], count: int) -> dict | None:
    """调用 LLM 生成题目 JSON；异常或无 Provider 时返回 None。"""
    return None
```

在 `create_question_drafts()` 中优先使用 LLM 输出；LLM 为空时保留当前模板化回退。

- [ ] **Step 3: 运行题库测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_question_generation.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
```

Expected: PASS。

---

## Task 5: 主观题 LLM 批改

**Files:**

- Modify: `backend/app/services/training_classroom_service.py`
- Create: `backend/app/tests/integration/test_employee_training_subjective_grading.py`

- [ ] **Step 1: 写失败测试，验证主观题按 rubric 由 LLM 返回评分依据**

```python
def test_subjective_answer_uses_llm_rubric_grading(db, monkeypatch):
    credential, app_id, question_id = insert_subjective_question(db)

    def fake_grade_subjective_answer(*args, **kwargs):
        return {"score": 85, "reason": "覆盖了异常识别和上报流程。", "matchedCriteria": ["流程", "风险"]}

    monkeypatch.setattr("app.services.training_classroom_service.grade_subjective_answer_with_llm", fake_grade_subjective_answer)

    response = submit_answer_in_quiz_state(
        db,
        credential,
        app_id,
        question_id,
        answer="发现异常后先停机，记录现象并上报主管。",
    )

    assert "得分：85" in response.visibleContent
    assert "覆盖了异常识别和上报流程" in response.visibleContent
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_subjective_grading.py -q
```

Expected: FAIL，提示函数不存在或仍返回规则分。

- [ ] **Step 2: 实现 LLM 批改函数边界和回退**

```python
def grade_subjective_answer_with_llm(answer: str, rubric: dict, evidences: list[dict]) -> dict | None:
    """按 rubric 调用 LLM 批改主观题；失败时返回 None。"""
    return None
```

修改 `_grade_subjective_answer()`：

```python
llm_result = grade_subjective_answer_with_llm(answer, rubric or {}, evidences)
if llm_result:
    return int(llm_result["score"]), str(llm_result["reason"])
```

- [ ] **Step 3: 运行测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_subjective_grading.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
```

Expected: PASS。

---

## Task 6: 学习进度、答题记录和完成判定

**Files:**

- Create: `backend/app/schemas/training_progress.py`
- Create: `backend/app/services/training_progress_service.py`
- Create: `backend/app/api/routes/training_progress.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/tables.py`
- Modify: `backend/migrations/versions/0040_training_completion_tables.py`
- Test: `backend/app/tests/integration/test_employee_training_progress.py`

- [ ] **Step 1: 写失败测试，验证通过分数后课程完成**

```python
def test_training_progress_marks_section_completed_after_passing_quiz(db):
    credential, app_id, session_id, question_id = create_quiz_session(db, passing_score=80)

    response = submit_classroom_event(
        db,
        credential,
        session_id,
        ClassroomEventSubmitRequest(eventType="submit_answer", payload={"questionId": question_id, "answer": "A"}),
    )

    progress = get_training_progress(db, app_id=app_id, end_user_id="employee-001")

    assert response.classroomState == "GRADE"
    assert progress.completedSections == 1
    assert progress.lastScore == 100
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_progress.py -q
```

Expected: FAIL，提示进度服务不存在。

- [ ] **Step 2: 新增进度和答题记录表**

在 `backend/app/tables.py` 和 `0040` migration 增加：

```python
training_progress_records = sa.Table(
    "training_progress_records",
    metadata,
    sa.Column("progress_id", UUIDString(), primary_key=True),
    sa.Column("app_id", UUIDString(), nullable=False),
    sa.Column("plan_id", UUIDString(), nullable=True),
    sa.Column("session_id", UUIDString(), nullable=False),
    sa.Column("end_user_id", sa.String(length=128), nullable=False),
    sa.Column("current_section_index", sa.Integer(), nullable=False),
    sa.Column("completed_sections", sa.Integer(), nullable=False),
    sa.Column("last_score", sa.Integer(), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("metadata", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

training_answer_records = sa.Table(
    "training_answer_records",
    metadata,
    sa.Column("answer_record_id", UUIDString(), primary_key=True),
    sa.Column("app_id", UUIDString(), nullable=False),
    sa.Column("session_id", UUIDString(), nullable=False),
    sa.Column("question_id", UUIDString(), nullable=True),
    sa.Column("end_user_id", sa.String(length=128), nullable=False),
    sa.Column("answer", sa.Text(), nullable=False),
    sa.Column("score", sa.Integer(), nullable=False),
    sa.Column("is_correct", sa.Boolean(), nullable=True),
    sa.Column("metadata", sa.JSON(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
```

- [ ] **Step 3: 实现进度服务**

Create `backend/app/services/training_progress_service.py`:

```python
"""员工培训进度服务。"""
from datetime import UTC, datetime

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.tables import training_progress_records


def upsert_training_progress(session: Session, *, app_id, plan_id, session_id, end_user_id: str, section_index: int, score: int | None, passed: bool) -> None:
    """按课堂测验结果更新员工学习进度。"""
    now = datetime.now(UTC)
    row = session.execute(
        select(training_progress_records).where(training_progress_records.c.session_id == session_id).limit(1)
    ).mappings().first()
    values = {
        "current_section_index": section_index,
        "completed_sections": section_index + 1 if passed else section_index,
        "last_score": score,
        "status": "completed" if passed else "in_progress",
        "updated_at": now,
    }
    if row is None:
        session.execute(
            insert(training_progress_records).values(
                progress_id=new_id(),
                app_id=app_id,
                plan_id=plan_id,
                session_id=session_id,
                end_user_id=end_user_id,
                metadata={},
                created_at=now,
                **values,
            )
        )
        return
    session.execute(update(training_progress_records).where(training_progress_records.c.progress_id == row["progress_id"]).values(**values))
```

- [ ] **Step 4: 在课堂评分后调用进度服务**

在 `training_classroom_service.submit_classroom_event()` 的 `submit_answer` 分支中：

```python
passed = score >= _passing_score(state_row)
upsert_training_progress(
    session,
    app_id=state_row["app_id"],
    plan_id=state_row["plan_id"],
    session_id=state_row["session_id"],
    end_user_id=state_row["end_user_id"],
    section_index=state_row["current_section_index"],
    score=score,
    passed=passed,
)
```

- [ ] **Step 5: 运行进度测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_progress.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
```

Expected: PASS。

---

## Task 7: 章节边界、错题复习和课程完成

**Files:**

- Modify: `backend/app/services/training_classroom_service.py`
- Test: `backend/app/tests/integration/test_employee_training_progress.py`

- [ ] **Step 1: 写失败测试，验证未通过进入 REVIEW，最后一节进入 COMPLETED**

```python
def test_failed_quiz_goes_review_and_last_section_can_complete(db):
    credential, session_id, question_id = create_two_section_session(db)

    failed = submit_classroom_event(
        db,
        credential,
        session_id,
        ClassroomEventSubmitRequest(eventType="submit_answer", payload={"questionId": question_id, "answer": "wrong"}),
    )

    assert failed.classroomState == "GRADE"
    assert "未通过" in failed.visibleContent

    review = submit_classroom_event(db, credential, session_id, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    assert review.classroomState == "REVIEW"
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_progress.py -q
```

Expected: FAIL，当前不会根据通过分生成明确未通过复习策略。

- [ ] **Step 2: 增加通过分读取和章节总数判断**

```python
def _passing_score(state_row: Any) -> int:
    """读取员工培训场景通过分，缺省 80。"""
    metadata = state_row["metadata"] or {}
    scenario = metadata.get("scenarioConfig") if isinstance(metadata, dict) else None
    if isinstance(scenario, dict):
        return int(scenario.get("passingScore") or 80)
    return 80


def _section_total(session: Session, kb_id: Any) -> int:
    """按当前可用证据估算章节总数。"""
    rows = read_training_evidence(session, kb_id, "", limit=100)
    return max(1, len(rows))
```

- [ ] **Step 3: 调整 `GRADE -> REVIEW/SUMMARY` 逻辑**

在 `submit_answer` 事件 metadata 中保存 `passed`，`continue` from `GRADE` 时：

```python
if last_result.get("passed"):
    return _event_to_response(..., "SUMMARY", "本节已通过...", ...)
return _event_to_response(..., "REVIEW", "本节未通过，请先复习错题...", ...)
```

- [ ] **Step 4: 运行进度和课堂测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_progress.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
```

Expected: PASS。

---

## Task 8: 管理员审核、发布和版本冻结

**Files:**

- Modify: `backend/app/api/routes/training_plans.py`
- Modify: `backend/app/api/routes/training_questions.py`
- Modify: `backend/app/services/training_plan_service.py`
- Modify: `backend/app/services/training_question_service.py`
- Modify: `external-training-app/backend/app/services/training_plan_service.py`
- Modify: `external-training-app/backend/app/services/training_question_service.py`
- Test: `backend/app/tests/integration/test_employee_training_review_publish.py`

- [ ] **Step 1: 写失败测试，验证计划审核发布后不可直接覆盖**

```python
def test_reviewed_plan_is_published_as_version_snapshot(db):
    credential, app_id = insert_training_app_with_chunks(db)
    plan = create_plan_draft(db, credential, PlanDraftRequest(appId=app_id, jobTitle="安全员"))

    published = publish_training_plan(db, credential, plan.planId, reviewer_id="admin-001")

    assert published.status == "published"
    assert published.version == 1

    with pytest.raises(TrainingPlanConflictError):
        update_training_plan_draft(db, credential, plan.planId, {"documents": []})
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_review_publish.py -q
```

Expected: FAIL，发布接口不存在。

- [ ] **Step 2: 实现计划发布接口**

API:

```python
@router.post("/{plan_id}/publish", response_model=PlanDraftDTO)
def publish_plan(plan_id: UUID, request: TrainingPlanPublishRequest, ...):
    ...
```

服务规则：

- 只有 `draft` 可发布。
- 发布时写 `status="published"`、`version=version+1` 或冻结当前 `version`。
- 已发布计划不可通过草稿更新接口直接覆盖。

- [ ] **Step 3: 实现题目发布接口**

API:

```python
@router.post("/{question_id}/publish", response_model=QuestionDraftDTO)
def publish_question(question_id: UUID, request: TrainingQuestionPublishRequest, ...):
    ...
```

服务规则：

- 只有 `draft` 可发布。
- 发布后 `status="approved"` 或 `published`，课堂只选择已发布题。

- [ ] **Step 4: 应用端接入平台发布接口**

在 `external-training-app/backend/app/services/platform_client.py` 增加：

```python
def publish_training_plan(self, plan_id: str, payload: dict) -> dict:
    resp = httpx.post(f"{self.base_url}/training/plans/{plan_id}/publish", headers=self.headers, json=payload, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def publish_training_question(self, question_id: str, payload: dict) -> dict:
    resp = httpx.post(f"{self.base_url}/training/questions/{question_id}/publish", headers=self.headers, json=payload, timeout=60.0)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 5: 运行审核发布测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_review_publish.py -q
python -m pytest app/tests/integration/test_classroom_api.py -q
```

Expected: PASS。

---

## Task 9: 断线续接与上下文摘要记忆

**Files:**

- Modify: `backend/app/services/training_classroom_service.py`
- Modify: `backend/app/schemas/training_classroom.py`
- Modify: `external-training-app/frontend/src/pages/ClassroomPage.tsx`
- Test: `backend/app/tests/integration/test_employee_training_resume.py`

- [ ] **Step 1: 写失败测试，验证读取会话返回待处理动作**

```python
def test_get_classroom_session_returns_pending_actions_for_resume(db):
    credential, session_id = create_session_in_check_understand(db)

    detail = get_classroom_session(db, session_id, credential)

    assert detail.currentState == "CHECK_UNDERSTAND"
    assert detail.metadata["pendingActions"][0]["actionType"] == "button_group"
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_resume.py -q
```

Expected: FAIL，详情响应没有 pendingActions。

- [ ] **Step 2: 在会话详情 metadata 中返回待处理动作**

```python
def _pending_actions_for_state(state: str) -> list[dict]:
    if state == "CHECK_UNDERSTAND":
        return [_button_group(("听懂了，继续", "continue", {}), ("我还不清楚", "query", {})).model_dump()]
    if state == "SUMMARY":
        return [_button_group(("下一节", "next_section", {}), ("完成课程", "complete", {})).model_dump()]
    return []
```

在 `get_classroom_session()` 中：

```python
metadata = dict(row["metadata"] or {})
metadata["pendingActions"] = _pending_actions_for_state(row["current_state"])
```

- [ ] **Step 3: 前端恢复 pending actions**

在 `ClassroomPage.tsx` 的会话加载逻辑中：

```tsx
setUiActions((detail.metadata?.pendingActions as ClassroomUiAction[]) || []);
```

- [ ] **Step 4: 运行续接测试和前端构建**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_resume.py -q
cd external-training-app/frontend
npm run build
```

Expected: PASS。

---

## Task 10: 权限隔离与安全边界

**Files:**

- Modify: `backend/app/services/training_classroom_service.py`
- Modify: `backend/app/services/training_plan_service.py`
- Modify: `backend/app/services/training_question_service.py`
- Test: `backend/app/tests/integration/test_employee_training_security.py`

- [ ] **Step 1: 写失败测试，验证跨 App API Key 不能读取或推进会话**

```python
def test_api_key_cannot_access_other_app_classroom_session(db):
    credential_a, app_a = insert_training_app_with_chunks(db)
    credential_b, app_b = insert_training_app_with_chunks(db)
    session = create_classroom_session(db, credential_a, ClassroomSessionCreateRequest(appId=app_a, endUserId="u1"))

    with pytest.raises(TrainingAgentConflictError):
        submit_classroom_event(db, credential_b, session.sessionId, ClassroomEventSubmitRequest(eventType="start", payload={}))
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_security.py -q
```

Expected: FAIL if service does not raise stable conflict for cross-app credential.

- [ ] **Step 2: 强化会话、计划、题库 appId 校验**

规则：

- `credential -> app_id` 必须等于资源 `app_id`。
- 外部 `endUserId` 只能访问自己的课堂会话；管理员接口另行校验管理权限。
- 对外响应不返回完整 Prompt、Trace、未授权 Chunk 正文。

- [ ] **Step 3: 运行安全测试**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_security.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
```

Expected: PASS。

---

## Task 11: 培训报表与薄弱点统计

**Files:**

- Create: `backend/app/services/training_report_service.py`
- Create: `backend/app/api/routes/training_reports.py`
- Modify: `backend/app/api/router.py`
- Modify: `external-training-app/backend/app/services/platform_client.py`
- Modify: `external-training-app/frontend/src/pages/ReviewPage.tsx`
- Test: `backend/app/tests/integration/test_employee_training_reports.py`

- [ ] **Step 1: 写失败测试，验证报表聚合完成率和平均分**

```python
def test_training_report_aggregates_completion_and_scores(db):
    credential, app_id = seed_training_progress_records(db, completed=2, total=3, scores=[100, 60, 80])

    report = get_training_report(db, credential, app_id)

    assert report.completionRate == 0.67
    assert report.averageScore == 80
    assert report.weaknesses
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_reports.py -q
```

Expected: FAIL，报表服务不存在。

- [ ] **Step 2: 实现报表服务**

```python
def get_training_report(session: Session, credential: str, app_id: str) -> TrainingReportDTO:
    """聚合当前 App 的员工培训完成率、平均分和薄弱点。"""
    context = resolve_training_context(session, credential, app_id)
    # 查询 training_progress_records 和 training_answer_records
    # 返回 completionRate、averageScore、failedQuestionCount、weaknesses
```

- [ ] **Step 3: 暴露报表 API 并接入应用端**

API:

```python
GET /api/v1/training/reports/summary?appId=...
```

应用端 `PlatformClient` 增加 `get_training_report()`，管理员页面展示完成率、平均分、错题分布。

- [ ] **Step 4: 运行报表测试和前端构建**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_reports.py -q
cd external-training-app/frontend
npm run build
```

Expected: PASS。

---

## Task 12: 端到端验收

**Files:**

- Create: `backend/app/tests/integration/test_employee_training_e2e.py`
- Create: `external-training-app/backend/app/tests/integration/test_training_e2e_contract.py`
- Update: `docs/04-迭代与交付/plans/2026-05-29-employee-training-agent-completion-plan.md`

- [ ] **Step 1: 写平台 E2E 测试**

```python
def test_employee_training_platform_e2e(db, monkeypatch):
    credential, app_id = seed_training_app_with_documents(db)
    plan = create_plan_draft(db, credential, PlanDraftRequest(appId=app_id, jobTitle="现场安全员"))
    published_plan = publish_training_plan(db, credential, plan.planId, reviewer_id="admin")
    questions = create_question_drafts(db, credential, QuestionDraftRequest(planId=published_plan.planId, appId=app_id, jobTitle="现场安全员", count=3))
    publish_all_questions(db, credential, [item.questionId for item in questions])
    session = create_classroom_session(db, credential, ClassroomSessionCreateRequest(appId=app_id, planId=published_plan.planId, endUserId="employee-001"))

    assert submit_classroom_event(db, credential, session.sessionId, ClassroomEventSubmitRequest(eventType="start", payload={})).classroomState == "PLAN"
    assert submit_classroom_event(db, credential, session.sessionId, ClassroomEventSubmitRequest(eventType="continue", payload={})).classroomState == "TEACH"
    assert submit_classroom_event(db, credential, session.sessionId, ClassroomEventSubmitRequest(eventType="continue", payload={})).classroomState == "CHECK_UNDERSTAND"
```

Run:

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_e2e.py -q
```

Expected: FAIL until previous tasks are complete.

- [ ] **Step 2: 写应用端契约 E2E 测试**

```python
def test_external_app_delegates_training_e2e_to_platform(client, monkeypatch):
    fake_platform = FakePlatformClientWithPlanQuestionClassroom()
    monkeypatch.setattr("app.services.training_classroom_service._platform_client", lambda: fake_platform)

    create_resp = client.post("/api/v1/classroom/sessions", json={"appId": "app-001", "endUserId": "employee-001"})
    event_resp = client.post(f"/api/v1/classroom/sessions/{create_resp.json()['sessionId']}/events", json={"eventType": "start", "payload": {}})

    assert event_resp.status_code == 201
    assert event_resp.json()["classroomState"] == "PLAN"
```

Run:

```powershell
cd external-training-app/backend
python -m pytest app/tests/integration/test_training_e2e_contract.py -q
```

Expected: PASS after previous app-side tasks.

- [ ] **Step 3: 全量验证命令**

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_agent_runtime.py backend/app/tests/integration/test_employee_training_llm_plan.py backend/app/tests/integration/test_employee_training_question_generation.py backend/app/tests/integration/test_employee_training_subjective_grading.py backend/app/tests/integration/test_employee_training_progress.py backend/app/tests/integration/test_employee_training_security.py backend/app/tests/integration/test_employee_training_reports.py backend/app/tests/integration/test_employee_training_e2e.py -q
python -m compileall backend/app
cd external-training-app/backend
python -m pytest app/tests/unit/test_classroom_state_machine.py app/tests/unit/test_platform_client.py app/tests/integration/test_classroom_api.py app/tests/integration/test_training_e2e_contract.py -q
python -m compileall app
cd ../frontend
npm run build
cd ../../
git diff --check
```

Expected:

- 所有 pytest 通过。
- 两个 `compileall` 通过。
- 前端 build 通过。
- `git diff --check` 无错误。

---

## 4. 完成定义

达到完整员工培训智能体标准时，必须同时满足：

- 管理员能输入岗位信息，平台基于知识库和 LLM 生成结构化学习计划草稿。
- 管理员能审核、修改、发布学习计划，发布版本不可被草稿覆盖。
- 管理员能对单文档生成判断、选择和主观题草稿，并审核发布。
- 员工课堂由平台状态机权威控制，支持讲解、理解确认、追问、偏题、违规拦截、测验、复习、小结和完成。
- 客观题由服务端按题库正确答案评分；主观题由 LLM 按 rubric 辅助评分，并记录评分依据。
- 学习进度、答题记录、错题、薄弱点和课程完成状态落库。
- 断线续接能恢复当前状态、最近消息、摘要记忆和待处理动作。
- 应用端不调用 LLM/RAG Provider，不解析自然语言隐藏标记，不保存长期平台 API Key 到浏览器。
- 平台能阻止跨 App、跨员工、跨计划访问。
- 管理端能查看完成率、平均分、错题和薄弱能力报表。
- 平台和应用端 E2E 测试通过。

## 5. 执行顺序建议

优先级顺序：

1. Task 1-2：Skill 与 LLM 结构化基座。
2. Task 3-5：AI 学习计划、题库、主观题评分。
3. Task 6-7：进度、答题记录、完成判定。
4. Task 8-9：审核发布、断线续接。
5. Task 10-12：安全、报表和 E2E。

不建议并行修改同一个核心文件 `training_classroom_service.py`。如果使用 subagent，建议按里程碑分支或逐任务串行合并，避免状态机冲突。
