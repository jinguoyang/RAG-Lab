from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.services.qa_providers import (
    HttpEmbeddingProvider,
    HttpLlmProvider,
    HttpRerankProvider,
    ProviderCandidate,
)


@dataclass
class ProviderProbeResult:
    """记录单个真实 Provider 网络复测结果，避免在日志中输出凭据。"""

    name: str
    provider: str
    status: str
    latencyMs: int | None
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _run_probe(name: str, provider: str, probe: Callable[[], dict[str, Any]]) -> ProviderProbeResult:
    """执行一次网络探测，并将常见异常归一成发布记录可消费的状态。"""
    started = time.perf_counter()
    try:
        evidence = probe()
    except Exception as exc:  # noqa: BLE001 - 复测脚本需要收敛所有 Provider SDK 异常。
        status, detail = _classify_exception(exc)
        return ProviderProbeResult(
            name=name,
            provider=provider,
            status=status,
            latencyMs=int((time.perf_counter() - started) * 1000),
            detail=detail,
        )
    return ProviderProbeResult(
        name=name,
        provider=provider,
        status="success",
        latencyMs=int((time.perf_counter() - started) * 1000),
        detail="Real provider network probe succeeded.",
        evidence=evidence,
    )


def _blocked(name: str, provider: str, detail: str) -> ProviderProbeResult:
    """生成未发起网络请求的阻塞结果。"""
    return ProviderProbeResult(name=name, provider=provider, status="blocked", latencyMs=None, detail=detail)


def _local_provider(name: str, provider: str) -> ProviderProbeResult:
    """显式标记本地降级 Provider，防止被误读为真实网络复测通过。"""
    return ProviderProbeResult(
        name=name,
        provider=provider,
        status="local_provider",
        latencyMs=None,
        detail="Local or identity provider is configured; no real network probe was executed.",
    )


def _classify_exception(exc: Exception) -> tuple[str, str]:
    """按异常类型和 HTTP 状态粗分类，覆盖超时、鉴权、限流和响应格式异常。"""
    current: BaseException | None = exc
    messages: list[str] = []
    while current is not None:
        class_name = type(current).__name__
        messages.append(f"{class_name}: {current}")
        if class_name in {"TimeoutException", "ReadTimeout", "ConnectTimeout", "PoolTimeout"}:
            return "timeout", _safe_detail(messages)
        if class_name == "HTTPStatusError":
            response = getattr(current, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in {401, 403}:
                return "auth_failed", f"Provider authentication failed with HTTP {status_code}."
            if status_code == 429:
                return "rate_limited", "Provider returned HTTP 429 rate limit or quota response."
            return "failed", f"Provider HTTP request failed with status {status_code}."
        if class_name == "ModuleNotFoundError":
            return "missing_dependency", _safe_detail(messages)
        current = current.__cause__ or current.__context__

    detail = _safe_detail(messages)
    if "response is invalid" in detail.lower() or "response invalid" in detail.lower():
        return "format_error", detail
    return "failed", detail


def _safe_detail(messages: list[str]) -> str:
    """限制异常明细长度，避免把 SDK 响应或环境细节完整落入记录。"""
    return " | ".join(messages)[:300]


def _probe_llm() -> ProviderProbeResult:
    settings = get_settings()
    if settings.llm_provider == "local":
        return _local_provider("llm", settings.llm_provider)
    if settings.llm_provider != "http":
        return _blocked("llm", settings.llm_provider, "Only http LLM provider supports real network retest.")
    if not settings.llm_endpoint:
        return _blocked("llm", settings.llm_provider, "RAG_LAB_LLM_ENDPOINT is missing.")

    def probe() -> dict[str, Any]:
        provider = HttpLlmProvider(settings)
        answer = provider.generate_answer(
            "请只回答 pong",
            [ProviderCandidate(source_type="retest", chunk_id=None, raw_score=1.0, content="ping -> pong", metadata={})],
            temperature=0,
        )
        if not answer.strip():
            raise ValueError("LLM response is invalid: empty content.")
        return {"model": settings.llm_model, "answerLength": len(answer), "usage": provider.last_usage}

    return _run_probe("llm", settings.llm_provider, probe)


def _probe_embedding() -> ProviderProbeResult:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return _local_provider("embedding", settings.embedding_provider)
    if settings.embedding_provider != "http":
        return _blocked("embedding", settings.embedding_provider, "Only http Embedding provider supports real network retest.")
    if not settings.embedding_endpoint:
        return _blocked("embedding", settings.embedding_provider, "RAG_LAB_EMBEDDING_ENDPOINT is missing.")

    def probe() -> dict[str, Any]:
        provider = HttpEmbeddingProvider(settings)
        vector = provider.embed_query("provider network retest ping")
        if not vector:
            raise ValueError("Embedding response is invalid: empty vector.")
        return {"model": settings.embedding_model, "dimension": len(vector), "usage": provider.last_usage}

    return _run_probe("embedding", settings.embedding_provider, probe)


def _probe_rerank() -> ProviderProbeResult:
    settings = get_settings()
    if settings.rerank_provider == "identity":
        return _local_provider("rerank", settings.rerank_provider)
    if settings.rerank_provider != "http":
        return _blocked("rerank", settings.rerank_provider, "Only http Rerank provider supports real network retest.")
    if not settings.rerank_endpoint:
        return _blocked("rerank", settings.rerank_provider, "RAG_LAB_RERANK_ENDPOINT is missing.")

    def probe() -> dict[str, Any]:
        provider = HttpRerankProvider(settings)
        candidates = [
            ProviderCandidate(source_type="retest", chunk_id=None, raw_score=0.5, content="pong", metadata={}),
            ProviderCandidate(source_type="retest", chunk_id=None, raw_score=0.4, content="irrelevant", metadata={}),
        ]
        reranked = provider.rerank("ping", candidates, 1)
        if not reranked:
            raise ValueError("Rerank response is invalid: empty result.")
        return {"model": settings.rerank_model, "resultCount": len(reranked), "usage": provider.last_usage}

    return _run_probe("rerank", settings.rerank_provider, probe)


def _probe_milvus() -> ProviderProbeResult:
    settings = get_settings()
    if settings.dense_retrieval_provider == "local":
        return _local_provider("milvus", settings.dense_retrieval_provider)
    if settings.dense_retrieval_provider != "milvus":
        return _blocked("milvus", settings.dense_retrieval_provider, "Only milvus Dense provider supports real network retest.")
    if not settings.milvus_uri:
        return _blocked("milvus", settings.dense_retrieval_provider, "RAG_LAB_MILVUS_URI is missing.")

    def probe() -> dict[str, Any]:
        from pymilvus import MilvusClient

        client = MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token)
        collection_exists = client.has_collection(settings.milvus_collection)
        return {"collection": settings.milvus_collection, "collectionExists": collection_exists}

    return _run_probe("milvus", settings.dense_retrieval_provider, probe)


