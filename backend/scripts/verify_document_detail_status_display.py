from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.document import IngestJobDTO
from app.services.qa_providers import MilvusDenseRetrievalProvider, ProviderError, _to_milvus_row



class _FailingMilvusClient:
    """模拟 Milvus SDK 底层异常，验证 Provider 不吞掉真实原因。"""

    def has_collection(self, collection_name: str) -> bool:
        return True

    def upsert(self, **_: object) -> None:
        raise RuntimeError("collection default does not exist")


class _MissingCollectionMilvusClient:
    """模拟空 Milvus 环境，验证首次写入会创建可用 Collection。"""

    def __init__(self) -> None:
        self.created = False
        self.upserted = False

    def has_collection(self, collection_name: str) -> bool:
        return False

    def create_collection(self, **kwargs: object) -> None:
        self.created = kwargs.get("collection_name") == "default"

    def upsert(self, **_: object) -> None:
        self.upserted = True


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def verify_milvus_error_keeps_root_cause() -> None:
    """Milvus upsert 失败时，页面排障需要看到 SDK 返回的底层原因。"""
    provider = object.__new__(MilvusDenseRetrievalProvider)
    provider._collection = "default"
    provider._client = _FailingMilvusClient()

    try:
        provider.upsert_chunks(
            [
                {
                    "chunkId": "chunk-1",
                    "kbId": "kb-1",
                    "documentId": "doc-1",
                    "versionId": "ver-1",
                    "embedding": [0.1, 0.2],
                }
            ]
        )
    except ProviderError as exc:
        message = str(exc)
    else:
        raise AssertionError("Milvus upsert failure should raise ProviderError.")

    _assert("Milvus dense index upsert failed" in message, "Provider 错误缺少稳定摘要")
    _assert("collection default does not exist" in message, "Provider 错误缺少 Milvus 底层原因")


def verify_milvus_collection_auto_create() -> None:
    """Milvus Collection 缺失时，Dense Provider 应按首批向量维度初始化。"""
    provider = object.__new__(MilvusDenseRetrievalProvider)
    provider._collection = "default"
    client = _MissingCollectionMilvusClient()
    provider._client = client

    provider.upsert_chunks(
        [
            {
                "chunkId": "chunk-1",
                "kbId": "kb-1",
                "documentId": "doc-1",
                "versionId": "ver-1",
                "embedding": [0.1, 0.2],
            }
        ]
    )

    _assert(client.created, "Milvus Collection 缺失时未自动创建")
    _assert(client.upserted, "Milvus Collection 创建后未继续 upsert")


def verify_milvus_delete_missing_collection_is_idempotent() -> None:
    """重试入库会先删除旧副本；Collection 缺失时 delete 应视为已清理。"""
    provider = object.__new__(MilvusDenseRetrievalProvider)
    provider._collection = "default"
    provider._client = _MissingCollectionMilvusClient()

    summary = provider.delete_chunks([UUID("00000000-0000-0000-0000-000000000001")])

    _assert(summary["operation"] == "delete", "delete 空范围应返回删除诊断")
    _assert(summary["chunkCount"] == 1, "Collection 缺失时仍应按请求数量返回诊断")


def verify_milvus_payload_normalizes_nullable_scalars() -> None:
    """Milvus 标量字段不能写入 nil；可空来源字段需在 Provider 边界归一化。"""
    row = _to_milvus_row(
        {
            "chunkId": "chunk-1",
            "kbId": "kb-1",
            "documentId": "doc-1",
            "versionId": "ver-1",
            "pageNo": None,
            "section": None,
            "contentHash": None,
            "embedding": [0.1, 0.2],
        }
    )

    _assert(row["page_no"] == 0, "pageNo 为空时未归一化为 Milvus INT64 哨兵值")
    _assert(row["section"] == "", "section 为空时未归一化为空字符串")
    _assert(row["content_hash"] == "", "contentHash 为空时未归一化为空字符串")


def verify_ingest_job_result_summary_contract() -> None:
    """入库作业必须把阶段诊断摘要传到前端，避免用总状态推导每个阶段。"""
    _assert("resultSummary" in IngestJobDTO.model_fields, "IngestJobDTO 缺少 resultSummary")

    frontend_type = _read("frontend/src/app/types/document.ts")
    adapter = _read("frontend/src/app/adapters/documentAdapter.ts")

    _assert("resultSummary" in frontend_type, "前端 IngestJobDTO 类型缺少 resultSummary")
    _assert("error_summary" in adapter, "前端入库作业阶段未读取 resultSummary.error_summary")
    _assert("formatIndexStageStatus" in adapter, "前端未将底层状态转换为可读展示文案")
    _assert("inferMissingReplicaStatus" in adapter, "前端未兼容历史作业缺失副本阶段摘要")


def verify_table_wrapping_guards() -> None:
    """文档详情表格的表头、状态徽标和长列应避免异常换行。"""
    table = _read("frontend/src/app/components/rag/Table.tsx")
    badge = _read("frontend/src/app/components/rag/Badge.tsx")
    page = _read("frontend/src/app/pages/P07_DocumentDetail.tsx")

    _assert("overflow-x-auto" in table, "表格容器缺少横向滚动保护")
    _assert("whitespace-nowrap" in table, "表头缺少不换行保护")
    _assert("whitespace-nowrap" in badge, "Badge 缺少不换行保护")
    _assert("副本状态" in page, "版本页仍使用容易混淆的索引阶段表头")


def main() -> None:
    verify_milvus_error_keeps_root_cause()
    verify_milvus_collection_auto_create()
    verify_milvus_delete_missing_collection_is_idempotent()
    verify_milvus_payload_normalizes_nullable_scalars()
    verify_ingest_job_result_summary_contract()
    verify_table_wrapping_guards()
    print("Document detail status display verification passed.")


if __name__ == "__main__":
    main()
