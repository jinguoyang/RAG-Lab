# V1.6 Real RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a V1.6 verification-first path that proves one real document can be parsed, indexed, queried, monitored, replayed, and compared without silently falling back to mock success.

**Architecture:** Reuse the existing FastAPI service layer and Provider abstractions. PostgreSQL remains the business truth for documents, chunks, permissions, QA runs, evidence, citations, and trace; Milvus, OpenSearch, and Neo4j remain rebuildable retrieval copies. The V1.6 script becomes the single smoke entry and classifies failures as code gaps, missing local dependencies, or external Provider environment limits.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy Core, existing document and QA services, React 18, Vite, TypeScript, PowerShell/Conda verification commands.

---

## File Structure

- Create: `backend/scripts/verify_v16_real_rag_e2e.py` as the V1.6 end-to-end smoke verification entry.
- Modify: `backend/app/services/document_service.py` only if the verification shows ingest does not expose enough stage diagnostics.
- Modify: `backend/app/services/qa_run_service.py` only if the verification shows QA trace, replay, or comparison is missing real-document context.
- Modify: `backend/app/services/observability_service.py` only if diagnostics cannot classify parse, index, retrieval, generation, and replay failures.
- Modify: `frontend/src/app/types/document.ts`, `frontend/src/app/types/qaRun.ts`, `frontend/src/app/adapters/documentAdapter.ts`, and `frontend/src/app/adapters/qaRunAdapter.ts` only when API DTOs already expose data but the UI model drops it.
- Modify: `frontend/src/app/pages/P06_DocumentCenter.tsx`, `frontend/src/app/pages/P07_DocumentDetail.tsx`, `frontend/src/app/pages/P09_QADebug.tsx`, and `frontend/src/app/pages/P10_QAHistory.tsx` only for missing real-chain status or failure reason visibility.
- Modify: `docs/06-发布与运维/发布验收与运维手册.md` to record V1.6 smoke commands and Provider environment result categories.
- Modify: `docs/04-迭代与交付/产品待办清单.md` and Sprint docs after each backlog is completed.

## Task 1: B-101 / B-107 V1.6 Smoke Verification Harness

**Files:**
- Create: `backend/scripts/verify_v16_real_rag_e2e.py`
- Modify: `docs/04-迭代与交付/sprints/sprint21-40/Sprint-23.md`
- Modify: `docs/04-迭代与交付/sprints/sprint21-40/Sprint-24.md`

- [ ] **Step 1: Create the failing verification script**

Create `backend/scripts/verify_v16_real_rag_e2e.py`:

