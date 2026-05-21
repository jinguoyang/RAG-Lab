# Sprint 42 三层架构前端体验改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Sprint 42 — refactor frontend pages to surface three-layer architecture concepts (Document Library, Knowledge Base, Smart App) with version management, deletion impact analysis, evidence traceability, permission sources, and Runtime status.

**Architecture:** Backend adds 4 API extensions (deletion-impact endpoint, evidence metadata, app KB status, permission sources). Frontend modifies 5 existing pages (P16, P06, P10, P12, P13) using existing component patterns (ConfirmDialog, StatusBadge, Drawer, Alert). Implementation order: backend first, then frontend pages sequentially.

**Tech Stack:** Python/FastAPI (backend), React 18 + TypeScript + Vite + Tailwind CSS 4 + shadcn/ui (frontend)

---

## File Structure

### Backend (new/modified)
- Modify: `backend/app/api/routes/library.py` — add deletion-impact endpoint
- Modify: `backend/app/schemas/qa_run.py` — extend QARunEvidenceDTO with metadata fields
- Modify: `backend/app/schemas/rag_app.py` — extend RagAppDTO with KB status fields
- Modify: `backend/app/services/qa_run_service.py` — join evidence with chunk/document metadata
- Modify: `backend/app/services/rag_app_service.py` — join app with KB status
- Modify: `backend/app/api/routes/rag_apps.py` — pass KB status through

### Frontend (modified)
- Modify: `frontend/src/app/types/library.ts` — add DeletionImpactAnalysis, ParseRevisionDTO
- Modify: `frontend/src/app/types/qaRun.ts` — extend QARunEvidenceDTO with metadata
- Modify: `frontend/src/app/types/ragApp.ts` — extend RagAppDTO with KB status
- Modify: `frontend/src/app/services/libraryService.ts` — add getDeletionImpact
- Modify: `frontend/src/app/services/ragAppService.ts` — (no change needed, DTO flows through)
- Modify: `frontend/src/app/pages/P16_LibraryDetail.tsx` — B-209
- Modify: `frontend/src/app/pages/P06_DocumentCenter.tsx` — B-210
- Modify: `frontend/src/app/pages/P10_QAHistory.tsx` — B-211
- Modify: `frontend/src/app/pages/P12_MembersAndPermissions.tsx` — B-212
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx` — B-213

---

## Task 1: Backend — Deletion Impact Analysis Endpoint

**Files:**
- Modify: `backend/app/api/routes/library.py`

- [ ] **Step 1: Add the deletion-impact GET endpoint**

In `backend/app/api/routes/library.py`, add a new endpoint before the existing `delete_version` endpoint (around line 330). Import `analyze_document_version_deletion_impact` from `document_service` and `DeletionImpactAnalysis` from schemas:

```python
@router.get("/{document_id}/versions/{version_id}/deletion-impact", response_model=DeletionImpactAnalysis)
def get_deletion_impact(
    document_id: UUID,
    version_id: UUID,
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db_session)],
) -> DeletionImpactAnalysis:
    """获取删除文档版本的影响分析。"""
    try:
        # Verify the version belongs to the document
        version = db.execute(
            select(document_versions).where(
                document_versions.c.version_id == version_id,
                document_versions.c.document_id == document_id,
            )
        ).first()
        if not version is None:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        result = analyze_document_version_deletion_impact(db, version_id)
        return DeletionImpactAnalysis(**result)
    except Exception as exc:
        _raise_library_error(exc)
        raise  # unreachable
```

Add required imports at the top of the file:
```python
from app.services.document_service import analyze_document_version_deletion_impact
from app.schemas.document import DeletionImpactAnalysis
from app.tables import document_versions
from sqlalchemy import select
```

- [ ] **Step 2: Verify the endpoint compiles**

Run:
```powershell
cd backend
conda run -n rag-lab python -m compileall app/api/routes/library.py
```
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routes/library.py
git commit -m "feat: add deletion-impact analysis GET endpoint for library versions"
```

---

## Task 2: Backend — Extend QARunEvidenceDTO with Metadata

**Files:**
- Modify: `backend/app/schemas/qa_run.py`
- Modify: `backend/app/services/qa_run_service.py`

- [ ] **Step 1: Extend QARunEvidenceDTO schema**

In `backend/app/schemas/qa_run.py`, find the `QARunEvidenceDTO` class and add metadata fields:

