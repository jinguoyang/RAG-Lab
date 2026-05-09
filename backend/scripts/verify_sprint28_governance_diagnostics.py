"""Sprint 28 知识库治理诊断可操作化的最小验证脚本。"""

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
    """提供明确失败原因，便于定位 Sprint 28 诊断字段缺口。"""
    if not condition:
        raise AssertionError(message)


def _read_backend(relative_path: str) -> str:
    """读取后端源码，验证质量诊断已补充可操作详情。"""
    return (BACKEND_DIR / relative_path).read_text(encoding="utf-8")


def _read_frontend(relative_path: str) -> str:
    """读取前端源码，验证索引同步作业已在页面承载。"""
    return (FRONTEND_DIR / relative_path).read_text(encoding="utf-8")


def verify_quality_issue_schema() -> None:
    """确认质量问题 DTO 已兼容性扩展可操作字段。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    properties = schema.get("components", {}).get("schemas", {}).get("DocumentQualityIssueDTO", {}).get("properties", {})
    for field in ["contentHash", "sampleChunkIds", "recommendedAction", "targetStore"]:
        _assert(field in properties, f"DocumentQualityIssueDTO 缺少字段: {field}")


def verify_duplicate_chunk_diagnostics() -> None:
    """确认重复 Chunk 诊断能携带样例和建议动作。"""
    source = _read_backend("app/services/document_service.py")
    for keyword in ["sampleChunkIds=", "contentHash=", "recommendedAction=", "targetStore="]:
        _assert(keyword in source, f"质量诊断实现缺少 {keyword}")


def verify_index_sync_frontend_entries() -> None:
    """确认前端能查询和触发索引副本重建作业。"""
    service = _read_frontend("src/app/services/documentService.ts")
    p06 = _read_frontend("src/app/pages/P06_DocumentCenter.tsx")
    p07 = _read_frontend("src/app/pages/P07_DocumentDetail.tsx")

    for keyword in ["fetchIndexSyncJobs", "rebuildIndexSync"]:
        _assert(keyword in service, f"documentService 缺少 {keyword}")
    for keyword in ["索引同步作业", "fetchIndexSyncJobs", "rebuildIndexSync"]:
        _assert(keyword in p06, f"P06 缺少索引同步入口: {keyword}")
        _assert(keyword in p07, f"P07 缺少索引同步入口: {keyword}")


def main() -> None:
    """执行 Sprint 28 诊断可操作化验收检查。"""
    verify_quality_issue_schema()
    verify_duplicate_chunk_diagnostics()
    verify_index_sync_frontend_entries()
    print("Sprint 28 governance diagnostics verification passed.")


if __name__ == "__main__":
    main()