```python
"""V1.6 real RAG end-to-end smoke verification.

The script checks that a real example document can flow through ingest,
retrieval QA, monitoring trace, and replay comparison. It reports environment
limits separately from implementation gaps so local development does not hide
real Provider failures behind mock success.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
EXAMPLE_DIR = ROOT_DIR / "docs" / "examples"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class V16CodeGap(AssertionError):
    """Raised when the code path is missing a V1.6 requirement."""


class V16EnvironmentLimit(RuntimeError):
    """Raised when external Provider or local dependency limits block a true smoke run."""


@dataclass(frozen=True)
class SmokeDocument:
    """Real sample document used by the V1.6 smoke verification."""

    path: Path
    query: str


def _assert(condition: bool, message: str) -> None:
    """Fail with an implementation-gap label to keep smoke output actionable."""
    if not condition:
        raise V16CodeGap(message)


def _select_smoke_document() -> SmokeDocument:
    """Pick one stable example document and pair it with a deterministic query."""
    candidates = sorted(EXAMPLE_DIR.glob("*.txt")) + sorted(EXAMPLE_DIR.glob("*.md")) + sorted(EXAMPLE_DIR.glob("*.pdf"))
    _assert(bool(candidates), "docs/examples 缺少可用于 V1.6 smoke 的真实文档")
    return SmokeDocument(path=candidates[0], query="这份文档的核心管理要求是什么？")


def verify_source_level_contracts() -> None:
    """Check that the existing code still exposes the stages needed by V1.6."""
    service_source = (BACKEND_DIR / "app/services/qa_run_service.py").read_text(encoding="utf-8")
    document_source = (BACKEND_DIR / "app/services/document_service.py").read_text(encoding="utf-8")
    for needle in [
        '"queryRewrite"',
        '"denseRetrieval"',
        '"sparseRetrieval"',
        '"graphRetrieval"',
        '"permissionFilter"',
        '"generation"',
        '"citation"',
        "get_qa_run_replay_context",
        "_compare_trace_rows",
    ]:
        _assert(needle in service_source, f"QA 链路缺少 V1.6 所需片段: {needle}")
    for needle in ["parse_document(", "_run_index_sync_job(", ".upsert_chunks(", "INDEX_SYNC_FAILED"]:
        _assert(needle in document_source, f"入库链路缺少 V1.6 所需片段: {needle}")


def verify_real_document_parse() -> None:
    """Verify that the selected smoke document parses into real chunks."""
    from app.services.document_parsing import parse_document

    smoke = _select_smoke_document()
    parsed = parse_document(smoke.path.name, None, smoke.path.read_bytes(), chunk_size=700, chunk_overlap=80)
    _assert(parsed.chunks, "真实样例文档未生成 Chunk")
    _assert(parsed.parser_name != "placeholder", "真实样例文档仍使用占位解析器")
    _assert(all(chunk.content.strip() for chunk in parsed.chunks), "真实样例文档生成了空 Chunk")
    _assert(any(chunk.page_no is not None or chunk.section for chunk in parsed.chunks), "Chunk 缺少页码或章节定位信息")


def main() -> None:
    """Run the V1.6 local smoke guardrails."""
    try:
        verify_source_level_contracts()
        verify_real_document_parse()
    except ModuleNotFoundError as exc:
        raise V16EnvironmentLimit(f"本地依赖缺失，无法执行完整 V1.6 smoke: {exc.name}") from exc
    print("V1.6 real RAG smoke source verification passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script and confirm the current failure or pass condition**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
```

Expected:

- PASS with `V1.6 real RAG smoke source verification passed.`, or
- FAIL with `V16CodeGap` if a required implementation path is missing, or
- FAIL with `V16EnvironmentLimit` if the local `rag-lab` environment lacks dependencies.

- [ ] **Step 3: Record the first smoke result**

In `docs/04-迭代与交付/sprints/sprint21-40/Sprint-23.md`, add a short completion note only after the script result is known:

```markdown
## 8. 执行记录

- V1.6 smoke 初始结果：记录 `conda run -n rag-lab python scripts/verify_v16_real_rag_e2e.py` 的退出码、首个错误类型和最后一行输出。
```

- [ ] **Step 4: Commit**

```powershell
git add backend/scripts/verify_v16_real_rag_e2e.py docs/04-迭代与交付/sprints/sprint21-40/Sprint-23.md docs/04-迭代与交付/sprints/sprint21-40/Sprint-24.md
git commit -m "test: add v1.6 real rag smoke verification"
```

## Task 2: B-102 Real Ingest Path Closure

**Files:**
- Modify: `backend/app/services/document_service.py`
- Modify: `backend/scripts/verify_v16_real_rag_e2e.py`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Extend the verification for ingest stage diagnostics**

Add this function to `backend/scripts/verify_v16_real_rag_e2e.py`:

```python
def verify_ingest_stage_diagnostics_contract() -> None:
    """Verify ingest jobs expose parse, embedding, and index-copy stage outcomes."""
    document_source = (BACKEND_DIR / "app/services/document_service.py").read_text(encoding="utf-8")
    for needle in [
        '"parse"',
        '"embedding"',
        '"milvus"',
        '"opensearch"',
        '"neo4j"',
        "dense_index_status",
        "sparse_index_status",
        "graph_index_status",
        "error_summary",
    ]:
        _assert(needle in document_source, f"入库诊断缺少字段或阶段: {needle}")
```

Call it from `main()` after `verify_real_document_parse()`.

