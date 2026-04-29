"""Sprint 18 协作与治理增强的最小验证脚本。

脚本检查 V1.3 协作治理接口、前端入口和状态文档，避免只完成文档层面的
交付声明。
"""

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
    """输出明确失败原因，避免验收脚本只留下 AssertionError。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """按 UTF-8 读取文件，并在缺失时给出完整路径。"""
    _assert(path.exists(), f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _openapi() -> dict:
    """生成当前 OpenAPI Schema。"""
    return TestClient(create_app()).get("/openapi.json").json()


def verify_config_release_records() -> None:
    """校验配置发布记录、变更说明和回滚确认入口。"""
    schema = _openapi()
    paths = schema.get("paths", {})
    for path in [
        "/api/v1/knowledge-bases/{kb_id}/config-revisions/release-records",
        "/api/v1/knowledge-bases/{kb_id}/config-revisions/{revision_id}/release-records",
        "/api/v1/knowledge-bases/{kb_id}/config-revisions/{revision_id}/rollback-confirmation",
    ]:
        _assert(path in paths, f"OpenAPI 缺少配置发布治理接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for name in ["ConfigReleaseRecordDTO", "ConfigReleaseRecordCreateRequest", "ConfigRollbackConfirmRequest"]:
        _assert(name in schemas, f"OpenAPI 缺少配置发布 DTO: {name}")

    page = _read(FRONTEND_DIR / "src/app/pages/P08_ConfigCenter.tsx")
    for keyword in ["发布记录", "变更说明", "回滚确认", "fetchConfigReleaseRecords"]:
        _assert(keyword in page, f"P08 缺少配置发布入口: {keyword}")


def verify_qa_collaboration() -> None:
    """校验 QA Run 分享、评论、责任人和处理状态。"""
    schema = _openapi()
    paths = schema.get("paths", {})
    for path in [
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}/collaboration",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}/collaboration/comments",
    ]:
        _assert(path in paths, f"OpenAPI 缺少 QA 协作接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for name in ["QARunCollaborationDTO", "QARunCollaborationUpdateRequest", "QARunCommentCreateRequest"]:
        _assert(name in schemas, f"OpenAPI 缺少 QA 协作 DTO: {name}")

    page = _read(FRONTEND_DIR / "src/app/pages/P10_QAHistory.tsx")
    for keyword in ["协作处理", "责任人", "处理状态", "addQARunComment"]:
        _assert(keyword in page, f"P10 缺少 QA 协作入口: {keyword}")


def verify_audit_report_and_export() -> None:
    """校验审计报表、保留策略和导出能力。"""
    schema = _openapi()
    paths = schema.get("paths", {})
    for path in ["/api/v1/audit-logs/report", "/api/v1/audit-logs/export"]:
        _assert(path in paths, f"OpenAPI 缺少审计治理接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for name in ["AuditReportResponse", "AuditExportResponse"]:
        _assert(name in schemas, f"OpenAPI 缺少审计治理 DTO: {name}")

    source = _read(BACKEND_DIR / "app/services/audit_service.py")
    for keyword in ["retentionPolicy", "groupByAction", "csv", "markdown"]:
        _assert(keyword in source, f"审计服务缺少报表或导出逻辑: {keyword}")


def verify_effective_permission_explainer() -> None:
    """校验有效权限模拟和权限来源解释。"""
    schema = _openapi()
    paths = schema.get("paths", {})
    _assert(
        "/api/v1/knowledge-bases/{kb_id}/permissions/effective-simulations" in paths,
        "OpenAPI 缺少有效权限模拟接口",
    )
    schemas = schema.get("components", {}).get("schemas", {})
    for name in ["EffectivePermissionSimulationRequest", "EffectivePermissionSimulationResponse"]:
        _assert(name in schemas, f"OpenAPI 缺少有效权限 DTO: {name}")

    page = _read(FRONTEND_DIR / "src/app/pages/P12_MembersAndPermissions.tsx")
    for keyword in ["权限解释", "simulateEffectivePermission", "来源", "拒绝原因"]:
        _assert(keyword in page, f"P12 缺少有效权限解释入口: {keyword}")


def verify_sprint18_docs_done() -> None:
    """确认 Sprint 18 与产品待办状态已回填。"""
    sprint = _read(ROOT_DIR / "docs/04-迭代与交付/sprints/Sprint-18.md")
    backlog = _read(ROOT_DIR / "docs/04-迭代与交付/产品待办清单.md")
    for item_id in ["B-077", "B-078", "B-079", "B-080"]:
        line = next((row for row in backlog.splitlines() if row.startswith(f"| {item_id} |")), "")
        _assert("| Done | Codex |" in line, f"产品待办 {item_id} 未标记 Done")
    for item_id in ["S18-001", "S18-002", "S18-003", "S18-004"]:
        line = next((row for row in sprint.splitlines() if row.startswith(f"| {item_id} |")), "")
        _assert("| Done |" in line, f"Sprint 18 {item_id} 未标记 Done")


def main() -> None:
    """执行 Sprint 18 验收检查。"""
    verify_config_release_records()
    verify_qa_collaboration()
    verify_audit_report_and_export()
    verify_effective_permission_explainer()
    verify_sprint18_docs_done()
    print("Sprint 18 governance verification passed.")


if __name__ == "__main__":
    main()