def _probe_opensearch() -> ProviderProbeResult:
    settings = get_settings()
    if settings.sparse_retrieval_provider == "local":
        return _local_provider("opensearch", settings.sparse_retrieval_provider)
    if settings.sparse_retrieval_provider != "opensearch":
        return _blocked(
            "opensearch",
            settings.sparse_retrieval_provider,
            "Only opensearch Sparse provider supports real network retest.",
        )
    if not settings.opensearch_hosts:
        return _blocked("opensearch", settings.sparse_retrieval_provider, "RAG_LAB_OPENSEARCH_HOSTS is missing.")

    def probe() -> dict[str, Any]:
        from opensearchpy import OpenSearch

        auth = None
        if settings.opensearch_username and settings.opensearch_password:
            auth = (settings.opensearch_username, settings.opensearch_password)
        hosts = [host.strip() for host in settings.opensearch_hosts.split(",") if host.strip()]
        client = OpenSearch(hosts=hosts, http_auth=auth)
        info = client.info()
        index_exists = client.indices.exists(index=settings.opensearch_index)
        return {
            "clusterName": info.get("cluster_name"),
            "index": settings.opensearch_index,
            "indexExists": bool(index_exists),
        }

    return _run_probe("opensearch", settings.sparse_retrieval_provider, probe)


def _probe_neo4j() -> ProviderProbeResult:
    settings = get_settings()
    if settings.graph_retrieval_provider == "local":
        return _local_provider("neo4j", settings.graph_retrieval_provider)
    if settings.graph_retrieval_provider != "neo4j":
        return _blocked("neo4j", settings.graph_retrieval_provider, "Only neo4j Graph provider supports real network retest.")
    if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
        return _blocked("neo4j", settings.graph_retrieval_provider, "Neo4j URI, username or password is missing.")

    def probe() -> dict[str, Any]:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password))
        try:
            driver.verify_connectivity()
        finally:
            driver.close()
        return {"database": settings.neo4j_database or "default"}

    return _run_probe("neo4j", settings.graph_retrieval_provider, probe)


def _summarize_status(results: list[ProviderProbeResult]) -> str:
    """汇总发布级状态；只有所有 Provider 真实成功才返回 success。"""
    statuses = {item.status for item in results}
    if statuses == {"success"}:
        return "success"
    if "failed" in statuses or "timeout" in statuses or "auth_failed" in statuses or "format_error" in statuses:
        return "failed"
    return "blocked"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Provider network retest probes for release evidence.")
    parser.add_argument("--output", type=Path, help="Optional JSON output path for release retest evidence.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when any provider is not real success.")
    args = parser.parse_args()

    results = [
        _probe_embedding(),
        _probe_milvus(),
        _probe_opensearch(),
        _probe_neo4j(),
        _probe_llm(),
        _probe_rerank(),
    ]
    payload = {
        "status": _summarize_status(results),
        "note": "local_provider/blocked does not mean the real provider network retest passed.",
        "results": [asdict(item) for item in results],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 1 if args.strict and payload["status"] != "success" else 0


if __name__ == "__main__":
    sys.exit(main())