- [ ] **Step 2: Run verification to classify the gap**

Run:

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
```

Expected: FAIL if stage diagnostics are missing, otherwise PASS.

- [ ] **Step 3: Implement the minimal diagnostic fix if needed**

If the script reports missing stage fields, update `backend/app/services/document_service.py` so ingest and index sync errors are summarized using existing status fields. Keep the shape small:

```python
stage_summary = {
    "parse": {"status": "completed", "error": None},
    "embedding": {"status": embedding_status, "error": embedding_error},
    "milvus": {"status": dense_status, "error": dense_error},
    "opensearch": {"status": sparse_status, "error": sparse_error},
    "neo4j": {"status": graph_status, "error": graph_error},
}
```

Store the summary in the existing metadata or error summary field already used by ingest jobs; do not add a new table unless the current schema cannot store it.

- [ ] **Step 4: Run verification and compile**

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
conda run -n rag-lab python -m compileall app
```

Expected: both commands exit 0.

- [ ] **Step 5: Update backlog and commit B-102**

Change `B-102` status from `Ready` to `Done` only after verification passes.

```powershell
git add backend/app/services/document_service.py backend/scripts/verify_v16_real_rag_e2e.py docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: close v1.6 real ingest smoke path"
```

## Task 3: B-103 Real Document QA Closure

**Files:**
- Modify: `backend/app/services/qa_run_service.py`
- Modify: `backend/scripts/verify_v16_real_rag_e2e.py`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Extend verification for real-document QA evidence**

Add this function:

```python
def verify_real_qa_evidence_contract() -> None:
    """Verify QA evidence is grounded in PostgreSQL chunks and not mock fallback."""
    service_source = (BACKEND_DIR / "app/services/qa_run_service.py").read_text(encoding="utf-8")
    for forbidden in ["MOCK_EVIDENCE_CHUNK_ID", "fallbackEvidence", "postgresChunkFallback"]:
        _assert(forbidden not in service_source, f"QA 仍保留 mock/fallback 成功路径: {forbidden}")
    for needle in [
        '"truthSource": "postgres_chunks"',
        "chunk_access_filters",
        "drop_reason=",
        '"documentId"',
        '"versionId"',
        '"chunkId"',
        '"pageNo"',
        '"section"',
    ]:
        _assert(needle in service_source, f"真实 QA Evidence/Citation 缺少片段: {needle}")
```

Call it from `main()`.

- [ ] **Step 2: Run verification**

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
```

Expected: PASS or a precise missing field message.

- [ ] **Step 3: Patch only the missing QA evidence fields**

If a field is missing, update evidence or citation construction in `backend/app/services/qa_run_service.py` so every Evidence source snapshot contains:

```python
source_snapshot = {
    "truthSource": "postgres_chunks",
    "documentId": str(chunk_row["document_id"]),
    "versionId": str(chunk_row["version_id"]),
    "chunkId": str(chunk_row["chunk_id"]),
    "pageNo": chunk_row["page_no"],
    "section": chunk_row["section"],
}
```

Do not bypass `chunk_access_filters`; missing evidence should fail or return no authorized evidence instead of fabricating context.

- [ ] **Step 4: Run verification and compile**

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
conda run -n rag-lab python -m compileall app
```

- [ ] **Step 5: Update backlog and commit B-103**

```powershell
git add backend/app/services/qa_run_service.py backend/scripts/verify_v16_real_rag_e2e.py docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: ground v1.6 qa evidence in real document chunks"
```

## Task 4: B-104 Monitoring Diagnostics

**Files:**
- Modify: `backend/app/services/observability_service.py`
- Modify: `backend/scripts/verify_v16_real_rag_e2e.py`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Add diagnostics verification**

Add:

```python
def verify_monitoring_stage_contract() -> None:
    """Verify monitoring can classify real RAG stages and failures."""
    observability_source = (BACKEND_DIR / "app/services/observability_service.py").read_text(encoding="utf-8")
    for needle in ["ingest_jobs", "index_sync_jobs", "qa_run_trace_steps", "denseRetrieval", "generation"]:
        _assert(needle in observability_source, f"监控诊断缺少真实 RAG 来源: {needle}")
```

