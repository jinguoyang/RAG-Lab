"""验证图索引构建会写入 Graph -> Chunk 回溯摘要。

脚本不连接真实 PostgreSQL 或 Neo4j，只检查后端服务层是否在图抽取结果
写入成功路径中维护 `graph_chunk_refs`，避免 P11 有图结果但没有支撑 Chunk。
"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    """读取源码文件，并在失败时给出明确路径。"""
    path = ROOT_DIR / relative_path
    if not path.exists():
        raise AssertionError(f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """断言关键实现片段存在，确保回溯写入不是只停留在文档中。"""
    if needle not in source:
        raise AssertionError(message)


def verify_graph_chunk_refs_are_written() -> None:
    """确认图抽取结果会落库为实体和关系支撑 Chunk 引用。"""
    source = _read("app/services/document_service.py")
    _assert_contains(source, "def _write_graph_chunk_refs(", "缺少 graph_chunk_refs 写入函数")
    _assert_contains(source, "delete(graph_chunk_refs).where(graph_chunk_refs.c.graph_snapshot_id == graph_snapshot_id)", "重建同一快照前未清理旧回溯")
    _assert_contains(source, "insert(graph_chunk_refs).values", "未插入 graph_chunk_refs")
    _assert_contains(source, 'ref_type="entity_support"', "未写入实体支撑 Chunk")
    _assert_contains(source, 'ref_type="relation_support"', "未写入关系支撑 Chunk")
    _assert_contains(source, "_write_graph_chunk_refs(session, graph_snapshot_id,", "图构建成功路径未调用回溯写入")


def main() -> None:
    """执行图支撑 Chunk 回溯写入检查。"""
    verify_graph_chunk_refs_are_written()
    print("Graph chunk refs write verification passed.")


if __name__ == "__main__":
    main()
