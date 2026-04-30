"""验证 V1.7 第二阶段：评估闭环可复核、可对比、可生成优化建议。"""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_ROOT.parent
FRONTEND_ROOT = ROOT_DIR / "frontend"
DOCS_ROOT = ROOT_DIR / "docs" / "04-迭代与交付"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """输出明确断言错误，便于验收时快速定位缺失能力。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """按 UTF-8 读取源码或文档，避免 Windows 默认编码影响中文内容。"""
    _assert(path.exists(), f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """检查关键实现片段存在，防止只更新局部契约。"""
    if needle not in source:
        raise AssertionError(message)


def verify_openapi_snapshot_contracts() -> None:
    """确认 QARun 详情和优化草稿 DTO 暴露第二阶段新增字段。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    schemas = schema.get("components", {}).get("schemas", {})

    qa_detail_props = schemas.get("QARunDetailDTO", {}).get("properties", {})
    _assert("pipelineSnapshot" in qa_detail_props, "QARunDetailDTO 缺少 pipelineSnapshot")
    _assert("nodeParamSnapshot" in qa_detail_props, "QARunDetailDTO 缺少 nodeParamSnapshot")

    optimization_props = schemas.get("EvaluationOptimizationDraftResponse", {}).get("properties", {})
    _assert("recommendations" in optimization_props, "优化草稿响应缺少 recommendations")


def verify_snapshot_persistence_guards() -> None:
    """确认 QARun 固化 Pipeline 和节点参数快照，而不是只回读当前配置。"""
    table_source = _read(BACKEND_ROOT / "app/tables.py")
    qa_source = _read(BACKEND_ROOT / "app/services/qa_run_service.py")
    migration_source = _read(BACKEND_ROOT / "migrations/versions/0013_add_v17_qa_run_snapshots.py")

    for needle in ["pipeline_snapshot", "node_param_snapshot"]:
        _assert_contains(table_source, needle, f"qa_runs 表定义缺少 {needle}")
        _assert_contains(migration_source, needle, f"迁移缺少 {needle}")
        _assert_contains(qa_source, needle, f"QA 服务未接入 {needle}")
    _assert_contains(qa_source, "pipelineSnapshot=", "QARun 详情未返回 pipelineSnapshot")
    _assert_contains(qa_source, "nodeParamSnapshot=", "QARun 详情未返回 nodeParamSnapshot")


def verify_evaluation_metrics_and_recommendations() -> None:
    """确认评估结果包含对比指标，优化建议包含样本、参数、影响和风险。"""
    qa_source = _read(BACKEND_ROOT / "app/services/qa_run_service.py")
    schema_source = _read(BACKEND_ROOT / "app/schemas/qa_run.py")
    frontend_types = _read(FRONTEND_ROOT / "src/app/types/qaRun.ts")

    for needle in ["hitCount", "citationCount", "failureReason", "configRevisionId", "nodeParamSnapshot"]:
        _assert_contains(qa_source, needle, f"评估指标缺少 {needle}")
    for needle in ["expectedImpact", "risk", "relatedSampleIds", "paramPath"]:
        _assert_contains(schema_source, needle, f"优化建议 DTO 缺少 {needle}")
        _assert_contains(frontend_types, needle, f"前端优化建议类型缺少 {needle}")


def verify_frontend_v17_evaluation_views() -> None:
    """确认 P10/P08 暴露参数快照、配置效果对比和优化建议入口。"""
    p10_source = _read(FRONTEND_ROOT / "src/app/pages/P10_QAHistory.tsx")
    p08_source = _read(FRONTEND_ROOT / "src/app/pages/P08_ConfigCenter.tsx")

    for needle in ["参数快照", "配置效果对比", "优化建议", "预期影响", "风险", "关联样本"]:
        _assert_contains(p10_source, needle, f"P10 缺少 {needle} 展示")
    for needle in ["优化建议", "评估对比"]:
        _assert_contains(p08_source, needle, f"P08 缺少 {needle} 联动提示")


def verify_docs_and_backlog_are_updated() -> None:
    """确认调优指南与 Sprint/Release/待办文档同步回填第二阶段状态。"""
    guide = _read(DOCS_ROOT / "V1.7-RAG调优指南.md")
    sprint = _read(DOCS_ROOT / "sprints/Sprint-26.md")
    release = _read(DOCS_ROOT / "releases/V1.7-RAG模块化优化规划.md")
    backlog = _read(DOCS_ROOT / "产品待办清单.md")

    for needle in ["参数字典", "推荐范围", "调参流程", "快照", "评估对比", "优化建议"]:
        _assert_contains(guide, needle, f"调优指南缺少 {needle}")
    for backlog_id in ["B-115", "B-116", "B-117", "B-118"]:
        _assert(
            any(backlog_id in line and "| Done |" in line for line in sprint.splitlines()),
            f"Sprint 26 未回填 {backlog_id}",
        )
        _assert(
            any(backlog_id in line and "| Done |" in line for line in release.splitlines()),
            f"Release 规划未回填 {backlog_id}",
        )
        _assert(
            any(backlog_id in line and "| Done |" in line for line in backlog.splitlines()),
            f"产品待办未回填 {backlog_id}",
        )


def main() -> None:
    """执行 V1.7 Sprint 26 评估闭环验收。"""
    verify_openapi_snapshot_contracts()
    verify_snapshot_persistence_guards()
    verify_evaluation_metrics_and_recommendations()
    verify_frontend_v17_evaluation_views()
    verify_docs_and_backlog_are_updated()
    print("V1.7 pipeline evaluation verification passed.")


if __name__ == "__main__":
    main()