```python
class QARunEvidenceDTO(BaseModel):
    """授权 Evidence 摘要，后续会与真实 Chunk 权限二次校验衔接。"""

    evidenceId: str
    chunkId: str
    candidateId: str | None
    contentSnapshot: str | None
    sourceSnapshot: dict[str, Any]
    redactionStatus: str
    # Sprint 42: traceability metadata
    sourceStatus: str = "available"  # "available" | "source_deleted"
    documentName: str | None = None
    versionNo: int | None = None
    pageNo: int | None = None
    sectionPath: str | None = None
    chunkStatus: str | None = None  # "active" | "retired" | "deleted"
```

- [ ] **Step 2: Extend evidence query in service layer**

In `backend/app/services/qa_run_service.py`, find where `QARunEvidenceDTO` instances are constructed (in the `get_qa_run_detail` function or similar). After fetching evidence rows, join with chunks, document_versions, and documents tables to populate the new fields:

```python
# After fetching evidence rows, enrich with metadata
if evidence_rows:
    chunk_ids = [e["chunk_id"] for e in evidence_rows]
    chunk_meta = session.execute(
        select(
            chunks.c.chunk_id,
            chunks.c.status.label("chunk_status"),
            chunks.c.page_no,
            chunks.c.section_path,
            chunks.c.document_version_id,
            document_versions.c.version_no,
            documents.c.name.label("document_name"),
        )
        .join(document_versions, chunks.c.document_version_id == document_versions.c.version_id)
        .join(documents, chunks.c.document_id == documents.c.document_id)
        .where(chunks.c.chunk_id.in_(chunk_ids))
    ).all()
    chunk_meta_map = {str(row.chunk_id): row for row in chunk_meta}

    # Also fetch source_status from qa_run_evidence
    evidence_status_map = {
        str(e["evidence_id"]): e.get("source_status", "available")
        for e in evidence_rows
    }
```

Then when constructing DTOs, populate the new fields from `chunk_meta_map` and `evidence_status_map`.

- [ ] **Step 3: Verify compilation**

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/qa_run.py backend/app/services/qa_run_service.py
git commit -m "feat: extend QARunEvidenceDTO with traceability metadata for Sprint 42"
```

---

## Task 3: Backend — Extend RagAppDTO with KB Status

**Files:**
- Modify: `backend/app/schemas/rag_app.py`
- Modify: `backend/app/services/rag_app_service.py`

- [ ] **Step 1: Extend RagAppDTO schema**

In `backend/app/schemas/rag_app.py`, add KB status fields to `RagAppDTO`:

```python
class RagAppDTO(BaseModel):
    """RAG App 管理端摘要，接口层统一使用 camelCase 字段。"""

    appId: str
    kbId: str
    defaultConfigRevisionId: str | None = None
    name: str
    description: str | None = None
    status: str
    outputPolicy: dict[str, Any]
    metadata: dict[str, Any]
    createdAt: str
    updatedAt: str
    # Sprint 42: KB status fields
    knowledgeBaseName: str | None = None
    knowledgeBaseStatus: str | None = None  # "active" | "disabled" | "deleted"
```

- [ ] **Step 2: Populate KB status in service layer**

In `backend/app/services/rag_app_service.py`, find the `get_rag_app` function. After fetching the app row, join with knowledge_bases to get KB name and status:

```python
# After fetching the app row
kb_row = session.execute(
    select(
        knowledge_bases.c.name,
        knowledge_bases.c.status,
    ).where(knowledge_bases.c.knowledge_base_id == app_row.kb_id)
).first()

# When constructing RagAppDTO, include:
# knowledgeBaseName=kb_row.name if kb_row else None
# knowledgeBaseStatus=kb_row.status if kb_row else None
```

Also apply the same enrichment to `list_rag_apps` if it returns `RagAppDTO` objects.

- [ ] **Step 3: Verify compilation**

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/rag_app.py backend/app/services/rag_app_service.py
git commit -m "feat: extend RagAppDTO with knowledgeBaseName and knowledgeBaseStatus"
```

---

## Task 4: Frontend Types — Add New Types for Sprint 42

**Files:**
- Modify: `frontend/src/app/types/library.ts`
- Modify: `frontend/src/app/types/qaRun.ts`
- Modify: `frontend/src/app/types/ragApp.ts`

- [ ] **Step 1: Add DeletionImpactAnalysis and ParseRevisionDTO to library types**

In `frontend/src/app/types/library.ts`, add at the end:

```typescript
export interface DeletionImpactAnalysis {
  canDelete: boolean;
  blockingReasons: string[];
  isActiveVersion: boolean;
  activeBindingCount: number;
  pendingJobsCount: number;
  qaEvidenceCount: number;
  qaCitationCount: number;
  requiresStrongConfirmation: boolean;
}

export interface ParseRevisionDTO {
  parseRevisionId: string;
  documentVersionId: string;
  status: "pending" | "running" | "success" | "failed";
  parserName: string | null;
  createdAt: string;
}
```

