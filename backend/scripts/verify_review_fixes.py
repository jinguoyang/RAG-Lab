"""验证 Epic7~Epic10 code review 反馈的关键修复点。

脚本采用源码级护栏检查，避免依赖真实 PostgreSQL、Milvus、OpenSearch 或 Neo4j。
它只覆盖本轮 review 指出的安全和数据一致性边界。
"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    """读取后端源码文件，保持失败信息能直接定位文件。"""
    path = ROOT_DIR / relative_path
    if not path.exists():
        raise AssertionError(f"缺少文件: {path}")
    return path.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """用清晰错误描述约束关键实现片段。"""
    if needle not in source:
        raise AssertionError(message)


def verify_graph_supporting_chunks_guard() -> None:
    """确认图支撑 Chunk 查询同时校验快照归属、回表 Chunk，并返回裁剪数量。"""
    source = _read("app/services/graph_service.py")
    _assert_contains(source, "graph_snapshots.c.graph_snapshot_id == graph_snapshot_id", "未校验 graphSnapshotId 归属")
    _assert_contains(source, "graph_snapshots.c.kb_id == kb_id", "graphSnapshot 未绑定当前 kbId")
    _assert_contains(source, "chunks.c.kb_id == kb_id", "supporting chunks 未回表校验 kbId")
    _assert_contains(source, "document_versions.c.status == \"active\"", "supporting chunks 未校验 active version")
    _assert_contains(source, "has_kb_permission(session, current_user, kb_id, \"kb.chunk.read\")", "supporting chunks 未执行正文读取权限裁剪")
    _assert_contains(source, "filteredCount=filtered_count", "supporting chunks 未返回实际 filteredCount")


def verify_qa_candidate_backfill_guard() -> None:
    """确认 QA Provider 候选进入证据前会回表 PostgreSQL 做最终授权裁剪。"""
    source = _read("app/services/qa_run_service.py")
    _assert_contains(source, "def _authorize_provider_candidates", "缺少 Provider 候选回表授权函数")
    _assert_contains(source, "chunks.c.chunk_id.in_(chunk_ids)", "候选授权未按 chunk_id 回表")
    _assert_contains(source, "chunks.c.kb_id == kb_id", "候选授权未校验 kbId")
    _assert_contains(source, "document_versions.c.status == \"active\"", "候选授权未校验 active version")
    _assert_contains(source, "_authorize_provider_candidates(", "QA 执行链路未调用候选授权函数")


def verify_document_version_filter_status() -> None:
    """确认 Chunk 访问过滤摘要使用版本状态，而不是 chunk 自身 active 状态。"""
    source = _read("app/services/document_service.py")
    _assert_contains(source, "version_status: str", "写入 Chunk 访问过滤摘要时缺少 version_status 入参")
    _assert_contains(source, "version_status=version_status", "访问过滤摘要未使用版本状态")
    _assert_contains(source, "_write_chunk_access_filters(session, current_user, kb_row[\"kb_id\"], chunk_rows, new_version_status)", "入库后未按实际版本状态写过滤摘要")


def verify_missing_source_fails() -> None:
    """确认重解析或重试无法读取源文件时会失败，而不是生成占位成功版本。"""
    source = _read("app/services/document_service.py")
    _assert_contains(source, "Source file content is unavailable.", "源文件缺失时未显式失败")
    _assert_contains(source, "raise DocumentConflictError(\"Source file content is unavailable.\")", "源文件缺失没有抛出业务冲突")


def main() -> None:
    """执行本轮 review 修复的最小回归验证。"""
    verify_graph_supporting_chunks_guard()
    verify_qa_candidate_backfill_guard()
    verify_document_version_filter_status()
    verify_missing_source_fails()
    print("Review fixes verification passed.")


if __name__ == "__main__":
    main()
