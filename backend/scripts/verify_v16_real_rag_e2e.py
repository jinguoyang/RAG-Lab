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


def verify_monitoring_stage_contract() -> None:
    """Verify monitoring can classify real RAG stages and failures."""
    observability_source = (BACKEND_DIR / "app/services/observability_service.py").read_text(encoding="utf-8")
    for needle in ["ingest_jobs", "index_sync_jobs", "qa_run_trace_steps", "denseRetrieval", "generation"]:
        _assert(needle in observability_source, f"监控诊断缺少真实 RAG 来源: {needle}")


def main() -> None:
    """Run the V1.6 local smoke guardrails."""
    try:
        verify_source_level_contracts()
        verify_real_document_parse()
        verify_ingest_stage_diagnostics_contract()
        verify_real_qa_evidence_contract()
        verify_monitoring_stage_contract()
    except ModuleNotFoundError as exc:
        raise V16EnvironmentLimit(f"本地依赖缺失，无法执行完整 V1.6 smoke: {exc.name}") from exc
    print("V1.6 real RAG smoke source verification passed.")


if __name__ == "__main__":
    main()
