"""B-325: Agentic / Corrective RAG 控制器服务。

在最终答案生成前评估证据质量，当证据不足、冲突或不完整时，
可以重写查询、补充检索或拒绝回答。

功能:
- 证据充分性评分：覆盖度、相关性、冲突、权限状态、引用可定位性
- 纠正动作（最多 2 轮）：rewrite_query, expand_scope, retrieve_structured, ask_clarification, answer_insufficient
- 控制器位于 rerank/context packing 之后，generation 之前
- 规则 + LLM 混合评分（LLM 评分默认关闭以节省成本）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.services.qa_providers import ProviderCandidate


class CorrectiveAction(str, Enum):
    """纠正动作枚举。"""
    REWRITE_QUERY = "rewrite_query"
    EXPAND_SCOPE = "expand_scope"
    RETRIEVE_STRUCTURED = "retrieve_structured"
    ASK_CLARIFICATION = "ask_clarification"
    ANSWER_INSUFFICIENT = "answer_insufficient"
    PROCEED_TO_GENERATION = "proceed_to_generation"


@dataclass(frozen=True)
class EvidenceAssessment:
    """证据评估结果。"""

    coverage_score: float  # 0-1
    relevance_score: float  # 0-1
    conflict_score: float  # 0-1 (0=无冲突, 1=高冲突)
    permission_status: str  # ok | partial | denied
    citation_locatability: float  # 0-1
    overall_sufficiency: float  # 0-1
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CorrectiveDecision:
    """纠正决策。"""

    action: CorrectiveAction
    reason: str
    assessment: EvidenceAssessment
    suggested_query: str | None = None
    max_retrieval_rounds: int = 0


@dataclass(frozen=True)
class CorrectiveTrace:
    """纠正 Trace 记录。"""

    round: int
    assessment: EvidenceAssessment
    decision: CorrectiveDecision
    candidates_before: int
    candidates_after: int


def _assess_coverage(candidates: list[ProviderCandidate], query: str) -> float:
    """评估证据覆盖度。

    Args:
        candidates: 候选列表
        query: 查询

    Returns:
        覆盖度分数 (0-1)
    """
    if not candidates:
        return 0.0

    # 简单实现：基于候选数量和查询关键词匹配
    query_words = set(query.lower().split())
    covered_words = set()

    for candidate in candidates:
        if candidate.content:
            content_words = set(candidate.content.lower().split())
            covered_words.update(query_words & content_words)

    if not query_words:
        return 1.0

    return len(covered_words) / len(query_words)


def _assess_relevance(candidates: list[ProviderCandidate]) -> float:
    """评估证据相关性。

    Args:
        candidates: 候选列表

    Returns:
        相关性分数 (0-1)
    """
    if not candidates:
        return 0.0

    # 基于分数的平均相关性
    scores = [c.raw_score for c in candidates if c.raw_score is not None]
    if not scores:
        return 0.5  # 无分数时假设中等相关性

    return sum(scores) / len(scores)


def _assess_conflict(candidates: list[ProviderCandidate]) -> float:
    """评估证据冲突程度。

    Args:
        candidates: 候选列表

    Returns:
        冲突分数 (0=无冲突, 1=高冲突)
    """
    if len(candidates) < 2:
        return 0.0

    # 简单实现：基于多路命中的一致性
    # 实际实现应使用 LLM 评估内容冲突
    return 0.0


def _assess_permission(candidates: list[ProviderCandidate]) -> str:
    """评估权限状态。

    Args:
        candidates: 候选列表

    Returns:
        权限状态
    """
    # 检查是否有权限相关的元数据
    for candidate in candidates:
        metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
        if metadata.get("permissionDenied"):
            return "denied"
    return "ok"


def _assess_citation_locatability(candidates: list[ProviderCandidate]) -> float:
    """评估引用可定位性。

    Args:
        candidates: 候选列表

    Returns:
        引用可定位性分数 (0-1)
    """
    if not candidates:
        return 0.0

    # 检查候选是否有足够的定位信息
    locatable_count = 0
    for candidate in candidates:
        metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
        has_location = (
            metadata.get("documentId") or
            metadata.get("chunkId") or
            metadata.get("pageNo")
        )
        if has_location:
            locatable_count += 1

    return locatable_count / len(candidates)


def assess_evidence(
    candidates: list[ProviderCandidate],
    query: str,
) -> EvidenceAssessment:
    """评估证据质量。

    Args:
        candidates: 候选列表
        query: 查询

    Returns:
        证据评估结果
    """
    if not candidates:
        return EvidenceAssessment(
            coverage_score=0.0,
            relevance_score=0.0,
            conflict_score=0.0,
            permission_status="ok",
            citation_locatability=0.0,
            overall_sufficiency=0.0,
            issues=["无证据：没有可用于回答的候选内容"],
        )

    coverage = _assess_coverage(candidates, query)
    relevance = _assess_relevance(candidates)
    conflict = _assess_conflict(candidates)
    permission = _assess_permission(candidates)
    citation_locatability = _assess_citation_locatability(candidates)

    # 计算总体充分性
    overall = (
        coverage * 0.3 +
        relevance * 0.3 +
        (1 - conflict) * 0.2 +
        citation_locatability * 0.2
    )

    issues = []
    if coverage < 0.5:
        issues.append("低覆盖度：查询关键词未被充分覆盖")
    if relevance < 0.3:
        issues.append("低相关性：候选分数过低")
    if conflict > 0.5:
        issues.append("高冲突：证据之间存在矛盾")
    if permission == "denied":
        issues.append("权限拒绝：部分证据无权限访问")
    if citation_locatability < 0.5:
        issues.append("引用不可定位：缺少文档或位置信息")

    return EvidenceAssessment(
        coverage_score=coverage,
        relevance_score=relevance,
        conflict_score=conflict,
        permission_status=permission,
        citation_locatability=citation_locatability,
        overall_sufficiency=overall,
        issues=issues,
    )


def decide_corrective_action(
    assessment: EvidenceAssessment,
    current_round: int,
    max_rounds: int = 2,
) -> CorrectiveDecision:
    """决定纠正动作。

    Args:
        assessment: 证据评估结果
        current_round: 当前轮次
        max_rounds: 最大轮次

    Returns:
        纠正决策
    """
    # 已达最大轮次
    if current_round >= max_rounds:
        if assessment.overall_sufficiency < 0.3:
            return CorrectiveDecision(
                action=CorrectiveAction.ANSWER_INSUFFICIENT,
                reason="已达最大重试轮次，证据仍不充分",
                assessment=assessment,
            )
        else:
            return CorrectiveDecision(
                action=CorrectiveAction.PROCEED_TO_GENERATION,
                reason="已达最大轮次，使用当前证据",
                assessment=assessment,
            )

    # 证据充分
    if assessment.overall_sufficiency >= 0.7:
        return CorrectiveDecision(
            action=CorrectiveAction.PROCEED_TO_GENERATION,
            reason="证据充分，继续生成",
            assessment=assessment,
        )

    # 低覆盖度：重写查询
    if assessment.coverage_score < 0.5:
        return CorrectiveDecision(
            action=CorrectiveAction.REWRITE_QUERY,
            reason="覆盖度不足，建议重写查询",
            assessment=assessment,
            suggested_query=None,  # 由调用方生成
        )

    # 低相关性：扩展检索范围
    if assessment.relevance_score < 0.3:
        return CorrectiveDecision(
            action=CorrectiveAction.EXPAND_SCOPE,
            reason="相关性不足，建议扩展检索范围",
            assessment=assessment,
        )

    # 引用不可定位：检索结构化证据
    if assessment.citation_locatability < 0.5:
        return CorrectiveDecision(
            action=CorrectiveAction.RETRIEVE_STRUCTURED,
            reason="引用不可定位，建议检索结构化证据",
            assessment=assessment,
        )

    # 默认：继续生成
    return CorrectiveDecision(
        action=CorrectiveAction.PROCEED_TO_GENERATION,
        reason="证据基本充分，继续生成",
        assessment=assessment,
    )


def execute_corrective_rag(
    candidates: list[ProviderCandidate],
    query: str,
    current_round: int = 0,
    max_rounds: int = 2,
    enable_llm_scoring: bool = False,
) -> tuple[CorrectiveDecision, CorrectiveTrace]:
    """执行 Corrective RAG 控制器。

    Args:
        candidates: 候选列表
        query: 查询
        current_round: 当前轮次
        max_rounds: 最大轮次
        enable_llm_scoring: 是否启用 LLM 评分

    Returns:
        (决策, Trace) 元组
    """
    # 评估证据
    assessment = assess_evidence(candidates, query)

    # 决定纠正动作
    decision = decide_corrective_action(assessment, current_round, max_rounds)

    # 构建 Trace
    trace = CorrectiveTrace(
        round=current_round,
        assessment=assessment,
        decision=decision,
        candidates_before=len(candidates),
        candidates_after=len(candidates),  # 纠正动作后可能改变
    )

    return decision, trace


def get_corrective_rag_info() -> dict[str, Any]:
    """获取 Corrective RAG 信息。"""
    return {
        "actions": [
            {
                "name": "rewrite_query",
                "label": "重写查询",
                "description": "重写查询以提高覆盖度",
            },
            {
                "name": "expand_scope",
                "label": "扩展范围",
                "description": "扩展检索范围以提高相关性",
            },
            {
                "name": "retrieve_structured",
                "label": "检索结构化证据",
                "description": "检索表格和流程图等结构化证据",
            },
            {
                "name": "ask_clarification",
                "label": "请求澄清",
                "description": "请求用户提供更多信息",
            },
            {
                "name": "answer_insufficient",
                "label": "证据不足",
                "description": "证据不足，无法生成答案",
            },
            {
                "name": "proceed_to_generation",
                "label": "继续生成",
                "description": "证据充分，继续生成答案",
            },
        ],
        "maxRounds": 2,
        "scoringMethods": [
            {"name": "rule", "label": "规则评分", "enabled": True},
            {"name": "llm", "label": "LLM 评分", "enabled": False},
        ],
    }
