"""验证文档删除流程的源码级契约。

本脚本避免依赖真实 MinIO、Milvus、OpenSearch、Neo4j 常驻服务；
重点校验业务删除、外部副本清理和前端入口是否按设计形成闭环。
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


def _read(relative_path: str) -> str:
    """读取仓库文件，统一使用 UTF-8 以避免中文注释和文案乱码。"""
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _assert(condition: bool, message: str) -> None:
    """用明确错误说明指出文档删除流程缺失项。"""
    if not condition:
        raise AssertionError(message)


def _assert_contains(source: str, needle: str, message: str) -> None:
    """校验关键实现片段存在，避免验收脚本被外部服务依赖阻塞。"""
    _assert(needle in source, message)


def verify_backend_api_contract() -> None:
    """校验删除接口、请求 DTO 和响应 DTO 已暴露给 API 层。"""
    schemas = _read("backend/app/schemas/document.py")
    routes = _read("backend/app/api/routes/documents.py")

    _assert_contains(schemas, "class DocumentDeleteRequest", "缺少文档删除请求 DTO")
    _assert_contains(schemas, "confirmImpact: bool", "删除请求缺少二次确认字段")
    _assert_contains(schemas, "class DocumentDeleteResponse", "缺少文档删除响应 DTO")
    _assert_contains(schemas, "cleanupJobs: list", "删除响应缺少清理作业摘要")
    _assert_contains(routes, "@router.delete", "Documents 路由缺少 DELETE 接口")
    _assert_contains(routes, "delete_document_endpoint", "缺少文档删除 endpoint")
    _assert_contains(routes, "delete_document(", "Endpoint 未调用服务层删除函数")


def verify_backend_service_contract() -> None:
    """校验服务层按 PostgreSQL 真值和外部副本清理边界实现删除。"""
    source = _read("backend/app/services/document_service.py")

    _assert_contains(source, "def delete_document(", "服务层缺少 delete_document 函数")
    _assert_contains(source, "document.delete_requested", "删除流程缺少审计动作")
    _assert_contains(source, 'status="archived"', "删除流程未归档 documents.status")
    _assert_contains(source, "deleted_at=func.now()", "删除流程未写入 deleted_at")
    _assert_contains(source, 'status="deleted"', "删除流程未将 Chunk 或文件标记为 deleted")
    _assert_contains(source, "chunk_status=\"deleted\"", "删除流程未同步访问过滤摘要状态")
    _assert_contains(source, "mark_graph_snapshots_stale(session, kb_id, \"document_deleted\"", "删除流程未标记图快照 stale")
    _assert_contains(source, "storage.delete_object", "删除流程未调用对象存储物理删除")
    _assert('target_store="minio"' not in source, "MinIO 不允许写入 index_sync_jobs.target_store")
    _assert("syncJobId=None" in source, "MinIO 清理摘要应明确不关联 IndexSyncJob")
    _assert_contains(source, 'sync_type="delete"', "删除流程未创建 delete 类型清理作业")
    _assert_contains(source, "provider_set.dense.delete_chunks", "删除流程未调用 Milvus 删除")
    _assert_contains(source, "provider_set.sparse.delete_chunks", "删除流程未调用 OpenSearch 删除")
    _assert_contains(source, "provider_set.graph.delete_chunks", "删除流程未调用 Neo4j 删除")
    _assert_contains(source, "warnings.append", "删除流程未记录外部清理失败 warning")


def verify_deleted_content_is_filtered() -> None:
    """校验后续 QA 和图支撑查询仍依赖 PostgreSQL 删除状态过滤。"""
    qa_service = _read("backend/app/services/qa_run_service.py")
    graph_service = _read("backend/app/services/graph_service.py")

    _assert_contains(qa_service, "documents.c.deleted_at.is_(None)", "QA 回表缺少文档逻辑删除过滤")
    _assert_contains(qa_service, 'documents.c.status == "active"', "QA 回表缺少文档 active 状态过滤")
    _assert_contains(qa_service, 'chunks.c.status == "active"', "QA 回表缺少 Chunk active 状态过滤")
    _assert_contains(graph_service, "documents.c.deleted_at.is_(None)", "图支撑 Chunk 缺少文档逻辑删除过滤")
    _assert_contains(graph_service, 'chunks.c.status == "active"', "图支撑 Chunk 缺少 Chunk active 状态过滤")


def verify_frontend_contract() -> None:
    """校验 P06 提供删除入口并调用 DELETE API。"""
    types = _read("frontend/src/app/types/document.ts")
    service = _read("frontend/src/app/services/documentService.ts")
    page = _read("frontend/src/app/pages/P06_DocumentCenter.tsx")

    _assert_contains(types, "DocumentDeleteResponse", "前端缺少删除响应类型")
    _assert_contains(service, "deleteDocument", "前端服务层缺少 deleteDocument")
    _assert_contains(service, "apiDeleteJson", "前端删除接口未提交确认请求体")
    _assert_contains(page, "Trash2", "P06 缺少删除图标入口")
    _assert_contains(page, "handleDeleteDocument", "P06 缺少单文档删除处理函数")
    _assert_contains(page, "confirmImpact: true", "P06 删除请求未传二次确认字段")


def main() -> None:
    """执行文档删除流程源码级验收。"""
    verify_backend_api_contract()
    verify_backend_service_contract()
    verify_deleted_content_is_filtered()
    verify_frontend_contract()
    print("Document delete flow verification passed.")


if __name__ == "__main__":
    main()
