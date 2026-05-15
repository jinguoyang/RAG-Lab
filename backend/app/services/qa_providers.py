import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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


@dataclass(frozen=True)
class GraphEntity:
    """从 Chunk 中抽取出的图实体，写入 Neo4j 前保持轻量结构。"""

    entity_key: str
    name: str
    entity_type: str
    aliases: list[str]
    chunk_id: str


@dataclass(frozen=True)
class GraphRelation:
    """从 Chunk 中抽取出的图关系，必须能回溯支撑 Chunk。"""

    relation_key: str
    source_entity_key: str
    target_entity_key: str
    relation_type: str
    chunk_id: str


@dataclass(frozen=True)
class ChunkGraphExtraction:
    """单个 Chunk 的实体关系抽取结果。"""

    chunk_id: str
    summary: str
    entities: list[GraphEntity]
    relations: list[GraphRelation]


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
        self.last_usage: dict = {}

    def embed_query(self, query: str) -> list[float]:
        import httpx

        self.last_usage = {}
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
        usage = payload.get("usage")
        if isinstance(usage, dict):
            self.last_usage = {
                "inputTokens": usage.get("prompt_tokens", 0),
                "totalTokens": usage.get("total_tokens", 0),
                "model": self._model,
            }
        try:
            return [float(value) for value in payload["data"][0]["embedding"]]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError("Embedding response is invalid.") from exc


