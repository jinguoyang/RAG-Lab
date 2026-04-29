"""Sprint 16 知识库治理与文档质量的最小验证脚本。"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """提供明确失败原因，避免 Sprint 验收定位困难。"""
    if not condition:
        raise AssertionError(message)


def _read_backend(relative_path: str) -> str:
    """读取后端源码，供源码护栏检查复用。"""
    return (BACKEND_DIR / relative_path).read_text(encoding="utf-8")


def verify_document_quality_contract() -> None:
    """校验文档质量检查接口和诊断类型进入 OpenAPI 与服务层。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/documents/quality-summary" in paths,
        "OpenAPI 缺少文档质量检查接口",
    )
    schemas = schema.get("components", {}).get("schemas", {})
    _assert("DocumentQualitySummaryDTO" in schemas, "OpenAPI 缺少 DocumentQualitySummaryDTO")

    source = _read_backend("app/services/document_service.py")
    for keyword in ["parse_failed", "empty_chunk", "duplicate_chunk", "permission_filter_missing"]:
        _assert(keyword in source, f"文档质量诊断缺少类型: {keyword}")


def verify_bulk_governance_contract() -> None:
    """校验批量治理入口覆盖重解析、重建索引和停用动作。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/documents/batch-governance" in paths,
        "OpenAPI 缺少文档批量治理接口",
    )
    schemas = schema.get("components", {}).get("schemas", {})
    _assert("BulkDocumentGovernanceRequest" in schemas, "OpenAPI 缺少 BulkDocumentGovernanceRequest")

    source = _read_backend("app/services/document_service.py")
    for keyword in ["confirmImpact must be true.", "reparse", "rebuild_index", "document.batch_disable"]:
        _assert(keyword in source, f"批量治理实现缺少关键逻辑: {keyword}")


def verify_chunk_governance_contract() -> None:
    """校验 Chunk 排除标记、治理备注和权限继承说明。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/chunks/{chunk_id}/governance" in paths,
        "OpenAPI 缺少 Chunk 治理接口",
    )
    schemas = schema.get("components", {}).get("schemas", {})
    _assert("ChunkGovernanceResponse" in schemas, "OpenAPI 缺少 ChunkGovernanceResponse")

    document_source = _read_backend("app/services/document_service.py")
    qa_source = _read_backend("app/services/qa_run_service.py")
    graph_source = _read_backend("app/services/graph_service.py")
    _assert("permissionInheritance" in document_source, "Chunk 治理响应缺少权限继承说明")
    _assert("chunk.governance_update" in document_source, "Chunk 治理缺少审计动作")
    _assert("_chunk_is_governance_excluded" in qa_source, "QA 链路未过滤治理排除 Chunk")
    _assert("governance.get(\"excluded\") is True" in graph_source, "图支撑 Chunk 未过滤治理排除标记")


def main() -> None:
    """执行 Sprint 16 当前已落地范围的验收检查。"""
    verify_document_quality_contract()
    verify_bulk_governance_contract()
    verify_chunk_governance_contract()
    print("Sprint 16 KB governance verification passed.")


if __name__ == "__main__":
    main()
