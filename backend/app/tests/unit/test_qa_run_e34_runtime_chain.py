"""E34 运行链路收口测试。

验证结构化证据、Corrective RAG、parent-child 上下文扩展和答案校验
不再只停留在独立服务层，而是有可被 QA Run 调用的轻量编排函数。
"""

from uuid import uuid4

from app.services.qa_providers import ProviderCandidate
from app.services.qa_run_service import (
    _build_answer_verification_trace,
    _build_corrective_rag_trace,
    _build_structured_evidence_trace,
    _expand_context_pairs_with_chunk_window,
)


def _candidate(content: str, metadata: dict | None = None) -> ProviderCandidate:
    return ProviderCandidate(
        source_type="sparse",
        chunk_id=uuid4(),
        raw_score=0.9,
        content=content,
        metadata=metadata or {},
    )


def test_structured_evidence_trace_counts_table_and_flowchart_candidates():
    """结构化证据 trace 应能识别表格和流程图候选。"""
    candidates = [
        _candidate("table", {"blockType": "table"}),
        _candidate("flow", {"evidenceType": "flowchart"}),
        _candidate("text", {"blockType": "paragraph"}),
    ]

    trace = _build_structured_evidence_trace(candidates)

    assert trace["structuredEvidenceCount"] == 2
    assert trace["tableCount"] == 1
    assert trace["flowchartCount"] == 1


def test_corrective_rag_trace_returns_controlled_action():
    """Corrective RAG trace 应返回受控动作和证据质量摘要。"""
    trace = _build_corrective_rag_trace([], "unknown policy", current_round=2, max_rounds=2)

    assert trace["action"] == "answer_insufficient"
    assert trace["maxRounds"] == 2
    assert trace["assessment"]["overallSufficiency"] == 0


def test_chunk_window_expands_neighbor_rows_after_authorization():
    """chunkWindow 应在权限过滤后扩展相邻上下文，不改变原始检索证据。"""
    base = _candidate("hit", {"chunkIndex": 2})
    base_id = uuid4()
    rows = [
        {"chunk_id": uuid4(), "chunk_index": 1, "content": "before", "metadata": {"section": "A"}},
        {"chunk_id": uuid4(), "chunk_index": 3, "content": "after", "metadata": {"section": "A"}},
    ]

    expanded = _expand_context_pairs_with_chunk_window([(base, base_id)], rows, chunk_window=1)

    assert len(expanded) == 3
    assert expanded[0][0] is base
    assert expanded[1][0].metadata["expandedContext"] is True
    assert expanded[1][0].metadata["expandedFromChunkId"] == str(base.chunk_id)


def test_answer_verification_trace_degrades_unsupported_answer():
    """答案校验 trace 应在无引用时给出降级动作。"""
    trace = _build_answer_verification_trace("unsupported answer", [], [])

    assert trace["status"] in {"fail", "degraded"}
    assert trace["suggestedAction"] in {"degrade", "refuse", "clarify"}
