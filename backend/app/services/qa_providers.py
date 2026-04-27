from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from app.core.config import Settings, get_settings
from app.services.permission_service import ChunkAccessFilterContext


@dataclass(frozen=True)
class ProviderCandidate:
    """统一检索候选，所有外部检索结果必须先归一化再进入 QA 编排。"""

    source_type: str
    chunk_id: UUID | None
    raw_score: float | None
    content: str | None
    metadata: dict


class ProviderError(RuntimeError):
    """Provider 调用失败，QA 编排用它记录 Trace 并决定是否降级。"""


class EmbeddingProvider:
    """Query / Chunk 向量化 Provider 抽象。"""

    def embed_query(self, query: str) -> list[float]:
        raise NotImplementedError


class LocalEmbeddingProvider(EmbeddingProvider):
    """本地确定性 embedding，占位用于无模型服务环境的端到端验证。"""

    def embed_query(self, query: str) -> list[float]:
        digest = sha256(query.encode("utf-8")).digest()
        return [round(byte / 255, 6) for byte in digest[:16]]


class HttpEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible embedding Provider，通过配置 endpoint 接入真实模型服务。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.embedding_endpoint:
            raise ProviderError("Embedding endpoint is required.")
        self._endpoint = settings.embedding_endpoint
        self._api_key = settings.embedding_api_key
        self._model = settings.embedding_model

    def embed_query(self, query: str) -> list[float]:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = httpx.post(
                self._endpoint,
                headers=headers,
                json={"model": self._model, "input": query},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("Embedding provider request failed.") from exc
        payload = response.json()
        try:
            return [float(value) for value in payload["data"][0]["embedding"]]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Embedding response is invalid.") from exc


class DenseRetrievalProvider:
    """Dense Retrieval Provider 抽象，返回值不得直接当作业务真值。"""

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        embedding: list[float],
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        raise NotImplementedError


class LocalDenseRetrievalProvider(DenseRetrievalProvider):
    """本地 Dense 降级 Provider，保留链路形态而不依赖 Milvus。"""

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        embedding: list[float],
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        return [
            ProviderCandidate(
                source_type="dense",
                chunk_id=None,
                raw_score=0.72,
                content=f"本地 Dense Provider 降级候选：{query}",
                metadata={"provider": "local", "kbId": str(kb_id), "accessFilterHash": access_filter.filter_hash},
            )
        ][:limit]


class MilvusDenseRetrievalProvider(DenseRetrievalProvider):
    """Milvus Dense Provider，只返回 chunk_id 和诊断摘要，正文仍应回表确认。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.milvus_uri:
            raise ProviderError("Milvus URI is required.")
        from pymilvus import MilvusClient

        self._collection = settings.milvus_collection
        self._client = MilvusClient(uri=settings.milvus_uri, token=settings.milvus_token)

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        embedding: list[float],
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        filter_expr = (
            f'kb_id == "{kb_id}" && '
            f'document_status == "{access_filter.document_status}" && '
            f'version_status == "{access_filter.version_status}" && '
            f'chunk_status == "{access_filter.chunk_status}"'
        )
        try:
            result_sets = self._client.search(
                collection_name=self._collection,
                data=[embedding],
                filter=filter_expr,
                limit=limit,
                output_fields=["chunk_id", "content", "document_id", "version_id", "title", "page_no", "section"],
            )
        except Exception as exc:
            raise ProviderError("Milvus dense retrieval failed.") from exc

        candidates: list[ProviderCandidate] = []
        for hit in result_sets[0] if result_sets else []:
            entity = hit.get("entity", {}) if isinstance(hit, dict) else {}
            chunk_id = _parse_uuid(entity.get("chunk_id"))
            candidates.append(
                ProviderCandidate(
                    source_type="dense",
                    chunk_id=chunk_id,
                    raw_score=_safe_float(hit.get("distance") if isinstance(hit, dict) else None),
                    content=entity.get("content"),
                    metadata={key: value for key, value in entity.items() if key != "content"},
                )
            )
        return candidates


class SparseRetrievalProvider:
    """Sparse Retrieval Provider 抽象，屏蔽 OpenSearch 查询细节。"""

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        raise NotImplementedError


class LocalSparseRetrievalProvider(SparseRetrievalProvider):
    """本地 Sparse 降级 Provider，便于无 OpenSearch 环境验证 Trace。"""

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        return [
            ProviderCandidate(
                source_type="sparse",
                chunk_id=None,
                raw_score=0.65,
                content=f"本地 Sparse Provider 降级候选：{query}",
                metadata={"provider": "local", "kbId": str(kb_id), "accessFilterHash": access_filter.filter_hash},
            )
        ][:limit]


class OpenSearchSparseRetrievalProvider(SparseRetrievalProvider):
    """OpenSearch Sparse Provider，按 kb_id 先过滤再召回文本候选。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.opensearch_hosts:
            raise ProviderError("OpenSearch hosts are required.")
        from opensearchpy import OpenSearch

        hosts = [host.strip() for host in settings.opensearch_hosts.split(",") if host.strip()]
        auth = None
        if settings.opensearch_username and settings.opensearch_password:
            auth = (settings.opensearch_username, settings.opensearch_password)
        self._index = settings.opensearch_index
        self._client = OpenSearch(hosts=hosts, http_auth=auth)

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        body = {
            "size": limit,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"kb_id": str(kb_id)}},
                        {"term": {"document_status": access_filter.document_status}},
                        {"term": {"version_status": access_filter.version_status}},
                        {"term": {"chunk_status": access_filter.chunk_status}},
                    ],
                    "must": [{"multi_match": {"query": query, "fields": ["content", "title", "section"]}}],
                }
            },
        }
        try:
            payload = self._client.search(index=self._index, body=body)
        except Exception as exc:
            raise ProviderError("OpenSearch sparse retrieval failed.") from exc

        candidates: list[ProviderCandidate] = []
        for hit in payload.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            candidates.append(
                ProviderCandidate(
                    source_type="sparse",
                    chunk_id=_parse_uuid(source.get("chunk_id")),
                    raw_score=_safe_float(hit.get("_score")),
                    content=source.get("content"),
                    metadata={key: value for key, value in source.items() if key != "content"},
                )
            )
        return candidates


