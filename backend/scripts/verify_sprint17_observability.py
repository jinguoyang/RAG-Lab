"""Sprint 17 稳定性与观测的最小验证脚本。

脚本以 OpenAPI 契约和源码护栏为主，不依赖真实外部 Provider，确保本地
V1.3 验收可以稳定复跑。
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
    """输出明确失败原因，避免 Sprint 验收定位困难。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """按 UTF-8 读取文件，并在缺失时给出可读错误。"""
    _assert(path.exists(), f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _openapi() -> dict:
    """生成当前 FastAPI OpenAPI Schema，供接口契约检查。"""
    return TestClient(create_app()).get("/openapi.json").json()


def verify_observability_contract() -> None:
    """校验运行指标、慢链路、错误摘要和健康面板接口。"""
    schema = _openapi()
    paths = schema.get("paths", {})
    required_paths = [
        "/api/v1/knowledge-bases/{kb_id}/observability/metrics",
        "/api/v1/knowledge-bases/{kb_id}/observability/slow-links",
        "/api/v1/knowledge-bases/{kb_id}/observability/error-summary",
        "/api/v1/knowledge-bases/{kb_id}/observability/health-panel",
    ]
    for path in required_paths:
        _assert(path in paths, f"OpenAPI 缺少观测接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for name in [
        "RuntimeMetricsResponse",
        "SlowLinkDiagnosticsResponse",
        "ErrorSummaryResponse",
        "HealthPanelResponse",
    ]:
        _assert(name in schemas, f"OpenAPI 缺少观测 DTO: {name}")

    source = _read(BACKEND_DIR / "app/services/observability_service.py")
    for keyword in [
        "qa_runs.c.metrics",
        "ingest_jobs.c.result_summary",
        "qa_run_trace_steps.c.step_key",
        "permissionFilter",
        "generation",
    ]:
        _assert(keyword in source, f"观测服务缺少关键采集逻辑: {keyword}")


def verify_idempotency_and_compensation_guards() -> None:
    """校验重复补偿不会创建不可解释的重复作业。"""
    document_source = _read(BACKEND_DIR / "app/services/document_service.py")
    for keyword in [
        "retryOfJobId",
        "idempotency",
        "existing_retry",
        "compensationStatus",
    ]:
        _assert(keyword in document_source, f"Ingest 重试幂等护栏缺少关键字: {keyword}")

    observability_source = _read(BACKEND_DIR / "app/services/observability_service.py")
    _assert("compensationStatus" in observability_source, "健康面板未暴露任务补偿状态")


def verify_backup_drill_contract() -> None:
    """校验备份恢复演练记录接口和运维文档回填。"""
    schema = _openapi()
    paths = schema.get("paths", {})
    for path in [
        "/api/v1/knowledge-bases/{kb_id}/backup-drills",
        "/api/v1/knowledge-bases/{kb_id}/backup-drills/{drill_id}",
    ]:
        _assert(path in paths, f"OpenAPI 缺少备份恢复演练接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for name in ["BackupDrillCreateRequest", "BackupDrillDTO"]:
        _assert(name in schemas, f"OpenAPI 缺少备份恢复 DTO: {name}")

    ops_doc = _read(ROOT_DIR / "docs/06-发布与运维/发布验收与运维手册.md")
    for keyword in [
        "备份恢复演练记录",
        "/api/v1/knowledge-bases/{kbId}/backup-drills",
        "restoredObjects",
        "residualRisks",
    ]:
        _assert(keyword in ops_doc, f"运维手册缺少备份演练说明: {keyword}")


def verify_sprint17_docs_done() -> None:
    """确认 Sprint 17 与产品待办状态已回填。"""
    sprint = _read(ROOT_DIR / "docs/04-迭代与交付/sprints/Sprint-17.md")
    backlog = _read(ROOT_DIR / "docs/04-迭代与交付/产品待办清单.md")
    for item_id in ["B-073", "B-074", "B-075", "B-076"]:
        _assert(f"| {item_id} " in backlog and f"| {item_id} " in backlog, f"产品待办缺少 {item_id}")
        line = next((row for row in backlog.splitlines() if row.startswith(f"| {item_id} |")), "")
        _assert("| Done | Codex |" in line, f"产品待办 {item_id} 未标记 Done")
    for item_id in ["S17-001", "S17-002", "S17-003", "S17-004"]:
        line = next((row for row in sprint.splitlines() if row.startswith(f"| {item_id} |")), "")
        _assert("| Done |" in line, f"Sprint 17 {item_id} 未标记 Done")


def main() -> None:
    """执行 Sprint 17 验收检查。"""
    verify_observability_contract()
    verify_idempotency_and_compensation_guards()
    verify_backup_drill_contract()
    verify_sprint17_docs_done()
    print("Sprint 17 observability verification passed.")


if __name__ == "__main__":
    main()
