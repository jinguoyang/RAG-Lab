"""验证 QA Graph/Rerank Provider 修复点。

该脚本只做源码级契约检查，避免依赖真实 Neo4j / DashScope 服务。
"""

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_graph_query_param_does_not_shadow_driver_argument() -> None:
    """Graph 检索不能把业务查询参数命名为 query，避免撞 Neo4j session.run(query=)。"""
    source = _read("app/services/qa_providers.py")
    _assert("$search_text" in source, "Neo4j Graph 检索 Cypher 应使用 $search_text 参数。")
    _assert("search_text=query" in source, "Graph retrieve 应把业务查询传为 search_text。")
    _assert(
        "graph_snapshot_id=graph_snapshot_id, query=query" not in source,
        "Graph retrieve 不能继续传 query=query，避免 session.run 参数名冲突。",
    )


def verify_rerank_model_and_payload_contract() -> None:
    """HTTP Rerank 应携带模型名，并按 DashScope compatible reranks 契约发请求。"""
    provider_source = _read("app/services/qa_providers.py")
    config_source = _read("app/core/config.py")
    health_source = _read("app/api/routes/health.py")
    env_example = _read(".env.example")

    _assert("rerank_model" in config_source, "Settings 缺少 rerank_model 配置。")
    _assert("RAG_LAB_RERANK_MODEL" in health_source, "健康诊断缺少 RAG_LAB_RERANK_MODEL。")
    _assert("RAG_LAB_RERANK_MODEL" in env_example, ".env.example 缺少 RAG_LAB_RERANK_MODEL。")
    _assert('"model": self._model' in provider_source, "Rerank 请求体应包含 model。")
    _assert('"query": query' in provider_source, "Rerank 请求体应包含 query。")
    _assert('"documents": [candidate.content or "" for candidate in candidates]' in provider_source, "Rerank 请求体应包含 documents。")
    _assert('"top_n": limit' in provider_source, "Rerank 请求体应包含 top_n。")
    _assert(
        "https://dashscope.aliyuncs.com/compatible-api/v1/reranks" in env_example,
        ".env.example 应给出 DashScope compatible reranks endpoint。",
    )


def main() -> None:
    verify_graph_query_param_does_not_shadow_driver_argument()
    verify_rerank_model_and_payload_contract()
    print("QA provider fixes verification passed.")


if __name__ == "__main__":
    main()