class GraphRetrievalProvider:
    """Graph Retrieval Provider 抽象，图结果必须通过 chunk_id 回落。"""

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        graph_snapshot_id: UUID | None,
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        raise NotImplementedError

    def search_entities(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        raise NotImplementedError


class LocalGraphRetrievalProvider(GraphRetrievalProvider):
    """本地图检索降级 Provider，只返回诊断候选。"""

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        graph_snapshot_id: UUID | None,
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        return [
            ProviderCandidate(
                source_type="graph",
                chunk_id=None,
                raw_score=0.58,
                content=f"本地 Graph Provider 降级候选：{query}",
                metadata={
                    "provider": "local",
                    "kbId": str(kb_id),
                    "graphSnapshotId": str(graph_snapshot_id) if graph_snapshot_id else None,
                    "accessFilterHash": access_filter.filter_hash,
                },
            )
        ][:limit]

    def search_entities(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        return []


class Neo4jGraphRetrievalProvider(GraphRetrievalProvider):
    """Neo4j Graph Provider，返回实体诊断和支撑 chunk_id，不直接提供最终证据。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
            raise ProviderError("Neo4j URI, username and password are required.")
        from neo4j import GraphDatabase

        self._database = settings.neo4j_database
        self._driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password))

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        graph_snapshot_id: UUID | None,
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        cypher = """
        MATCH (e:Entity)-[:SUPPORTED_BY]->(c:ChunkRef)
        WHERE e.kb_id = $kb_id
          AND ($graph_snapshot_id IS NULL OR e.graph_snapshot_id = $graph_snapshot_id)
          AND toLower(e.name) CONTAINS toLower($query)
        RETURN c.chunk_id AS chunk_id, c.summary AS content, e.name AS entity_name, e.entity_key AS entity_key
        LIMIT $limit
        """
        records = self._run_read(cypher, kb_id=kb_id, graph_snapshot_id=graph_snapshot_id, query=query, limit=limit)
        return [
            ProviderCandidate(
                source_type="graph",
                chunk_id=_parse_uuid(record.get("chunk_id")),
                raw_score=None,
                content=record.get("content"),
                metadata={"entityName": record.get("entity_name"), "entityKey": record.get("entity_key")},
            )
            for record in records
        ]

    def search_entities(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        cypher = """
        MATCH (e:Entity)
        WHERE e.kb_id = $kb_id
          AND ($graph_snapshot_id IS NULL OR e.graph_snapshot_id = $graph_snapshot_id)
          AND toLower(e.name) CONTAINS toLower($keyword)
        RETURN e.entity_key AS entityKey, e.name AS name, e.type AS type, e.aliases AS aliases
        LIMIT $limit
        """
        return self._run_read(cypher, kb_id=kb_id, graph_snapshot_id=graph_snapshot_id, keyword=keyword, limit=limit)

    def _run_read(self, cypher: str, **params: object) -> list[dict]:
        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(
                    cypher,
                    **{key: str(value) if isinstance(value, UUID) else value for key, value in params.items()},
                )
                return [dict(record) for record in result]
        except Exception as exc:
            raise ProviderError("Neo4j graph retrieval failed.") from exc


class RerankProvider:
    """Rerank Provider 抽象，统一 Dense/Sparse/Graph 候选排序。"""

    def rerank(self, query: str, candidates: list[ProviderCandidate], limit: int) -> list[ProviderCandidate]:
        raise NotImplementedError


class IdentityRerankProvider(RerankProvider):
    """默认 Rerank Provider，按原始分数和原顺序稳定排序。"""

    def rerank(self, query: str, candidates: list[ProviderCandidate], limit: int) -> list[ProviderCandidate]:
        return sorted(candidates, key=lambda item: item.raw_score or 0, reverse=True)[:limit]


class HttpRerankProvider(RerankProvider):
    """HTTP Rerank Provider，兼容返回 index/score 列表的常见重排服务。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.rerank_endpoint:
            raise ProviderError("Rerank endpoint is required.")
        self._endpoint = settings.rerank_endpoint
        self._api_key = settings.rerank_api_key

    def rerank(self, query: str, candidates: list[ProviderCandidate], limit: int) -> list[ProviderCandidate]:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = httpx.post(
                self._endpoint,
                headers=headers,
                json={"query": query, "documents": [candidate.content or "" for candidate in candidates], "top_n": limit},
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("Rerank provider request failed.") from exc
        payload = response.json()
        results = payload.get("results", [])
        reranked: list[ProviderCandidate] = []
        for result in results:
            index = result.get("index")
            if isinstance(index, int) and 0 <= index < len(candidates):
                base = candidates[index]
                reranked.append(
                    ProviderCandidate(
                        source_type=base.source_type,
                        chunk_id=base.chunk_id,
                        raw_score=_safe_float(result.get("relevance_score")) or base.raw_score,
                        content=base.content,
                        metadata={**base.metadata, "rerankProvider": "http"},
                    )
                )
        return reranked[:limit] if reranked else candidates[:limit]


class LlmProvider:
    """LLM Provider 抽象，负责 Query Rewrite 和 Answer Generation。"""

    def rewrite_query(self, query: str) -> str:
        raise NotImplementedError

    def generate_answer(self, query: str, evidence: list[ProviderCandidate]) -> str:
        raise NotImplementedError


class LocalLlmProvider(LlmProvider):
    """本地 LLM 降级 Provider，用于无模型服务环境保持 QA 链路可运行。"""

    def rewrite_query(self, query: str) -> str:
        return query if query.endswith("?") or query.endswith("？") else f"{query}?"

    def generate_answer(self, query: str, evidence: list[ProviderCandidate]) -> str:
        if not evidence:
            return f"未召回到可用证据，无法基于知识库回答：{query}"
        summary = "；".join((candidate.content or "无正文摘要")[:80] for candidate in evidence[:3])
        return f"这是基于 Provider 链路生成的本地降级回答：{query}\n证据摘要：{summary}"


class HttpLlmProvider(LlmProvider):
    """OpenAI-compatible Chat Completion Provider，通过 endpoint 接入真实 LLM。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_endpoint:
            raise ProviderError("LLM endpoint is required.")
        self._endpoint = settings.llm_endpoint
        self._api_key = settings.llm_api_key
        self._model = settings.llm_model

    def rewrite_query(self, query: str) -> str:
        content = self._chat(
            [
                {"role": "system", "content": "Rewrite the user query for retrieval. Return only the rewritten query."},
                {"role": "user", "content": query},
            ]
        )
        return content.strip() or query

    def generate_answer(self, query: str, evidence: list[ProviderCandidate]) -> str:
        evidence_text = "\n".join(f"[{index}] {candidate.content or candidate.metadata}" for index, candidate in enumerate(evidence, start=1))
        return self._chat(
            [
                {"role": "system", "content": "Answer using only the provided evidence. If evidence is insufficient, say so."},
                {"role": "user", "content": f"Question: {query}\nEvidence:\n{evidence_text}"},
            ]
        )

    def _chat(self, messages: list[dict[str, str]]) -> str:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = httpx.post(
                self._endpoint,
                headers=headers,
                json={"model": self._model, "messages": messages, "temperature": 0.2},
                timeout=60,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("LLM provider request failed.") from exc
        payload = response.json()
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("LLM response is invalid.") from exc


@dataclass(frozen=True)
class QARunProviders:
    """QA 编排所需 Provider 集合，便于测试时替换单个能力。"""

    embedding: EmbeddingProvider
    dense: DenseRetrievalProvider
    sparse: SparseRetrievalProvider
    graph: GraphRetrievalProvider
    rerank: RerankProvider
    llm: LlmProvider


def get_qa_run_providers() -> QARunProviders:
    """按配置构造 Provider 集合；真实 SDK 均懒加载，避免影响默认启动。"""
    settings = get_settings()
    return QARunProviders(
        embedding=_build_embedding_provider(settings),
        dense=_build_dense_provider(settings),
        sparse=_build_sparse_provider(settings),
        graph=_build_graph_provider(settings),
        rerank=_build_rerank_provider(settings),
        llm=_build_llm_provider(settings),
    )


def _build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "http":
        return HttpEmbeddingProvider(settings)
    if settings.embedding_provider == "local":
        return LocalEmbeddingProvider()
    raise ProviderError(f"Unsupported embedding provider: {settings.embedding_provider}")


def _build_dense_provider(settings: Settings) -> DenseRetrievalProvider:
    if settings.dense_retrieval_provider == "milvus":
        return MilvusDenseRetrievalProvider(settings)
    if settings.dense_retrieval_provider == "local":
        return LocalDenseRetrievalProvider()
    raise ProviderError(f"Unsupported dense retrieval provider: {settings.dense_retrieval_provider}")


def _build_sparse_provider(settings: Settings) -> SparseRetrievalProvider:
    if settings.sparse_retrieval_provider == "opensearch":
        return OpenSearchSparseRetrievalProvider(settings)
    if settings.sparse_retrieval_provider == "local":
        return LocalSparseRetrievalProvider()
    raise ProviderError(f"Unsupported sparse retrieval provider: {settings.sparse_retrieval_provider}")


def _build_graph_provider(settings: Settings) -> GraphRetrievalProvider:
    if settings.graph_retrieval_provider == "neo4j":
        return Neo4jGraphRetrievalProvider(settings)
    if settings.graph_retrieval_provider == "local":
        return LocalGraphRetrievalProvider()
    raise ProviderError(f"Unsupported graph retrieval provider: {settings.graph_retrieval_provider}")


def _build_rerank_provider(settings: Settings) -> RerankProvider:
    if settings.rerank_provider == "http":
        return HttpRerankProvider(settings)
    if settings.rerank_provider == "identity":
        return IdentityRerankProvider()
    raise ProviderError(f"Unsupported rerank provider: {settings.rerank_provider}")


def _build_llm_provider(settings: Settings) -> LlmProvider:
    if settings.llm_provider == "http":
        return HttpLlmProvider(settings)
    if settings.llm_provider == "local":
        return LocalLlmProvider()
    raise ProviderError(f"Unsupported llm provider: {settings.llm_provider}")


def _parse_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
