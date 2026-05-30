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
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib import error, request


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


class QAEvaluationRunner(Protocol):
    """真实 QA 评测 Runner 协议。

    Runner 负责调用真实 QA 链路并返回 QA Run 详情结构；指标计算仍由本脚本统一完成。
    """

    def run(self, sample: EvaluationSample) -> dict[str, Any]:
        """执行单个评测样本并返回 QA Run 详情。"""
        ...


@dataclass(frozen=True)
class HttpQARunEvaluationRunner:
    """通过现有 QA Run HTTP API 执行真实评测。"""

    api_base_url: str
    kb_id: str
    config_revision_id: str | None = None
    dev_user: str = "admin"
    timeout_seconds: int = 60

    def run(self, sample: EvaluationSample) -> dict[str, Any]:
        """创建 QA Run 并读取详情，失败时抛出包含接口上下文的 RuntimeError。"""
        api_base = self.api_base_url.rstrip("/")
        create_url = f"{api_base}/knowledge-bases/{self.kb_id}/qa-runs"
        payload: dict[str, Any] = {"query": sample.query}
        config_revision_id = sample.metadata.get("configRevisionId") or self.config_revision_id
        if config_revision_id:
            payload["configRevisionId"] = config_revision_id

        create_response = self._request_json("POST", create_url, payload)
        run_id = create_response.get("runId")
        if not run_id:
            raise RuntimeError("真实 QA 评测失败：创建 QA Run 后未返回 runId。")

        detail_url = f"{api_base}/knowledge-bases/{self.kb_id}/qa-runs/{run_id}?includeTrace=true&includeCandidates=true"
        return self._request_json("GET", detail_url)

    def _request_json(self, method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """发送 JSON 请求并返回 JSON 对象，保留 HTTP 错误摘要便于定位环境问题。"""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/json",
            "X-Dev-User": self.dev_user,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"真实 QA 评测 HTTP {exc.code}: {error_body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"真实 QA 评测无法连接后端: {exc.reason}") from exc

        data = json.loads(response_body) if response_body else {}
        if not isinstance(data, dict):
            raise RuntimeError("真实 QA 评测接口返回格式不是 JSON object。")
        return data


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
            metadata=item.get("metadata", {}),
        ))

    return samples if samples else DEFAULT_SAMPLES


def build_runner_from_config(
    kb_id: str | None = None,
    api_base_url: str | None = None,
    config_revision_id: str | None = None,
    dev_user: str | None = None,
    timeout_seconds: int | None = None,
) -> HttpQARunEvaluationRunner:
    """合并显式参数和环境变量，构造真实 QA HTTP Runner。

    显式参数用于命令行临时复测；环境变量用于 CI 或固定环境。缺少知识库 ID
    时直接失败，避免真实验收静默回退到模拟指标。
    """
    resolved_kb_id = kb_id or os.getenv("RAG_LAB_EVAL_KB_ID")
    if not resolved_kb_id:
        raise RuntimeError("真实 QA 评测需要配置 RAG_LAB_EVAL_KB_ID。")

    resolved_api_base_url = (
        api_base_url
        or os.getenv("RAG_LAB_EVAL_API_BASE_URL")
        or os.getenv("RAG_LAB_API_BASE_URL")
        or "http://127.0.0.1:8000/api/v1"
    )
    return HttpQARunEvaluationRunner(
        api_base_url=resolved_api_base_url,
        kb_id=resolved_kb_id,
        config_revision_id=config_revision_id or os.getenv("RAG_LAB_EVAL_CONFIG_REVISION_ID"),
        dev_user=dev_user or os.getenv("RAG_LAB_EVAL_DEV_USER", "admin"),
        timeout_seconds=timeout_seconds or int(os.getenv("RAG_LAB_EVAL_TIMEOUT_SECONDS", "60")),
    )


def _collect_evidence_ids(evidence: list[dict[str, Any]]) -> list[str]:
    """提取证据中可用于 expectedEvidenceIds 匹配的标识。"""
    ids: list[str] = []
    for item in evidence:
        for key in ("evidenceId", "chunkId", "documentId"):
            value = item.get(key)
            if value:
                ids.append(str(value))
        source_snapshot = item.get("sourceSnapshot")
        if isinstance(source_snapshot, dict):
            for key in ("documentId", "versionId", "chunkId"):
                value = source_snapshot.get(key)
                if value:
                    ids.append(str(value))
    return ids


def _evidence_item_ids(item: dict[str, Any]) -> set[str]:
    """提取单条 evidence 的全部可匹配标识，用于按证据条目计算排名。"""
    ids: set[str] = set()
    for key in ("evidenceId", "chunkId", "documentId"):
        value = item.get(key)
        if value:
            ids.add(str(value))
    source_snapshot = item.get("sourceSnapshot")
    if isinstance(source_snapshot, dict):
        for key in ("documentId", "versionId", "chunkId"):
            value = source_snapshot.get(key)
            if value:
                ids.add(str(value))
    return ids


def _is_refusal_answer(answer: str) -> bool:
    """判断答案是否为资料不足、无权限或无法回答类拒答。"""
    normalized = answer.lower()
    markers = ["资料不足", "无法回答", "不能回答", "无权限", "insufficient", "not enough", "permission"]
    return any(marker in normalized for marker in markers)


