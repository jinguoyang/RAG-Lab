# Sprint 53: 外部培训应用基线 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立独立的外部培训应用（external-training-app/），包含前后端，可独立启动，通过平台 API 完成学习计划审核最小链路。

**Architecture:** 独立 Vite+React+TypeScript 前端 + FastAPI+SQLite 后端。前端复用 shadcn/ui 风格，后端通过 HTTP 调用平台 API。无 LLM、无 Embedding、无 RAG。

**Tech Stack:** Vite, React 18, TypeScript, Tailwind CSS, shadcn/ui, FastAPI, SQLAlchemy, SQLite, Alembic

---

## 文件结构

```
external-training-app/
  backend/
    app/
      api/
        routes/
          bindings.py          # 平台绑定 CRUD
          reviews.py           # 学习计划审核
          health.py            # 健康检查
        router.py              # 路由注册
      core/
        config.py              # 配置（平台地址、DB URL）
        database.py            # DB 连接
      schemas/
        binding.py             # 绑定 schemas
        review.py              # 审核 schemas
      services/
        platform_client.py     # 平台 API 客户端
        review_service.py      # 审核业务逻辑
      tables.py                # 表定义
      main.py                  # FastAPI app
    alembic/
      env.py
      versions/
        0001_initial.py        # 初始迁移
    requirements.txt
  frontend/
    src/
      components/
        ui/                    # shadcn/ui 组件
      pages/
        BindingPage.tsx        # 平台绑定页
        ReviewPage.tsx         # 学习计划审核页
      services/
        apiClient.ts           # API 客户端
        bindingService.ts      # 绑定 API
        reviewService.ts       # 审核 API
      types/
        binding.ts             # 绑定类型
        review.ts              # 审核类型
      App.tsx
      main.tsx
      routes.tsx
    index.html
    package.json
    vite.config.ts
    tailwind.config.ts
    tsconfig.json
  README.md
```

---

### Task 1: 后端项目骨架

**Files:**
- Create: `external-training-app/backend/app/main.py`
- Create: `external-training-app/backend/app/core/config.py`
- Create: `external-training-app/backend/app/core/database.py`
- Create: `external-training-app/backend/requirements.txt`

- [ ] **Step 1: 创建后端目录和配置**

创建 `external-training-app/backend/requirements.txt`:
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0
pydantic>=2.0
httpx>=0.27.0
alembic>=1.13.0
```

创建 `external-training-app/backend/app/core/config.py`:
```python
"""外部培训应用配置。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./training.db"
    platform_base_url: str = "http://localhost:8000/api/v1"
    platform_app_id: str = ""
    platform_api_key: str = ""

    model_config = {"env_prefix": "EXT_TRAINING_"}


def get_settings() -> Settings:
    return Settings()
```

创建 `external-training-app/backend/app/core/database.py`:
```python
"""数据库连接。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

创建 `external-training-app/backend/app/main.py`:
```python
"""外部培训应用 FastAPI 入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.database import engine
from app.tables import metadata

metadata.create_all(bind=engine)

app = FastAPI(title="外部培训应用", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: 验证后端可启动**

```powershell
cd external-training-app/backend
pip install -r requirements.txt
python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add external-training-app/backend/
git commit -m "feat(ext-training): add backend skeleton with FastAPI, config, and DB"
```

---

### Task 2: 数据库表与迁移

**Files:**
- Create: `external-training-app/backend/app/tables.py`
- Create: `external-training-app/backend/alembic/` (init + migration)

- [ ] **Step 1: 创建表定义**

创建 `external-training-app/backend/app/tables.py`:
```python
"""外部培训应用表定义。"""
import sqlalchemy as sa

metadata = sa.MetaData()

