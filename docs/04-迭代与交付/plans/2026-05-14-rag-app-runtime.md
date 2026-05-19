# RAG App Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V1.8 minimal RAG App Runtime so external Web applications can call a governed RAG App through App API Key and every answer remains traceable to QARun.

**Architecture:** Add a thin application runtime layer above the existing QARun service. RAG App, API Key, Conversation, Message and Invocation records live in PostgreSQL; runtime calls reuse existing QA orchestration, permission filtering, Evidence, Citation and Trace.

**Tech Stack:** FastAPI, SQLAlchemy Core tables, PostgreSQL/Alembic migrations, existing QARun providers, React/Vite if the management page is included in the same implementation pass.

---

## Startup Calibration Decisions

- Existing QARun creation lives in `backend/app/services/qa_run_service.py:create_qa_run` and currently requires a `CurrentUserResponse` with `kb.qa.run`.
- Existing QARun execution lives in `_execute_provider_qa_run` and already performs Provider orchestration, PostgreSQL truth-table authorization, Evidence, Citation, Trace and metrics persistence.
- App Runtime must not call Provider classes directly and must not duplicate QA orchestration.
- App Runtime has no platform login token. The minimal implementation should create an internal app runtime actor from the RagApp owner or creator and still use backend-generated `ChunkAccessFilterContext`; external requests must never provide subject-level chunk filters.
- The first implementation should keep route error handling consistent with the current codebase: use `HTTPException(detail="<stable_code>")` instead of introducing a global response wrapper.
- The next migration should be `backend/migrations/versions/0014_create_rag_app_runtime_tables.py`, with `down_revision = "0013_add_v17_qa_run_snapshots"`.
- Current repository has no `backend/tests` package. Verification should start with a small script or FastAPI TestClient sample under `backend/scripts/` only if the implementation needs repeatable automated checks.

### Task 1: Data Model And Migration

**Files:**
- Modify: `backend/app/tables.py`
- Create: `backend/migrations/versions/0014_create_rag_app_runtime_tables.py`
- Test: FastAPI TestClient 接口抽样、`python -m compileall app`、`scripts/export_openapi.py`

- [ ] Add `rag_apps`, `rag_app_api_keys`, `app_conversations`, `app_messages` and `app_invocations` to `backend/app/tables.py`.
- [ ] Keep DB fields `snake_case`; keep API schemas later in `camelCase`.
- [ ] Add FK constraints to `knowledge_bases`, `config_revisions`, `users`, `qa_runs`, `rag_apps`, `rag_app_api_keys`, `app_conversations` and `app_messages` where the relationship is stable.
- [ ] Add status check constraints:
  - `rag_apps.status IN ('active', 'disabled', 'archived')`
  - `rag_app_api_keys.status IN ('active', 'revoked')`
  - `app_conversations.status IN ('active', 'archived')`
  - `app_messages.role IN ('user', 'assistant')`
  - `app_messages.status IN ('success', 'failed')`
  - `app_invocations.status IN ('success', 'failed')`
- [ ] Add indexes for `rag_apps(kb_id, status, created_at)`, unique `rag_app_api_keys(key_hash)`, `app_conversations(app_id, end_user_id, updated_at)`, `app_messages(conversation_id, created_at)`, `app_invocations(app_id, status, created_at)` and `app_invocations(qa_run_id)`.
- [ ] Run `conda run -n rag-lab python -m compileall app` from `backend/` and confirm no import or table definition errors.

### Task 2: RAG App Management Service

**Files:**
- Create: `backend/app/schemas/rag_app.py`
- Create: `backend/app/services/rag_app_service.py`
- Create: `backend/app/api/routes/rag_apps.py`
- Modify: `backend/app/api/router.py`

- [ ] Implement DTOs for app create/update/detail, API Key create/revoke/list and invocation list.
- [ ] Implement service functions that validate KB visibility and `kb.app.manage` or `kb.manage` before app/key changes.
- [ ] When `kb.app.manage` is not yet seeded for a role in local data, allow `kb.manage` as the initial management permission to avoid blocking Sprint 30 on permission seed work.
- [ ] Generate API Keys with a stable prefix such as `rlak_`; store only `sha256(plaintext_key)` and `key_prefix`.
- [ ] Return plaintext API Key only in the create-key response; list/detail responses must only return `keyPrefix`, status and timestamps.
- [ ] Revoke keys by changing status to `revoked` and setting `revoked_at` / `revoked_by`; do not delete keys.
- [ ] Register `/api/v1/rag-apps` routes in `backend/app/api/router.py`.