class DenseRetrievalProvider:
    """Dense Retrieval Provider 抽象，返回值不得直接当作业务真值。"""

    def upsert_chunks(self, chunk_payloads: list[dict]) -> dict:
        """写入 Dense 副本，返回 Provider 诊断摘要。"""
        raise NotImplementedError

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        """从 Dense 副本删除 Chunk，返回 Provider 诊断摘要。"""
        raise NotImplementedError

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

    def upsert_chunks(self, chunk_payloads: list[dict]) -> dict:
        return {"provider": "local", "targetStore": "milvus", "operation": "upsert", "chunkCount": len(chunk_payloads)}

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        return {"provider": "local", "targetStore": "milvus", "operation": "delete", "chunkCount": len(chunk_ids)}

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

    def upsert_chunks(self, chunk_payloads: list[dict]) -> dict:
        """将 Chunk 向量和过滤字段真实 upsert 到 Milvus。"""
        rows = [_to_milvus_row(payload) for payload in chunk_payloads]
        try:
            self._ensure_collection(rows)
            self._client.upsert(collection_name=self._collection, data=rows)
        except Exception as exc:
            raise ProviderError(f"Milvus dense index upsert failed: {exc}") from exc
        return {"provider": "milvus", "targetStore": "milvus", "operation": "upsert", "chunkCount": len(rows)}

    def _ensure_collection(self, rows: list[dict]) -> None:
        """按首批向量维度初始化缺失 Collection，避免空 Milvus 环境直接 upsert 失败。"""
        if not rows or self._client.has_collection(self._collection):
            return
        embedding = rows[0].get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise ProviderError("Milvus collection creation requires a non-empty embedding.")

        from pymilvus import DataType, MilvusClient

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
        schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("kb_id", DataType.VARCHAR, max_length=64)
        schema.add_field("document_id", DataType.VARCHAR, max_length=64)
        schema.add_field("version_id", DataType.VARCHAR, max_length=64)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        schema.add_field("content_hash", DataType.VARCHAR, max_length=128)
        schema.add_field("page_no", DataType.INT64)
        schema.add_field("section", DataType.VARCHAR, max_length=1024)
        schema.add_field("security_level", DataType.VARCHAR, max_length=64)
        schema.add_field("document_status", DataType.VARCHAR, max_length=32)
        schema.add_field("version_status", DataType.VARCHAR, max_length=32)
        schema.add_field("chunk_status", DataType.VARCHAR, max_length=32)
        schema.add_field("allow_subject_keys", DataType.JSON)
        schema.add_field("deny_subject_keys", DataType.JSON)
        schema.add_field("filter_hash", DataType.VARCHAR, max_length=128)
        schema.add_field("metadata", DataType.JSON)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=len(embedding))

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(field_name="embedding", index_type="AUTOINDEX", metric_type="COSINE")
        self._client.create_collection(
            collection_name=self._collection,
            schema=schema,
            index_params=index_params,
        )

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        """按 chunk_id 从 Milvus 删除可重建副本。"""
        if not chunk_ids:
            return {"provider": "milvus", "targetStore": "milvus", "operation": "delete", "chunkCount": 0}
        if not self._client.has_collection(self._collection):
            return {"provider": "milvus", "targetStore": "milvus", "operation": "delete", "chunkCount": len(chunk_ids)}
        escaped_ids = ", ".join(f'"{chunk_id}"' for chunk_id in chunk_ids)
        try:
            self._client.delete(collection_name=self._collection, filter=f"chunk_id in [{escaped_ids}]")
        except Exception as exc:
            raise ProviderError(f"Milvus dense index delete failed: {exc}") from exc
        return {"provider": "milvus", "targetStore": "milvus", "operation": "delete", "chunkCount": len(chunk_ids)}

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

    def upsert_chunks(self, chunk_payloads: list[dict]) -> dict:
        """写入 Sparse 文本副本，返回 Provider 诊断摘要。"""
        raise NotImplementedError

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        """从 Sparse 文本副本删除 Chunk，返回 Provider 诊断摘要。"""
        raise NotImplementedError

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

    def upsert_chunks(self, chunk_payloads: list[dict]) -> dict:
        return {"provider": "local", "targetStore": "opensearch", "operation": "upsert", "chunkCount": len(chunk_payloads)}

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        return {"provider": "local", "targetStore": "opensearch", "operation": "delete", "chunkCount": len(chunk_ids)}

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

    def upsert_chunks(self, chunk_payloads: list[dict]) -> dict:
        """将 Chunk 文本、metadata 和过滤字段真实 upsert 到 OpenSearch。"""
        try:
            for payload in chunk_payloads:
                self._client.index(index=self._index, id=payload["chunkId"], body=_to_search_document(payload))
        except Exception as exc:
            raise ProviderError("OpenSearch sparse index upsert failed.") from exc
        return {"provider": "opensearch", "targetStore": "opensearch", "operation": "upsert", "chunkCount": len(chunk_payloads)}

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        """按 chunk_id 从 OpenSearch 删除文本副本。"""
        try:
            for chunk_id in chunk_ids:
                self._client.delete(index=self._index, id=str(chunk_id), ignore=[404])
        except Exception as exc:
            raise ProviderError("OpenSearch sparse index delete failed.") from exc
        return {"provider": "opensearch", "targetStore": "opensearch", "operation": "delete", "chunkCount": len(chunk_ids)}

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
                        _exact_field_filter("kb_id", str(kb_id)),
                        _exact_field_filter("document_status", access_filter.document_status),
                        _exact_field_filter("version_status", access_filter.version_status),
                        _exact_field_filter("chunk_status", access_filter.chunk_status),
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

    def upsert_chunks(self, chunk_payloads: list[dict], graph_items: list[ChunkGraphExtraction]) -> dict:
        """写入图结构和 ChunkRef，返回 Provider 诊断摘要。"""
        raise NotImplementedError

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        """从图结构中删除 ChunkRef，返回 Provider 诊断摘要。"""
        raise NotImplementedError

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

    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        """按关键词搜索图关系路径摘要。"""
        raise NotImplementedError

    def search_communities(
        self,
        kb_id: UUID,
        keyword: str | None,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        """按关键词搜索图社区摘要。"""
        raise NotImplementedError


class LocalGraphRetrievalProvider(GraphRetrievalProvider):
    """本地图检索降级 Provider，只返回诊断候选。"""

    def upsert_chunks(self, chunk_payloads: list[dict], graph_items: list[ChunkGraphExtraction]) -> dict:
        entity_count = sum(len(item.entities) for item in graph_items)
        relation_count = sum(len(item.relations) for item in graph_items)
        return {
            "provider": "local",
            "targetStore": "neo4j",
            "operation": "upsert",
            "chunkCount": len(chunk_payloads),
            "entityCount": entity_count,
            "relationCount": relation_count,
        }

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        return {"provider": "local", "targetStore": "neo4j", "operation": "delete", "chunkCount": len(chunk_ids)}

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

    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        return []

    def search_communities(
        self,
        kb_id: UUID,
        keyword: str | None,
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

    def upsert_chunks(self, chunk_payloads: list[dict], graph_items: list[ChunkGraphExtraction]) -> dict:
        """将 LLM 抽取的实体、关系和 ChunkRef 写入 Neo4j。"""
        payload_by_chunk_id = {str(payload["chunkId"]): payload for payload in chunk_payloads}
        try:
            with self._driver.session(database=self._database) as session:
                for item in graph_items:
                    payload = payload_by_chunk_id.get(item.chunk_id)
                    if payload is None:
                        continue
                    session.run(
                        """
                        MERGE (chunk:ChunkRef {chunk_id: $chunk_id})
                        SET chunk.kb_id = $kb_id,
                            chunk.version_id = $version_id,
                            chunk.document_id = $document_id,
                            chunk.summary = $summary,
                            chunk.section = $section,
                            chunk.security_level = $security_level
                        """,
                        chunk_id=item.chunk_id,
                        kb_id=payload["kbId"],
                        version_id=payload["versionId"],
                        document_id=payload["documentId"],
                        summary=item.summary,
                        section=payload.get("section"),
                        security_level=payload.get("securityLevel"),
                    )
                    for entity in item.entities:
                        session.run(
                            """
                            MERGE (entity:Entity {entity_key: $entity_key})
                            SET entity.name = $name,
                                entity.type = $type,
                                entity.aliases = $aliases,
                                entity.kb_id = $kb_id,
                                entity.graph_snapshot_id = $graph_snapshot_id
                            WITH entity
                            MATCH (chunk:ChunkRef {chunk_id: $chunk_id})
                            MERGE (entity)-[:SUPPORTED_BY]->(chunk)
                            """,
                            entity_key=entity.entity_key,
                            name=entity.name,
                            type=entity.entity_type,
                            aliases=entity.aliases,
                            kb_id=payload["kbId"],
                            graph_snapshot_id=payload.get("graphSnapshotId"),
                            chunk_id=item.chunk_id,
                        )
                    for relation in item.relations:
                        session.run(
                            """
                            MATCH (source:Entity {entity_key: $source_entity_key})
                            MATCH (target:Entity {entity_key: $target_entity_key})
                            MERGE (source)-[relation:RELATED_TO {relation_key: $relation_key}]->(target)
                            SET relation.relation_type = $relation_type,
                                relation.support_chunk_id = $chunk_id,
                                relation.support_node_key = $source_entity_key
                            """,
                            source_entity_key=relation.source_entity_key,
                            target_entity_key=relation.target_entity_key,
                            relation_key=relation.relation_key,
                            relation_type=relation.relation_type,
                            chunk_id=relation.chunk_id,
                        )
        except Exception as exc:
            raise ProviderError("Neo4j graph index upsert failed.") from exc
        return {
            "provider": "neo4j",
            "targetStore": "neo4j",
            "operation": "upsert",
            "chunkCount": len(chunk_payloads),
            "entityCount": sum(len(item.entities) for item in graph_items),
            "relationCount": sum(len(item.relations) for item in graph_items),
        }

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        """删除 ChunkRef 与其支撑边；孤立实体由后续重建清理。"""
        try:
            with self._driver.session(database=self._database) as session:
                for chunk_id in chunk_ids:
                    session.run(
                        """
                        MATCH (chunk:ChunkRef {chunk_id: $chunk_id})
                        DETACH DELETE chunk
                        """,
                        chunk_id=str(chunk_id),
                    )
        except Exception as exc:
            raise ProviderError("Neo4j graph index delete failed.") from exc
        return {"provider": "neo4j", "targetStore": "neo4j", "operation": "delete", "chunkCount": len(chunk_ids)}

    def retrieve(
        self,
        kb_id: UUID,
        query: str,
        graph_snapshot_id: UUID | None,
        limit: int,
        access_filter: ChunkAccessFilterContext,
    ) -> list[ProviderCandidate]:
        search_terms = _graph_query_terms(query)
        cypher = """
        MATCH (e:Entity)-[:SUPPORTED_BY]->(c:ChunkRef)
        WHERE e.kb_id = $kb_id
          AND ($graph_snapshot_id IS NULL OR e.graph_snapshot_id = $graph_snapshot_id)
          AND ANY(term IN $search_terms WHERE
            toLower(e.name) CONTAINS term
            OR ANY(alias IN coalesce(e.aliases, []) WHERE toLower(alias) CONTAINS term)
            OR toLower(coalesce(c.summary, "")) CONTAINS term
          )
        RETURN c.chunk_id AS chunk_id, c.summary AS content, e.name AS entity_name, e.entity_key AS entity_key
        LIMIT $limit
        """
        records = self._run_read(
            cypher,
            kb_id=kb_id,
            graph_snapshot_id=graph_snapshot_id,
            search_terms=search_terms,
            limit=limit,
        )
        return [
            ProviderCandidate(
                source_type="graph",
                chunk_id=_parse_uuid(record.get("chunk_id")),
                raw_score=None,
                content=record.get("content"),
                metadata={
                    "entityName": record.get("entity_name"),
                    "entityKey": record.get("entity_key"),
                    "graphSnapshotId": str(graph_snapshot_id) if graph_snapshot_id else None,
                    "queryTerms": search_terms,
                },
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

    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        cypher = """
        MATCH (source:Entity)-[rel:RELATED_TO]->(target:Entity)
        WHERE source.kb_id = $kb_id
          AND target.kb_id = $kb_id
          AND ($graph_snapshot_id IS NULL OR source.graph_snapshot_id = $graph_snapshot_id)
          AND ($graph_snapshot_id IS NULL OR target.graph_snapshot_id = $graph_snapshot_id)
          AND (
            toLower(source.name) CONTAINS toLower($keyword)
            OR toLower(target.name) CONTAINS toLower($keyword)
            OR toLower(type(rel)) CONTAINS toLower($keyword)
          )
        RETURN
          coalesce(rel.relation_key, elementId(rel)) AS pathKey,
          source.entity_key AS sourceEntityKey,
          source.name AS sourceName,
          source.type AS sourceType,
          target.entity_key AS targetEntityKey,
          target.name AS targetName,
          target.type AS targetType,
          type(rel) AS relationType,
          coalesce(rel.support_node_key, source.entity_key) AS nodeKey,
          rel.relation_key AS relationKey
        LIMIT $limit
        """
        return self._run_read(cypher, kb_id=kb_id, graph_snapshot_id=graph_snapshot_id, keyword=keyword, limit=limit)

    def search_communities(
        self,
        kb_id: UUID,
        keyword: str | None,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        cypher = """
        MATCH (community:Community)
        WHERE community.kb_id = $kb_id
          AND ($graph_snapshot_id IS NULL OR community.graph_snapshot_id = $graph_snapshot_id)
          AND (
            $keyword IS NULL
            OR toLower(community.summary) CONTAINS toLower($keyword)
            OR toLower(coalesce(community.title, community.community_key)) CONTAINS toLower($keyword)
          )
        RETURN
          community.community_key AS communityKey,
          coalesce(community.title, community.community_key) AS title,
          community.summary AS summary,
          community.entity_count AS entityCount,
          community.community_key AS communityKeyForSupport
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
        self._model = settings.rerank_model
        self.last_usage: dict = {}

    def rerank(self, query: str, candidates: list[ProviderCandidate], limit: int) -> list[ProviderCandidate]:
        import httpx

        self.last_usage = {}
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = httpx.post(
                self._endpoint,
                headers=headers,
                json={
                    "model": self._model,
                    "query": query,
                    "documents": [candidate.content or "" for candidate in candidates],
                    "top_n": limit,
                },
                timeout=30,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("Rerank provider request failed.") from exc
        payload = response.json()
        usage = payload.get("usage")
        if isinstance(usage, dict):
            self.last_usage = {
                "inputTokens": usage.get("prompt_tokens", usage.get("total_tokens", 0)),
                "totalTokens": usage.get("total_tokens", 0),
                "model": self._model,
            }
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

    def extract_graph(self, chunk_payloads: list[dict]) -> list[ChunkGraphExtraction]:
        """从 Chunk 正文抽取实体关系，供 Neo4j 写入使用。"""
        raise NotImplementedError

    def generate_answer(
        self,
        query: str,
        evidence: list[ProviderCandidate],
        temperature: float | None = None,
        max_context_tokens: int | None = None,
    ) -> str:
        raise NotImplementedError


class LocalLlmProvider(LlmProvider):
    """本地 LLM 降级 Provider，用于无模型服务环境保持 QA 链路可运行。"""

    def rewrite_query(self, query: str) -> str:
        return query if query.endswith("?") or query.endswith("？") else f"{query}?"

    def extract_graph(self, chunk_payloads: list[dict]) -> list[ChunkGraphExtraction]:
        """本地环境生成可回表的轻量图结果，不冒充真实模型质量。"""
        items: list[ChunkGraphExtraction] = []
        for payload in chunk_payloads:
            chunk_id = str(payload["chunkId"])
            name = (payload.get("section") or payload.get("content") or "Chunk")[:64]
            entity_key = _entity_key(payload["kbId"], name, chunk_id)
            entity = GraphEntity(entity_key=entity_key, name=name, entity_type="ChunkTopic", aliases=[], chunk_id=chunk_id)
            items.append(
                ChunkGraphExtraction(
                    chunk_id=chunk_id,
                    summary=(payload.get("content") or "")[:160],
                    entities=[entity],
                    relations=[],
                )
            )
        return items

    def generate_answer(
        self,
        query: str,
        evidence: list[ProviderCandidate],
        temperature: float | None = None,
        max_context_tokens: int | None = None,
    ) -> str:
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
        self._graph_extraction_concurrency = max(1, min(8, getattr(settings, "graph_extraction_concurrency", 3)))
        self.last_graph_extraction_errors: list[dict] = []
        self.last_usage: dict = {}

    def rewrite_query(self, query: str) -> str:
        content = self._chat(
            [
                {"role": "system", "content": "Rewrite the user query for retrieval. Return only the rewritten query."},
                {"role": "user", "content": query},
            ]
        )
        return content.strip() or query

    def extract_graph(self, chunk_payloads: list[dict]) -> list[ChunkGraphExtraction]:
        """调用真实 LLM 从 Chunk 中抽取可写入 Neo4j 的实体关系 JSON。"""
        self.last_graph_extraction_errors = []
        if not chunk_payloads:
            return []
        results: list[ChunkGraphExtraction | None] = [None] * len(chunk_payloads)
        max_workers = min(self._graph_extraction_concurrency, len(chunk_payloads))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._extract_graph_payload, payload): (index, payload)
                for index, payload in enumerate(chunk_payloads)
            }
            for future in as_completed(futures):
                index, payload = futures[future]
                try:
                    results[index] = future.result()
                except ProviderError as exc:
                    self.last_graph_extraction_errors.append(
                        {
                            "chunkId": str(payload.get("chunkId")),
                            "errorMessage": str(exc),
                        }
                    )
        items = [item for item in results if item is not None]
        if not items and chunk_payloads:
            raise ProviderError("All graph extraction requests failed.")
        return items

    def _extract_graph_payload(self, payload: dict) -> ChunkGraphExtraction:
        """抽取单个 Chunk 的图结构，供并发执行器调用。"""
        content = str(payload.get("content") or "")
        response = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract entities and relations from the user's chunk. "
                        "Return strict JSON with keys: summary, entities, relations. "
                        "entities items: name,type,aliases. relations items: source,target,type. "
                        "Do not include markdown."
                    ),
                },
                {"role": "user", "content": content[:4000]},
            ],
            temperature=0,
        )
        data = _parse_llm_json(response)
        chunk_id = str(payload["chunkId"])
        entities = [
            GraphEntity(
                entity_key=_entity_key(payload["kbId"], str(entity.get("name") or "entity"), chunk_id),
                name=str(entity.get("name") or "entity"),
                entity_type=str(entity.get("type") or "Unknown"),
                aliases=[str(alias) for alias in entity.get("aliases", []) if alias],
                chunk_id=chunk_id,
            )
            for entity in data.get("entities", [])
            if isinstance(entity, dict)
        ]
        key_by_name = {entity.name: entity.entity_key for entity in entities}
        relations = []
        for relation in data.get("relations", []):
            if not isinstance(relation, dict):
                continue
            source_name = str(relation.get("source") or "")
            target_name = str(relation.get("target") or "")
            source_key = key_by_name.get(source_name)
            target_key = key_by_name.get(target_name)
            if not source_key or not target_key:
                continue
            relation_type = str(relation.get("type") or "RELATED_TO")
            relations.append(
                GraphRelation(
                    relation_key=_relation_key(payload["kbId"], source_key, target_key, relation_type, chunk_id),
                    source_entity_key=source_key,
                    target_entity_key=target_key,
                    relation_type=relation_type,
                    chunk_id=chunk_id,
                )
            )
        return ChunkGraphExtraction(
            chunk_id=chunk_id,
            summary=str(data.get("summary") or content[:160]),
            entities=entities,
            relations=relations,
        )

    def generate_answer(
        self,
        query: str,
        evidence: list[ProviderCandidate],
        temperature: float | None = None,
        max_context_tokens: int | None = None,
    ) -> str:
        evidence_text = "\n".join(f"[{index}] {candidate.content or candidate.metadata}" for index, candidate in enumerate(evidence, start=1))
        return self._chat(
            [
                {"role": "system", "content": "Answer using only the provided evidence. If evidence is insufficient, say so."},
                {"role": "user", "content": f"Question: {query}\nEvidence:\n{evidence_text}"},
            ],
            temperature=temperature,
        )

    def _chat(self, messages: list[dict[str, str]], temperature: float | None = None) -> str:
        import httpx

        self.last_usage = {}
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        try:
            response = httpx.post(
                self._endpoint,
                headers=headers,
                json={"model": self._model, "messages": messages, "temperature": temperature if temperature is not None else 0.2},
                timeout=60,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError("LLM provider request failed.") from exc
        payload = response.json()
        usage = payload.get("usage")
        if isinstance(usage, dict):
            self.last_usage = {
                "inputTokens": usage.get("prompt_tokens", 0),
                "outputTokens": usage.get("completion_tokens", 0),
                "totalTokens": usage.get("total_tokens", 0),
                "model": self._model,
            }
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


def _graph_query_terms(query: str) -> list[str]:
    """从自然语言问题生成图检索关键词，避免整句匹配导致实体召回为 0。"""
    terms: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+", query.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            for size in (4, 3, 2):
                if len(token) >= size:
                    terms.extend(token[index : index + size] for index in range(0, len(token) - size + 1))
        elif len(token) >= 2:
            terms.append(token)

    ignored_terms = {"通常", "哪些", "哪个", "什么", "如何", "是否", "以及", "由哪", "负责"}
    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in terms:
        if term in ignored_terms or term in seen:
            continue
        seen.add(term)
        unique_terms.append(term)
    return unique_terms[:32] or [query.lower()]


def _to_milvus_row(payload: dict) -> dict:
    """把 camelCase Chunk payload 转成 Milvus Collection 字段。"""
    return {
        "chunk_id": payload["chunkId"],
        "kb_id": payload["kbId"],
        "document_id": payload["documentId"],
        "version_id": payload["versionId"],
        "content": payload.get("content") or "",
        "content_hash": payload.get("contentHash") or "",
        "page_no": payload.get("pageNo") or 0,
        "section": payload.get("section") or "",
        "security_level": payload.get("securityLevel") or "",
        "document_status": payload.get("documentStatus") or "",
        "version_status": payload.get("versionStatus") or "",
        "chunk_status": payload.get("chunkStatus") or "",
        "allow_subject_keys": payload.get("allowSubjectKeys", []),
        "deny_subject_keys": payload.get("denySubjectKeys", []),
        "filter_hash": payload.get("filterHash") or "",
        "metadata": payload.get("metadata", {}),
        "embedding": payload.get("embedding"),
    }


def _to_search_document(payload: dict) -> dict:
    """把 camelCase Chunk payload 转成 OpenSearch 文档。"""
    document = _to_milvus_row(payload)
    document["embedding_dimension"] = payload.get("embeddingDimension")
    document.pop("embedding", None)
    return document


def _exact_field_filter(field: str, value: object) -> dict:
    """构造兼容 keyword 字段和动态 text.keyword 子字段的精确过滤条件。"""
    return {
        "bool": {
            "should": [
                {"term": {field: value}},
                {"term": {f"{field}.keyword": value}},
            ],
            "minimum_should_match": 1,
        }
    }


def _parse_llm_json(content: str) -> dict:
    """解析 LLM JSON 输出，兼容少量 fenced code 包裹。"""
    cleaned = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderError("LLM graph extraction response is invalid.") from exc
    if not isinstance(data, dict):
        raise ProviderError("LLM graph extraction response must be a JSON object.")
    return data


def _entity_key(kb_id: object, name: str, chunk_id: str) -> str:
    """生成稳定实体键，避免不同知识库或 Chunk 之间互相覆盖。"""
    digest = sha256(f"{kb_id}:{name}:{chunk_id}".encode("utf-8")).hexdigest()[:16]
    return f"entity:{digest}"


def _relation_key(kb_id: object, source_key: str, target_key: str, relation_type: str, chunk_id: str) -> str:
    """生成稳定关系键，支撑 Neo4j MERGE 幂等写入。"""
    digest = sha256(f"{kb_id}:{source_key}:{target_key}:{relation_type}:{chunk_id}".encode("utf-8")).hexdigest()[:16]
    return f"relation:{digest}"