external_users = sa.Table(
    "external_users",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("display_name", sa.String(length=128), nullable=False),
    sa.Column("employee_no", sa.String(length=64), nullable=True),
    sa.Column("role", sa.String(length=32), nullable=False, server_default="employee"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

platform_app_bindings = sa.Table(
    "platform_app_bindings",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("platform_base_url", sa.String(length=512), nullable=False),
    sa.Column("platform_app_id", sa.String(length=36), nullable=False),
    sa.Column("platform_api_key_ref", sa.String(length=256), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_review_tasks = sa.Table(
    "training_review_tasks",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("platform_draft_id", sa.String(length=36), nullable=True),
    sa.Column("platform_plan_id", sa.String(length=36), nullable=True),
    sa.Column("review_type", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
    sa.Column("reviewer_id", sa.String(length=36), nullable=True),
    sa.Column("submitted_payload", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_class_sessions = sa.Table(
    "training_class_sessions",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("external_user_id", sa.String(length=36), nullable=False),
    sa.Column("platform_session_id", sa.String(length=36), nullable=True),
    sa.Column("platform_plan_id", sa.String(length=36), nullable=True),
    sa.Column("current_state", sa.String(length=32), nullable=False, server_default="INIT"),
    sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_class_messages = sa.Table(
    "training_class_messages",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("session_id", sa.String(length=36), nullable=False),
    sa.Column("role", sa.String(length=16), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("platform_message_id", sa.String(length=36), nullable=True),
    sa.Column("ui_actions_json", sa.JSON(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_answer_records = sa.Table(
    "training_answer_records",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("session_id", sa.String(length=36), nullable=False),
    sa.Column("platform_question_id", sa.String(length=36), nullable=True),
    sa.Column("question_type", sa.String(length=32), nullable=True),
    sa.Column("selected_answer", sa.String(length=256), nullable=True),
    sa.Column("submitted_payload", sa.JSON(), nullable=True),
    sa.Column("score", sa.Numeric(10, 2), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
```

- [ ] **Step 2: 初始化 Alembic 并创建迁移**

```powershell
cd external-training-app/backend
alembic init alembic
```

修改 `alembic/env.py` 以使用 app 的 metadata 和数据库 URL。

创建 `alembic/versions/0001_initial.py` 创建所有 6 张表。

- [ ] **Step 3: 验证表创建**

```powershell
cd external-training-app/backend
python -c "from app.tables import metadata, external_users, platform_app_bindings; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add external-training-app/backend/
git commit -m "feat(ext-training): add database tables and Alembic migration"
```

---

### Task 3: 平台绑定 API

**Files:**
- Create: `external-training-app/backend/app/schemas/binding.py`
- Create: `external-training-app/backend/app/api/routes/bindings.py`
- Create: `external-training-app/backend/app/api/router.py`
- Create: `external-training-app/backend/app/api/routes/health.py`

- [ ] **Step 1: 创建绑定 schemas**

创建 `external-training-app/backend/app/schemas/binding.py`:
```python
"""平台绑定 schemas。"""
from pydantic import BaseModel, Field


class BindingCreateRequest(BaseModel):
    platformBaseUrl: str = Field(min_length=1, max_length=512)
    platformAppId: str = Field(min_length=1, max_length=36)
    platformApiKey: str = Field(min_length=1, max_length=256)


class BindingResponse(BaseModel):
    id: str
    platformBaseUrl: str
    platformAppId: str
    status: str
    createdAt: str
```

- [ ] **Step 2: 创建路由**

创建 `external-training-app/backend/app/api/routes/health.py`:
```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}
```

创建 `external-training-app/backend/app/api/routes/bindings.py`:
```python
"""平台绑定路由。"""
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.binding import BindingCreateRequest, BindingResponse
from app.tables import platform_app_bindings

router = APIRouter(prefix="/bindings", tags=["bindings"])


@router.post("", response_model=BindingResponse, status_code=201)
def create_binding(request: BindingCreateRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    binding_id = str(uuid4())
    db.execute(
        platform_app_bindings.insert().values(
            id=binding_id,
            platform_base_url=request.platformBaseUrl,
            platform_app_id=request.platformAppId,
            platform_api_key_ref=request.platformApiKey,
            status="active",
            created_at=now,
        )
    )
    db.commit()
    return BindingResponse(
        id=binding_id,
        platformBaseUrl=request.platformBaseUrl,
        platformAppId=request.platformAppId,
        status="active",
        createdAt=now.isoformat(),
    )


@router.get("", response_model=list[BindingResponse])
def list_bindings(db: Session = Depends(get_db)):
    rows = db.execute(
        platform_app_bindings.select().where(
            platform_app_bindings.c.status == "active"
        )
    ).fetchall()
    return [
        BindingResponse(
            id=r.id,
            platformBaseUrl=r.platform_base_url,
            platformAppId=r.platform_app_id,
            status=r.status,
            createdAt=r.created_at.isoformat(),
        )
        for r in rows
    ]
```

创建 `external-training-app/backend/app/api/router.py`:
```python
from fastapi import APIRouter

from app.api.routes.bindings import router as bindings_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(bindings_router)
```

- [ ] **Step 3: 验证编译**

```powershell
cd external-training-app/backend
python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add external-training-app/backend/
git commit -m "feat(ext-training): add platform binding CRUD API"
```

---

### Task 4: 平台 API 客户端与审核服务

**Files:**
- Create: `external-training-app/backend/app/services/platform_client.py`
- Create: `external-training-app/backend/app/services/review_service.py`
- Create: `external-training-app/backend/app/schemas/review.py`
- Create: `external-training-app/backend/app/api/routes/reviews.py`

- [ ] **Step 1: 创建平台客户端**

创建 `external-training-app/backend/app/services/platform_client.py`:
```python
"""平台 API 客户端。"""
import httpx

from app.core.config import get_settings


class PlatformClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def create_plan_draft(self, app_id: str, job_title: str, job_description: str) -> dict:
        resp = httpx.post(
            f"{self.base_url}/training/plans/drafts",
            json={"appId": app_id, "jobTitle": job_title, "jobDescription": job_description},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def review_plan_draft(self, draft_id: str, decision: str, notes: str = "") -> dict:
        resp = httpx.post(
            f"{self.base_url}/training/plans/{draft_id}/review",
            json={"decision": decision, "notes": notes},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def create_classroom_session(self, app_id: str, end_user_id: str, plan_id: str | None = None) -> dict:
        resp = httpx.post(
            f"{self.base_url}/training/classroom/sessions",
            json={"appId": app_id, "endUserId": end_user_id, "planId": plan_id},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def submit_classroom_event(self, session_id: str, event_type: str, payload: dict = None, query: str = None) -> dict:
        body: dict = {"eventType": event_type, "payload": payload or {}}
        if query:
            body["query"] = query
        resp = httpx.post(
            f"{self.base_url}/training/classroom/sessions/{session_id}/events",
            json=body,
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get_classroom_session(self, session_id: str) -> dict:
        resp = httpx.get(
            f"{self.base_url}/training/classroom/sessions/{session_id}",
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: 创建审核 schemas 和服务**

创建 `external-training-app/backend/app/schemas/review.py`:
```python
"""审核 schemas。"""
from typing import Any
from pydantic import BaseModel, Field


class ReviewTaskResponse(BaseModel):
    id: str
    platformDraftId: str | None = None
    platformPlanId: str | None = None
    reviewType: str
    status: str
    submittedPayload: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class ReviewSubmitRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""
    adjustments: dict[str, Any] | None = None
```

创建 `external-training-app/backend/app/services/review_service.py`:
```python
"""审核服务。"""
from uuid import uuid4
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.tables import training_review_tasks, platform_app_bindings
from app.services.platform_client import PlatformClient


def _get_platform_client(db: Session) -> PlatformClient:
    """获取平台客户端。"""
    row = db.execute(
        platform_app_bindings.select().where(
            platform_app_bindings.c.status == "active"
        )
    ).fetchone()
    if row is None:
        raise ValueError("未配置平台绑定")
    return PlatformClient(row.platform_base_url, row.platform_api_key_ref)


def list_review_tasks(db: Session, review_type: str | None = None) -> list[dict]:
    query = training_review_tasks.select()
    if review_type:
        query = query.where(training_review_tasks.c.review_type == review_type)
    rows = db.execute(query.order_by(training_review_tasks.c.created_at.desc())).fetchall()
    return [
        {
            "id": r.id,
            "platformDraftId": r.platform_draft_id,
            "platformPlanId": r.platform_plan_id,
            "reviewType": r.review_type,
            "status": r.status,
            "submittedPayload": r.submitted_payload or {},
            "createdAt": r.created_at.isoformat(),
        }
        for r in rows
    ]


def generate_plan_draft(db: Session, job_title: str, job_description: str) -> dict:
    """调用平台生成学习计划草稿。"""
    client = _get_platform_client(db)
    binding = db.execute(
        platform_app_bindings.select().where(
            platform_app_bindings.c.status == "active"
        )
    ).fetchone()

    result = client.create_plan_draft(binding.platform_app_id, job_title, job_description)

    now = datetime.now(timezone.utc)
    task_id = str(uuid4())
    db.execute(
        training_review_tasks.insert().values(
            id=task_id,
            platform_draft_id=result.get("draftId", result.get("planId")),
            review_type="plan",
            status="pending",
            submitted_payload=result,
            created_at=now,
        )
    )
    db.commit()

    return {"taskId": task_id, "draft": result}


def submit_review(db: Session, task_id: str, decision: str, notes: str = "", adjustments: dict | None = None) -> dict:
    """提交审核结果到平台。"""
    row = db.execute(
        training_review_tasks.select().where(
            training_review_tasks.c.id == task_id
        )
    ).fetchone()

    if row is None:
        raise ValueError(f"审核任务 {task_id} 不存在")

    client = _get_platform_client(db)

    draft_id = row.platform_draft_id
    if draft_id:
        client.review_plan_draft(draft_id, decision, notes)

    now = datetime.now(timezone.utc)
    db.execute(
        training_review_tasks.update().where(
            training_review_tasks.c.id == task_id
        ).values(
            status=decision,
            reviewed_at=now,
        )
    )
    db.commit()

    return {"taskId": task_id, "status": decision}
```

- [ ] **Step 3: 创建审核路由**

创建 `external-training-app/backend/app/api/routes/reviews.py`:
```python
"""审核路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.review import ReviewSubmitRequest, ReviewTaskResponse
from app.services.review_service import list_review_tasks, generate_plan_draft, submit_review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewTaskResponse])
def list_reviews(reviewType: str | None = None, db: Session = Depends(get_db)):
    return list_review_tasks(db, reviewType)


@router.post("/plans/drafts", status_code=201)
def create_plan_draft(
    jobTitle: str = "",
    jobDescription: str = "",
    db: Session = Depends(get_db),
):
    if not jobTitle:
        raise HTTPException(400, "jobTitle 不能为空")
    return generate_plan_draft(db, jobTitle, jobDescription)


@router.post("/{task_id}/submit")
def submit_review_result(task_id: str, request: ReviewSubmitRequest, db: Session = Depends(get_db)):
    try:
        return submit_review(db, task_id, request.decision, request.notes, request.adjustments)
    except ValueError as e:
        raise HTTPException(404, str(e))
```

在 `router.py` 中追加审核路由注册。

- [ ] **Step 4: 验证编译**

```powershell
cd external-training-app/backend
python -c "from app.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add external-training-app/backend/
git commit -m "feat(ext-training): add platform client, review service and API"
```

---

### Task 5: 前端项目骨架

**Files:**
- Create: `external-training-app/frontend/` (Vite project)

- [ ] **Step 1: 创建前端项目**

```powershell
cd external-training-app
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install react-router lucide-react
```

- [ ] **Step 2: 配置 Tailwind 和 Vite proxy**

修改 `vite.config.ts` 添加 Tailwind 插件和代理：

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
```

在 `src/index.css` 顶部添加：
```css
@import "tailwindcss";
```

- [ ] **Step 3: 验证前端可构建**

```powershell
cd external-training-app/frontend
npm run build
```

Expected: 成功构建

- [ ] **Step 4: Commit**

```bash
git add external-training-app/frontend/
git commit -m "feat(ext-training): add frontend skeleton with Vite, React, Tailwind"
```

---

### Task 6: 前端类型与 API 客户端

**Files:**
- Create: `external-training-app/frontend/src/services/apiClient.ts`
- Create: `external-training-app/frontend/src/types/binding.ts`
- Create: `external-training-app/frontend/src/types/review.ts`
- Create: `external-training-app/frontend/src/services/bindingService.ts`
- Create: `external-training-app/frontend/src/services/reviewService.ts`

- [ ] **Step 1: 创建 API 客户端**

创建 `external-training-app/frontend/src/services/apiClient.ts`:
```typescript
const API_BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body}`);
  }
  return resp.json();
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, data: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(data) });
}
```

- [ ] **Step 2: 创建类型和服务**

创建 `external-training-app/frontend/src/types/binding.ts`:
```typescript
export interface BindingCreateRequest {
  platformBaseUrl: string;
  platformAppId: string;
  platformApiKey: string;
}

export interface BindingResponse {
  id: string;
  platformBaseUrl: string;
  platformAppId: string;
  status: string;
  createdAt: string;
}
```

创建 `external-training-app/frontend/src/types/review.ts`:
```typescript
export interface ReviewTask {
  id: string;
  platformDraftId: string | null;
  platformPlanId: string | null;
  reviewType: string;
  status: string;
  submittedPayload: Record<string, unknown>;
  createdAt: string;
}

export interface ReviewSubmitRequest {
  decision: "approved" | "rejected";
  notes: string;
  adjustments?: Record<string, unknown>;
}
```

创建 `external-training-app/frontend/src/services/bindingService.ts`:
```typescript
import { apiGet, apiPost } from "./apiClient";
import type { BindingCreateRequest, BindingResponse } from "../types/binding";

export function createBinding(data: BindingCreateRequest): Promise<BindingResponse> {
  return apiPost("/bindings", data);
}

export function listBindings(): Promise<BindingResponse[]> {
  return apiGet("/bindings");
}
```

创建 `external-training-app/frontend/src/services/reviewService.ts`:
```typescript
import { apiGet, apiPost } from "./apiClient";
import type { ReviewTask, ReviewSubmitRequest } from "../types/review";

export function listReviews(reviewType?: string): Promise<ReviewTask[]> {
  const query = reviewType ? `?reviewType=${reviewType}` : "";
  return apiGet(`/reviews${query}`);
}

export function generatePlanDraft(jobTitle: string, jobDescription: string): Promise<unknown> {
  return apiPost(`/reviews/plans/drafts?jobTitle=${encodeURIComponent(jobTitle)}&jobDescription=${encodeURIComponent(jobDescription)}`, {});
}

export function submitReview(taskId: string, data: ReviewSubmitRequest): Promise<unknown> {
  return apiPost(`/reviews/${taskId}/submit`, data);
}
```

- [ ] **Step 3: 验证构建**

```powershell
cd external-training-app/frontend
npm run build
```

Expected: 成功

- [ ] **Step 4: Commit**

```bash
git add external-training-app/frontend/src/
git commit -m "feat(ext-training): add frontend types, API client, and services"
```

---

### Task 7: 前端页面

**Files:**
- Create: `external-training-app/frontend/src/pages/BindingPage.tsx`
- Create: `external-training-app/frontend/src/pages/ReviewPage.tsx`
- Create: `external-training-app/frontend/src/App.tsx`
- Create: `external-training-app/frontend/src/routes.tsx`

- [ ] **Step 1: 创建绑定页面**

创建 `external-training-app/frontend/src/pages/BindingPage.tsx`:
```tsx
import { useState, useEffect } from "react";
import { createBinding, listBindings } from "../services/bindingService";
import type { BindingResponse } from "../types/binding";

export function BindingPage() {
  const [bindings, setBindings] = useState<BindingResponse[]>([]);
  const [form, setForm] = useState({ platformBaseUrl: "", platformAppId: "", platformApiKey: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listBindings().then(setBindings).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await createBinding(form);
      setBindings([result, ...bindings]);
      setForm({ platformBaseUrl: "", platformAppId: "", platformApiKey: "" });
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">平台绑定配置</h1>

      <form onSubmit={handleSubmit} className="space-y-4 mb-8">
        <div>
          <label className="block text-sm font-medium mb-1">平台地址</label>
          <input
            type="text"
            value={form.platformBaseUrl}
            onChange={(e) => setForm({ ...form, platformBaseUrl: e.target.value })}
            className="w-full border rounded px-3 py-2"
            placeholder="http://localhost:8000/api/v1"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">App ID</label>
          <input
            type="text"
            value={form.platformAppId}
            onChange={(e) => setForm({ ...form, platformAppId: e.target.value })}
            className="w-full border rounded px-3 py-2"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">API Key</label>
          <input
            type="password"
            value={form.platformApiKey}
            onChange={(e) => setForm({ ...form, platformApiKey: e.target.value })}
            className="w-full border rounded px-3 py-2"
            required
          />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          {loading ? "保存中..." : "保存绑定"}
        </button>
      </form>

      <h2 className="text-lg font-semibold mb-3">已有绑定</h2>
      {bindings.length === 0 ? (
        <p className="text-gray-500">暂无绑定</p>
      ) : (
        <div className="space-y-2">
          {bindings.map((b) => (
            <div key={b.id} className="border rounded p-3">
              <p className="font-medium">{b.platformBaseUrl}</p>
              <p className="text-sm text-gray-500">App: {b.platformAppId} | 状态: {b.status}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建审核页面**

创建 `external-training-app/frontend/src/pages/ReviewPage.tsx`:
```tsx
import { useState, useEffect } from "react";
import { listReviews, generatePlanDraft, submitReview } from "../services/reviewService";
import type { ReviewTask } from "../types/review";

export function ReviewPage() {
  const [tasks, setTasks] = useState<ReviewTask[]>([]);
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    listReviews("plan").then(setTasks).catch(() => {});
  }, []);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await generatePlanDraft(jobTitle, jobDesc);
      const updated = await listReviews("plan");
      setTasks(updated);
      setJobTitle("");
      setJobDesc("");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(taskId: string, decision: "approved" | "rejected") {
    try {
      await submitReview(taskId, { decision, notes: "" });
      const updated = await listReviews("plan");
      setTasks(updated);
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">学习计划审核</h1>

      <form onSubmit={handleGenerate} className="space-y-4 mb-8 p-4 border rounded">
        <h2 className="text-lg font-semibold">生成学习计划草稿</h2>
        <div>
          <label className="block text-sm font-medium mb-1">岗位名称</label>
          <input
            type="text"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            className="w-full border rounded px-3 py-2"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">岗位描述</label>
          <textarea
            value={jobDesc}
            onChange={(e) => setJobDesc(e.target.value)}
            className="w-full border rounded px-3 py-2 h-24"
            required
          />
        </div>
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          {loading ? "生成中..." : "生成草稿"}
        </button>
      </form>

      <h2 className="text-lg font-semibold mb-3">审核任务列表</h2>
      {tasks.length === 0 ? (
        <p className="text-gray-500">暂无审核任务</p>
      ) : (
        <div className="space-y-4">
          {tasks.map((t) => (
            <div key={t.id} className="border rounded p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <span className="text-sm text-gray-500">{t.reviewType}</span>
                  <span className={`ml-2 px-2 py-0.5 text-xs rounded ${
                    t.status === "pending" ? "bg-yellow-100 text-yellow-800" :
                    t.status === "approved" ? "bg-green-100 text-green-800" :
                    "bg-red-100 text-red-800"
                  }`}>{t.status}</span>
                </div>
                <span className="text-xs text-gray-400">{new Date(t.createdAt).toLocaleString()}</span>
              </div>

              {t.submittedPayload && Object.keys(t.submittedPayload).length > 0 && (
                <pre className="bg-gray-50 p-3 rounded text-sm overflow-auto max-h-48 mb-3">
                  {JSON.stringify(t.submittedPayload, null, 2)}
                </pre>
              )}

              {t.status === "pending" && (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleReview(t.id, "approved")}
                    className="bg-green-600 text-white px-3 py-1 rounded text-sm"
                  >
                    通过
                  </button>
                  <button
                    onClick={() => handleReview(t.id, "rejected")}
                    className="bg-red-600 text-white px-3 py-1 rounded text-sm"
                  >
                    驳回
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 创建路由和 App 入口**

创建 `external-training-app/frontend/src/routes.tsx`:
```tsx
import { createBrowserRouter } from "react-router";
import { BindingPage } from "./pages/BindingPage";
import { ReviewPage } from "./pages/ReviewPage";

export const router = createBrowserRouter([
  { path: "/", element: <ReviewPage /> },
  { path: "/bindings", element: <BindingPage /> },
  { path: "/reviews", element: <ReviewPage /> },
]);
```

修改 `external-training-app/frontend/src/App.tsx`:
```tsx
import { RouterProvider } from "react-router";
import { router } from "./routes";

export default function App() {
  return <RouterProvider router={router} />;
}
```

- [ ] **Step 4: 验证构建**

```powershell
cd external-training-app/frontend
npm run build
```

Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add external-training-app/frontend/src/
git commit -m "feat(ext-training): add binding and review pages with routing"
```

---

### Task 8: 集成验证

- [ ] **Step 1: 后端编译验证**

```powershell
cd external-training-app/backend
python -c "from app.main import app; print('Backend OK')"
```

Expected: `Backend OK`

- [ ] **Step 2: 前端构建验证**

```powershell
cd external-training-app/frontend
npm run build
```

Expected: 成功

- [ ] **Step 3: 验证无 LLM/Embedding 配置**

```powershell
cd external-training-app
grep -r "llm\|embedding\|openai\|anthropic\|provider" --include="*.py" --include="*.ts" --include="*.tsx" -i -l
```

Expected: 无结果（代码中不应有 LLM 相关配置）

- [ ] **Step 4: 更新 Sprint 53 文档**

更新 `docs/04-迭代与交付/sprints/sprint41-60/Sprint-53.md` 的执行记录。

- [ ] **Step 5: Commit**

```bash
git add external-training-app/ docs/
git commit -m "feat(ext-training): verify external training app baseline complete"
```

---

## 完成标准

- [ ] 外部培训应用可独立启动（backend + frontend）
- [ ] 数据库包含 6 张最小表
- [ ] 平台绑定页面可配置平台地址和 App 绑定
- [ ] 学习计划审核页面可展示和提交审核
- [ ] 代码中不存在 LLM Provider、Embedding Provider 配置
- [ ] `npm run build` 和 `python -c "from app.main import app"` 均成功
