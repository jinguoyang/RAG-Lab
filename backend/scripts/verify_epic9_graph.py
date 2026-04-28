"""Epic9 图检索分析与诊断的最小回归验证脚本。

脚本避免依赖真实 Neo4j 或测试数据库，重点校验本地代码已经暴露
P11 所需接口契约、支撑 Chunk 回表字段和图快照 stale 标记入口。
"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import create_app  # noqa: E402


def _read(relative_path: str) -> str:
    """读取源码文件，并在缺失时给出可定位路径。"""
    path = BACKEND_DIR / relative_path
    if not path.exists():
        raise AssertionError(f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """断言关键实现片段存在，避免接口只在文档中完成。"""
    if needle not in source:
        raise AssertionError(message)


def verify_openapi_paths() -> None:
    """校验 OpenAPI 已包含 P11 需要的图检索分析接口。"""
    schema = TestClient(create_app()).get("/openapi.json").json()
    paths = schema.get("paths", {})
    for path in [
        "/api/v1/knowledge-bases/{kb_id}/graph-snapshots",
        "/api/v1/knowledge-bases/{kb_id}/graph/entities",
        "/api/v1/knowledge-bases/{kb_id}/graph/paths",
        "/api/v1/knowledge-bases/{kb_id}/graph/communities",
        "/api/v1/knowledge-bases/{kb_id}/graph/supporting-chunks",
    ]:
        if path not in paths:
            raise AssertionError(f"OpenAPI 缺少图接口: {path}")

    schemas = schema.get("components", {}).get("schemas", {})
    for name in ["GraphPathSearchResponse", "GraphCommunitySearchResponse", "GraphSupportingChunkDTO"]:
        if name not in schemas:
            raise AssertionError(f"OpenAPI 缺少 Schema: {name}")


def verify_provider_contract() -> None:
    """校验 Graph Provider 抽象已支持路径和社区摘要查询。"""
    source = _read("app/services/qa_providers.py")
    _assert_contains(source, "def search_paths(", "Graph Provider 缺少 search_paths")
    _assert_contains(source, "def search_communities(", "Graph Provider 缺少 search_communities")
    _assert_contains(source, "MATCH (source:Entity)-[rel:RELATED_TO]->(target:Entity)", "Neo4j 路径查询未实现")
    _assert_contains(source, "MATCH (community:Community)", "Neo4j 社区查询未实现")


def verify_graph_service_guards() -> None:
    """校验服务层有降级诊断、支撑 Chunk 回表和 stale 标记规则。"""
    source = _read("app/services/graph_service.py")
    _assert_contains(source, "def search_graph_paths(", "服务层缺少路径查询")
    _assert_contains(source, "def search_graph_communities(", "服务层缺少社区查询")
    _assert_contains(source, "GraphQueryDiagnosticsDTO(degraded=True", "缺少 Provider 降级诊断")
    _assert_contains(source, "def mark_graph_snapshots_stale(", "缺少集中 stale 标记函数")
    _assert_contains(source, "chunks.c.kb_id == kb_id", "supporting chunks 未回表校验 kbId")
    _assert_contains(source, "document_versions.c.status == \"active\"", "supporting chunks 未裁剪 inactive version")


def verify_frontend_contract() -> None:
    """校验 P11 已通过 service/adapter 层接入真实 Graph API。"""
    types_path = ROOT_DIR / "frontend/src/app/types/graph.ts"
    if not types_path.exists():
        raise AssertionError(f"缺少文件: {types_path}")
    service = (ROOT_DIR / "frontend/src/app/services/graphService.ts").read_text(encoding="utf-8")
    adapter = (ROOT_DIR / "frontend/src/app/adapters/graphAdapter.ts").read_text(encoding="utf-8")
    page = (ROOT_DIR / "frontend/src/app/pages/P11_GraphSearchAnalysis.tsx").read_text(encoding="utf-8")
    _assert_contains(service, "/graph/paths", "前端 Graph service 缺少 paths 接口")
    _assert_contains(service, "/graph/communities", "前端 Graph service 缺少 communities 接口")
    _assert_contains(adapter, "toGraphAnalysisView", "前端 Graph adapter 缺少 ViewModel 转换")
    _assert_contains(page, "fetchGraphPaths", "P11 未接入真实 Graph API")
    _assert_contains(page, "filteredCount", "P11 未展示权限裁剪诊断")


def main() -> None:
    """执行 Epic9 本地可验证闭环检查。"""
    verify_openapi_paths()
    verify_provider_contract()
    verify_graph_service_guards()
    verify_frontend_contract()
    print("Epic9 graph verification passed.")


if __name__ == "__main__":
    main()
