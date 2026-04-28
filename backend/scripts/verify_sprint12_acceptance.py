"""Sprint 12 V1.0 验收硬化脚本。

脚本采用 OpenAPI 契约检查和源码级护栏检查，不连接真实 PostgreSQL 或外部
Provider。它用于发布前快速确认主链路接口、权限回归边界和验收清单回填状态。
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
    """输出明确失败原因，避免验收脚本只留下不可定位的 AssertionError。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """读取 UTF-8 文件，并在缺失时给出完整路径。"""
    _assert(path.exists(), f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _read_backend(relative_path: str) -> str:
    """读取后端源码文件，供源码级护栏检查复用。"""
    return _read(BACKEND_DIR / relative_path)


def _assert_contains(source: str, needle: str, message: str) -> None:
    """检查关键实现片段存在，确保验收项不是只停留在文档层。"""
    if needle not in source:
        raise AssertionError(message)


def verify_openapi_acceptance_paths() -> None:
    """校验 A-001~A-005 主链路所需接口已进入 OpenAPI。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    required_paths = [
        "/api/v1/knowledge-bases/{kb_id}/documents",
        "/api/v1/knowledge-bases/{kb_id}/documents/{document_id}/reparse",
        "/api/v1/knowledge-bases/{kb_id}/documents/{document_id}",
        "/api/v1/knowledge-bases/{kb_id}/documents/{document_id}/versions",
        "/api/v1/knowledge-bases/{kb_id}/documents/{document_id}/versions/{version_id}/activate",
        "/api/v1/knowledge-bases/{kb_id}/documents/{document_id}/versions/{version_id}/chunks",
        "/api/v1/knowledge-bases/{kb_id}/config-revisions/validate",
        "/api/v1/knowledge-bases/{kb_id}/config-revisions",
        "/api/v1/knowledge-bases/{kb_id}/config-revisions/{revision_id}/activate",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}/status",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}/feedback",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}/replay-context",
        "/api/v1/knowledge-bases/{kb_id}/qa-runs/{run_id}/evaluation-samples",
        "/api/v1/knowledge-bases/{kb_id}/graph/supporting-chunks",
    ]
    for path in required_paths:
        _assert(path in paths, f"OpenAPI 缺少 Sprint 12 验收接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for name in ["QARunDetailDTO", "QARunReplayContextDTO", "EvaluationSampleDTO", "GraphSupportingChunksResponse"]:
        _assert(name in schemas, f"OpenAPI 缺少验收 DTO: {name}")


def verify_e2e_flow_guards() -> None:
    """校验文档、配置、QA 历史和图支撑证据的最小闭环实现。"""
    document_source = _read_backend("app/services/document_service.py")
    config_source = _read_backend("app/services/config_service.py")
    qa_source = _read_backend("app/services/qa_run_service.py")
    graph_source = _read_backend("app/services/graph_service.py")

    _assert_contains(document_source, "run_ingest_job(session, current_user, kb_row", "文档上传/重解析未触发本地入库 Worker")
    _assert_contains(document_source, "def reparse_document(", "缺少文档重解析服务")
    _assert_contains(document_source, "confirmImpact must be true", "版本切换缺少二次确认约束")
    _assert_contains(document_source, "mark_graph_snapshots_stale(", "active version 切换未联动图快照 stale")
    _assert_contains(config_source, "def validate_pipeline_definition(", "缺少 pipelineDefinition 后端校验")
    _assert_contains(config_source, "def activate_config_revision(", "缺少 ConfigRevision 激活服务")
    _assert_contains(qa_source, "_execute_provider_qa_run(", "QARun 创建未进入执行链路")
    _assert_contains(qa_source, '"pipelineParams": pipeline_params', "QARun 未记录参数生效快照")
    _assert_contains(qa_source, "def get_qa_run_replay_context(", "缺少 QA 历史回放上下文")
    _assert_contains(qa_source, "def create_evaluation_sample_from_run(", "缺少从 QARun 沉淀评估样本")
    _assert_contains(graph_source, "def list_supporting_chunks(", "缺少图支撑 Chunk 回落查询")


def verify_permission_regression_guards() -> None:
    """校验 B-054 权限与跨 KB 回归所依赖的后端边界。"""
    permission_source = _read_backend("app/services/permission_service.py")
    document_source = _read_backend("app/services/document_service.py")
    qa_source = _read_backend("app/services/qa_run_service.py")
    graph_source = _read_backend("app/services/graph_service.py")

    _assert_contains(permission_source, '"versionStatus": "active"', "ChunkAccessFilter 未固定 active version")
    _assert_contains(permission_source, '"chunkStatus": "active"', "ChunkAccessFilter 未固定 active chunk")
    _assert_contains(permission_source, 'allowed = "kb.chunk.read" in evaluation.permissions', "ChunkAccessFilter 未绑定正文读取权限")
    _assert_contains(document_source, '_ensure_permission(session, current_user, kb_id, "kb.chunk.read")', "文档 Chunk 正文读取缺少后端鉴权")
    _assert_contains(qa_source, "def _authorize_provider_candidates(", "Provider 候选缺少 PostgreSQL 回表授权")
    _assert_contains(qa_source, "chunks.c.kb_id == kb_id", "QA 候选回表未校验 kbId")
    _assert_contains(qa_source, 'document_versions.c.status == "active"', "QA 候选回表未裁剪 inactive version")
    _assert_contains(qa_source, 'provider_errors.append("permissionFiltered")', "QA 权限裁剪未写入诊断")
    _assert_contains(qa_source, "Source QA run not found for this knowledge base.", "QARun 回放未按当前 KB 校验来源 run")
    _assert_contains(graph_source, "graph_snapshots.c.kb_id == kb_id", "图支撑查询未校验快照归属 KB")
    _assert_contains(graph_source, "chunks.c.kb_id == kb_id", "图支撑 Chunk 未回表校验 kbId")
    _assert_contains(graph_source, 'document_versions.c.status == "active"', "图支撑 Chunk 未裁剪 inactive version")
    _assert_contains(graph_source, 'has_kb_permission(session, current_user, kb_id, "kb.chunk.read")', "图支撑 Chunk 缺少正文权限裁剪")


def verify_acceptance_checklist_results() -> None:
    """确认 A-001~A-005 已从空结果推进到可复核状态。"""
    checklist = _read(ROOT_DIR / "docs/05-测试与验收/验收清单.md")
    for item_id in ["A-001", "A-002", "A-003", "A-004", "A-005"]:
        line = next((row for row in checklist.splitlines() if row.startswith(f"| {item_id} |")), "")
        _assert(line, f"验收清单缺少 {item_id}")
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        _assert(len(columns) >= 5, f"验收清单 {item_id} 行格式不完整")
        _assert(columns[3] != "", f"验收清单 {item_id} 结果仍为空")
        _assert(columns[4] != "", f"验收清单 {item_id} 备注仍为空")


def verify_project_docs_reference_script() -> None:
    """确认测试计划和 Sprint 计划均能指向本脚本。"""
    test_plan = _read(ROOT_DIR / "docs/05-测试与验收/测试计划.md")
    sprint_plan = _read(ROOT_DIR / "docs/04-迭代与交付/Epic-11/迭代计划-Sprint-12.md")
    _assert_contains(test_plan, "verify_sprint12_acceptance.py", "测试计划未纳入 Sprint 12 验收脚本")
    _assert_contains(sprint_plan, "verify_sprint12_acceptance.py", "Sprint 12 计划未记录验收脚本")


def main() -> None:
    """执行 Sprint 12 可复核验收检查。"""
    verify_openapi_acceptance_paths()
    verify_e2e_flow_guards()
    verify_permission_regression_guards()
    verify_acceptance_checklist_results()
    verify_project_docs_reference_script()
    print("Sprint 12 acceptance verification passed.")


if __name__ == "__main__":
    main()
