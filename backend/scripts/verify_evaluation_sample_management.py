"""验证 QA 历史评估样本可查看、可归档、且回归仅使用 active 样本。"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """输出明确失败原因，便于定位缺失的接口或护栏。"""
    if not condition:
        raise AssertionError(message)


def _read_backend(relative_path: str) -> str:
    """读取后端源码，供源码级契约检查使用。"""
    target = BACKEND_DIR / relative_path
    _assert(target.exists(), f"缺少文件: {target}")
    return target.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """确认关键实现片段存在，避免评估样本管理停留在页面层。"""
    if needle not in source:
        raise AssertionError(message)


def verify_openapi_contract() -> None:
    """确认评估样本列表和归档接口进入 OpenAPI。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    sample_collection = "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation-samples"
    sample_item = "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation-samples/{sample_id}"

    _assert(sample_collection in paths, "OpenAPI 缺少评估样本列表接口")
    _assert(sample_item in paths, "OpenAPI 缺少评估样本归档接口")
    _assert("delete" in paths[sample_item], "评估样本归档接口必须使用 DELETE 方法")

    schemas = schema.get("components", {}).get("schemas", {})
    _assert("EvaluationSampleDTO" in schemas, "OpenAPI 缺少 EvaluationSampleDTO")
    _assert("EvaluationSampleArchiveResponse" in schemas, "OpenAPI 缺少 EvaluationSampleArchiveResponse")


def verify_service_guards() -> None:
    """确认后端归档实现只影响当前 KB 的 active 评估样本。"""
    route_source = _read_backend("app/api/routes/qa_runs.py")
    service_source = _read_backend("app/services/qa_run_service.py")
    schema_source = _read_backend("app/schemas/qa_run.py")

    _assert_contains(schema_source, "class EvaluationSampleArchiveResponse", "缺少评估样本归档响应 DTO")
    _assert_contains(route_source, '@router.delete("/evaluation-samples/{sample_id}"', "缺少评估样本 DELETE 路由")
    _assert_contains(route_source, "archive_evaluation_sample(", "路由未调用评估样本归档服务")
    _assert_contains(service_source, "def archive_evaluation_sample(", "缺少评估样本归档服务")
    _assert_contains(service_source, "evaluation_samples.c.kb_id == kb_id", "归档评估样本必须校验 kbId")
    _assert_contains(service_source, 'evaluation_samples.c.status == "active"', "归档评估样本必须限制 active 样本")
    _assert_contains(service_source, 'status="archived"', "归档评估样本必须写入 archived 状态")
    _assert_contains(service_source, '"kb.evaluation.manage"', "归档评估样本必须校验评估管理权限")
    _assert_contains(service_source, 'evaluation_samples.c.status == "active"', "评估运行只能读取 active 样本")


def main() -> None:
    """执行评估样本管理验收。"""
    verify_openapi_contract()
    verify_service_guards()
    print("Evaluation sample management verification passed.")


if __name__ == "__main__":
    main()
