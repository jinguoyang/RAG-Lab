"""验证 Sprint 20 真实索引副本写入链路。

脚本采用源码级护栏检查，避免本地必须常驻 Milvus、OpenSearch、Neo4j；
真实环境可在此基础上追加网络级连通性复测。
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    """读取仓库文件，统一使用 UTF-8 避免中文注释乱码。"""
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    """用明确错误说明指出 Sprint 20 未完成项。"""
    if not condition:
        raise AssertionError(message)


def _assert_contains(source: str, needle: str, message: str) -> None:
    """校验关键实现片段存在，避免验收脚本被环境依赖阻塞。"""
    _assert(needle in source, message)


def verify_provider_write_contracts() -> None:
    """校验 Milvus、OpenSearch、Neo4j Provider 具备真实写入和删除能力。"""
    source = _read("app/services/qa_providers.py")
    _assert_contains(source, "def upsert_chunks(", "Dense/Sparse/Graph Provider 缺少 upsert_chunks 写入契约")
    _assert_contains(source, "def delete_chunks(", "Dense/Sparse/Graph Provider 缺少 delete_chunks 删除契约")
    _assert_contains(source, "self._client.upsert(", "Milvus Provider 未调用真实 upsert")
    _assert_contains(source, "self._client.delete(", "Milvus Provider 未调用真实 delete")
    _assert_contains(source, "self._client.index(", "OpenSearch Provider 未调用真实 index/upsert")
    _assert_contains(source, "self._client.delete(", "OpenSearch Provider 未调用真实 delete")
    _assert_contains(source, "MERGE (entity:Entity", "Neo4j Provider 未写入 Entity 节点")
    _assert_contains(source, "MERGE (chunk:ChunkRef", "Neo4j Provider 未写入 ChunkRef 节点")
    _assert_contains(source, "MERGE (source)-[relation:RELATED_TO", "Neo4j Provider 未写入 RELATED_TO 关系")


def verify_index_sync_worker_contract() -> None:
    """校验 IndexSyncJob 不再只是记录，而会执行 Provider 写入并记录失败。"""
    source = _read("app/services/document_service.py")
    _assert_contains(source, "_run_index_sync_job(", "缺少 IndexSync 执行型 Worker")
    _assert_contains(source, ".upsert_chunks(", "入库 Worker 未调用副本 upsert")
    _assert_contains(source, ".delete_chunks(", "入库 Worker 未调用副本 delete")
    _assert_contains(source, "INDEX_SYNC_FAILED", "副本写入失败未记录统一错误码")
    _assert_contains(source, "targetStore", "失败摘要未包含 targetStore")
    _assert_contains(source, "dense_index_status=dense_status", "版本 Dense 状态未由真实同步结果驱动")
    _assert_contains(source, "sparse_index_status=sparse_status", "版本 Sparse 状态未由真实同步结果驱动")
    _assert_contains(source, "graph_index_status=graph_status", "版本 Graph 状态未由真实同步结果驱动")


def verify_frontend_status_visibility() -> None:
    """校验 P05/P06/P07 能展示 parse、embedding 和各副本阶段状态。"""
    types_source = _read("../frontend/src/app/types/document.ts")
    adapter_source = _read("../frontend/src/app/adapters/documentAdapter.ts")
    p05_source = _read("../frontend/src/app/pages/P05_KBOverview.tsx")
    p06_source = _read("../frontend/src/app/pages/P06_DocumentCenter.tsx")
    p07_source = _read("../frontend/src/app/pages/P07_DocumentDetail.tsx")
    _assert_contains(types_source, "indexStages", "前端 IngestJobViewModel 缺少阶段状态摘要")
    _assert_contains(adapter_source, "denseIndexStatus", "前端适配器未映射 Dense 状态")
    _assert_contains(adapter_source, "sparseIndexStatus", "前端适配器未映射 Sparse 状态")
    _assert_contains(adapter_source, "graphIndexStatus", "前端适配器未映射 Graph 状态")
    _assert_contains(p05_source, "检索与索引", "P05 未展示检索与索引配置状态")
    _assert_contains(p06_source, "indexStages", "P06 未展示入库阶段状态")
    _assert_contains(p07_source, "indexStages", "P07 未展示入库阶段状态")


def main() -> None:
    """执行 Sprint 20 源码级验收。"""
    verify_provider_write_contracts()
    verify_index_sync_worker_contract()
    verify_frontend_status_visibility()
    print("Sprint 20 real index verification passed.")


if __name__ == "__main__":
    main()
