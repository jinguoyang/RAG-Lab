# 外部培训应用 Stub 替换 实施计划

> 2026-05-29 更新：本文为历史计划。员工培训课堂链路已调整为平台侧 `/training/classroom/*` 负责 Agent 状态机、上下文和结构化动作，应用端只调用平台并保存本地镜像。后续以 [2026-05-29-employee-training-agent-implementation.md](./2026-05-29-employee-training-agent-implementation.md) 为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 替换外部培训应用中所有模板 stub，接入平台 RAG API 实现真实的计划生成、题目生成和课堂回答。

**Architecture:** 平台侧新增两个 training 专用端点（plans/drafts、questions/drafts），外部应用通过 `PlatformClient` 调用。课堂回答直接复用平台已有的 `app-runtime/chat-messages` 端点。

**Tech Stack:** FastAPI, SQLAlchemy, httpx, 平台 app-runtime API

---

## 文件结构

```
backend/app/api/routes/
  training_plans.py          [新建] 平台侧 /training/plans/drafts 端点
  training_questions.py      [新建] 平台侧 /training/questions/drafts 端点

external-training-app/backend/app/services/
  platform_client.py         [修改] 添加 3 个方法
  training_plan_service.py   [修改] 替换 _generate_template_plan
  training_question_service.py [修改] 替换 _generate_template_questions
  training_classroom_service.py [修改] 替换 3 个 stub 函数
```

## Track 依赖关系

```
Track A (plans/drafts) ← 用户正在做
Track B (questions/drafts) ← 完全独立，可并行
Track C (classroom RAG) ← 依赖 PlatformClient 有基础结构，可与 A/B 并行
Track D (偏题检测 + UI 动作) ← 与 C 并行（不同函数）
```

---

## Track A — 计划生成（用户进行中，此处不展开）

平台 `/training/plans/drafts` + `PlatformClient.create_plan_draft()` + 替换 `_generate_template_plan()`

---

## Track B — 题目生成接入

### Task B1: 平台侧 `/training/questions/drafts` 端点

**Files:**
- Create: `backend/app/api/routes/training_questions.py`

- [ ] **Step 1: 创建路由文件**

```python
"""培训题目生成端点。"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/training/questions", tags=["training"])


class QuestionDraftRequest(BaseModel):
    planId: str
    appId: str
    jobTitle: str = ""
    abilityGroups: list[str] = Field(default_factory=list)
    count: int = 4


class QuestionOptionDTO(BaseModel):
    label: str
    text: str


class QuestionDraftDTO(BaseModel):
    questionType: str
    category: str
    content: str
    options: list[QuestionOptionDTO] = Field(default_factory=list)
    correctAnswer: str | None = None
    explanation: str | None = None
    rubric: dict | None = None
    evidenceChunkIds: list[str] = Field(default_factory=list)


@router.post("/drafts", response_model=list[QuestionDraftDTO], status_code=status.HTTP_201_CREATED)
async def create_question_drafts(request: QuestionDraftRequest):
    """RAG 检索 + LLM 生成题目。首版使用简化实现。"""
    # TODO: 接入 RAG 检索 + LLM 生成
    # 临时返回硬编码数据，与外部应用 _generate_template_questions 一致
    templates = [
        {
            "questionType": "single_choice",
            "category": "practice",
            "content": f"关于「{request.jobTitle}」，以下哪项是正确的？",
            "options": [
                {"label": "A", "text": "选项 A"},
                {"label": "B", "text": "选项 B"},
                {"label": "C", "text": "选项 C"},
                {"label": "D", "text": "选项 D"},
            ],
            "correctAnswer": "A",
            "explanation": "待 LLM 生成",
            "evidenceChunkIds": [],
        }
    ]
    return templates[: request.count]
```

- [ ] **Step 2: 注册路由**

在 `backend/app/api/router.py` 中添加：

```python
from app.api.routes.training_questions import router as training_questions_router
api_router.include_router(training_questions_router)
```

- [ ] **Step 3: 验证端点可用**

Run: `curl -X POST http://localhost:8000/api/v1/training/questions/drafts -H "Content-Type: application/json" -d '{"planId":"test","appId":"test","jobTitle":"测试岗位","count":2}'`

