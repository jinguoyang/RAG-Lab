"""校验知识库已有文档后索引能力不可直接变更。"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def _assert(condition: bool, message: str) -> None:
    """提供清晰失败信息，便于定位锁定规则是否缺失。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """按 UTF-8 读取源码，避免 Windows 默认编码影响中文检查。"""
    return path.read_text(encoding="utf-8")


def verify_backend_lock() -> None:
    """校验服务层和路由层都覆盖已有文档后的索引能力锁定。"""
    service = _read(BACKEND_DIR / "app/services/knowledge_base_service.py")
    route = _read(BACKEND_DIR / "app/api/routes/knowledge_bases.py")

    _assert("KnowledgeBaseIndexCapabilityLockedError" in service, "缺少索引能力锁定异常")
    _assert("documents.c.kb_id == kb_id" in service, "未按知识库检查已有文档")
    _assert("documents.c.deleted_at.is_(None)" in service, "文档存在性检查应排除已删除文档")
    _assert("_ensure_index_capabilities_mutable" in service, "更新前未调用索引能力锁定校验")
    _assert("sparse_index_enabled" in service and "graph_index_enabled" in service, "锁定规则未覆盖 Sparse 和 Graph")
    _assert("KnowledgeBaseIndexCapabilityLockedError" in route, "路由未映射索引能力锁定异常")
    _assert("KB_INDEX_CAPABILITY_LOCKED" in route, "接口缺少明确的锁定错误码")


def verify_frontend_lock_hint() -> None:
    """校验 P02 编辑弹窗在已有文档时禁用索引能力开关并给出提示。"""
    page = _read(FRONTEND_DIR / "src/app/pages/P02_PlatformHome.tsx")

    _assert("fetchDocuments" in page, "前端编辑知识库时未查询文档数量")
    _assert("indexCapabilityLocked" in page, "前端缺少索引能力锁定状态")
    _assert("disabled={indexCapabilityControlsDisabled}" in page, "Sparse 或 Graph 开关未在锁定时禁用")
    _assert("已有文档后不可变更" in page, "前端缺少锁定原因提示")


def main() -> None:
    """执行索引能力锁定规则的源码级验收。"""
    verify_backend_lock()
    verify_frontend_lock_hint()
    print("Knowledge base index capability lock verification passed.")


if __name__ == "__main__":
    main()
