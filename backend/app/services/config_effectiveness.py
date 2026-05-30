"""RAG Pipeline 节点配置项生效状态审计服务。

每个节点的每个配置项维护一个 effectiveness 状态：
- effective: 后端代码读取并改变执行路径，可在 trace 中证明。
- partiallyEffective: 后端读取但效果有限，或仅在特定条件下生效。
- planned: 配置项已展示在 UI 但后端未实现，不影响运行结果。
- deprecated: 已废弃，保留仅为兼容历史数据。

配置项清单与 default_pipeline.py 同源，新增节点或配置项时必须同步更新本文件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConfigItemEffectiveness:
    """单个配置项的生效状态描述。"""

    key: str
    status: str  # effective | partiallyEffective | planned | deprecated
    execution_location: str
    note: str = ""
    since_version: str = ""


@dataclass(frozen=True)
class NodeCapability:
    """节点级能力清单，包含所有配置项及其生效状态。"""

    node_id: str
    node_type: str
    stage: str
    items: list[ConfigItemEffectiveness] = field(default_factory=list)

    def effective_items(self) -> list[ConfigItemEffectiveness]:
        return [i for i in self.items if i.status == "effective"]

    def partially_effective_items(self) -> list[ConfigItemEffectiveness]:
        return [i for i in self.items if i.status == "partiallyEffective"]

    def planned_items(self) -> list[ConfigItemEffectiveness]:
        return [i for i in self.items if i.status == "planned"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodeId": self.node_id,
            "nodeType": self.node_type,
            "stage": self.stage,
            "items": [
                {
                    "key": item.key,
                    "status": item.status,
                    "executionLocation": item.execution_location,
                    "note": item.note,
                    "sinceVersion": item.since_version,
                }
                for item in self.items
            ],
        }


def _i(key: str, status: str, loc: str, note: str = "", since: str = "") -> ConfigItemEffectiveness:
    return ConfigItemEffectiveness(key, status, loc, note, since)


def build_default_capability_registry() -> list[NodeCapability]:
    """构建系统默认 Pipeline 所有节点的配置项生效状态清单。

    此函数是配置项生效状态的唯一真相源。QA Run trace 和前端配置中心均从此处获取数据。
    """
    return [
        # ── preprocess ──
        NodeCapability(
            node_id="input",
            node_type="input",
            stage="preprocess",
            items=[],
        ),
        NodeCapability(
            node_id="queryRewrite",
            node_type="queryRewrite",
            stage="preprocess",
            items=[
                _i("enabled", "effective", "qa_run_service._execute_provider_qa_run",
                   "控制是否进入 LLM 改写分支", "sprint19"),
                _i("rewriteStrategy", "partiallyEffective", "qa_run_service._execute_provider_qa_run",
                   "hybrid/semantic/keyword 三种策略已实现，但语义和关键词策略共用同一 prompt", "sprint19"),
                _i("preserveOriginalQuery", "effective", "qa_run_service._execute_provider_qa_run",
                   "控制改写结果是否追加原始 query", "sprint19"),
                _i("expansionCount", "partiallyEffective", "qa_run_service._execute_provider_qa_run",
                   "LLM 改写输出条数受此约束，但实际输出可能少于配置值", "sprint19"),
                _i("promptVersion", "planned", "",
                   "Prompt 版本切换尚未实现，当前固定使用内置 prompt"),
            ],
        ),
        NodeCapability(
            node_id="multiQuery",
            node_type="multiQuery",
            stage="preprocess",
            items=[
                _i("enabled", "effective", "qa_run_service._build_effective_pipeline_params",
                   "控制是否进入多查询分支", "sprint19"),
                _i("queryCount", "effective", "LlmProvider.generate_multi_queries -> qa_run_service",
                   "B-317: 使用 LLM 生成多个查询变体，数量受此配置约束", "sprint63"),
                _i("mergeStrategy", "effective", "qa_run_service._fuse_provider_candidates",
                   "B-317: 支持 rrf 和 weighted 两种合并策略", "sprint63"),
            ],
        ),
        # ── retrieval ──
        NodeCapability(
            node_id="dense",
            node_type="denseRetrieval",
            stage="retrieval",
            items=[
                _i("enabled", "effective", "qa_run_service._effective_retrieval_channels",
                   "控制 Dense 检索通道是否启用", "sprint19"),
                _i("topK", "effective", "qa_run_service._build_effective_pipeline_params -> MilvusDenseRetrievalProvider",
                   "传递给 Milvus 检索的 top_k 参数", "sprint19"),
                _i("scoreThreshold", "effective", "qa_run_service._filter_candidates_by_score_threshold",
                   "低于阈值的候选被过滤", "sprint19"),
                _i("fusionWeight", "effective", "qa_run_service._weighted_score_fusion",
                   "参与加权融合的权重", "sprint19"),
                _i("embeddingModel", "planned", "",
                   "Embedding 模型由全局 Settings 控制，节点级切换尚未实现"),
                _i("metadataFilter", "partiallyEffective", "qa_run_service",
                   "当前仅用于 permission filter 阶段的文档状态过滤", "sprint19"),
            ],
        ),
        NodeCapability(
            node_id="sparse",
            node_type="sparseRetrieval",
            stage="retrieval",
            items=[
                _i("enabled", "effective", "qa_run_service._effective_retrieval_channels",
                   "控制 Sparse 检索通道是否启用", "sprint19"),
                _i("topK", "effective", "qa_run_service._build_effective_pipeline_params -> OpenSearchSparseRetrievalProvider",
                   "传递给 OpenSearch 的 size 参数", "sprint19"),
                _i("scoreThreshold", "effective", "qa_run_service._filter_candidates_by_score_threshold",
                   "低于阈值的候选被过滤", "sprint19"),
                _i("fusionWeight", "effective", "qa_run_service._weighted_score_fusion",
                   "参与加权融合的权重", "sprint19"),
                _i("matchMode", "planned", "",
                   "BM25+phrase / BM25 / keyword-exact 模式切换尚未实现，固定使用默认匹配"),
                _i("metadataFilter", "partiallyEffective", "qa_run_service",
                   "当前仅用于 permission filter 阶段的文档状态过滤", "sprint19"),
            ],
        ),
        NodeCapability(
            node_id="graph",
            node_type="graphRetrieval",
            stage="retrieval",
            items=[
                _i("enabled", "effective", "qa_run_service._effective_retrieval_channels",
                   "控制 Graph 检索通道是否启用", "sprint19"),
                _i("graphDepth", "partiallyEffective", "Neo4jGraphRetrievalProvider",
                   "传递给 Neo4j Cypher 查询的路径深度，但当前仅支持实体路径搜索", "sprint19"),
                _i("graphExpansionLimit", "effective", "Neo4jGraphRetrievalProvider",
                   "限制图扩展的节点数量", "sprint19"),
                _i("maxNodes", "effective", "Neo4jGraphRetrievalProvider",
                   "限制返回的最大节点数", "sprint19"),
                _i("fusionWeight", "effective", "qa_run_service._weighted_score_fusion",
                   "参与加权融合的权重", "sprint19"),
                _i("pathMode", "partiallyEffective", "Neo4jGraphRetrievalProvider",
                   "entity-path 已实现，community-summary 和 path-and-community 尚未完全实现", "sprint19"),
                _i("mustFallbackToChunk", "effective", "Neo4jGraphRetrievalProvider",
                   "控制图谱证据是否必须回落到授权 Chunk", "sprint19"),
            ],
        ),
        # ── fusion ──
        NodeCapability(
            node_id="fusion",
            node_type="fusion",
            stage="fusion",
            items=[
                _i("method", "effective", "qa_run_service._fuse_provider_candidates",
                   "B-317/B-322: 支持 weighted、rrf 和 mmr 融合算法", "sprint63"),
                _i("rrfK", "effective", "qa_run_service._fuse_provider_candidates",
                   "B-317: RRF K 参数在 method=rrf 时生效", "sprint63"),
                _i("candidateLimit", "effective", "qa_run_service._build_effective_pipeline_params",
                   "限制融合后的候选数量", "sprint19"),
                _i("dedupBy", "effective", "qa_run_service._candidate_fusion_key",
                   "控制去重键的生成方式", "sprint19"),
            ],
        ),
        NodeCapability(
            node_id="permissionFilter",
            node_type="permissionFilter",
            stage="fusion",
            items=[
                _i("enabled", "effective", "qa_run_service._apply_permission_filter",
                   "安全门禁：PostgreSQL 真值校验，不可跳过", "sprint19"),
            ],
        ),
        # ── rerank ──
        NodeCapability(
            node_id="rerank",
            node_type="rerank",
            stage="fusion",
            items=[
                _i("enabled", "effective", "qa_run_service._build_effective_pipeline_params",
                   "控制是否进入 rerank 分支", "sprint19"),
                _i("topN", "effective", "HttpRerankProvider / IdentityRerankProvider",
                   "限制 rerank 后保留的候选数量", "sprint19"),
                _i("scoreThreshold", "effective", "qa_run_service",
                   "rerank 后低于阈值的候选被过滤", "sprint19"),
                _i("model", "partiallyEffective", "HttpRerankProvider",
                   "Rerank 模型由全局 Settings 控制，节点级 model 配置未驱动模型切换", "sprint19"),
                _i("keepRejectedReason", "partiallyEffective", "qa_run_service",
                   "被拒绝候选的拒绝原因记录在 trace 中，但格式不统一", "sprint19"),
            ],
        ),
        # ── generation ──
        NodeCapability(
            node_id="contextPacking",
            node_type="contextPacking",
            stage="generation",
            items=[
                _i("maxContextTokens", "effective", "qa_run_service._limit_candidate_pairs_by_context_tokens",
                   "控制生成上下文的 token 预算", "sprint19"),
                _i("packingStrategy", "partiallyEffective", "qa_run_service._limit_candidate_pairs_by_context_tokens",
                   "citation-aware 策略已实现基础版本，score 和 source-balanced 尚未区分", "sprint19"),
                _i("chunkWindow", "effective", "qa_run_service._expand_context_pairs_with_chunk_window",
                   "B-317/B-323: 权限过滤后按相邻 Chunk 扩展生成上下文", "sprint66"),
                _i("citationPolicy", "partiallyEffective", "qa_run_service",
                   "strict 模式下无证据会降级回答，relaxed 模式效果有限", "sprint19"),
            ],
        ),
        NodeCapability(
            node_id="generation",
            node_type="generation",
            stage="generation",
            items=[
                _i("temperature", "effective", "qa_run_service._build_effective_pipeline_params -> HttpLlmProvider",
                   "传递给 LLM 的温度参数", "sprint19"),
                _i("model", "planned", "",
                   "LLM 模型由全局 Settings 控制，节点级 model 配置未驱动模型切换"),
                _i("maxOutputTokens", "effective", "qa_run_service -> LlmProvider.generate_answer",
                   "B-317: 最大输出 token 数已传递给 LLM Provider", "sprint63"),
                _i("citationPolicy", "partiallyEffective", "qa_run_service",
                   "传递给生成 prompt 的引用策略，但效果依赖 LLM 遵循程度", "sprint19"),
            ],
        ),
        NodeCapability(
            node_id="citation",
            node_type="citation",
            stage="generation",
            items=[
                _i("minEvidence", "effective", "qa_run_service._apply_min_evidence_check",
                   "最少证据数校验，不满足时降级回答", "sprint19"),
                _i("citationPolicy", "partiallyEffective", "qa_run_service",
                   "strict 模式下强制引用，但引用准确性依赖 LLM", "sprint19"),
                _i("enableGraphLinks", "partiallyEffective", "qa_run_service",
                   "图谱链接在证据中保留，但前端展示支持有限", "sprint19"),
            ],
        ),
        # ── diagnostics ──
        NodeCapability(
            node_id="output",
            node_type="output",
            stage="diagnostics",
            items=[],
        ),
    ]


_REGISTRY_CACHE: list[NodeCapability] | None = None


def get_capability_registry() -> list[NodeCapability]:
    """获取配置能力清单（单例缓存）。"""
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None:
        _REGISTRY_CACHE = build_default_capability_registry()
    return _REGISTRY_CACHE


def get_effectiveness_summary() -> dict[str, Any]:
    """返回全量配置生效状态摘要，供 API 和 trace 使用。"""
    registry = get_capability_registry()
    total = 0
    effective = 0
    partially = 0
    planned = 0
    deprecated = 0
    for node in registry:
        for item in node.items:
            total += 1
            if item.status == "effective":
                effective += 1
            elif item.status == "partiallyEffective":
                partially += 1
            elif item.status == "planned":
                planned += 1
            elif item.status == "deprecated":
                deprecated += 1
    return {
        "total": total,
        "effective": effective,
        "partiallyEffective": partially,
        "planned": planned,
        "deprecated": deprecated,
        "nodes": [node.to_dict() for node in registry],
    }


def get_node_effectiveness(node_type: str) -> dict[str, Any] | None:
    """获取单个节点的配置生效状态。"""
    registry = get_capability_registry()
    for node in registry:
        if node.node_type == node_type:
            return node.to_dict()
    return None


def build_trace_effective_configs(
    pipeline_params: dict[str, Any],
    enabled_channels: set[str],
) -> dict[str, Any]:
    """基于实际执行参数构建 trace 中的 effectiveConfigs / ignoredConfigs。

    Args:
        pipeline_params: _build_effective_pipeline_params 的输出
        enabled_channels: 实际启用的检索通道

    Returns:
        包含 effectiveConfigs 和 ignoredConfigs 的字典
    """
    registry = get_capability_registry()
    effective_configs: list[dict[str, Any]] = []
    ignored_configs: list[dict[str, Any]] = []

    for node in registry:
        for item in node.items:
            config_entry = {
                "nodeId": node.node_id,
                "nodeType": node.node_type,
                "key": item.key,
                "status": item.status,
                "executionLocation": item.execution_location,
            }

            # 判断配置项是否在本次运行中被实际使用
            if item.status == "planned" or item.status == "deprecated":
                config_entry["reason"] = "配置项尚未实现或已废弃" if item.status == "planned" else "配置项已废弃"
                ignored_configs.append(config_entry)
            elif node.node_type in {"denseRetrieval", "sparseRetrieval", "graphRetrieval"}:
                channel_key = {"denseRetrieval": "dense", "sparseRetrieval": "sparse", "graphRetrieval": "graph"}.get(node.node_type)
                if channel_key and channel_key not in enabled_channels:
                    config_entry["reason"] = f"检索通道 {channel_key} 未启用"
                    ignored_configs.append(config_entry)
                else:
                    effective_configs.append(config_entry)
            elif node.node_type == "multiQuery":
                mq_params = pipeline_params.get("multiQuery", {})
                if not mq_params.get("enabled"):
                    config_entry["reason"] = "多查询节点未启用"
                    ignored_configs.append(config_entry)
                else:
                    effective_configs.append(config_entry)
            elif node.node_type == "rerank":
                rerank_params = pipeline_params.get("rerank", {})
                if not rerank_params.get("enabled"):
                    config_entry["reason"] = "Rerank 节点未启用"
                    ignored_configs.append(config_entry)
                else:
                    effective_configs.append(config_entry)
            else:
                effective_configs.append(config_entry)

    return {
        "effectiveConfigs": effective_configs,
        "ignoredConfigs": ignored_configs,
        "summary": {
            "effectiveCount": len(effective_configs),
            "ignoredCount": len(ignored_configs),
        },
    }
