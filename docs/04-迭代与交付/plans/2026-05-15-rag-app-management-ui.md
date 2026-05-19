# RAG App Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Sprint 31 P13 RAG App management UI so platform users can manage RAG Apps, API Keys, invocation records and conversation summaries from the admin interface.

**Architecture:** Add a thin frontend layer over the Sprint 30 RAG App management APIs. Keep App Runtime execution in the backend; the UI only creates and updates app metadata, manages API Keys, lists invocation summaries and links back to existing QARun detail pages.

**Tech Stack:** React, TypeScript, Vite, existing frontend service/adapter/page patterns, existing backend FastAPI RAG App APIs.

---

## 1. Scope

### In Scope

- P13 RAG App management route and navigation entry.
- App list with knowledge base filter, status filter and keyword search.
- Create/edit app drawer or dialog.
- API Key list, create-key modal with one-time plaintext display, revoke action.
- Invocation list with status/error/latency/request/response summary and QARun link.
- Conversation summary panel using existing app message/invocation data where available; if the backend lacks a dedicated conversation list endpoint, show conversationId grouping from invocation rows only.
- Frontend verification script for API field mapping and route registration.

### Out Of Scope

- SSE streaming.
- Rate limits, quotas or statistics charts.
- External feedback回流.
- Prompt template or input-variable editor.
- Storing or re-displaying API Key plaintext after the create response modal closes.

## 2. Page Prototype

### P13 App List

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ RAG 应用管理                                            [创建应用]            │
│ 将治理后的知识库和配置版本发布为外部可调用应用                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ [知识库筛选 v] [状态: 全部 | 启用 | 停用] [搜索应用名...]          [刷新]     │
├──────────────────────────────────────────────────────────────────────────────┤
│ 应用名称        知识库          默认配置        状态    Key    最近调用  操作 │
│ 客服问答助手    车辆知识库      active v12      启用    2      5分钟前   查看 │
│ 运维检索助手    运维手册        active v8       停用    1      昨天      查看 │
│ 故障分析助手    故障案例库      跟随知识库      启用    0      -         查看 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### P13 Detail

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 客服问答助手                         启用中        [停用应用] [编辑]         │
│ 车辆知识库 / active v12 / appId: 8f2...                                      │
├──────────────────────────────────────────────────────────────────────────────┤
│ [概览] [API Keys] [调用记录] [会话]                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ API Keys                                                     [生成 Key]       │
│ 前缀              状态      过期时间        最近使用        操作             │
│ rlak_xxxxxxxx     active    永不过期        5分钟前         撤销             │
│ rlak_yyyyyyyy     revoked   -               昨天            -                │
├──────────────────────────────────────────────────────────────────────────────┤
│ 调用记录                                                     [状态筛选 v]     │
│ 时间             状态      延迟    conversationId         QARun              │
│ 13:45:12         success   823ms   62a...                 打开详情           │
│ 13:42:01         failed    12ms    -                      RAG_APP_DISABLED   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 3. File Map

- Create: `frontend/src/app/types/ragApp.ts`
  - RAG App DTO, API Key DTO, invocation DTO and request types.
- Create: `frontend/src/app/adapters/ragAppAdapter.ts`
  - Convert backend camelCase DTOs into view models with display labels.
- Create: `frontend/src/app/services/ragAppService.ts`
  - Call `/api/v1/rag-apps`, `/api-keys`, `/revoke`, `/invocations`.
- Create: `frontend/src/app/pages/P13_RagAppManagement.tsx`
  - Main page, list/detail tabs, create/edit/key dialogs.
- Modify: `frontend/src/app/routes.tsx`
  - Register P13 route.
- Modify: `frontend/src/app/layouts/PlatformLayout.tsx`
  - Add navigation entry if platform-level nav is defined there.
- Create: `frontend/scripts/verify_rag_app_management_ui.mjs`
  - Static verification for route, service methods and one-time key display guard.

## 4. Tasks

### Task 1: Types And Service Contract

**Files:**
- Create: `frontend/src/app/types/ragApp.ts`
- Create: `frontend/src/app/services/ragAppService.ts`
- Test: `frontend/scripts/verify_rag_app_management_ui.mjs`

- [ ] Add TypeScript DTOs matching OpenAPI field names: `RagAppDTO`, `RagAppApiKeyDTO`, `RagAppApiKeyCreateResponse`, `AppInvocationDTO`.
- [ ] Add request types: `RagAppCreateRequest`, `RagAppUpdateRequest`, `RagAppApiKeyCreateRequest`.
- [ ] Implement service methods:
  - `listRagApps(params)`
  - `createRagApp(payload)`
  - `updateRagApp(appId, payload)`
  - `listRagAppApiKeys(appId)`
  - `createRagAppApiKey(appId, payload)`
  - `revokeRagAppApiKey(appId, apiKeyId)`
  - `listRagAppInvocations(appId, params)`
