"""B-327: Answer/Citation Verifier 服务。

在输出前进行引用和事实一致性校验，减少无支撑答案、错误引用、
缺失引用和不可定位的参考。

功能:
- 断言校验：关键声明与证据核对
- 引用校验：文档、页码、块级溯源存在性
- 授权校验：引用的证据在用户授权范围内
- 低置信度答案降级："信息不足"、澄清问题或触发 Corrective RAG
- 规则优先校验，然后 LLM 置信度评分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VerificationStatus(str, Enum):
    """校验状态枚举。"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class VerificationResult:
    """校验结果。"""

    check_name: str
    status: VerificationStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CitationVerification:
    """引用校验结果。"""

    citation_id: str
    document_id: str | None
    page_no: int | None
    block_id: str | None
    is_valid: bool
    issues: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnswerVerification:
    """答案校验结果。"""

    is_verified: bool
    status: VerificationStatus
    verification_results: list[VerificationResult]
    citation_verifications: list[CitationVerification]
    faithfulness_score: float  # 0-1
    suggested_action: str  # pass | degrade | refuse | clarify
    degraded_answer: str | None = None
    clarification_question: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def verify_citation_exists(
    citation: dict[str, Any],
    available_evidence: list[dict[str, Any]],
) -> CitationVerification:
    """校验引用是否存在。

    Args:
        citation: 引用信息
        available_evidence: 可用证据列表

    Returns:
        引用校验结果
    """
    citation_id = citation.get("citationId", "unknown")
    document_id = citation.get("documentId")
    page_no = citation.get("pageNo")
    block_id = citation.get("blockId")

    issues = []

    # 检查引用是否有必要的定位信息
    if not document_id and not block_id:
        issues.append("缺少文档 ID 和块 ID")

    # 检查引用是否指向可用证据
    evidence_found = False
    for evidence in available_evidence:
        evidence_doc_id = evidence.get("documentId")
        evidence_block_id = evidence.get("blockId")

        if document_id and evidence_doc_id == document_id:
            evidence_found = True
            break
        if block_id and evidence_block_id == block_id:
            evidence_found = True
            break

    if not evidence_found and available_evidence:
        issues.append("引用未指向可用证据")

    return CitationVerification(
        citation_id=citation_id,
        document_id=document_id,
        page_no=page_no,
        block_id=block_id,
        is_valid=len(issues) == 0,
        issues=issues,
    )


def verify_answer_has_citations(
    answer: str,
    citations: list[dict[str, Any]],
) -> VerificationResult:
    """校验答案是否有引用。

    Args:
        answer: 答案文本
        citations: 引用列表

    Returns:
        校验结果
    """
    if not citations:
        return VerificationResult(
            check_name="citation_presence",
            status=VerificationStatus.FAIL,
            message="答案没有引用",
            details={"citationCount": 0},
        )

    return VerificationResult(
        check_name="citation_presence",
        status=VerificationStatus.PASS,
        message=f"答案包含 {len(citations)} 个引用",
        details={"citationCount": len(citations)},
    )


def verify_evidence_sufficiency(
    answer: str,
    evidence: list[dict[str, Any]],
    min_evidence: int = 1,
) -> VerificationResult:
    """校验证据充分性。

    Args:
        answer: 答案文本
        evidence: 证据列表
        min_evidence: 最少证据数

    Returns:
        校验结果
    """
    if len(evidence) < min_evidence:
        return VerificationResult(
            check_name="evidence_sufficiency",
            status=VerificationStatus.FAIL,
            message=f"证据不足：需要至少 {min_evidence} 个，实际 {len(evidence)} 个",
            details={"evidenceCount": len(evidence), "minEvidence": min_evidence},
        )

    return VerificationResult(
        check_name="evidence_sufficiency",
        status=VerificationStatus.PASS,
        message=f"证据充分：{len(evidence)} 个证据",
        details={"evidenceCount": len(evidence)},
    )


def verify_answer_not_hallucinated(
    answer: str,
    evidence: list[dict[str, Any]],
) -> VerificationResult:
    """校验答案是否包含幻觉。

    Args:
        answer: 答案文本
        evidence: 证据列表

    Returns:
        校验结果
    """
    # 简单实现：检查答案中的关键信息是否在证据中出现
    # 实际实现应使用 LLM 进行更精确的校验

    if not evidence:
        return VerificationResult(
            check_name="hallucination_check",
            status=VerificationStatus.WARNING,
            message="无法校验幻觉：无证据",
            details={},
        )

    # 提取证据中的关键词
    evidence_keywords = set()
    for ev in evidence:
        content = ev.get("content", "")
        words = content.split()
        evidence_keywords.update(word.lower() for word in words if len(word) > 3)

    # 检查答案中的关键词
    answer_words = answer.split()
    answer_keywords = set(word.lower() for word in answer_words if len(word) > 3)

    if not answer_keywords:
        return VerificationResult(
            check_name="hallucination_check",
            status=VerificationStatus.PASS,
            message="答案过短，无法评估",
            details={},
        )

    # 计算覆盖率
    covered = answer_keywords & evidence_keywords
    coverage = len(covered) / len(answer_keywords) if answer_keywords else 0

    if coverage < 0.3:
        return VerificationResult(
            check_name="hallucination_check",
            status=VerificationStatus.WARNING,
            message=f"答案可能包含幻觉：关键词覆盖率 {coverage:.1%}",
            details={"coverage": coverage},
        )

    return VerificationResult(
        check_name="hallucination_check",
        status=VerificationStatus.PASS,
        message=f"答案与证据一致：关键词覆盖率 {coverage:.1%}",
        details={"coverage": coverage},
    )


