# RAG App Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V1.8 minimal RAG App Runtime so external Web applications can call a governed RAG App through App API Key and every answer remains traceable to QARun.

**Architecture:** Add a thin application runtime layer above the existing QARun service. RAG App, API Key, Conversation, Message and Invocation records live in PostgreSQL; runtime calls reuse existing QA orchestration, permission filtering, Evidence, Citation and Trace.

**Tech Stack:** FastAPI, SQLAlchemy Core tables, PostgreSQL/Alembic migrations, existing QARun providers, React/Vite if the management page is included in the same implementation pass.

---

### Task 1: Data Model And Migration

**Files:**
- Modify: `backend/app/tables.py`
- Create: `backend/migrations/versions/0014_create_rag_app_runtime_tables.py`
- Test: FastAPI TestClient 接口抽样、`python -m compileall app`、`scripts/export_openapi.py`

- [ ] Add `rag_apps`, `rag_app_api_keys`, `app_conversations`, `app_messages` and `app_invocations` tables using `snake_case` fields from `docs/03-系统设计/数据模型设计.md`.
- [ ] Add Alembic migration with indexes for `rag_apps(kb_id, status, created_at)`, `rag_app_api_keys(key_hash)`, `app_conversations(app_id, end_user_id, updated_at)`, `app_messages(conversation_id, created_at)`, `app_invocations(app_id, status, created_at)` and `app_invocations(qa_run_id)`.
- [ ] Run `conda run -n rag-lab python -m compileall app` and confirm no import or table definition errors.

### Task 2: RAG App Management Service

**Files:**
- Create: `backend/app/schemas/rag_app.py`
- Create: `backend/app/services/rag_app_service.py`
- Create: `backend/app/api/routes/rag_apps.py`
- Modify: `backend/app/api/router.py`

- [ ] Implement DTOs for app create/update/detail, API Key create/revoke/list and invocation list.
- [ ] Implement service functions that validate KB visibility and `kb.app.manage` or `kb.manage` before app/key changes.
- [ ] Hash API Keys before persistence; return plaintext only from the create-key response.
- [ ] Register `/api/v1/rag-apps` routes and export them through the existing API router.

### Task 3: App Runtime Blocking Chat

**Files:**
- Create: `backend/app/schemas/app_runtime.py`
- Create: `backend/app/services/app_runtime_service.py`
- Create: `backend/app/api/routes/app_runtime.py`
- Modify: `backend/app/api/router.py`

- [ ] Implement App API Key authentication from `Authorization: Bearer <app_api_key>`.
- [ ] Resolve the App, KB and runnable ConfigRevision; reject disabled app/key/KB and missing runnable revision with stable business errors.
- [ ] Create or reuse `app_conversations`, write user `app_messages`, call existing QARun creation/execution path, then write assistant `app_messages` and `app_invocations`.
- [ ] Return `answer`, `conversationId`, `messageId`, `runId`, `citations`, `usage` and safe `metadata`; do not expose full Trace or filtered candidate content.

### Task 4: Verification

**Files:**
- Modify: `docs/06-发布与运维/openapi.json` only if OpenAPI export is part of the implementation pass.

- [ ] Use FastAPI TestClient or local interface calls to verify successful blocking chat creates an App Conversation, two App Messages, one Invocation and one linked QARun.
- [ ] Use FastAPI TestClient or local interface calls to verify invalid/revoked API Key returns `APP_API_KEY_INVALID`.
- [ ] Use FastAPI TestClient or local interface calls to verify disabled App returns `RAG_APP_DISABLED`.
- [ ] Use FastAPI TestClient or local interface calls to verify missing runnable revision returns `RAG_APP_NO_RUNNABLE_REVISION`.
- [ ] Use FastAPI TestClient or local interface calls to verify external response citations only come from authorized Evidence.
- [ ] Run `conda run -n rag-lab python scripts/export_openapi.py`.
- [ ] Run `git diff --check`.

### Task 5: Optional Management UI

**Files:**
- Create or modify frontend files under `frontend/src/app/pages/` and `frontend/src/app/services/` only if B-138 is included in the same sprint execution.

- [ ] Add a P13 RAG App management route following existing page/service/adapter patterns.
- [ ] Support app list, create/update, API Key create/revoke and invocation summary.
- [ ] Run `npm run build` from `frontend/`.
