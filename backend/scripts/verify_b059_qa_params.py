"""验证 B-059：P08 保存的核心参数会被 QA 执行链路解析为执行快照。"""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.qa_run_service import _build_effective_pipeline_params


def _assert(condition: bool, message: str) -> None:
    """用脚本级断言输出可读失败原因，便于本地验收定位。"""
    if not condition:
        raise AssertionError(message)


def _read(relative_path: str) -> str:
    """读取源码文件，用于验证 QA 执行链路没有只停留在参数解析层。"""
    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """源码护栏断言，失败时直接指出缺失的关键执行片段。"""
    if needle not in source:
        raise AssertionError(message)


def verify_pipeline_params_snapshot() -> None:
    """验证 pipelineDefinition 节点参数与单次覆盖能合并成 QA 执行参数。"""
    revision_row = {
        "pipeline_definition": {
            "nodes": [
                {"type": "denseRetrieval", "enabled": True, "params": {"topK": 12}},
                {"type": "sparseRetrieval", "enabled": True, "params": {"topK": 7}},
                {"type": "graphRetrieval", "enabled": True, "params": {"topK": 5}},
                {"type": "rerank", "enabled": True, "params": {"topN": 4}},
                {"type": "contextBuilder", "enabled": True, "params": {"maxContextTokens": 2048}},
                {"type": "llmGeneration", "enabled": True, "params": {"temperature": 0.35}},
            ],
        },
    }

    params = _build_effective_pipeline_params(
        revision_row,
        {"params": {"denseTopK": 9, "temperature": 0.2}},
    )

    _assert(params["retrievalTopK"]["dense"] == 9, "dense topK 未应用单次覆盖")
    _assert(params["retrievalTopK"]["sparse"] == 7, "sparse topK 未读取 P08 节点参数")
    _assert(params["retrievalTopK"]["graph"] == 5, "graph topK 未读取 P08 节点参数")
    _assert(params["rerankTopN"] == 4, "rerank topN 未读取 P08 节点参数")
    _assert(params["maxContextTokens"] == 2048, "maxContextTokens 未读取 P08 节点参数")
    _assert(params["temperature"] == 0.2, "temperature 未应用单次覆盖")


def verify_execution_uses_pipeline_params() -> None:
    """确认 QA 执行链路把生效参数用于检索、重排、上下文和生成。"""
    qa_source = _read("app/services/qa_run_service.py")
    provider_source = _read("app/services/qa_providers.py")

    _assert_contains(qa_source, 'pipeline_params["retrievalTopK"]["dense"]', "Dense 检索未使用生效 topK")
    _assert_contains(qa_source, 'pipeline_params["retrievalTopK"]["sparse"]', "Sparse 检索未使用生效 topK")
    _assert_contains(qa_source, 'pipeline_params["retrievalTopK"]["graph"]', "Graph 检索未使用生效 topK")
    _assert_contains(qa_source, 'pipeline_params["rerankTopN"]', "Rerank 未使用生效 topN")
    _assert_contains(qa_source, "_limit_candidates_by_context_tokens(", "生成上下文未按 maxContextTokens 裁剪")
    _assert_contains(qa_source, 'temperature=pipeline_params["temperature"]', "生成未传入生效 temperature")
    _assert_contains(qa_source, '"pipelineParams": pipeline_params', "QARun metrics 未写入参数生效快照")
    _assert_contains(provider_source, "temperature if temperature is not None else 0.2", "HTTP LLM 未使用传入 temperature")


def main() -> None:
    """执行 B-059 最小验证。"""
    verify_pipeline_params_snapshot()
    verify_execution_uses_pipeline_params()
    print("B-059 QA params snapshot verification passed")


if __name__ == "__main__":
    main()