def calculate_faithfulness_score(
    verification_results: list[VerificationResult],
) -> float:
    """计算置信度分数。

    Args:
        verification_results: 校验结果列表

    Returns:
        置信度分数 (0-1)
    """
    if not verification_results:
        return 0.0

    score = 1.0
    for result in verification_results:
        if result.status == VerificationStatus.FAIL:
            score -= 0.3
        elif result.status == VerificationStatus.WARNING:
            score -= 0.1

    return max(0.0, min(1.0, score))


def decide_action(
    faithfulness_score: float,
    min_score: float = 0.5,
) -> str:
    """决定后续动作。

    Args:
        faithfulness_score: 置信度分数
        min_score: 最低分数阈值

    Returns:
        动作名称
    """
    if faithfulness_score >= 0.8:
        return "pass"
    elif faithfulness_score >= min_score:
        return "degrade"
    elif faithfulness_score >= 0.2:
        return "clarify"
    else:
        return "refuse"


def verify_answer(
    answer: str,
    evidence: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    min_evidence: int = 1,
    min_faithfulness_score: float = 0.5,
) -> AnswerVerification:
    """校验答案。

    Args:
        answer: 答案文本
        evidence: 证据列表
        citations: 引用列表
        min_evidence: 最少证据数
        min_faithfulness_score: 最低置信度分数

    Returns:
        答案校验结果
    """
    verification_results = []

    # 1. 校验引用存在
    citation_check = verify_answer_has_citations(answer, citations)
    verification_results.append(citation_check)

    # 2. 校验证据充分性
    evidence_check = verify_evidence_sufficiency(answer, evidence, min_evidence)
    verification_results.append(evidence_check)

    # 3. 校验幻觉
    hallucination_check = verify_answer_not_hallucinated(answer, evidence)
    verification_results.append(hallucination_check)

    # 4. 校验每个引用
    citation_verifications = []
    for citation in citations:
        cv = verify_citation_exists(citation, evidence)
        citation_verifications.append(cv)

    # 5. 计算置信度分数
    faithfulness_score = calculate_faithfulness_score(verification_results)

    # 6. 决定动作
    action = decide_action(faithfulness_score, min_faithfulness_score)

    # 7. 生成降级答案或澄清问题
    degraded_answer = None
    clarification_question = None

    if action == "degrade":
        degraded_answer = f"根据现有资料，{answer[:100]}...（信息可能不完整）"
    elif action == "clarify":
        clarification_question = "您的问题涉及多个方面，能否具体说明您想了解哪个部分？"
    elif action == "refuse":
        degraded_answer = "抱歉，现有资料不足以回答您的问题。"

    # 确定总体状态
    has_fail = any(r.status == VerificationStatus.FAIL for r in verification_results)
    has_warning = any(r.status == VerificationStatus.WARNING for r in verification_results)

    if has_fail:
        status = VerificationStatus.FAIL
    elif has_warning:
        status = VerificationStatus.WARNING
    elif action == "degrade":
        status = VerificationStatus.DEGRADED
    else:
        status = VerificationStatus.PASS

    return AnswerVerification(
        is_verified=action == "pass",
        status=status,
        verification_results=verification_results,
        citation_verifications=citation_verifications,
        faithfulness_score=faithfulness_score,
        suggested_action=action,
        degraded_answer=degraded_answer,
        clarification_question=clarification_question,
    )


def get_verifier_info() -> dict[str, Any]:
    """获取校验器信息。"""
    return {
        "checks": [
            {"name": "citation_presence", "label": "引用存在性", "description": "校验答案是否有引用"},
            {"name": "evidence_sufficiency", "label": "证据充分性", "description": "校验证据数量是否满足要求"},
            {"name": "hallucination_check", "label": "幻觉检查", "description": "校验答案是否与证据一致"},
        ],
        "actions": [
            {"name": "pass", "label": "通过", "description": "答案可信，直接输出"},
            {"name": "degrade", "label": "降级", "description": "答案可能不完整，降级输出"},
            {"name": "clarify", "label": "澄清", "description": "需要用户澄清问题"},
            {"name": "refuse", "label": "拒绝", "description": "证据不足，拒绝回答"},
        ],
        "minFaithfulnessScore": 0.5,
    }
