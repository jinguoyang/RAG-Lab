"""Ingest 阶段进度与 Graph 并发抽取契约验证。"""

from pathlib import Path
import sys
import time


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings  # noqa: E402
from app.services.qa_providers import HttpLlmProvider, ProviderError  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """用明确错误信息暴露入库进度和 Graph 并发契约缺口。"""
    if not condition:
        raise AssertionError(message)


def _read_backend_file(relative_path: str) -> str:
    """按 UTF-8 读取后端源码文件。"""
    return (BACKEND_DIR / relative_path).read_text(encoding="utf-8")


def verify_ingest_stage_progress_contract() -> None:
    """校验入库 Worker 会写入固定阶段和阶段耗时摘要。"""
    source = _read_backend_file("app/services/document_service.py")
    for stage in ["parse", "embedding", "dense_index", "sparse_index", "graph_extract", "graph_index", "completed", "failed"]:
        _assert(f'"{stage}"' in source, f"run_ingest_job 缺少阶段: {stage}")
    _assert('"index_sync"' not in source, "run_ingest_job 不应继续写入旧 index_sync 阶段")
    _assert("stageTimings" in source, "Ingest result_summary 缺少阶段耗时摘要")
    _assert("processedCount" in source, "Ingest result_summary 缺少已处理数量")
    _assert("chunkCount" in source, "Ingest result_summary 缺少 chunk 总数")
    _assert("graphExtractionErrors" in source, "Ingest result_summary 缺少 Graph 单 chunk 失败摘要")


def verify_graph_concurrency_configuration() -> None:
    """校验 Graph 抽取并发配置存在且默认值稳定。"""
    settings = Settings()
    _assert(settings.graph_extraction_concurrency == 3, "Graph 抽取默认并发应为 3")
    _assert("RAG_LAB_GRAPH_EXTRACTION_CONCURRENCY" in _read_backend_file(".env.example"), ".env.example 缺少 Graph 并发配置示例")


class FakeGraphLlmProvider(HttpLlmProvider):
    """用 fake _chat 验证并发抽取，不发真实网络请求。"""

    def __init__(self, fail_marker: str | None = None) -> None:
        class SettingsStub:
            llm_endpoint = "https://llm.example.test/v1/chat/completions"
            llm_api_key = "secret"
            llm_model = "fake"
            graph_extraction_concurrency = 3

        super().__init__(SettingsStub())
        self.fail_marker = fail_marker
        self.call_order: list[str] = []

    def _chat(self, messages: list[dict], temperature: float | None = None) -> str:
        """模拟不同 chunk 的响应耗时，逼出并发顺序问题。"""
        _ = temperature
        content = str(messages[-1]["content"])
        self.call_order.append(content)
        if self.fail_marker and self.fail_marker in content:
            raise ProviderError("fake chunk graph extraction failed")
        if "slow" in content:
            time.sleep(0.05)
        return '{"summary":"ok","entities":[{"name":"Entity","type":"Thing","aliases":[]}],"relations":[]}'


def _payload(chunk_id: str, content: str) -> dict:
    """构造最小 Chunk payload。"""
    return {"chunkId": chunk_id, "kbId": "kb-1", "content": content}


def verify_graph_extraction_preserves_input_order() -> None:
    """校验并发抽取完成顺序不影响返回顺序。"""
    provider = FakeGraphLlmProvider()
    items = provider.extract_graph([
        _payload("chunk-1", "slow first"),
        _payload("chunk-2", "fast second"),
        _payload("chunk-3", "fast third"),
    ])
    _assert([item.chunk_id for item in items] == ["chunk-1", "chunk-2", "chunk-3"], "Graph 抽取结果未按输入 chunk 顺序返回")
    _assert(getattr(provider, "last_graph_extraction_errors") == [], "成功抽取时不应记录失败摘要")


def verify_graph_extraction_keeps_partial_success() -> None:
    """校验单个 chunk 失败不会导致整批 Graph 抽取失败。"""
    provider = FakeGraphLlmProvider(fail_marker="bad")
    items = provider.extract_graph([
        _payload("chunk-1", "good first"),
        _payload("chunk-2", "bad second"),
        _payload("chunk-3", "good third"),
    ])
    _assert([item.chunk_id for item in items] == ["chunk-1", "chunk-3"], "Graph 抽取应保留成功 chunk")
    errors = getattr(provider, "last_graph_extraction_errors")
    _assert(len(errors) == 1 and errors[0]["chunkId"] == "chunk-2", "Graph 抽取应记录失败 chunk 摘要")


def verify_graph_extraction_fails_when_all_chunks_fail() -> None:
    """校验整批失败时 Graph 阶段明确失败。"""
    provider = FakeGraphLlmProvider(fail_marker="bad")
    try:
        provider.extract_graph([
            _payload("chunk-1", "bad first"),
            _payload("chunk-2", "bad second"),
        ])
    except ProviderError as exc:
        _assert("All graph extraction requests failed" in str(exc), "整批失败应返回稳定错误信息")
        return
    raise AssertionError("整批 Graph 抽取失败时必须抛出 ProviderError")


def main() -> None:
    """执行 Ingest 进度和 Graph 并发契约验收。"""
    verify_ingest_stage_progress_contract()
    verify_graph_concurrency_configuration()
    verify_graph_extraction_preserves_input_order()
    verify_graph_extraction_keeps_partial_success()
    verify_graph_extraction_fails_when_all_chunks_fail()
    print("Ingest progress and graph concurrency verification passed.")


if __name__ == "__main__":
    main()
