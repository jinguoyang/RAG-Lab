"""验证 QA 证据追溯与 Graph 检索召回修复点。

该脚本做源码级契约检查，避免依赖真实 LLM、Neo4j 或历史运行数据。
"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_context_candidates_are_all_persisted_as_evidence() -> None:
    """LLM 看到的每条上下文候选都应有 Evidence/Citation，避免回答引用悬空。"""
    source = _read("app/services/qa_run_service.py")
    _assert(
        "top_candidate, top_candidate_id = context_pairs[0]" not in source,
        "Citation Builder 不能只持久化第一条上下文候选。",
    )
    _assert(
        "for evidence_order, (candidate, candidate_id) in enumerate(context_pairs, start=1)" in source,
        "Citation Builder 应按 context_pairs 顺序逐条生成 Evidence/Citation。",
    )
    _assert(
        '"evidenceCount": len(context_pairs)' in source and '"citationCount": len(context_pairs)' in source,
        "QARun metrics 应记录真实 Evidence/Citation 数量。",
    )


def verify_graph_retrieval_uses_query_terms() -> None:
    """Graph 检索应从完整问题拆出关键词，不能只用整句做 CONTAINS。"""
    source = _read("app/services/qa_providers.py")
    _assert("def _graph_query_terms" in source, "缺少 Graph 查询关键词提取函数。")
    _assert("$search_terms" in source, "Neo4j Graph 检索 Cypher 应使用关键词列表。")
    _assert("ANY(term IN $search_terms" in source, "Graph retrieve 应按关键词匹配实体、别名或摘要。")


def main() -> None:
    verify_context_candidates_are_all_persisted_as_evidence()
    verify_graph_retrieval_uses_query_terms()
    print("QA traceability fixes verification passed.")


if __name__ == "__main__":
    main()