- [ ] Verify every method uses existing `apiClient` and does not store API Key plaintext outside the create response promise.

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
node scripts/verify_rag_app_management_ui.mjs
```

Expected: route check may fail until Task 3, service export checks pass after this task.

### Task 2: View Models And Display Rules

**Files:**
- Create: `frontend/src/app/adapters/ragAppAdapter.ts`
- Modify: `frontend/scripts/verify_rag_app_management_ui.mjs`

- [ ] Convert `status` values to display labels: `active -> 启用`, `disabled -> 停用`, `archived -> 已归档`, `revoked -> 已撤销`.
- [ ] Convert missing `defaultConfigRevisionId` to `跟随知识库 active revision`.
- [ ] Convert invocation status and error codes to concise display text without hiding raw code.
- [ ] Add tests in the verification script for status label conversion and default revision display.

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
node scripts/verify_rag_app_management_ui.mjs
```

Expected: adapter checks pass.

### Task 3: P13 Route And Navigation

**Files:**
- Create: `frontend/src/app/pages/P13_RagAppManagement.tsx`
- Modify: `frontend/src/app/routes.tsx`
- Modify: `frontend/src/app/layouts/PlatformLayout.tsx`
- Modify: `frontend/scripts/verify_rag_app_management_ui.mjs`

- [ ] Add `/rag-apps` or the existing platform route equivalent for P13.
- [ ] Add a navigation entry named `RAG 应用`.
- [ ] Implement initial page shell with header, filters, app table, loading state, empty state and error state.
- [ ] Use existing shared `PageHeader`, `Button`, `Badge`, `Table`, `Drawer` or local equivalents already present in the project.
- [ ] Keep the page operational and dense; avoid a marketing-style hero page.

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

Expected: build succeeds.

### Task 4: App Create/Edit Flow

**Files:**
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx`
- Modify: `frontend/src/app/services/ragAppService.ts` if service gaps are found

- [ ] Add create app dialog/drawer with fields: name, description, kbId, defaultConfigRevisionId, status display.
- [ ] Add edit app dialog/drawer with fields: name, description, defaultConfigRevisionId, outputPolicy metadata placeholder only if already returned by API.
- [ ] Refresh list after create/update.
- [ ] Show backend conflict errors directly enough for diagnosis, e.g. `RAG_APP_NO_RUNNABLE_REVISION`.
- [ ] Do not create new backend fields or config options for UI convenience.

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

Expected: build succeeds.

### Task 5: API Key Management Flow

**Files:**
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx`

- [ ] Add API Key tab/table for selected app.
- [ ] Add create-key action.
- [ ] Show plaintext key only in a modal that appears immediately after create success.
- [ ] Clear plaintext key from component state when modal closes.
- [ ] Add revoke confirmation before calling revoke endpoint.
- [ ] Refresh key list after revoke.

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
node scripts/verify_rag_app_management_ui.mjs
npm run build
```

Expected: verification confirms no persistent plaintext key list binding; build succeeds.

### Task 6: Invocation And Conversation Visibility

**Files:**
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx`
- Modify: `frontend/src/app/adapters/ragAppAdapter.ts`

- [ ] Add invocation tab/table with status, errorCode, latencyMs, requestSummary, responseSummary, conversationId, messageId and qaRunId.
- [ ] Add status filter for `success` and `failed`.
- [ ] Add QARun link using existing QA history/detail route pattern.
- [ ] Add conversation tab that groups invocation rows by `conversationId` as a temporary summary when there is no dedicated conversation endpoint.
- [ ] Clearly show that full Trace remains in QARun detail.

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

Expected: build succeeds and P13 has all tabs.

### Task 7: Final Verification And Docs

**Files:**
- Modify: `docs/04-迭代与交付/产品待办清单.md`
- Modify: `docs/04-迭代与交付/sprints/sprint21-40/Sprint-31.md`
- Modify: `docs/04-迭代与交付/sprints/README.md`

- [ ] Run frontend build.
- [ ] Run backend compileall.
- [ ] Run App Runtime smoke.
- [ ] Run `git diff --check`.
- [ ] Update B-138 and B-143 to `Done` only after verification passes.
- [ ] Add Sprint 31 execution record with exact commands and result.

Commands:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
node scripts/verify_rag_app_management_ui.mjs
npm run build

cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python scripts/verify_app_runtime_smoke.py

cd C:\Users\Public\Documents\Code\jin\rag-lab
git diff --check
```

Expected: all commands pass or any environment blocker is recorded in Sprint 31.

## 5. Self-Review

- Spec coverage: covers B-138 and B-143; explicitly excludes B-139, B-140, B-141 and B-144.
- Placeholder scan: no TBD/TODO placeholders are used as implementation instructions.
- Type consistency: frontend DTO names follow existing camelCase API fields and planned service method names stay consistent across tasks.
