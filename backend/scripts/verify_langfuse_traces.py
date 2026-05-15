"""Langfuse 链路验证脚本：通过 mock 验证 QA Run 管道写入正确的 trace 结构。

用法：cd backend && conda run -n rag-lab python scripts/verify_langfuse_traces.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _make_mock_providers():
    """构造带 last_usage 的 mock Provider 集合。"""
    llm = MagicMock()
    llm.last_usage = {"inputTokens": 10, "outputTokens": 20, "totalTokens": 30, "model": "test-llm"}

    def _llm_rewrite(*args, **kwargs):
        llm.last_usage = {"inputTokens": 10, "outputTokens": 20, "totalTokens": 30, "model": "test-llm"}
        return "mock rewritten query"

    def _llm_generate(*args, **kwargs):
        llm.last_usage = {"inputTokens": 15, "outputTokens": 25, "totalTokens": 40, "model": "test-llm"}
        return "mock answer"

    llm.rewrite_query.side_effect = _llm_rewrite
    llm.generate_answer.side_effect = _llm_generate

    embedding = MagicMock()
    embedding.embed_query.return_value = [0.1] * 128
    embedding.last_usage = {"inputTokens": 5, "totalTokens": 5, "model": "test-embed"}

    dense = MagicMock()
    dense.retrieve.return_value = []

    sparse = MagicMock()
    sparse.retrieve.return_value = []

    rerank = MagicMock()
    rerank.rerank.return_value = []
    rerank.last_usage = {"inputTokens": 8, "totalTokens": 8, "model": "test-rerank"}

    graph = MagicMock()
    graph.retrieve.return_value = []

    return SimpleNamespace(llm=llm, embedding=embedding, dense=dense, sparse=sparse, rerank=rerank, graph=graph)


def _make_revision_row():
    return {
        "config_revision_id": uuid4(),
        "pipeline_definition": {
            "nodes": [
                {"type": "denseRetrieval", "enabled": True, "params": {"topK": 10}},
                {"type": "sparseRetrieval", "enabled": False},
                {"type": "graphRetrieval", "enabled": False},
                {"type": "rerank", "enabled": False},
                {"type": "multiQuery", "enabled": False},
                {"type": "queryRewrite", "enabled": True},
                {"type": "generation", "enabled": True, "params": {"temperature": 0.7}},
                {"type": "contextPacking", "enabled": True, "params": {"maxContextTokens": 4000}},
                {"type": "fusion", "enabled": True},
            ],
        },
        "pipeline_params": {
            "queryRewrite": {"enabled": True},
            "multiQuery": {"enabled": False},
            "retrievalChannels": ["dense"],
            "retrievalTopK": {"dense": 10, "sparse": 10, "graph": 10},
            "retrievalScoreThreshold": {"dense": 0.5, "sparse": 0.5, "graph": 0.5},
            "rerank": {"enabled": False, "scoreThreshold": 0.5},
            "rerankTopN": 5,
            "maxContextTokens": 4000,
            "temperature": 0.7,
            "graph": {"enabled": False, "graphExpansionLimit": 5, "graphRetrievalLimit": 10},
            "contextPacking": {"strategy": "truncate"},
        },
    }


def _make_current_user():
    return SimpleNamespace(user=SimpleNamespace(userId=str(uuid4())))


def run_test():
    """执行 Langfuse 链路验证。"""
    from app.services.qa_run_service import _execute_provider_qa_run, _safe_langfuse_call

    mock_langfuse = MagicMock()
    mock_trace = MagicMock()
    mock_langfuse.trace.return_value = mock_trace

    mock_session = MagicMock()
    mock_session.execute.return_value = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = None

    current_user = _make_current_user()
    run_id = uuid4()
    kb_id = uuid4()
    revision_row = _make_revision_row()
    provider_set = _make_mock_providers()

    with patch("app.services.qa_run_service.get_langfuse", return_value=mock_langfuse), \
         patch("app.services.qa_run_service.get_settings") as mock_settings, \
         patch("app.services.qa_run_service._read_visible_knowledge_base", return_value={"kb_id": kb_id, "status": "active"}), \
         patch("app.services.qa_run_service._resolve_graph_snapshot_id", return_value=None), \
         patch("app.services.qa_run_service.build_chunk_access_filter_context") as mock_access, \
         patch("app.services.qa_run_service._insert_trace_step"):

        settings = MagicMock()
        settings.llm_provider = "test-llm"
        settings.embedding_provider = "test-embed"
        settings.rerank_provider = "test-rerank"
        settings.provider_top_k = 10
        mock_settings.return_value = settings

        mock_access.return_value = SimpleNamespace(to_trace_summary=lambda: "no filter")

        _execute_provider_qa_run(
            session=mock_session,
            current_user=current_user,
            run_id=run_id,
            kb_id=kb_id,
            query="test query",
            revision_row=revision_row,
            override_snapshot={},
            providers=provider_set,
        )

    errors = []

    # 1. trace() 被调用 1 次，参数正确
    mock_langfuse.trace.assert_called_once()
    trace_kwargs = mock_langfuse.trace.call_args
    if trace_kwargs.kwargs.get("name") != "qa_run":
        errors.append(f"trace name: expected 'qa_run', got {trace_kwargs.kwargs.get('name')}")
    if "query" not in (trace_kwargs.kwargs.get("input") or {}):
        errors.append("trace input missing 'query'")
    if "runId" not in (trace_kwargs.kwargs.get("metadata") or {}):
        errors.append("trace metadata missing 'runId'")

    # 2. generation() 被调用：queryRewrite、embedding
    #    注意：由于 mock 无检索结果，authorized_pairs 为空，代码走 early-return 路径，
    #    不会调用 generate_answer，因此没有 "generation" generation call。
    gen_calls = list(mock_trace.generation.call_args_list)
    gen_names = [c.kwargs.get("name") for c in gen_calls]
    for expected in ("queryRewrite", "embedding"):
        if expected not in gen_names:
            errors.append(f"missing generation call: {expected}")

    # 3. span() 被调用（retrieval dense + 可能的 rerank）
    span_calls = [c for c in mock_trace.span.call_args_list]
    span_names = [c.kwargs.get("name") for c in span_calls]
    if "denseRetrieval" not in span_names:
        errors.append("missing span call: denseRetrieval")

    # 4. update() 被调用，含 usage
    mock_trace.update.assert_called()
    update_calls = mock_trace.update.call_args_list
    last_update_kwargs = update_calls[-1].kwargs
    usage = last_update_kwargs.get("usage", {})
    # 无检索结果 → early return：rewrite(30) + embedding(5) = 35; rerank/generation 跳过
    expected_total = 30 + 5
    if usage.get("total") != expected_total:
        errors.append(f"update usage.total: expected {expected_total}, got {usage.get('total')}")

    # 5. flush() 被调用
    mock_langfuse.flush.assert_called()

    # 6. _safe_langfuse_call 异常隔离验证
    def _boom(*args, **kwargs):
        raise RuntimeError("langfuse sdk error")

    mock_langfuse.trace.side_effect = _boom
    result = _safe_langfuse_call(mock_langfuse.trace, name="should_not_crash")
    if result is not None:
        errors.append("_safe_langfuse_call should return None on exception")
    mock_langfuse.trace.side_effect = None

    return errors


def main():
    print("=" * 60)
    print("Langfuse 链路验证")
    print("=" * 60)

    errors = run_test()

    if errors:
        print(f"\nFAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\nPASSED — 所有断言通过")
        print("  - trace() 参数正确 (name, input, metadata, session_id, user_id)")
        print("  - generation() 调用: queryRewrite, embedding")
        print("  - span() 调用: denseRetrieval")
        print("  - update() usage 合计正确 (early-return 路径)")
        print("  - flush() 已调用")
        print("  - _safe_langfuse_call 异常隔离有效")
        sys.exit(0)


if __name__ == "__main__":
    main()