- [ ] **Step 2: Run verification**

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
```

- [ ] **Step 3: Patch diagnostics only if missing**

If missing, extend the existing diagnostic response to include these source categories:

```python
stage_categories = {
    "parse": "document_processing",
    "embedding": "indexing",
    "denseRetrieval": "retrieval",
    "sparseRetrieval": "retrieval",
    "graphRetrieval": "retrieval",
    "generation": "llm",
    "citation": "answering",
}
```

Use existing DTO fields where possible; do not introduce a new observability table.

- [ ] **Step 4: Verify and commit B-104**

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
conda run -n rag-lab python -m compileall app
git add backend/app/services/observability_service.py backend/scripts/verify_v16_real_rag_e2e.py docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: expose v1.6 real rag monitoring diagnostics"
```

## Task 5: B-105 Replay And Comparison For Real Runs

**Files:**
- Modify: `backend/app/services/qa_run_service.py`
- Modify: `backend/scripts/verify_v16_real_rag_e2e.py`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Add replay comparison verification**

Add:

```python
def verify_replay_comparison_contract() -> None:
    """Verify replay preserves context and comparison includes trace and evidence deltas."""
    source = (BACKEND_DIR / "app/services/qa_run_service.py").read_text(encoding="utf-8")
    for needle in [
        "get_qa_run_replay_context",
        "sourceRunId",
        "retrievalChannels",
        "retrievalTopK",
        "graphSnapshotId",
        "traceDelta",
        "evidenceDelta",
        "citationDelta",
        "configDiff",
    ]:
        _assert(needle in source, f"回放对比缺少字段或逻辑: {needle}")
```

- [ ] **Step 2: Run verification**

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
```

- [ ] **Step 3: Patch replay fields only if needed**

If the replay context lacks real-run fields, update `_build_replay_context_snapshot()` so the snapshot contains:

```python
snapshot = {
    "retrievalChannels": retrieval_channels,
    "retrievalTopK": retrieval_top_k,
    "temperature": temperature,
    "maxContextTokens": max_context_tokens,
    "graphSnapshotId": graph_snapshot_id,
    "diagnostics": diagnostics,
}
```

Do not copy historical authorization results; replay must trigger a new QARun.

- [ ] **Step 4: Verify and commit B-105**

```powershell
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
conda run -n rag-lab python -m compileall app
git add backend/app/services/qa_run_service.py backend/scripts/verify_v16_real_rag_e2e.py docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: harden v1.6 real run replay comparison"
```

## Task 6: B-106 Frontend Real Chain Visibility

**Files:**
- Modify: `frontend/src/app/types/document.ts`
- Modify: `frontend/src/app/types/qaRun.ts`
- Modify: `frontend/src/app/adapters/documentAdapter.ts`
- Modify: `frontend/src/app/adapters/qaRunAdapter.ts`
- Modify: `frontend/src/app/pages/P06_DocumentCenter.tsx`
- Modify: `frontend/src/app/pages/P07_DocumentDetail.tsx`
- Modify: `frontend/src/app/pages/P09_QADebug.tsx`
- Modify: `frontend/src/app/pages/P10_QAHistory.tsx`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Add source-level frontend verification to the V1.6 script**

Add:

```python
def verify_frontend_real_chain_visibility() -> None:
    """Verify frontend pages expose real-chain status instead of hiding failures."""
    frontend_dir = ROOT_DIR / "frontend" / "src" / "app"
    checks = {
        "pages/P06_DocumentCenter.tsx": ["indexStages", "失败"],
        "pages/P07_DocumentDetail.tsx": ["indexStages", "Chunk"],
        "pages/P09_QADebug.tsx": ["Trace", "Evidence"],
        "pages/P10_QAHistory.tsx": ["Trace 差异", "Citation"],
    }
    for relative_path, needles in checks.items():
        source = (frontend_dir / relative_path).read_text(encoding="utf-8")
        for needle in needles:
            _assert(needle in source, f"{relative_path} 缺少真实链路展示: {needle}")
