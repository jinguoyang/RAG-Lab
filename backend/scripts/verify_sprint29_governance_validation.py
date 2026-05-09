"""Sprint 29 治理后验证闭环的最小验证脚本。"""

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
    """提供明确失败原因，便于定位治理后验证闭环缺口。"""
    if not condition:
        raise AssertionError(message)


def _read_backend(relative_path: str) -> str:
    """读取后端源码，复核治理排除不绕过 QA 和图支撑过滤。"""
    return (BACKEND_DIR / relative_path).read_text(encoding="utf-8")


def _read_frontend(relative_path: str) -> str:
    """读取前端源码，验证 P05 已承载治理后验证摘要。"""
    return (FRONTEND_DIR / relative_path).read_text(encoding="utf-8")


def verify_existing_evaluation_contract() -> None:
    """确认仍复用已有 EvaluationRun 接口作为治理后验证入口。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/evaluation/runs" in paths,
        "OpenAPI 缺少 EvaluationRun 创建接口",
    )


def verify_governance_exclusion_guards() -> None:
    """确认被治理排除的 Chunk 不进入 QA Evidence 或图支撑 Chunk。"""
    qa_source = _read_backend("app/services/qa_run_service.py")
    graph_source = _read_backend("app/services/graph_service.py")
    _assert("_chunk_is_governance_excluded" in qa_source, "QA 链路缺少治理排除判断")
    _assert("governanceExcluded" in qa_source, "QA 候选缺少治理排除原因")
    _assert('governance.get("excluded") is True' in graph_source, "图支撑 Chunk 缺少治理排除过滤")


def verify_p05_validation_summary() -> None:
    """确认 P05 已展示最近治理动作和治理后验证入口。"""
    p05 = _read_frontend("src/app/pages/P05_KBOverview.tsx")
    for keyword in ["最近治理动作", "治理验证摘要", "验证治理效果", "fetchAuditLogs", "createEvaluationRun", "fetchEvaluationRuns"]:
        _assert(keyword in p05, f"P05 缺少治理后验证能力: {keyword}")


def main() -> None:
    """执行 Sprint 29 治理后验证闭环验收检查。"""
    verify_existing_evaluation_contract()
    verify_governance_exclusion_guards()
    verify_p05_validation_summary()
    print("Sprint 29 governance validation verification passed.")


if __name__ == "__main__":
    main()
