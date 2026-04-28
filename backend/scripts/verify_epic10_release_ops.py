"""Epic10 发布验收与运维治理的最小验证脚本。

该脚本不连接数据库，只验证 OpenAPI Schema、关键接口声明和发布验收文档是否齐备，
用于本地或测试环境发布前的快速冒烟检查。
"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """输出清晰失败原因，避免发布检查只留下 AssertionError。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """读取 UTF-8 文档内容，并在缺失时给出可定位路径。"""
    _assert(path.exists(), f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def verify_openapi_schema() -> None:
    """校验 FastAPI 可生成 OpenAPI，且包含 Epic10 需要的审计与健康检查接口。"""
    app = create_app()
    client = TestClient(app)
    response = client.get("/openapi.json")
    _assert(response.status_code == 200, "OpenAPI Schema 无法生成")
    schema = response.json()
    paths = schema.get("paths", {})
    required_paths = [
        "/api/v1/health",
        "/api/v1/health/dependencies",
        "/api/v1/audit-logs",
    ]
    for path in required_paths:
        _assert(path in paths, f"OpenAPI 缺少接口: {path}")
    _assert("AuditLogDTO" in schema.get("components", {}).get("schemas", {}), "OpenAPI 缺少 AuditLogDTO")


def verify_release_docs() -> None:
    """校验 Epic10 交付文档已经覆盖部署、备份恢复、验证脚本和验收结果。"""
    ops_doc = _read(ROOT_DIR / "docs/06-发布与运维/发布验收与运维手册.md")
    for keyword in ["本地环境部署", "测试环境部署", "外部依赖健康检查", "备份恢复", "发布检查"]:
        _assert(keyword in ops_doc, f"运维手册缺少章节或关键字: {keyword}")

    test_plan = _read(ROOT_DIR / "docs/05-测试与验收/测试计划.md")
    _assert("verify_epic10_release_ops.py" in test_plan, "测试计划未纳入 Epic10 验证脚本")

    checklist = _read(ROOT_DIR / "docs/05-测试与验收/验收清单.md")
    _assert("| T-003 |" in checklist, "验收清单缺少接口与审计治理项")
    _assert("通过" in checklist, "验收清单未回填结果")


def main() -> None:
    """执行 Epic10 发布前最小验收检查。"""
    verify_openapi_schema()
    verify_release_docs()
    print("Epic10 release ops verification passed.")


if __name__ == "__main__":
    main()
