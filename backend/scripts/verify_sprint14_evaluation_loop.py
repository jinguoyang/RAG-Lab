"""Sprint 14 V1.1 质量回归闭环验证脚本。"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """输出可定位错误信息，避免验收脚本只抛通用断言异常。"""
    if not condition:
        raise AssertionError(message)


def _read_backend(relative_path: str) -> str:
    """读取后端源码，做关键护栏断言。"""
    target = BACKEND_DIR / relative_path
    _assert(target.exists(), f"缺少文件: {target}")
    return target.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """检查关键实现片段存在。"""
    if needle not in source:
        raise AssertionError(message)


def verify_openapi_paths() -> None:
    """确认 V1.1 评估运行接口进入 OpenAPI。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    required = [
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs/{evaluation_run_id}",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs/{evaluation_run_id}/retry",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs/{evaluation_run_id}/cancel",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs/{evaluation_run_id}/export",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs/{evaluation_run_id}/config-diff",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs/{evaluation_run_id}/optimization-draft",
    ]
    for path in required:
        _assert(path in paths, f"OpenAPI 缺少 V1.1 接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for schema_name in [
        "EvaluationRunDTO",
        "EvaluationResultDTO",
        "EvaluationRunDetailDTO",
        "EvaluationRunConfigDiffDTO",
        "EvaluationOptimizationDraftResponse",
    ]:
        _assert(schema_name in schemas, f"OpenAPI 缺少 DTO: {schema_name}")


def verify_source_guards() -> None:
    """检查 V1.1 闭环关键实现存在。"""
    qa_source = _read_backend("app/services/qa_run_service.py")
    table_source = _read_backend("app/tables.py")
    route_source = _read_backend("app/api/routes/qa_runs.py")

    _assert_contains(table_source, 'evaluation_runs = sa.Table(', "缺少 evaluation_runs 表定义")
    _assert_contains(table_source, 'evaluation_results = sa.Table(', "缺少 evaluation_results 表定义")
    _assert_contains(qa_source, "def create_evaluation_run(", "缺少创建评估运行服务")
    _assert_contains(qa_source, "def retry_evaluation_run(", "缺少重试评估运行服务")
    _assert_contains(qa_source, "def cancel_evaluation_run(", "缺少取消评估运行服务")
    _assert_contains(qa_source, "def export_evaluation_run(", "缺少评估导出服务")
    _assert_contains(qa_source, "def get_evaluation_run_config_diff(", "缺少配置差异服务")
    _assert_contains(qa_source, "def create_optimization_draft_from_evaluation_run(", "缺少优化草稿服务")
    _assert_contains(route_source, '@router.post("/evaluation/runs"', "缺少评估运行创建路由")


def main() -> None:
    """执行 Sprint 14 可复核验证。"""
    verify_openapi_paths()
    verify_source_guards()
    print("Sprint 14 evaluation loop verification passed.")


if __name__ == "__main__":
    main()
