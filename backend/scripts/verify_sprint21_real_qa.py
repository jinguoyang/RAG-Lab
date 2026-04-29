"""验证 Sprint 21 真实 QA 检索与生成链路。

脚本采用源码级护栏检查，避免本地必须常驻 Milvus、OpenSearch、Neo4j 和 LLM 服务。
真实环境可在此基础上追加网络级端到端复测；这里确保代码不再用 mock/fallback 冒充成功。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    """按 UTF-8 读取仓库文件，避免中文注释和验收提示乱码。"""
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    """用明确错误说明指出 Sprint 21 未完成项。"""
    if not condition:
        raise AssertionError(message)


def _assert_contains(source: str, needle: str, message: str) -> None:
    """校验关键实现片段存在，避免验收脚本被环境依赖阻塞。"""
    _assert(needle in source, message)


def _assert_not_contains(source: str, needle: str, message: str) -> None:
    """校验真实链路中不再保留会冒充成功的 mock/fallback 路径。"""
    _assert(needle not in source, message)


def verify_trace_stage_contract() -> None:
    """校验 QARun Trace 覆盖 Sprint 21 要求的真实执行阶段。"""
    source = _read("app/services/qa_run_service.py")
    for step_key in [
        '"queryRewrite"',
        '"embedding"',
        '"denseRetrieval"',
        '"sparseRetrieval"',
        '"graphRetrieval"',
        '"fusion"',
        '"rerank"',
        '"permissionFilter"',
        '"generation"',
        '"citation"',
    ]:
        _assert_contains(source, step_key, f"QARun Trace 缺少阶段: {step_key}")


def verify_no_mock_success_path() -> None:
    """校验 QA 主链路不再用 mock evidence 或 PostgreSQL fallback 覆盖真实检索结果。"""
    source = _read("app/services/qa_run_service.py")
    _assert_not_contains(source, "MOCK_EVIDENCE_CHUNK_ID", "QA 链路仍保留 mock evidence 成功路径")
    _assert_not_contains(source, "fallbackEvidence", "QA 链路仍会用 fallbackEvidence 冒充可回答证据")
    _assert_not_contains(source, "postgresChunkFallback", "QA 链路仍会用 PostgreSQL fallback 覆盖真实 Provider 候选")


def verify_postgres_authorization_contract() -> None:
    """校验 Provider 候选进入 Evidence 前会回表 PostgreSQL 并按 Chunk ACL 裁剪。"""
    source = _read("app/services/qa_run_service.py")
    _assert_contains(source, "chunk_access_filters", "权限裁剪未读取 chunk_access_filters")
    _assert_contains(source, "allow_subject_keys", "权限裁剪未校验 allow_subject_keys")
    _assert_contains(source, "deny_subject_keys", "权限裁剪未校验 deny_subject_keys")
    _assert_contains(source, "drop_reason=", "候选被裁剪时未持久化 drop_reason")
    _assert_contains(source, '"truthSource": "postgres_chunks"', "授权 Evidence 未标记 PostgreSQL 真值来源")


def verify_fusion_and_rerank_contract() -> None:
    """校验 Dense/Sparse/Graph 候选先融合去重，再进入 Rerank 和权限裁剪。"""
    source = _read("app/services/qa_run_service.py")
    _assert_contains(source, "_fuse_provider_candidates(", "缺少真实候选 Fusion 实现")
    _assert_contains(source, "matchedChannels", "Fusion 未保留多路命中来源")
    _assert_contains(source, "provider_set.rerank.rerank", "QA 链路未调用 Rerank Provider")


def verify_citation_location_contract() -> None:
    """校验 Citation 可定位到文档、版本、页码、章节和 Chunk。"""
    source = _read("app/services/qa_run_service.py")
    for key in ["documentId", "documentName", "versionId", "chunkId", "chunkIndex", "pageNo", "section"]:
        _assert_contains(source, f'"{key}"', f"Citation 或 Evidence 来源快照缺少 {key}")


def verify_provider_read_contracts() -> None:
    """校验 Milvus、OpenSearch、Neo4j Retrieval Provider 返回真实 chunk_id。"""
    source = _read("app/services/qa_providers.py")
    _assert_contains(source, "self._client.search(", "Milvus Provider 未调用真实 search")
    _assert_contains(source, '"chunk_id"', "Milvus/OpenSearch 检索未返回 chunk_id")
    _assert_contains(source, "self._client.search(index=self._index", "OpenSearch Provider 未调用真实 search")
    _assert_contains(source, "MATCH (e:Entity)-[:SUPPORTED_BY]->(c:ChunkRef)", "Neo4j Provider 未通过 ChunkRef 回落支撑 Chunk")


def main() -> None:
    """执行 Sprint 21 源码级验收。"""
    verify_trace_stage_contract()
    verify_no_mock_success_path()
    verify_postgres_authorization_contract()
    verify_fusion_and_rerank_contract()
    verify_citation_location_contract()
    verify_provider_read_contracts()
    print("Sprint 21 real QA verification passed.")


if __name__ == "__main__":
    main()