### Task 3: QARun Reuse Boundary

**Files:**
- Modify: `backend/app/services/qa_run_service.py`
- Create or modify only if needed: `backend/app/services/app_runtime_service.py`

- [ ] Prefer adding one small internal helper rather than duplicating `_execute_provider_qa_run`.
- [ ] Keep existing platform endpoint behavior unchanged: `POST /api/v1/knowledge-bases/{kbId}/qa-runs` should still call `create_qa_run`.
- [ ] Add a service-level path for App Runtime that can create a QARun for the app-bound KB and revision while preserving QARun snapshots, Evidence, Citation and Trace.
- [ ] Use a backend-created app runtime actor derived from the RagApp creator or owner. Do not accept user/group/ACL subjects from the external request body.
- [ ] Put app context into `override_snapshot` or metadata with safe fields only: `appId`, `conversationId`, `endUserId`, `apiKeyId`.
- [ ] Keep permission filtering inside `build_chunk_access_filter_context` and `_authorize_provider_candidates`; App Runtime must not build custom citation content.

### Task 4: App Runtime Blocking Chat

**Files:**
- Create: `backend/app/schemas/app_runtime.py`
- Create: `backend/app/services/app_runtime_service.py`
- Create: `backend/app/api/routes/app_runtime.py`
- Modify: `backend/app/api/router.py`

- [ ] Implement App API Key authentication from `Authorization: Bearer <app_api_key>`.
- [ ] Resolve the App, KB and runnable ConfigRevision; reject disabled app/key/KB and missing runnable revision with stable business errors.
- [ ] Create or reuse `app_conversations`, write user `app_messages`, call existing QARun creation/execution path, then write assistant `app_messages` and `app_invocations`.
- [ ] For `conversationId`, verify it belongs to the authenticated App before reuse; otherwise return `RESOURCE_NOT_FOUND` or `APP_API_KEY_INVALID` without leaking another App's existence.
- [ ] Persist failed invocations when the App and API Key are known, including `error_code`, latency and safe request summary. Do not persist plaintext API Key.
- [ ] Return `answer`, `conversationId`, assistant `messageId`, `runId`, `citations`, `usage` and safe `metadata`; do not expose full Trace or filtered candidate content.
- [ ] Map stable errors:
  - invalid, expired or revoked key -> `APP_API_KEY_INVALID` with HTTP 401
  - disabled app -> `RAG_APP_DISABLED` with HTTP 409
  - disabled KB -> `KB_DISABLED` with HTTP 409
  - no active or runnable revision -> `RAG_APP_NO_RUNNABLE_REVISION` with HTTP 409
  - no authorized evidence -> reuse `QA_NO_AUTHORIZED_EVIDENCE` where applicable

### Task 5: Verification

**Files:**
- Modify: `docs/06-发布与运维/openapi.json` only if OpenAPI export is part of the implementation pass.
- Create: `backend/scripts/verify_app_runtime_smoke.py` only if repeatable local smoke coverage is needed.

- [ ] Use FastAPI TestClient or local interface calls to verify successful blocking chat creates an App Conversation, two App Messages, one Invocation and one linked QARun.
- [ ] Use FastAPI TestClient or local interface calls to verify invalid/revoked API Key returns `APP_API_KEY_INVALID`.
- [ ] Use FastAPI TestClient or local interface calls to verify disabled App returns `RAG_APP_DISABLED`.
- [ ] Use FastAPI TestClient or local interface calls to verify missing runnable revision returns `RAG_APP_NO_RUNNABLE_REVISION`.
- [ ] Use FastAPI TestClient or local interface calls to verify external response citations only come from authorized Evidence.
- [ ] Run `conda run -n rag-lab python -m compileall app`.
- [ ] Run `conda run -n rag-lab python scripts/export_openapi.py`.
- [ ] Run `git diff --check`.

### Task 6: Optional Management UI

**Files:**
- Create or modify frontend files under `frontend/src/app/pages/` and `frontend/src/app/services/` only if B-138 is included in the same sprint execution.

- [ ] Add a P13 RAG App management route following existing page/service/adapter patterns.
- [ ] Support app list, create/update, API Key create/revoke and invocation summary.
- [ ] Run `npm run build` from `frontend/`.