def _answer_completeness(answer: str, expected_answer: str | None) -> float:
    """基于期望答案文本计算简单完整性分数。"""
    if not answer:
        return 0.0
    if not expected_answer:
        return 1.0
    return 1.0 if expected_answer.lower() in answer.lower() else 0.0


def _result_from_real_qa(sample: EvaluationSample, qa_detail: dict[str, Any], elapsed_ms: int) -> EvaluationResult:
    """将 QA Run 详情转换为高质量 RAG 评测指标。"""
    answer = str(qa_detail.get("answer") or "")
    evidence = qa_detail.get("evidence") if isinstance(qa_detail.get("evidence"), list) else []
    citations = qa_detail.get("citations") if isinstance(qa_detail.get("citations"), list) else []
    metrics = qa_detail.get("metrics") if isinstance(qa_detail.get("metrics"), dict) else {}

    expected_ids = {str(item) for item in sample.expected_evidence_ids}
    returned_ids = _collect_evidence_ids(evidence)
    returned_id_set = set(returned_ids)

    if expected_ids:
        hits = expected_ids & returned_id_set
        recall_at_k = len(hits) / len(expected_ids)
        first_rank = next(
            (index + 1 for index, item in enumerate(evidence) if _evidence_item_ids(item) & expected_ids),
            None,
        )
        mrr = 1 / first_rank if first_rank else 0.0
    else:
        recall_at_k = 1.0 if evidence or sample.should_refuse else 0.0
        mrr = 1.0 if evidence or sample.should_refuse else 0.0

    evidence_ids = {str(item.get("evidenceId")) for item in evidence if item.get("evidenceId")}
    if citations:
        valid_citation_count = sum(1 for citation in citations if str(citation.get("evidenceId")) in evidence_ids)
        citation_accuracy = valid_citation_count / len(citations)
    else:
        citation_accuracy = 1.0 if sample.should_refuse and _is_refusal_answer(answer) else 0.0

    answer_completeness = _answer_completeness(answer, sample.expected_answer)
    metric_faithfulness = metrics.get("faithfulness") or metrics.get("faithfulnessScore")
    if metric_faithfulness is not None:
        faithfulness = max(0.0, min(1.0, float(metric_faithfulness)))
    else:
        faithfulness = (recall_at_k + citation_accuracy + answer_completeness) / 3

    refusal_correct = _is_refusal_answer(answer) if sample.should_refuse else not _is_refusal_answer(answer)
    latency_ms = int(metrics.get("latencyMs") or metrics.get("latency_ms") or elapsed_ms)

    return EvaluationResult(
        sample_id=sample.sample_id,
        category=sample.category,
        query=sample.query,
        actual_answer=answer,
        recall_at_k=recall_at_k,
        mrr=mrr,
        citation_accuracy=citation_accuracy,
        faithfulness=faithfulness,
        answer_completeness=answer_completeness,
        refusal_correct=refusal_correct,
        latency_ms=latency_ms,
    )


def evaluate_sample(
    sample: EvaluationSample,
    use_real_qa: bool = False,
    runner: QAEvaluationRunner | None = None,
) -> EvaluationResult:
    """评测单个样本。

    Args:
        sample: 评测样本
        use_real_qa: 是否调用真实 QA Pipeline
        runner: 真实 QA Runner；未传时从环境变量构造 HTTP Runner

    Returns:
        评测结果
    """
    start_time = time.monotonic()

    if use_real_qa:
        real_runner = runner or build_runner_from_config()
        qa_detail = real_runner.run(sample)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        return _result_from_real_qa(sample, qa_detail, elapsed_ms)

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


def run_evaluation(
    fixture_path: str | None = None,
    use_real_qa: bool = True,
    runner: QAEvaluationRunner | None = None,
) -> dict[str, Any]:
    """运行评测。

    Args:
        fixture_path: fixture 文件路径
        use_real_qa: 是否调用真实 QA Pipeline；默认必须走真实链路。
        runner: 真实 QA Runner；测试或嵌入调用可显式注入。

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
            result = evaluate_sample(sample, use_real_qa=use_real_qa, runner=runner)
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
    parser.add_argument("--allow-mock", action="store_true", help="显式允许使用模拟指标，仅用于脚本结构检查")
    parser.add_argument("--kb-id", type=str, help="真实评测知识库 ID；未传时读取 RAG_LAB_EVAL_KB_ID")
    parser.add_argument(
        "--api-base-url",
        type=str,
        help="后端 API v1 基础地址；默认 http://127.0.0.1:8000/api/v1",
    )
    parser.add_argument("--config-revision-id", type=str, help="可选目标 ConfigRevision ID")
    parser.add_argument("--dev-user", type=str, help="开发态 X-Dev-User；默认 admin")
    parser.add_argument("--timeout-seconds", type=int, help="单次 HTTP 请求超时时间，默认 60 秒")
    args = parser.parse_args()

    runner = None
    if not args.allow_mock:
        runner = build_runner_from_config(
            kb_id=args.kb_id,
            api_base_url=args.api_base_url,
            config_revision_id=args.config_revision_id,
            dev_user=args.dev_user,
            timeout_seconds=args.timeout_seconds,
        )

    report = run_evaluation(args.fixture, use_real_qa=not args.allow_mock, runner=runner)

    # 保存报告
    output_path = Path("evaluation_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n报告已保存到: {output_path}")


if __name__ == "__main__":
    main()
