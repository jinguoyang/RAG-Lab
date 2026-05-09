"""Sprint 27 知识库治理工作流接入的最小验证脚本。"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """提供明确失败原因，便于定位 Sprint 27 工作流缺口。"""
    if not condition:
        raise AssertionError(message)


def _read_frontend(relative_path: str) -> str:
    """读取前端源码，验证页面已接入治理工作流。"""
    return (FRONTEND_DIR / relative_path).read_text(encoding="utf-8")


def verify_existing_governance_contracts() -> None:
    """确认批量治理和 Chunk 治理接口仍然存在于 OpenAPI。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/documents/batch-governance" in paths,
        "OpenAPI 缺少文档批量治理接口",
    )
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/chunks/{chunk_id}/governance" in paths,
        "OpenAPI 缺少 Chunk 治理接口",
    )


def verify_frontend_governance_services() -> None:
    """确认前端 service 暴露批量治理和 Chunk 治理调用。"""
    service = _read_frontend("src/app/services/documentService.ts")
    for keyword in ["runBulkDocumentGovernance", "updateChunkGovernance"]:
        _assert(keyword in service, f"documentService 缺少 {keyword}")


def verify_governance_pages() -> None:
    """确认 P05/P06/P07 已接入可操作治理入口。"""
    p05 = _read_frontend("src/app/pages/P05_KBOverview.tsx")
    p06 = _read_frontend("src/app/pages/P06_DocumentCenter.tsx")
    p07 = _read_frontend("src/app/pages/P07_DocumentDetail.tsx")

    for keyword in ["openGovernanceIssue", "governanceIssue", "chunkId"]:
        _assert(keyword in p05, f"P05 缺少治理问题跳转能力: {keyword}")
    for keyword in ["selectedDocumentIds", "runBulkDocumentGovernance", "batchOperation", "targetStore"]:
        _assert(keyword in p06, f"P06 缺少批量治理能力: {keyword}")
    for keyword in ["updateChunkGovernance", "governanceNoteInput", "排除 Chunk", "permissionInheritance"]:
        _assert(keyword in p07, f"P07 缺少 Chunk 治理能力: {keyword}")


def main() -> None:
    """执行 Sprint 27 治理工作流验收检查。"""
    verify_existing_governance_contracts()
    verify_frontend_governance_services()
    verify_governance_pages()
    print("Sprint 27 governance workflow verification passed.")


if __name__ == "__main__":
    main()