Also extend `LibraryDocumentVersionDTO` with an optional `parseRevisions` field:

```typescript
export interface LibraryDocumentVersionDTO {
  versionId: string;
  documentId: string;
  versionNo: number;
  sourceFileId: string;
  fileName?: string;
  fileSize?: number;
  status: string;
  parseStatus: "pending" | "running" | "success" | "failed";
  chunkCount: number;
  tokenCount: number | null;
  createdAt: string;
  updatedAt: string;
  // Sprint 42: ParseRevision list
  parseRevisions?: ParseRevisionDTO[];
}
```

- [ ] **Step 2: Extend QARunEvidenceDTO in qaRun types**

In `frontend/src/app/types/qaRun.ts`, find the evidence interface (likely named `QARunEvidenceDTO` or similar) and add:

```typescript
  // Sprint 42: traceability metadata
  sourceStatus?: string;  // "available" | "source_deleted"
  documentName?: string | null;
  versionNo?: number | null;
  pageNo?: number | null;
  sectionPath?: string | null;
  chunkStatus?: string | null;
```

- [ ] **Step 3: Extend RagAppDTO in ragApp types**

In `frontend/src/app/types/ragApp.ts`, add to `RagAppDTO`:

```typescript
  // Sprint 42: KB status
  knowledgeBaseName?: string | null;
  knowledgeBaseStatus?: string | null;
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/types/library.ts frontend/src/app/types/qaRun.ts frontend/src/app/types/ragApp.ts
git commit -m "feat: extend frontend types for Sprint 42 three-layer architecture"
```

---

## Task 5: Frontend Service — Add getDeletionImpact

**Files:**
- Modify: `frontend/src/app/services/libraryService.ts`

- [ ] **Step 1: Add the getDeletionImpact function**

In `frontend/src/app/services/libraryService.ts`, add after the `deleteLibraryVersion` function:

```typescript
export async function getDeletionImpact(
  documentId: string,
  versionId: string,
): Promise<DeletionImpactAnalysis> {
  return apiGet<DeletionImpactAnalysis>(`/library/documents/${documentId}/versions/${versionId}/deletion-impact`);
}
```

