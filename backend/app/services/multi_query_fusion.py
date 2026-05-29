"""B-322: 真 Multi Query、RRF/MMR 与融合可解释服务。

扩展检索从单查询到受控多查询，支持 RRF、MMR 和来源加权融合。

功能:
- 多查询生成：原始、同义词、关键词、约束查询
- 多 Provider 并发/顺序检索
- RRF 融合、MMR 冗余去除、来源加权融合
- Trace 显示每个候选的来源查询、Provider、原始排名和最终分数
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.services.qa_providers import ProviderCandidate


@dataclass(frozen=True)
class QueryVariant:
    """查询变体。"""

    query: str
    query_type: str  # original | synonym | keyword | constraint
    source_query: str  # 原始查询


@dataclass(frozen=True)
class RankedCandidate:
    """带排名信息的候选。"""

    candidate: ProviderCandidate
    source_query: str
    source_type: str
    original_rank: int
    original_score: float | None
    final_score: float = 0.0


def _compute_mmr_score(
    candidate: ProviderCandidate,
    selected: list[ProviderCandidate],
    lambda_param: float = 0.5,
) -> float:
    """计算 MMR (Maximal Marginal Relevance) 分数。

    MMR = λ * sim(query, doc) - (1-λ) * max(sim(doc, doc_j)) for doc_j in selected

    Args:
        candidate: 当前候选
        selected: 已选候选列表
        lambda_param: 相关性权重 (0-1)

    Returns:
        MMR 分数
    """
    relevance = candidate.raw_score or 0.0

    if not selected:
        return relevance

    # 计算与已选候选的最大相似度
    # 简化实现：使用内容长度差异作为相似度代理
    max_similarity = 0.0
    for selected_candidate in selected:
        if candidate.content and selected_candidate.content:
            # 简化的相似度计算
            len_diff = abs(len(candidate.content) - len(selected_candidate.content))
            max_len = max(len(candidate.content), len(selected_candidate.content))
            similarity = 1.0 - (len_diff / max_len) if max_len > 0 else 0.0
            max_similarity = max(max_similarity, similarity)

    return lambda_param * relevance - (1 - lambda_param) * max_similarity


def mmr_diversify(
    candidates: list[ProviderCandidate],
    lambda_param: float = 0.5,
    limit: int = 10,
) -> list[ProviderCandidate]:
    """使用 MMR 算法去除冗余候选。

    Args:
        candidates: 候选列表
        lambda_param: 相关性权重 (0-1)
        limit: 返回数量限制

    Returns:
        去重后的候选列表
    """
    if not candidates:
        return []

    selected: list[ProviderCandidate] = []
    remaining = list(candidates)

    while remaining and len(selected) < limit:
        # 计算每个剩余候选的 MMR 分数
        best_candidate = None
        best_score = float("-inf")

        for candidate in remaining:
            score = _compute_mmr_score(candidate, selected, lambda_param)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_candidate:
            selected.append(best_candidate)
            remaining.remove(best_candidate)
        else:
            break

    return selected


def _rrf_score(rank: int, k: int = 60) -> float:
    """计算 RRF (Reciprocal Rank Fusion) 分数。"""
    return 1.0 / (k + rank)


def multi_query_rrf_fusion(
    candidates_by_query: dict[str, list[ProviderCandidate]],
    k: int = 60,
    limit: int = 20,
) -> list[RankedCandidate]:
    """多查询 RRF 融合。

    Args:
        candidates_by_query: 按查询分组的候选字典
        k: RRF K 参数
        limit: 返回数量限制

    Returns:
        融合后的排名候选列表
    """
    # 为每个查询的候选计算 RRF 分数
    rrf_scores: dict[str, float] = {}  # chunk_id -> rrf_score
    candidate_info: dict[str, RankedCandidate] = {}  # chunk_id -> RankedCandidate

    for query, candidates in candidates_by_query.items():
        for rank, candidate in enumerate(candidates):
            chunk_key = str(candidate.chunk_id) if candidate.chunk_id else f"diag_{rank}"
            rrf = _rrf_score(rank, k)

            if chunk_key in rrf_scores:
                rrf_scores[chunk_key] += rrf
                # 更新来源查询信息
                existing = candidate_info[chunk_key]
                candidate_info[chunk_key] = RankedCandidate(
                    candidate=candidate,
                    source_query=f"{existing.source_query}; {query}",
                    source_type=candidate.source_type,
                    original_rank=rank,
                    original_score=candidate.raw_score,
                    final_score=rrf_scores[chunk_key],
                )
            else:
                rrf_scores[chunk_key] = rrf
                candidate_info[chunk_key] = RankedCandidate(
                    candidate=candidate,
                    source_query=query,
                    source_type=candidate.source_type,
                    original_rank=rank,
                    original_score=candidate.raw_score,
                    final_score=rrf,
                )

    # 按 RRF 分数排序
    sorted_candidates = sorted(
        candidate_info.values(),
        key=lambda x: x.final_score,
        reverse=True,
    )

    return sorted_candidates[:limit]


def multi_query_weighted_fusion(
    candidates_by_query: dict[str, list[ProviderCandidate]],
    weights: dict[str, float] | None = None,
    limit: int = 20,
) -> list[RankedCandidate]:
    """多查询加权融合。

    Args:
        candidates_by_query: 按查询分组的候选字典
        weights: 来源权重
        limit: 返回数量限制

    Returns:
        融合后的排名候选列表
    """
    weights = weights or {"dense": 1.0, "sparse": 1.0, "graph": 1.0}

    # 合并所有候选并计算加权分数
    all_candidates: dict[str, RankedCandidate] = {}

    for query, candidates in candidates_by_query.items():
        for rank, candidate in enumerate(candidates):
            chunk_key = str(candidate.chunk_id) if candidate.chunk_id else f"diag_{rank}"
            weighted_score = (candidate.raw_score or 0) * weights.get(candidate.source_type, 1.0)

            if chunk_key in all_candidates:
                # 多查询命中同一候选，累加分数
                existing = all_candidates[chunk_key]
                all_candidates[chunk_key] = RankedCandidate(
                    candidate=candidate,
                    source_query=f"{existing.source_query}; {query}",
                    source_type=candidate.source_type,
                    original_rank=rank,
                    original_score=candidate.raw_score,
                    final_score=existing.final_score + weighted_score,
                )
            else:
                all_candidates[chunk_key] = RankedCandidate(
                    candidate=candidate,
                    source_query=query,
                    source_type=candidate.source_type,
                    original_rank=rank,
                    original_score=candidate.raw_score,
                    final_score=weighted_score,
                )

    # 按分数排序
    sorted_candidates = sorted(
        all_candidates.values(),
        key=lambda x: x.final_score,
        reverse=True,
    )

    return sorted_candidates[:limit]


def build_fusion_trace(
    ranked_candidates: list[RankedCandidate],
) -> list[dict[str, Any]]:
    """构建融合 Trace，显示每个候选的来源信息。

    Args:
        ranked_candidates: 排名候选列表

    Returns:
        Trace 数据列表
    """
    trace = []
    for i, ranked in enumerate(ranked_candidates):
        trace.append({
            "rank": i + 1,
            "chunkId": str(ranked.candidate.chunk_id) if ranked.candidate.chunk_id else None,
            "sourceQuery": ranked.source_query,
            "sourceType": ranked.source_type,
            "originalRank": ranked.original_rank,
            "originalScore": ranked.original_score,
            "finalScore": ranked.final_score,
            "contentPreview": (ranked.candidate.content or "")[:100],
        })
    return trace


def get_multi_query_fusion_info() -> dict[str, Any]:
    """获取多查询融合信息。"""
    return {
        "methods": [
            {
                "name": "rrf",
                "label": "RRF 融合",
                "description": "Reciprocal Rank Fusion，基于排名的融合",
                "params": [
                    {"key": "k", "label": "RRF K", "type": "number", "default": 60},
                ],
            },
            {
                "name": "weighted",
                "label": "加权融合",
                "description": "基于分数权重的融合",
                "params": [
                    {"key": "denseWeight", "label": "Dense 权重", "type": "number", "default": 1.0},
                    {"key": "sparseWeight", "label": "Sparse 权重", "type": "number", "default": 1.0},
                    {"key": "graphWeight", "label": "Graph 权重", "type": "number", "default": 1.0},
                ],
            },
            {
                "name": "mmr",
                "label": "MMR 去重",
                "description": "Maximal Marginal Relevance，去除冗余候选",
                "params": [
                    {"key": "lambda", "label": "相关性权重", "type": "number", "default": 0.5},
                ],
            },
        ],
        "queryTypes": [
            {"name": "original", "label": "原始查询"},
            {"name": "synonym", "label": "同义词查询"},
            {"name": "keyword", "label": "关键词查询"},
            {"name": "constraint", "label": "约束查询"},
        ],
    }
