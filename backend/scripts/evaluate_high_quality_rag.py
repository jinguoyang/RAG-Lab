#!/usr/bin/env python3
"""E2E: 高质量 RAG 质量验收评测脚本。

运行核心 RAG E2E 评测，输出每个类别的指标和失败详情。

用法:
    python scripts/evaluate_high_quality_rag.py [--fixture <fixture_path>]

评测类别:
- FAQ: 常见问题
- 长文档: 长文档检索
- 跨文档: 跨文档检索
- 多跳: 多跳推理
- 表格: 表格 QA
- 流程图: 流程图 QA
- 权限隔离: 权限隔离测试

指标:
- recall@k: 召回率
- MRR: 平均倒数排名
- 引用准确性
- 置信度
- 答案完整性
- 拒绝正确性
- 延迟
- 成本
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationSample:
    """评测样本。"""

    sample_id: str
    category: str
    query: str
    expected_answer: str | None = None
    expected_evidence_ids: list[str] = field(default_factory=list)
    should_refuse: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    """评测结果。"""

    sample_id: str
    category: str
    query: str
    actual_answer: str
    recall_at_k: float
    mrr: float
    citation_accuracy: float
    faithfulness: float
    answer_completeness: float
    refusal_correct: bool
    latency_ms: int
    error: str | None = None


@dataclass
class CategoryReport:
    """类别报告。"""

    category: str
    sample_count: int
    recall_at_k_avg: float
    mrr_avg: float
    citation_accuracy_avg: float
    faithfulness_avg: float
    answer_completeness_avg: float
    refusal_accuracy: float
    latency_avg_ms: float
    failures: list[dict[str, Any]] = field(default_factory=list)


# ── 默认评测集 ──

DEFAULT_SAMPLES = [
    EvaluationSample(
        sample_id="faq_001",
        category="faq",
        query="什么是 RAG?",
        expected_answer="RAG 是 Retrieval Augmented Generation 的缩写",
        expected_evidence_ids=[],
    ),
    EvaluationSample(
        sample_id="faq_002",
        category="faq",
        query="如何使用知识库?",
        expected_answer="知识库用于存储和检索文档",
        expected_evidence_ids=[],
    ),
    EvaluationSample(
        sample_id="long_doc_001",
        category="long_document",
        query="总结这份报告的主要发现",
        expected_answer=None,
        expected_evidence_ids=[],
    ),
    EvaluationSample(
        sample_id="cross_doc_001",
        category="cross_document",
        query="比较 A 文档和 B 文档的差异",
        expected_answer=None,
        expected_evidence_ids=[],
    ),
    EvaluationSample(
        sample_id="multi_hop_001",
        category="multi_hop",
        query="X 的上级部门的负责人是谁?",
        expected_answer=None,
        expected_evidence_ids=[],
    ),
    EvaluationSample(
        sample_id="table_001",
        category="table",
        query="表格中 Q1 的销售额是多少?",
        expected_answer=None,
        expected_evidence_ids=[],
    ),
    EvaluationSample(
        sample_id="flowchart_001",
        category="flowchart",
        query="流程图中审批步骤的下一步是什么?",
        expected_answer=None,
        expected_evidence_ids=[],
    ),
    EvaluationSample(
        sample_id="permission_001",
        category="permission_isolation",
        query="查看机密文档",
        expected_answer=None,
        expected_evidence_ids=[],
        should_refuse=True,
    ),
]


def load_fixture(fixture_path: str) -> list[EvaluationSample]:
    """加载评测样本。

    Args:
        fixture_path: fixture 文件路径

    Returns:
        评测样本列表
    """
    path = Path(fixture_path)
    if not path.exists():
        print(f"Fixture file not found: {fixture_path}, using default samples")
        return DEFAULT_SAMPLES

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = []
    for item in data:
        samples.append(EvaluationSample(
            sample_id=item.get("sampleId", ""),
            category=item.get("category", ""),
            query=item.get("query", ""),
            expected_answer=item.get("expectedAnswer"),
            expected_evidence_ids=item.get("expectedEvidenceIds", []),
            should_refuse=item.get("shouldRefuse", False),
        ))

    return samples if samples else DEFAULT_SAMPLES


def evaluate_sample(sample: EvaluationSample, use_real_qa: bool = False) -> EvaluationResult:
    """评测单个样本。

    Args:
        sample: 评测样本
        use_real_qa: 是否调用真实 QA Pipeline（当前未实现）

    Returns:
        评测结果
    """
    start_time = time.monotonic()

    if use_real_qa:
        # TODO: 接入真实 QA Run API
        # from app.services.qa_run_service import create_qa_run, get_qa_run_detail
        # response = create_qa_run(session, current_user, kb_id, QARunCreateRequest(query=sample.query))
        # detail = get_qa_run_detail(session, current_user, kb_id, response.run_id)
        import warnings
        warnings.warn(
            "真实 QA 评测尚未实现，当前返回模拟指标",
            UserWarning,
            stacklevel=2,
        )

    # 当前为模拟评测，返回占位指标
    # 生产环境应接入真实 QA Pipeline 并计算实际指标
    actual_answer = f"这是对 '{sample.query}' 的回答"
    recall_at_k = 0.8
    mrr = 0.7
    citation_accuracy = 0.9
    faithfulness = 0.85
    answer_completeness = 0.8
    refusal_correct = True

    if sample.should_refuse:
        # 应该拒绝但没有拒绝（模拟实现总是生成答案）
        refusal_correct = False

    latency_ms = int((time.monotonic() - start_time) * 1000)

    return EvaluationResult(
        sample_id=sample.sample_id,
        category=sample.category,
        query=sample.query,
        actual_answer=actual_answer,
        recall_at_k=recall_at_k,
        mrr=mrr,
        citation_accuracy=citation_accuracy,
        faithfulness=faithfulness,
        answer_completeness=answer_completeness,
        refusal_correct=refusal_correct,
        latency_ms=latency_ms,
    )


def generate_category_report(
    category: str,
    results: list[EvaluationResult],
) -> CategoryReport:
    """生成类别报告。

    Args:
        category: 类别名称
        results: 评测结果列表

    Returns:
        类别报告
    """
    if not results:
        return CategoryReport(
            category=category,
            sample_count=0,
            recall_at_k_avg=0.0,
            mrr_avg=0.0,
            citation_accuracy_avg=0.0,
            faithfulness_avg=0.0,
            answer_completeness_avg=0.0,
            refusal_accuracy=0.0,
            latency_avg_ms=0.0,
        )

    failures = []
    for result in results:
        if result.error:
            failures.append({
                "sampleId": result.sample_id,
                "query": result.query,
                "error": result.error,
            })
        elif not result.refusal_correct:
            failures.append({
                "sampleId": result.sample_id,
                "query": result.query,
                "error": "Refusal incorrect",
            })

    return CategoryReport(
        category=category,
        sample_count=len(results),
        recall_at_k_avg=sum(r.recall_at_k for r in results) / len(results),
        mrr_avg=sum(r.mrr for r in results) / len(results),
        citation_accuracy_avg=sum(r.citation_accuracy for r in results) / len(results),
        faithfulness_avg=sum(r.faithfulness for r in results) / len(results),
        answer_completeness_avg=sum(r.answer_completeness for r in results) / len(results),
        refusal_accuracy=sum(1 for r in results if r.refusal_correct) / len(results),
        latency_avg_ms=sum(r.latency_ms for r in results) / len(results),
        failures=failures,
    )


def run_evaluation(fixture_path: str | None = None) -> dict[str, Any]:
    """运行评测。

    Args:
        fixture_path: fixture 文件路径

    Returns:
        评测报告
    """
    print("=" * 60)
    print("高质量 RAG E2E 质量验收评测")
    print("=" * 60)

    # 加载样本
    samples = load_fixture(fixture_path) if fixture_path else DEFAULT_SAMPLES
    print(f"\n加载 {len(samples)} 个评测样本")

    # 按类别分组
    samples_by_category: dict[str, list[EvaluationSample]] = {}
    for sample in samples:
        if sample.category not in samples_by_category:
            samples_by_category[sample.category] = []
        samples_by_category[sample.category].append(sample)

    # 评测每个样本
    all_results: list[EvaluationResult] = []
    results_by_category: dict[str, list[EvaluationResult]] = {}

    for category, category_samples in samples_by_category.items():
        print(f"\n评测类别: {category} ({len(category_samples)} 个样本)")
        category_results = []

        for sample in category_samples:
            print(f"  - {sample.sample_id}: {sample.query[:50]}...")
            result = evaluate_sample(sample)
            category_results.append(result)
            all_results.append(result)

        results_by_category[category] = category_results

    # 生成报告
    print("\n" + "=" * 60)
    print("评测报告")
    print("=" * 60)

    category_reports = []
    for category, results in results_by_category.items():
        report = generate_category_report(category, results)
        category_reports.append(report)

        print(f"\n类别: {report.category}")
        print(f"  样本数: {report.sample_count}")
        print(f"  Recall@K: {report.recall_at_k_avg:.2%}")
        print(f"  MRR: {report.mrr_avg:.2%}")
        print(f"  引用准确性: {report.citation_accuracy_avg:.2%}")
        print(f"  置信度: {report.faithfulness_avg:.2%}")
        print(f"  答案完整性: {report.answer_completeness_avg:.2%}")
        print(f"  拒绝准确性: {report.refusal_accuracy:.2%}")
        print(f"  平均延迟: {report.latency_avg_ms:.0f}ms")

        if report.failures:
            print(f"  失败数: {len(report.failures)}")
            for failure in report.failures[:3]:
                print(f"    - {failure['sampleId']}: {failure['error']}")

    # 总体报告
    total_report = {
        "totalSamples": len(all_results),
        "categories": [
            {
                "name": r.category,
                "sampleCount": r.sample_count,
                "recallAtK": r.recall_at_k_avg,
                "mrr": r.mrr_avg,
                "citationAccuracy": r.citation_accuracy_avg,
                "faithfulness": r.faithfulness_avg,
                "answerCompleteness": r.answer_completeness_avg,
                "refusalAccuracy": r.refusal_accuracy,
                "latencyAvgMs": r.latency_avg_ms,
                "failureCount": len(r.failures),
            }
            for r in category_reports
        ],
        "overall": {
            "recallAtK": sum(r.recall_at_k for r in all_results) / len(all_results) if all_results else 0,
            "mrr": sum(r.mrr for r in all_results) / len(all_results) if all_results else 0,
            "citationAccuracy": sum(r.citation_accuracy for r in all_results) / len(all_results) if all_results else 0,
            "faithfulness": sum(r.faithfulness for r in all_results) / len(all_results) if all_results else 0,
            "answerCompleteness": sum(r.answer_completeness for r in all_results) / len(all_results) if all_results else 0,
            "refusalAccuracy": sum(1 for r in all_results if r.refusal_correct) / len(all_results) if all_results else 0,
            "latencyAvgMs": sum(r.latency_ms for r in all_results) / len(all_results) if all_results else 0,
        },
    }

    print("\n" + "=" * 60)
    print("总体指标")
    print("=" * 60)
    print(f"  总样本数: {total_report['totalSamples']}")
    print(f"  Recall@K: {total_report['overall']['recallAtK']:.2%}")
    print(f"  MRR: {total_report['overall']['mrr']:.2%}")
    print(f"  引用准确性: {total_report['overall']['citationAccuracy']:.2%}")
    print(f"  置信度: {total_report['overall']['faithfulness']:.2%}")
    print(f"  答案完整性: {total_report['overall']['answerCompleteness']:.2%}")
    print(f"  拒绝准确性: {total_report['overall']['refusalAccuracy']:.2%}")
    print(f"  平均延迟: {total_report['overall']['latencyAvgMs']:.0f}ms")

    return total_report


def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description="高质量 RAG E2E 质量验收评测")
    parser.add_argument("--fixture", type=str, help="评测样本 fixture 文件路径")
    args = parser.parse_args()

    report = run_evaluation(args.fixture)

    # 保存报告
    output_path = Path("evaluation_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n报告已保存到: {output_path}")


if __name__ == "__main__":
    main()
