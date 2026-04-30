"""验证 V1.7 第一阶段：受控 RAG 节点参数可校验、可执行、可展示。"""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_ROOT.parent
FRONTEND_ROOT = ROOT_DIR / "frontend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.config import PipelineValidateRequest  # noqa: E402
from app.services.config_service import validate_pipeline_definition  # noqa: E402
from app.services.qa_run_service import (  # noqa: E402
    _build_effective_pipeline_params,
    _filter_candidates_by_score_threshold,
    _fuse_provider_candidates,
)
from app.services.qa_providers import ProviderCandidate  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    """输出可定位的断言错误，便于验收时快速找到缺口。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """按 UTF-8 读取源码，检查前端页面与执行链路是否接入 V1.7 关键字段。"""
    return path.read_text(encoding="utf-8")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """确认关键实现片段存在，避免只更新 DTO 而未接入执行或展示。"""
    if needle not in source:
        raise AssertionError(message)


def _v17_pipeline_definition() -> dict:
    """构造覆盖 Sprint 25 受控节点和核心参数的最小 Pipeline。"""
    return {
        "version": "1.7",
        "constraintsVersion": "1.7",
        "mode": "constrained-stage-pipeline",
        "stages": ["preprocess", "retrieval", "fusion", "generation", "diagnostics"],
        "nodes": [
            {"id": "input", "type": "input", "stage": "preprocess", "enabled": True, "locked": True, "params": {}},
            {
                "id": "queryRewrite",
                "type": "queryRewrite",
                "stage": "preprocess",
                "enabled": True,
                "params": {"rewriteStrategy": "hybrid", "preserveOriginalQuery": True},
            },
            {
                "id": "multiQuery",
                "type": "multiQuery",
                "stage": "preprocess",
                "enabled": True,
                "params": {"queryCount": 3, "mergeStrategy": "rrf"},
            },
            {
                "id": "dense",
                "type": "denseRetrieval",
                "stage": "retrieval",
                "enabled": True,
                "params": {"topK": 11, "scoreThreshold": 0.6, "fusionWeight": 0.5},
            },
            {
                "id": "sparse",
                "type": "sparseRetrieval",
                "stage": "retrieval",
                "enabled": True,
                "params": {"topK": 9, "scoreThreshold": 0.2, "fusionWeight": 0.3},
            },
            {
                "id": "graph",
                "type": "graphRetrieval",
                "stage": "retrieval",
                "enabled": True,
                "params": {"topK": 4, "graphDepth": 2, "graphExpansionLimit": 20, "mustFallbackToChunk": True},
            },
            {
                "id": "fusion",
                "type": "fusion",
                "stage": "fusion",
                "enabled": True,
                "locked": True,
                "params": {"method": "weighted", "candidateLimit": 8, "dedupBy": "chunkId"},
            },
            {
                "id": "permissionFilter",
                "type": "permissionFilter",
                "stage": "fusion",
                "enabled": True,
                "locked": True,
                "params": {},
            },
            {
                "id": "rerank",
                "type": "rerank",
                "stage": "fusion",
                "enabled": True,
                "params": {"topN": 6, "scoreThreshold": 0.1},
            },
            {
                "id": "contextPacking",
                "type": "contextPacking",
                "stage": "generation",
                "enabled": True,
                "locked": True,
                "params": {"maxContextTokens": 4096, "chunkWindow": 1, "citationPolicy": "strict"},
            },
            {
                "id": "generation",
                "type": "generation",
                "stage": "generation",
                "enabled": True,
                "locked": True,
                "params": {"temperature": 0.15, "maxOutputTokens": 1000},
            },
            {
                "id": "citation",
                "type": "citation",
                "stage": "generation",
                "enabled": True,
                "locked": True,
                "params": {"minEvidence": 1, "citationPolicy": "strict"},
            },
            {"id": "output", "type": "output", "stage": "diagnostics", "enabled": True, "locked": True, "params": {}},
        ],
    }


def verify_pipeline_validation_accepts_v17_nodes() -> None:
    """确认后端 Pipeline 校验接受 V1.7 受控节点和参数范围。"""
    result = validate_pipeline_definition(PipelineValidateRequest(pipelineDefinition=_v17_pipeline_definition()))
    _assert(result.valid, f"V1.7 Pipeline 应通过校验: {[error.message for error in result.errors]}")
    normalized = result.normalizedPipelineDefinition
    node_types = {node.get("type") for node in normalized.get("nodes", [])}
    _assert("multiQuery" in node_types, "Pipeline 校验未保留 multiQuery 节点")
    _assert("contextPacking" in node_types, "Pipeline 校验未保留 contextPacking 节点")


def verify_invalid_params_are_rejected() -> None:
    """确认非法参数会在保存前被后端二次校验拦截。"""
    definition = _v17_pipeline_definition()
    definition["nodes"][3]["params"]["topK"] = 0
    definition["nodes"][10]["params"]["maxContextTokens"] = 128
    result = validate_pipeline_definition(PipelineValidateRequest(pipelineDefinition=definition))
    codes = {error.code for error in result.errors}
    _assert("PIPELINE_PARAM_RANGE_INVALID" in codes, "topK 或 maxContextTokens 越界未被拦截")


def verify_effective_params_include_v17_fields() -> None:
    """确认 QA 执行参数快照包含 V1.7 节点级参数。"""
    params = _build_effective_pipeline_params(
        {"pipeline_definition": _v17_pipeline_definition()},
        {"params": {"denseTopK": 7, "rerankTopN": 5}},
        default_top_k=5,
    )
    _assert(params["retrievalTopK"]["dense"] == 7, "单次覆盖 denseTopK 未生效")
    _assert(params["retrievalScoreThreshold"]["dense"] == 0.6, "Dense scoreThreshold 未进入执行快照")
    _assert(params["fusionWeights"]["sparse"] == 0.3, "Sparse fusionWeight 未进入执行快照")
    _assert(params["graph"]["graphDepth"] == 2, "graphDepth 未进入执行快照")
    _assert(params["graph"]["graphExpansionLimit"] == 20, "graphExpansionLimit 未进入执行快照")
    _assert(params["contextPacking"]["chunkWindow"] == 1, "chunkWindow 未进入执行快照")
    _assert(params["citation"]["citationPolicy"] == "strict", "citationPolicy 未进入执行快照")


def verify_score_threshold_and_fusion_weights_apply() -> None:
    """确认 scoreThreshold 和 fusionWeight 对候选过滤与融合排序有实际影响。"""
    candidates = [
        ProviderCandidate("dense", None, 0.9, "dense strong", {"rank": 1}),
        ProviderCandidate("dense", None, 0.1, "dense weak", {"rank": 2}),
        ProviderCandidate("sparse", None, 0.5, "sparse mid", {"rank": 3}),
    ]
    filtered = _filter_candidates_by_score_threshold(
        candidates,
        {"dense": 0.5, "sparse": 0.2, "graph": 0.0},
    )
    _assert([candidate.content for candidate in filtered] == ["dense strong", "sparse mid"], "scoreThreshold 未过滤低分候选")

    fused = _fuse_provider_candidates(
        filtered,
        {"dense": 0.2, "sparse": 1.0, "graph": 0.1},
        candidate_limit=2,
    )
    _assert(fused[0].source_type == "sparse", "fusionWeight 未影响融合候选排序")


def verify_source_guards() -> None:
    """源码级护栏：确认执行链路、P08 和文档均接入第一阶段关键能力。"""
    qa_source = _read(BACKEND_ROOT / "app/services/qa_run_service.py")
    config_source = _read(BACKEND_ROOT / "app/services/config_service.py")
    p08_source = _read(FRONTEND_ROOT / "src/app/pages/P08_ConfigCenter.tsx")

    for needle in ["multiQuery", "contextPacking", "retrievalScoreThreshold", "fusionWeights", "graphExpansionLimit"]:
        _assert_contains(qa_source, needle, f"QA 执行链路缺少 {needle}")
    for needle in ["PIPELINE_PARAM_RANGE_INVALID", "multiQuery", "contextPacking"]:
        _assert_contains(config_source, needle, f"Pipeline 校验缺少 {needle}")
    for needle in ["Multi Query", "Context Packing", "scoreThreshold", "fusionWeight", "graphDepth"]:
        _assert_contains(p08_source, needle, f"P08 调参台缺少 {needle}")


def main() -> None:
    """执行 V1.7 Sprint 25 参数链路验收。"""
    verify_pipeline_validation_accepts_v17_nodes()
    verify_invalid_params_are_rejected()
    verify_effective_params_include_v17_fields()
    verify_score_threshold_and_fusion_weights_apply()
    verify_source_guards()
    print("V1.7 pipeline params verification passed.")


if __name__ == "__main__":
    main()