Add the import for `DeletionImpactAnalysis` from the types.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/app/services/libraryService.ts
git commit -m "feat: add getDeletionImpact API call to libraryService"
```

---

## Task 6: B-209 — Library Detail Deletion Impact and ParseRevision Status

**Files:**
- Modify: `frontend/src/app/pages/P16_LibraryDetail.tsx`

- [ ] **Step 1: Add deletion impact state and handler**

In `P16_LibraryDetail.tsx`, add new state variables after the existing upload state (around line 79):

```typescript
// Deletion impact state
const [deletionImpact, setDeletionImpact] = useState<import("../types/library").DeletionImpactAnalysis | null>(null);
const [impactLoading, setImpactLoading] = useState(false);
const [strongConfirmChecked, setStrongConfirmChecked] = useState(false);
```

Import `getDeletionImpact` from `../services/libraryService`.

- [ ] **Step 2: Replace handleDeleteVersion with impact-aware version**

Replace the existing `handleDeleteVersion` function (lines 179-201) with:

```typescript
async function handleDeleteVersion(versionId: string, versionNo: number) {
  setImpactLoading(true);
  setStrongConfirmChecked(false);
  try {
    const impact = await getDeletionImpact(docId, versionId);
    setDeletionImpact(impact);

    if (!impact.canDelete) {
      // Show blocking reasons in a dialog
      await confirm({
        title: `无法删除 v${versionNo}`,
        description: impact.blockingReasons.join("\n"),
        confirmText: "知道了",
      });
      setDeletionImpact(null);
      return;
    }

    // Build description with impact details
    const lines: string[] = [];
    if (impact.isActiveVersion) lines.push("- 该版本是当前活跃版本");
    if (impact.activeBindingCount > 0) lines.push(`- 支撑 ${impact.activeBindingCount} 个知识库的 active 绑定`);
    if (impact.pendingJobsCount > 0) lines.push(`- 存在 ${impact.pendingJobsCount} 个运行中任务`);
    if (impact.qaEvidenceCount > 0) lines.push(`- 被 ${impact.qaEvidenceCount} 条 QA 历史证据引用`);
    if (impact.requiresStrongConfirmation) {
      lines.push("");
      lines.push("删除后，相关 QA 历史的证据将显示「引用文件已被清理」。");
    }

    const description = lines.length > 0
      ? `确定要删除 v${versionNo} 吗？\n\n影响分析：\n${lines.join("\n")}`
      : `确定要删除 v${versionNo} 吗？此操作不可撤销。`;

    // Use the detail field for the impact info, and show checkbox if needed
    const detail = impact.requiresStrongConfirmation ? (
      <div className="space-y-3">
        <div className="text-sm text-near-black whitespace-pre-line">{description}</div>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={strongConfirmChecked}
            onChange={(e) => setStrongConfirmChecked(e.target.checked)}
            className="mt-0.5"
          />
          <span>我确认清理该文档版本，并接受相关 QA 历史证据不可回放。</span>
        </label>
      </div>
    ) : undefined;

    const confirmed = await confirm({
      title: `删除版本 v${versionNo}`,
      description: impact.requiresStrongConfirmation ? undefined : description,
      detail,
      confirmText: "确认删除",
      destructive: true,
    });

    if (!confirmed) {
      setDeletionImpact(null);
      return;
    }

    // If strong confirmation required, check the checkbox
    if (impact.requiresStrongConfirmation && !strongConfirmChecked) {
      setFeedback({ variant: "warning", title: "请确认", message: "请先勾选确认选项。" });
      setDeletionImpact(null);
      return;
    }
  } catch (error) {
    setFeedback({ variant: "error", title: "获取影响分析失败", message: error instanceof Error ? error.message : "请稍后重试。" });
    setDeletionImpact(null);
    return;
  } finally {
    setImpactLoading(false);
  }

  try {
    await deleteLibraryVersion(docId, versionId);
    setFeedback({ variant: "success", title: "删除成功", message: `v${versionNo} 已删除。` });
    setDeletionImpact(null);
    await loadData();
  } catch (error) {
    const msg = error instanceof Error ? error.message : "请稍后重试。";
    if (msg.includes("VERSION_IN_USE")) {
      setFeedback({ variant: "warning", title: "无法删除", message: "该版本正在被知识库绑定引用，请先在知识库中切换版本或解绑。" });
    } else if (msg.includes("VERSION_IS_ACTIVE")) {
      setFeedback({ variant: "warning", title: "无法删除", message: "不能删除当前活跃版本，请先切换到其他版本。" });
    } else {
      setFeedback({ variant: "error", title: "删除失败", message: msg });
    }
  }
}
```

Note: The `confirm` function from `useConfirmDialog` currently doesn't support a `detail` prop with JSX. We need to extend the ConfirmDialog to support this. Check if the existing `ConfirmDialogOptions` interface already has a `detail?: ReactNode` field — it does (confirmed in the code read). So we can pass JSX to `detail`.

However, the current `confirm` handler doesn't support the `detail` prop being a ReactNode that includes interactive elements (checkbox). We need a different approach: use a Drawer instead for the impact analysis.

**Revised approach:** Use a Drawer for the deletion impact analysis instead of ConfirmDialog, since we need interactive elements (checkbox).

Replace the approach with a Drawer-based flow:

```typescript
// Add state for deletion drawer
const [deleteDrawer, setDeleteDrawer] = useState<{ versionId: string; versionNo: number } | null>(null);
```

And create a Drawer component in the JSX that shows the impact analysis with a checkbox.

- [ ] **Step 3: Add ParseRevision status to version list**

In the versions table (around line 393-434), add a row below each version showing ParseRevision status. Modify the table to include ParseRevision info:

After the existing `<TableCell>` for parseStatus, add a new cell that shows ParseRevision details if available:

```typescript
<TableCell>
  <div className="flex items-center gap-1.5">
    <Badge variant={parseStatusVariant(v.parseStatus)}>{v.parseStatus}</Badge>
    {v.parseRevisions && v.parseRevisions.length > 0 && (
      <span className="text-xs text-stone-gray" title={v.parseRevisions.map(pr => `${pr.parserName}: ${pr.status}`).join(", ")}>
        ({v.parseRevisions.length} 解析版本)
      </span>
    )}
  </div>