```

- [ ] **Step 2: Run frontend verification and build**

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
cd ..\frontend
npm run build
```

- [ ] **Step 3: Patch only missing view model fields or page sections**

If a page lacks status visibility, add compact display of existing DTO fields. Prefer existing components and avoid large layout rewrites.

- [ ] **Step 4: Verify and commit B-106**

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
git add frontend/src/app/types/document.ts frontend/src/app/types/qaRun.ts frontend/src/app/adapters/documentAdapter.ts frontend/src/app/adapters/qaRunAdapter.ts frontend/src/app/pages/P06_DocumentCenter.tsx frontend/src/app/pages/P07_DocumentDetail.tsx frontend/src/app/pages/P09_QADebug.tsx frontend/src/app/pages/P10_QAHistory.tsx backend/scripts/verify_v16_real_rag_e2e.py docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: show v1.6 real rag chain status"
```

## Task 7: B-108 Provider Retest Documentation

**Files:**
- Modify: `docs/06-发布与运维/发布验收与运维手册.md`
- Modify: `docs/04-迭代与交付/releases/V1.6-真实RAG闭环规划.md`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Add V1.6 retest section**

In `docs/06-发布与运维/发布验收与运维手册.md`, add:

```markdown
## V1.6 真实 RAG 复测

- 验收命令：`conda run -n rag-lab python scripts/verify_v16_real_rag_e2e.py`
- 通过：真实样例文档完成解析、索引、QA、引用、回放和对比。
- 代码缺口：脚本输出 `V16CodeGap`，必须修复后重跑。
- 环境限制：脚本输出 `V16EnvironmentLimit`，必须记录缺失依赖、Provider、网络或凭据。
- 禁止事项：不得把真实 Provider 失败替换为 mock/local 成功并标记验收通过。
```

- [ ] **Step 2: Run markdown consistency search**

```powershell
rg -n "V1.6|B-108|verify_v16_real_rag_e2e" docs
```

Expected: release, sprint, backlog, and operation docs all reference the V1.6 smoke entry consistently.

- [ ] **Step 3: Commit B-108**

```powershell
git add docs/06-发布与运维/发布验收与运维手册.md docs/04-迭代与交付/releases/V1.6-真实RAG闭环规划.md docs/04-迭代与交付/产品待办清单.md
git commit -m "docs: add v1.6 real rag provider retest notes"
```

## Task 8: Final V1.6 Verification And Status Closure

**Files:**
- Modify: `docs/04-迭代与交付/产品待办清单.md`
- Modify: `docs/04-迭代与交付/sprints/sprint21-40/Sprint-23.md`
- Modify: `docs/04-迭代与交付/sprints/sprint21-40/Sprint-24.md`
- Modify: `docs/04-迭代与交付/releases/V1.6-真实RAG闭环规划.md`

- [ ] **Step 1: Run full V1.6 verification**

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py
cd ..\frontend
npm run build
cd ..
git diff --check
```

Expected: all commands exit 0, except a documented `V16EnvironmentLimit` may remain only if true external Provider infrastructure is unavailable and the release doc records it.

- [ ] **Step 2: Update statuses**

Only after verification:

- Change `B-101` to `B-108` from `Ready` to `Done`.
- Change `S23-*` and `S24-*` from `Todo` to `Done`.
- Change V1.6 release status from `规划中` to `已完成` in `docs/04-迭代与交付/releases/README.md`.

- [ ] **Step 3: Commit final closure**

```powershell
git add docs/04-迭代与交付/产品待办清单.md docs/04-迭代与交付/sprints/sprint21-40/Sprint-23.md docs/04-迭代与交付/sprints/sprint21-40/Sprint-24.md docs/04-迭代与交付/releases/README.md docs/04-迭代与交付/releases/V1.6-真实RAG闭环规划.md
git commit -m "docs: close v1.6 real rag plan status"
```
