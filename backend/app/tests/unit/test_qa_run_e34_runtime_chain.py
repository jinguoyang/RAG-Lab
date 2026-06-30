"""E34 运行链路收口测试。

验证结构化证据、Corrective RAG、parent-child 上下文扩展和答案校验
不再只停留在独立服务层，而是有可被 QA Run 调用的轻量编排函数。
"""

from uuid import uuid4

from app.services.qa_providers import ProviderCandidate
from app.services.qa_run_service import (
    _build_answer_blocks,
    _build_answer_verification_trace,
    _build_corrective_rag_trace,
    _dedupe_candidate_pairs_by_chunk_id,
    _build_structured_evidence_trace,
    _expand_context_pairs_with_chunk_window,
)


def _candidate(content: str, metadata: dict | None = None, chunk_id=None) -> ProviderCandidate:
    return ProviderCandidate(
        source_type="sparse",
        chunk_id=chunk_id or uuid4(),
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


def test_context_pairs_are_deduped_by_chunk_id_before_evidence_generation():
    """同一 Chunk 通过重检索或窗口扩展重复命中时，只能保留一条最终上下文证据。"""
    chunk_id = uuid4()
    first = _candidate("first", {"chunkIndex": 1}, chunk_id=chunk_id)
    duplicate = _candidate("duplicate", {"chunkIndex": 1}, chunk_id=chunk_id)

    deduped = _dedupe_candidate_pairs_by_chunk_id([(first, uuid4()), (duplicate, uuid4())])
    expanded = _expand_context_pairs_with_chunk_window(
        [(first, uuid4()), (duplicate, uuid4())],
        [{"chunk_id": chunk_id, "chunk_index": 1, "content": "same", "metadata": {}}],
        chunk_window=1,
    )

    assert [pair[0].content for pair in deduped] == ["first"]
    assert [pair[0].content for pair in expanded] == ["first"]


def test_answer_verification_trace_degrades_unsupported_answer():
    """答案校验 trace 应在无引用时给出降级动作。"""
    trace = _build_answer_verification_trace("unsupported answer", [], [])

    assert trace["status"] in {"fail", "degraded"}
    assert trace["suggestedAction"] in {"degrade", "refuse", "clarify"}


def test_build_answer_blocks_maps_inline_citations_to_evidence_ids():
    """临时引用编号应映射到稳定 evidenceId，并从最终答案正文中移除。"""
    answer = "杭州 12 号线车辆数为 33 辆。[[1]]\n车辆概况存在不同口径。[[2, 3]]"

    cleaned, blocks = _build_answer_blocks(answer, {1: "ev-1", 2: "ev-2", 3: "ev-3"})

    assert "[[" not in cleaned
    assert cleaned == "杭州 12 号线车辆数为 33 辆。\n车辆概况存在不同口径。"
    assert blocks == [
        {"text": "杭州 12 号线车辆数为 33 辆。", "citationEvidenceIds": ["ev-1"]},
        {"text": "车辆概况存在不同口径。", "citationEvidenceIds": ["ev-2", "ev-3"]},
    ]