</TableCell>
```

- [ ] **Step 4: Add duplicate file warning to upload drawer**

In the upload Drawer (around line 439-472), after the file input, add a duplicate check. When a file is selected, compute its hash (or use the upload response to detect duplicates). Since the backend returns duplicate info in the upload response, add a post-upload feedback:

The existing upload handler already shows feedback. Enhance it to check for duplicate info in the response:

```typescript
// In handleVersionUpload, after successful upload:
const result = await promise;
if (result.isDuplicate) {
  setFeedback({
    variant: "warning",
    title: "重复文件提醒",
    message: `该文件与版本 v${result.duplicateVersionNo} 内容相同。`,
  });
} else {
  setFeedback({ variant: "success", title: "上传成功", message: "版本文件已上传，解析任务已创建。" });
}
```

Note: This requires the backend upload response to include `isDuplicate` and `duplicateVersionNo` fields. If not already present, this step can be deferred — the backend Sprint 41 B-202 already implemented hash duplicate detection, but the response schema may need extension.

- [ ] **Step 5: Verify frontend builds**

```powershell
cd frontend
npm run lint
npm run build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/P16_LibraryDetail.tsx
git commit -m "feat(B-209): add deletion impact analysis, ParseRevision status, and duplicate warning to library detail"
```

---

## Task 7: B-210 — Knowledge Base Document Center Version Picker

**Files:**
- Modify: `frontend/src/app/pages/P06_DocumentCenter.tsx`

- [ ] **Step 1: Add version picker state**

In `P06_DocumentCenter.tsx`, add new state variables after the existing binding state (around line 84):

```typescript
// Version picker state for binding
const [versionPickerDoc, setVersionPickerDoc] = useState<LibraryDocumentDTO | null>(null);
const [versionPickerVersions, setVersionPickerVersions] = useState<LibraryDocumentVersionDTO[]>([]);
const [versionPickerLoading, setVersionPickerLoading] = useState(false);
const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);

// Binding version switch state
const [switchTarget, setSwitchTarget] = useState<{ bindingId: string; documentName: string } | null>(null);
const [switchVersions, setSwitchVersions] = useState<LibraryDocumentVersionDTO[]>([]);
const [switchLoading, setSwitchLoading] = useState(false);
```

Import `fetchLibraryVersions` and `switchBindingVersion` from `../services/libraryService`, and `LibraryDocumentVersionDTO` from `../types/library`.

- [ ] **Step 2: Modify handleBind to use version selection**

Replace the existing `handleBind` function (around line 331-355). Instead of binding directly, open a version picker for each selected document:

```typescript
async function handleBindWithVersion() {
  if (selectedDocIds.length === 0) {
    setFeedback({ variant: "warning", title: "请选择文档", message: "请至少选择一个文档库文档。" });
    return;
  }

  // For single document, open version picker directly
  if (selectedDocIds.length === 1) {
    const doc = libraryDocs.find(d => d.documentId === selectedDocIds[0]);
    if (doc) {
      await openVersionPicker(doc);
    }
    return;
  }

  // For multiple documents, bind directly (use active version)
  setBindingLoading(true);
  try {
    const result = await bindDocumentsToKB(kbId, selectedDocIds);
    setFeedback({
      variant: "success",
      title: "绑定成功",
      message: `已绑定 ${result.bindings.length} 个文档到当前知识库。`,
    });
    setShowLibraryPicker(false);
    await loadData(searchTerm, 1);
  } catch (error) {
    setFeedback({
      variant: "error",
      title: "绑定失败",
      message: error instanceof Error ? error.message : "请稍后重试。",
    });
  } finally {
    setBindingLoading(false);
  }
}

async function openVersionPicker(doc: LibraryDocumentDTO) {
  setVersionPickerDoc(doc);
  setVersionPickerLoading(true);
  setSelectedVersionId(null);
  try {
    const versions = await fetchLibraryVersions(doc.documentId);
    setVersionPickerVersions(versions.filter(v => v.parseStatus === "success"));
  } catch {
    setVersionPickerVersions([]);
  } finally {
    setVersionPickerLoading(false);
  }
}

