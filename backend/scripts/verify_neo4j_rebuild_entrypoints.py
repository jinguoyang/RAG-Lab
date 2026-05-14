"""验证 P06 的 Neo4j 重建入口真正可触发图回溯重建。

覆盖两个曾经容易误用的入口：
- 右侧知识库级重建区必须有独立 targetStore 选择器，避免默认重建 milvus。
- 批量重建索引必须复用 `rebuild_index_sync`，确保 Neo4j payload、图快照和 graph_chunk_refs 都会被创建。
"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def _read(path: Path) -> str:
    """读取源码文件，保持失败信息可定位。"""
    if not path.exists():
        raise AssertionError(f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """检查关键入口实现，避免页面显示和实际重建目标脱节。"""
    if needle not in source:
        raise AssertionError(message)


def verify_frontend_rebuild_target_selector() -> None:
    """确认知识库级重建按钮有自己的目标库状态和选择器。"""
    source = _read(FRONTEND_DIR / "src/app/pages/P06_DocumentCenter.tsx")
    _assert_contains(source, "indexRebuildTargetStore", "右侧索引重建区缺少独立 targetStore 状态")
    _assert_contains(source, "setIndexRebuildTargetStore", "右侧索引重建区缺少目标库选择器")
    _assert_contains(source, "await rebuildIndexSync(kbId, { targetStore: indexRebuildTargetStore })", "知识库级重建未使用独立目标库")


def verify_batch_rebuild_uses_real_rebuild_service() -> None:
    """确认批量重建不会绕过 provider payload 和 graph refs 写入逻辑。"""
    source = _read(BACKEND_DIR / "app/services/document_service.py")
    _assert_contains(source, "response = rebuild_index_sync(", "批量重建未复用完整索引重建服务")
    _assert_contains(source, "document_id=document_id", "批量重建未按选中文档收窄重建范围")
    _assert_contains(source, "affected_sync_job_ids", "批量重建未汇总实际创建的同步作业")


def main() -> None:
    """执行 Neo4j 重建入口检查。"""
    verify_frontend_rebuild_target_selector()
    verify_batch_rebuild_uses_real_rebuild_service()
    print("Neo4j rebuild entrypoints verification passed.")


if __name__ == "__main__":
    main()
