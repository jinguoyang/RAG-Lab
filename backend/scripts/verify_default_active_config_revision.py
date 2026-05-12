"""校验新建知识库会自动生成可运行的默认 ConfigRevision。"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"


def _assert(condition: bool, message: str) -> None:
    """提供清晰失败信息，便于定位默认查询版本缺失位置。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """按 UTF-8 读取源码，避免中文路径和注释在 Windows 下乱码。"""
    return path.read_text(encoding="utf-8")


def verify_default_pipeline_helper() -> None:
    """校验默认 Pipeline 构造函数存在，并按知识库能力开关启用检索通道。"""
    helper = _read(BACKEND_DIR / "app/services/default_pipeline.py")

    _assert("def build_default_pipeline_definition(" in helper, "缺少默认 Pipeline 构造函数")
    _assert("sparse_index_enabled" in helper, "默认 Pipeline 未接收 Sparse 能力开关")
    _assert("graph_index_enabled" in helper, "默认 Pipeline 未接收 Graph 能力开关")
    _assert('"type": "denseRetrieval"' in helper, "默认 Pipeline 缺少 Dense Retrieval 节点")
    _assert('"type": "sparseRetrieval"' in helper, "默认 Pipeline 缺少 Sparse Retrieval 节点")
    _assert('"type": "graphRetrieval"' in helper, "默认 Pipeline 缺少 Graph Retrieval 节点")
    _assert('"enabled": sparse_index_enabled' in helper, "Sparse 节点未跟随知识库 Sparse 能力开关")
    _assert('"enabled": graph_index_enabled' in helper, "Graph 节点未跟随知识库 Graph 能力开关")
    _assert('"type": "permissionFilter"' in helper, "默认 Pipeline 缺少权限过滤节点")


def verify_create_kb_auto_revision_contract() -> None:
    """校验创建知识库时同事务创建 active Revision 并同步知识库指针。"""
    service = _read(BACKEND_DIR / "app/services/knowledge_base_service.py")

    _assert("config_revisions" in service, "知识库服务未引用 config_revisions 表")
    _assert("build_default_pipeline_definition" in service, "创建知识库未使用默认 Pipeline")
    _assert("default_revision_id = uuid4()" in service, "创建知识库未生成默认 Revision ID")
    _assert("active_config_revision_id=default_revision_id" in service, "创建知识库未同步 active_config_revision_id")
    _assert("status=\"active\"" in service, "默认 Revision 未直接置为 active")
    _assert("revision_no=1" in service, "默认 Revision 未作为 rev_001 创建")
    _assert("config_revision.create_default" in service, "默认 Revision 创建缺少审计动作")
    _assert("system_default" in service, "默认 Revision 未标记系统默认来源")


def main() -> None:
    """执行默认 active ConfigRevision 源码级验收。"""
    verify_default_pipeline_helper()
    verify_create_kb_auto_revision_contract()
    print("Default active config revision verification passed.")


if __name__ == "__main__":
    main()