async function handleBindWithSelectedVersion() {
  if (!versionPickerDoc || !selectedVersionId) return;
  setBindingLoading(true);
  try {
    const result = await bindDocumentsToKB(kbId, [versionPickerDoc.documentId]);
    // Note: bindDocumentsToKB currently doesn't accept versionId.
    // If the backend supports it, pass selectedVersionId.
    // Otherwise, this needs backend extension.
    setFeedback({
      variant: "success",
      title: "绑定成功",
      message: `已绑定文档到当前知识库。`,
    });
    setVersionPickerDoc(null);
    setShowLibraryPicker(false);
    await loadData(searchTerm, 1);
  } catch (error) {
    setFeedback({
      variant: "error",
      title: "绑定失败",
      message: error instanceof Error ? error.message : "请稍后重试。",
    });
  } finally {
    setBindingLoading(false);
  }
}
```

- [ ] **Step 3: Add version picker Drawer in JSX**

After the existing library picker modal (around line 700+), add a version picker Drawer:

```typescript
{/* 版本选择 Drawer */}
{versionPickerDoc && (
  <Drawer title={`选择版本 — ${versionPickerDoc.name}`} onClose={() => setVersionPickerDoc(null)}>
    <DrawerSection>
      {versionPickerLoading ? (
        <p className="text-stone-gray text-sm">加载中...</p>
      ) : versionPickerVersions.length === 0 ? (
        <p className="text-stone-gray text-sm">没有可用的已解析版本</p>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-stone-gray">选择要绑定到知识库的版本：</p>
          {versionPickerVersions.map((v) => (
            <div
              key={v.versionId}
              className={`rounded-lg border p-4 flex items-center justify-between gap-4 cursor-pointer transition-colors ${
                selectedVersionId === v.versionId
                  ? "border-terracotta bg-terracotta/5"
                  : "border-border-cream bg-parchment hover:border-terracotta"
              }`}
              onClick={() => setSelectedVersionId(v.versionId)}
            >
              <div>
                <p className="font-medium text-near-black">v{v.versionNo}</p>
                <p className="text-xs text-stone-gray mt-1">{v.fileName ?? "-"} | 分块数: {v.chunkCount}</p>
              </div>
              <Badge variant={v.parseStatus === "success" ? "success" : v.parseStatus === "failed" ? "error" : "queued"}>
                {v.parseStatus}
              </Badge>
            </div>
          ))}
          <div className="flex gap-2 justify-end pt-2">
            <Button variant="secondary" onClick={() => setVersionPickerDoc(null)}>取消</Button>
            <Button
              variant="primary"
              disabled={!selectedVersionId || bindingLoading}
              onClick={() => void handleBindWithSelectedVersion()}
            >
              {bindingLoading ? "绑定中..." : "确认绑定"}
            </Button>
          </div>
        </div>
      )}
    </DrawerSection>
  </Drawer>
)}
```

- [ ] **Step 4: Add BindingRevision status to document list**

In the document list table, find the status column and enhance it to show BindingRevision status. The existing `toDocumentRow` adapter maps document data — we need to check if binding info is available. If the document list API returns binding status, display it:

```typescript
// In the table row, after the existing status badge:
{row.bindingRevisionStatus && (
  <Badge
    variant={
      row.bindingRevisionStatus === "active" ? "success" :
      row.bindingRevisionStatus === "building" ? "running" :
      row.bindingRevisionStatus === "failed" ? "error" :
      "default"
    }
    className="ml-2"
  >
    {row.bindingRevisionStatus === "active" ? "已激活" :
     row.bindingRevisionStatus === "building" ? "构建中" :
     row.bindingRevisionStatus === "failed" ? "构建失败" :
     row.bindingRevisionStatus === "retired" ? "已退役" :
     row.bindingRevisionStatus}
  </Badge>
)}
```

Note: This requires the document list API to return `bindingRevisionStatus`. If not available, this step can be deferred or added via the binding list API.

- [ ] **Step 5: Add switch-version handler for bound documents**

Add a handler for switching binding versions, similar to the one in P16:

```typescript
async function handleSwitchBindingVersion(bindingId: string, targetVersionId: string, versionNo: number) {
  const ok = await confirm({
    title: "切换绑定版本",
    description: `确定要切换到 v${versionNo} 吗？知识库将重新构建索引。`,
    confirmText: "确认切换",
  });
  if (!ok) return;

  try {
    await switchBindingVersion(kbId, bindingId, targetVersionId);
    setFeedback({ variant: "success", title: "切换成功", message: `绑定已切换到 v${versionNo}。` });
    setSwitchTarget(null);
    await loadData(searchTerm, pageNo);
  } catch (error) {
    setFeedback({ variant: "error", title: "切换失败", message: error instanceof Error ? error.message : "请稍后重试。" });
  }
}
```

- [ ] **Step 6: Verify frontend builds**

```powershell
cd frontend
npm run lint
npm run build
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/pages/P06_DocumentCenter.tsx
git commit -m "feat(B-210): add version picker for binding and BindingRevision status to document center"
```

---

## Task 8: B-211 — QA History Evidence Traceability

**Files:**
- Modify: `frontend/src/app/pages/P10_QAHistory.tsx`

- [ ] **Step 1: Enhance evidence display in the detail Drawer**

In `P10_QAHistory.tsx`, find the evidence section (around line 768-778) where evidence items are displayed. Replace the simple chunkId + contentSnapshot display with a traceability-aware version:

```typescript
<DrawerSection title="Trace 与 Evidence">
  <div className="space-y-3">
    <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm text-stone-gray">
      Trace 步骤：{selectedDetail?.trace.length ?? "-"} · Evidence：{selectedDetail?.evidence.length ?? "-"} · Candidate：{selectedDetail?.candidates.length ?? "-"}
    </div>
    {selectedDetail?.evidence.slice(0, 5).map((evidence) => (
      <div key={evidence.evidenceId} className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
        {evidence.sourceStatus === "source_deleted" ? (
          <div className="flex items-center gap-2">
            <Badge variant="inactive">已清理</Badge>
            <span className="text-stone-gray">引用文件已被清理</span>
          </div>
        ) : (
          <div className="space-y-1.5">
            {/* Traceability chain */}
            <div className="flex items-center gap-2 flex-wrap text-xs">
              {evidence.documentName && (
                <>
                  <Badge variant="info">{evidence.documentName}</Badge>
                  <span className="text-stone-gray">→</span>
                </>
              )}
              {evidence.versionNo != null && (
                <>
                  <Badge variant="default">v{evidence.versionNo}</Badge>
                  <span className="text-stone-gray">→</span>
                </>
              )}
              {evidence.pageNo != null && (
                <Badge variant="default">第 {evidence.pageNo} 页</Badge>
              )}
              {evidence.sectionPath && (
                <Badge variant="default">{evidence.sectionPath}</Badge>
              )}
              {evidence.chunkStatus && evidence.chunkStatus !== "active" && (
                <Badge variant={evidence.chunkStatus === "retired" ? "inactive" : "error"}>
                  {evidence.chunkStatus === "retired" ? "已退役" : "已删除"}
                </Badge>
              )}
            </div>
            {/* Chunk ID */}
            <div className="font-mono text-xs text-stone-gray">{evidence.chunkId}</div>
            {/* Content snapshot */}
            <p className="text-near-black">{evidence.contentSnapshot || "当前证据策略未返回正文快照。"}</p>
          </div>
        )}
      </div>
    ))}
  </div>
