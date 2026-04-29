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


def main() -> None:
    """执行 Sprint 16 当前已落地范围的验收检查。"""
    verify_document_quality_contract()
    print("Sprint 16 KB governance verification passed.")


if __name__ == "__main__":
    main()