Expected: 201, 返回 2 道题目

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/training_questions.py backend/app/api/router.py
git commit -m "feat(training): add /training/questions/drafts endpoint stub"
```

---

### Task B2: PlatformClient.create_question_drafts()

**Files:**
- Modify: `external-training-app/backend/app/services/platform_client.py`

- [ ] **Step 1: 添加方法**

在 `PlatformClient` 类中添加：

```python
def create_question_drafts(
    self, plan_id: str, app_id: str, job_title: str, ability_groups: list[str], count: int
) -> list[dict]:
    """调用平台 /training/questions/drafts 生成题目。"""
    resp = httpx.post(
        f"{self.base_url}/training/questions/drafts",
        headers=self.headers,
        json={
            "planId": plan_id,
            "appId": app_id,
            "jobTitle": job_title,
            "abilityGroups": ability_groups,
            "count": count,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 2: Commit**

```bash
git add external-training-app/backend/app/services/platform_client.py
git commit -m "feat(training): add PlatformClient.create_question_drafts()"
```

---

### Task B3: 替换 _generate_template_questions

**Files:**
- Modify: `external-training-app/backend/app/services/training_question_service.py:20-25`

- [ ] **Step 1: 修改 create_question_drafts 函数**

将 `training_question_service.py` 中 `create_question_drafts` 函数改为调用 `PlatformClient`：

```python
def create_question_drafts(session: Session, user_id: str | None, request: Any) -> list[dict]:
    """生成题库草稿。调用平台 RAG API。"""
    from app.schemas.training_question import TrainingQuestionDTO
    from app.services.platform_client import PlatformClient
    from app.core.config import get_settings

    now = datetime.now(timezone.utc)

    settings = get_settings()
    client = PlatformClient(settings.platform_base_url, settings.platform_api_key)
    # 同步调用（httpx 不支持 async 在 sync context，使用 httpx.Client）
    import httpx
    resp = httpx.post(
        f"{client.base_url}/training/questions/drafts",
        headers=client.headers,
        json={
            "planId": request.planId,
            "appId": request.appId,
            "jobTitle": request.jobTitle if hasattr(request, 'jobTitle') else "",
            "abilityGroups": request.abilityGroups if hasattr(request, 'abilityGroups') else [],
            "count": request.count,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    templates = resp.json()

    results = []
    for tmpl in templates:
        qid = new_id()
        session.execute(
            training_questions.insert().values(
                id=qid,
                plan_id=request.planId,
                app_id=request.appId,
                question_type=tmpl["questionType"],
                category=tmpl.get("category", "practice"),
                content=tmpl["content"],
                options_json=json.dumps(tmpl.get("options", [])),
                correct_answer=tmpl.get("correctAnswer"),
                explanation=tmpl.get("explanation"),
                rubric_json=json.dumps(tmpl.get("rubric")) if tmpl.get("rubric") else None,
                evidence_chunk_ids_json=json.dumps(tmpl.get("evidenceChunkIds", [])),
                status="draft",
                created_by=user_id,
                created_at=now,
                updated_at=now,
            )
        )
        results.append(
            TrainingQuestionDTO(
                questionId=qid,
                planId=request.planId,
                appId=request.appId,
                questionType=tmpl["questionType"],
                category=tmpl.get("category", "practice"),
                content=tmpl["content"],
                options=tmpl.get("options", []),
                correctAnswer=tmpl.get("correctAnswer"),
                explanation=tmpl.get("explanation"),
                rubric=tmpl.get("rubric"),
                evidenceChunkIds=tmpl.get("evidenceChunkIds", []),
                status="draft",
                createdBy=user_id,
                createdAt=now.isoformat(),
                updatedAt=now.isoformat(),
            )
        )

    session.commit()
    return results
```

- [ ] **Step 2: 删除 _generate_template_questions 函数**

删除 `training_question_service.py` 中的 `_generate_template_questions` 函数（:125-184）。

- [ ] **Step 3: 验证**

启动外部应用，调用 `POST /training/questions/drafts`，确认返回平台生成的题目。

- [ ] **Step 4: Commit**

```bash
git add external-training-app/backend/app/services/training_question_service.py
git commit -m "feat(training): replace template questions with platform RAG call"
```

---

## Track C — 课堂 RAG 回答

### Task C1: PlatformClient.chat()

**Files:**
- Modify: `external-training-app/backend/app/services/platform_client.py`

- [ ] **Step 1: 添加 chat 方法**

```python
def chat(
    self,
    conversation_id: str,
    query: str,
    inputs: dict | None = None,
) -> dict:
    """调用平台 app-runtime/chat-messages 获取 RAG 回答。"""
    import httpx

    payload = {
        "query": query,
        "conversation_id": conversation_id,
        "inputs": inputs or {},
    }
    resp = httpx.post(
        f"{self.base_url}/app-runtime/chat-messages",
        headers=self.headers,
        json=payload,
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 2: Commit**

```bash
git add external-training-app/backend/app/services/platform_client.py
git commit -m "feat(training): add PlatformClient.chat() for RAG queries"
```

---

### Task C2: 替换 _generate_classroom_answer

**Files:**
- Modify: `external-training-app/backend/app/services/training_classroom_service.py:414-441`

- [ ] **Step 1: 替换函数实现**

```python
def _generate_classroom_answer(
    session: Session,
    session_row: Any,
    query: str,
    context_messages: list[dict[str, str]],
) -> tuple[str, list[Any]]:
    """调用平台 RAG Agent 生成课堂回答。"""
    from app.schemas.training_classroom import ClassroomCitationDTO
    from app.services.platform_client import PlatformClient
    from app.core.config import get_settings
    import httpx

    settings = get_settings()
    client = PlatformClient(settings.platform_base_url, settings.platform_api_key)

    session_id = session_row["id"]

    try:
        result = client.chat(
            conversation_id=f"classroom-{session_id}",
            query=query,
        )
        answer_text = result.get("answer", "")
        citations = [
            ClassroomCitationDTO(
                chunkId=c.get("chunkId", ""),
                content=c.get("content", ""),
                score=c.get("score", 0.0),
                documentName=c.get("documentName"),
            )
            for c in result.get("citations", [])
        ]
        return answer_text, citations
    except httpx.HTTPStatusError:
        return f"关于您的问题「{query}」：当前无法获取 RAG 回答，请稍后重试。", []
    except Exception:
        return f"关于您的问题「{query}」：服务暂时不可用。", []
```

- [ ] **Step 2: Commit**

```bash
git add external-training-app/backend/app/services/training_classroom_service.py
git commit -m "feat(training): replace classroom answer stub with RAG call"
```

---

## Track D — 偏题检测 + UI 动作

### Task D1: 实现 _is_query_relevant

**Files:**
- Modify: `external-training-app/backend/app/services/training_classroom_service.py:309-315`

- [ ] **Step 1: 实现偏题检测**

```python
def _is_query_relevant(
    query: str,
    plan_context: dict[str, Any] | None,
) -> bool:
    """基于关键词匹配的偏题检测。"""
    if not plan_context:
        return True

    job_title = plan_context.get("jobTitle", "")
    ability_groups = plan_context.get("abilityGroups", [])
    keywords = [job_title] + ability_groups
    keywords = [kw.lower() for kw in keywords if kw]

    if not keywords:
        return True

    query_lower = query.lower()
    # 至少匹配一个关键词即视为相关
    return any(kw in query_lower for kw in keywords) or len(query) < 10
```

- [ ] **Step 2: Commit**

```bash
git add external-training-app/backend/app/services/training_classroom_service.py
git commit -m "feat(training): implement keyword-based off-topic detection"
```

---

### Task D2: 实现 _extract_ui_actions

**Files:**
- Modify: `external-training-app/backend/app/services/training_classroom_service.py:444-447`

- [ ] **Step 1: 实现 UI 动作提取**

```python
def _extract_ui_actions(answer_text: str) -> list[Any]:
    """从回答中提取 UI 动作。基于标记解析。"""
    from app.schemas.training_classroom import ClassroomUIActionDTO
    import json
    import re

    actions: list[ClassroomUIActionDTO] = []

    # 解析 [CHOICE:{"options":[...]}] 标记
    choice_pattern = r'\[CHOICE:(\{.*?\})\]'
    for match in re.finditer(choice_pattern, answer_text):
        try:
            data = json.loads(match.group(1))
            actions.append(ClassroomUIActionDTO(
                actionType="single_choice",
                payload=data,
            ))
        except json.JSONDecodeError:
            pass

    # 解析 [TRUE_FALSE] 标记
    if "[TRUE_FALSE]" in answer_text:
        actions.append(ClassroomUIActionDTO(
            actionType="true_false",
            payload={"options": [{"label": "true", "text": "正确"}, {"label": "false", "text": "错误"}]},
        ))

    return actions
```

- [ ] **Step 2: Commit**

```bash
git add external-training-app/backend/app/services/training_classroom_service.py
git commit -m "feat(training): implement UI action extraction from answer text"
```

---

## 合并顺序建议

```
1. 用户合 Track A (plans/drafts)
2. Track B 独立合（questions/drafts，无冲突）
3. Track C 合（classroom RAG，platform_client.py rebase）
4. Track D 合（偏题 + UI，classroom_service.py 不同函数，无冲突）
```