</DrawerSection>
```

- [ ] **Step 2: Verify frontend builds**

```powershell
cd frontend
npm run lint
npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/P10_QAHistory.tsx
git commit -m "feat(B-211): add evidence traceability chain and source_deleted display to QA history"
```

---

## Task 9: B-212 — Members and Permissions Three-Layer Display

**Files:**
- Modify: `frontend/src/app/pages/P12_MembersAndPermissions.tsx`

- [ ] **Step 1: Add platform role display to member list**

In `P12_MembersAndPermissions.tsx`, find the member table rows. Add a column or cell for platform role. The member data likely comes from `KbMemberBinding` — check if it includes `platformRole`. If not, we can display it from the user info if available.

Add to the ROLE_LABELS record:

```typescript
const PLATFORM_ROLE_LABELS: Record<string, string> = {
  platform_admin: "平台管理员",
  platform_user: "普通用户",
};
```

In the member table, add a cell for platform role:

```typescript
<TableCell>
  {member.platformRole && (
    <Badge variant={member.platformRole === "platform_admin" ? "warning" : "default"}>
      {PLATFORM_ROLE_LABELS[member.platformRole] ?? member.platformRole}
    </Badge>
  )}
</TableCell>
```

- [ ] **Step 2: Add permission source display**

Enhance the permission summary section to show the source of each permission (direct vs. user group). If the `fetchKbPermissionSummary` API returns source info, display it:

```typescript
// In the permission summary display section
{summary?.permissions.map((perm) => (
  <div key={perm.code} className="flex items-center gap-2">
    <Badge variant="default">{perm.code}</Badge>
    {perm.source === "group" && (
      <span className="text-xs text-stone-gray flex items-center gap-1">
        <Users className="w-3 h-3" /> {perm.groupName ?? "用户组"}
      </span>
    )}
    {perm.source === "direct" && (
      <span className="text-xs text-stone-gray">直接授权</span>
    )}
  </div>
))}
```

Note: This requires the backend permission summary endpoint to return `source` and `groupName` for each permission. If not available, display the existing role-based info and add a note about user group inheritance.

- [ ] **Step 3: Add role group labels**

In the member table, group roles by resource layer. Add visual grouping:

```typescript
{/* Role badges grouped by layer */}
<div className="flex flex-wrap gap-1.5">
  {member.roles?.libraryRole && (
    <Badge variant="info" className="text-xs">
      文档库: {ROLE_LABELS[member.roles.libraryRole] ?? member.roles.libraryRole}
    </Badge>
  )}
  {member.roles?.kbRole && (
    <Badge variant="success" className="text-xs">
      知识库: {ROLE_LABELS[member.roles.kbRole] ?? member.roles.kbRole}
    </Badge>
  )}
  {member.roles?.appRole && (
    <Badge variant="warning" className="text-xs">
      应用: {ROLE_LABELS[member.roles.appRole] ?? member.roles.appRole}
    </Badge>
  )}
