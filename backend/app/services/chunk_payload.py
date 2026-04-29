from collections.abc import Mapping, Sequence
from typing import Any


def _stringify(value: object) -> str | None:
    """统一把 UUID 等对象转成外部副本可保存的字符串键。"""
    if value is None:
        return None
    return str(value)


def build_chunk_index_payload(
    chunk: Mapping[str, Any],
    document_status: str,
    version_status: str,
    access_filter: Mapping[str, Any],
    embedding: Sequence[float] | None = None,
) -> dict[str, Any]:
    """构造 Dense/Sparse/Graph 副本共用的 Chunk payload。

    该 payload 只作为可重建副本输入；最终正文和授权仍以 PostgreSQL Chunk 真值为准。
    """
    vector = [float(value) for value in embedding] if embedding is not None else None
    return {
        "chunkId": _stringify(chunk.get("chunk_id")),
        "kbId": _stringify(chunk.get("kb_id")),
        "documentId": _stringify(chunk.get("document_id")),
        "versionId": _stringify(chunk.get("version_id")),
        "content": chunk.get("content"),
        "contentHash": chunk.get("content_hash"),
        "pageNo": chunk.get("page_no"),
        "section": chunk.get("section"),
        "securityLevel": chunk.get("security_level"),
        "documentStatus": document_status,
        "versionStatus": version_status,
        "chunkStatus": chunk.get("status"),
        "allowSubjectKeys": list(access_filter.get("allowSubjectKeys") or []),
        "denySubjectKeys": list(access_filter.get("denySubjectKeys") or []),
        "filterHash": access_filter.get("filterHash"),
        "metadata": dict(chunk.get("metadata") or {}),
        "embedding": vector,
        "embeddingDimension": len(vector) if vector is not None else None,
    }