</div>
```

Note: This requires the member list API to return roles grouped by layer. If the current API only returns a single role, this step requires backend extension or can be deferred.

- [ ] **Step 4: Verify frontend builds**

```powershell
cd frontend
npm run lint
npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/P12_MembersAndPermissions.tsx
git commit -m "feat(B-212): add three-layer role display and permission source to members page"
```

---

## Task 10: B-213 — Smart App Management KB Status and Runtime Rejection

**Files:**
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx`

- [ ] **Step 1: Add KB status display to app detail overview**

In `P13_RagAppManagement.tsx`, find the app detail overview section. After the existing app info display, add KB status:

```typescript
{/* Knowledge Base Status */}
{selectedAppDetail?.knowledgeBaseName && (
  <div className="rounded-lg border border-border-cream bg-parchment p-3 text-sm">
    <div className="flex items-center justify-between">
      <div>
        <span className="text-stone-gray">所属知识库：</span>
        <span className="text-near-black ml-2">{selectedAppDetail.knowledgeBaseName}</span>
      </div>
      <Badge
        variant={
          selectedAppDetail.knowledgeBaseStatus === "active" ? "success" :
          selectedAppDetail.knowledgeBaseStatus === "disabled" ? "warning" :
          "error"
        }
      >
        {selectedAppDetail.knowledgeBaseStatus === "active" ? "运行中" :
         selectedAppDetail.knowledgeBaseStatus === "disabled" ? "已停用" :
         selectedAppDetail.knowledgeBaseStatus}
      </Badge>
    </div>
    {selectedAppDetail.knowledgeBaseStatus === "disabled" && (
      <Alert variant="warning" title="知识库已停用" className="mt-2">
        Runtime 调用将被拒绝。请先恢复知识库。
      </Alert>
    )}
  </div>
)}
```

- [ ] **Step 2: Add Key availability display**

In the API Key list table, add an "availability" column. After the existing status column:

```typescript
<TableCell>
  {(() => {
    if (key.status === "revoked") return <Badge variant="inactive">已撤销</Badge>;
    if (key.expiresAt && new Date(key.expiresAt) < new Date()) return <Badge variant="inactive">已过期</Badge>;
    if (selectedAppDetail?.status === "disabled") return <Badge variant="warning">应用已停用</Badge>;
    if (selectedAppDetail?.knowledgeBaseStatus === "disabled") return <Badge variant="error">知识库已停用</Badge>;
    return <Badge variant="success">可用</Badge>;
  })()}
</TableCell>
```

- [ ] **Step 3: Add Runtime rejection reason display**

In the test run / trial section, enhance error display to show structured rejection reasons:

```typescript
// Where runtime errors are displayed
{runtimeError && (
  <Alert
    variant="error"
    title={
      runtimeError.includes("KB_DISABLED") ? "知识库已停用" :
      runtimeError.includes("KB_NOT_FOUND") ? "知识库不存在" :
      runtimeError.includes("APP_DISABLED") ? "应用已停用" :
      runtimeError.includes("KEY_EXPIRED") ? "API Key 已过期" :
      "Runtime 调用失败"
    }
  >
    {runtimeError.includes("KB_DISABLED")
      ? "知识库已停用，请先在知识库管理页面恢复知识库状态。"
      : runtimeError.includes("KB_NOT_FOUND")
      ? "知识库不存在或已删除，请检查应用配置。"
      : runtimeError.includes("APP_DISABLED")
      ? "应用已停用，请先启用应用。"
      : runtimeError.includes("KEY_EXPIRED")
      ? "API Key 已过期，请创建新的 Key。"
      : runtimeError}
  </Alert>
)}
```

- [ ] **Step 4: Add KB disabled note to invocation stats**

In the statistics panel, add a note when KB is disabled:

```typescript
{selectedAppDetail?.knowledgeBaseStatus === "disabled" && (
  <Alert variant="warning" title="调用统计受影响" className="mb-4">
    知识库已停用，自停用以来无新调用记录。
  </Alert>
)}
```

- [ ] **Step 5: Verify frontend builds**

```powershell
cd frontend
npm run lint
npm run build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/pages/P13_RagAppManagement.tsx
git commit -m "feat(B-213): add KB status, Key availability, and Runtime rejection reasons to app management"
```

---

## Task 11: Final Verification

- [ ] **Step 1: Run full frontend lint and build**

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

- [ ] **Step 2: Run backend compilation check**

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

- [ ] **Step 3: Check for uncommitted changes**

```powershell
git diff --check
git status
```

- [ ] **Step 4: Final commit if needed**

```bash
git add -A
git commit -m "feat: complete Sprint 42 three-layer frontend experience refactoring"
```
