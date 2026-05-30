"""E2E: 高质量 RAG 质量验收测试。

验证 E2E 评测脚本能正确运行并生成报告。
"""

import pytest
import sys
import importlib.util
from pathlib import Path

# 动态加载 scripts 目录中的模块
# 从 app/tests/e2e/ 向上 3 级到 backend/
backend_dir = Path(__file__).resolve().parent.parent.parent.parent
scripts_dir = backend_dir / "scripts"
evaluate_script = scripts_dir / "evaluate_high_quality_rag.py"

spec = importlib.util.spec_from_file_location("evaluate_high_quality_rag", evaluate_script)
evaluate_module = importlib.util.module_from_spec(spec)
sys.modules["evaluate_high_quality_rag"] = evaluate_module
spec.loader.exec_module(evaluate_module)

DEFAULT_SAMPLES = evaluate_module.DEFAULT_SAMPLES
EvaluationSample = evaluate_module.EvaluationSample
build_runner_from_config = evaluate_module.build_runner_from_config
evaluate_sample = evaluate_module.evaluate_sample
generate_category_report = evaluate_module.generate_category_report
load_fixture = evaluate_module.load_fixture
run_evaluation = evaluate_module.run_evaluation


class TestEvaluationSample:
    """评测样本测试。"""

    def test_default_samples_exist(self):
        """应有默认评测样本。"""
        assert len(DEFAULT_SAMPLES) > 0

    def test_default_samples_cover_categories(self):
        """默认样本应覆盖所有类别。"""
        categories = {s.category for s in DEFAULT_SAMPLES}
        assert "faq" in categories
        assert "table" in categories
        assert "permission_isolation" in categories

    def test_evaluation_sample_creation(self):
        """应能创建评测样本。"""
        sample = EvaluationSample(
            sample_id="test_001",
            category="faq",
            query="Test query",
        )
        assert sample.sample_id == "test_001"
        assert sample.category == "faq"


class TestEvaluateSample:
    """样本评测测试。"""

    def test_real_evaluation_requires_runner_configuration(self):
        """真实评测缺少 Runner 配置时必须明确失败，不能回退到模拟指标。"""
        sample = DEFAULT_SAMPLES[0]
        with pytest.raises(RuntimeError, match="真实 QA 评测需要配置"):
            evaluate_sample(sample, use_real_qa=True)

    def test_real_evaluation_uses_injected_runner(self):
        """真实评测应使用注入的 QA Runner 结果计算指标。"""

        class StubRunner:
            """测试用 Runner，模拟真实 QA Run 返回的详情结构。"""

            def run(self, sample):
                return {
                    "answer": "RAG 是 Retrieval Augmented Generation 的缩写。",
                    "evidence": [
                        {"evidenceId": "e1", "chunkId": "chunk-1", "contentSnapshot": "RAG 是 Retrieval Augmented Generation 的缩写。"},
                    ],
                    "citations": [
                        {"citationId": "c1", "evidenceId": "e1"},
                    ],
                    "metrics": {"latencyMs": 123},
                }

        sample = EvaluationSample(
            sample_id="real_001",
            category="faq",
            query="什么是 RAG?",
            expected_answer="Retrieval Augmented Generation",
            expected_evidence_ids=["chunk-1"],
        )

        result = evaluate_sample(sample, use_real_qa=True, runner=StubRunner())

        assert result.actual_answer.startswith("RAG 是")
        assert result.recall_at_k == 1.0
        assert result.mrr == 1.0
        assert result.citation_accuracy == 1.0
        assert result.latency_ms == 123

    def test_evaluate_sample_basic(self):
        """应能评测样本。"""
        sample = DEFAULT_SAMPLES[0]
        result = evaluate_sample(sample)
        assert result is not None
        assert result.sample_id == sample.sample_id
        assert result.category == sample.category

    def test_evaluate_sample_has_metrics(self):
        """评测结果应包含所有指标。"""
        sample = DEFAULT_SAMPLES[0]
        result = evaluate_sample(sample)
        assert 0 <= result.recall_at_k <= 1
        assert 0 <= result.mrr <= 1
        assert 0 <= result.citation_accuracy <= 1
        assert 0 <= result.faithfulness <= 1
        assert 0 <= result.answer_completeness <= 1

    def test_evaluate_sample_has_latency(self):
        """评测结果应包含延迟。"""
        sample = DEFAULT_SAMPLES[0]
        result = evaluate_sample(sample)
        assert result.latency_ms >= 0


class TestGenerateCategoryReport:
    """类别报告生成测试。"""

    def test_generate_category_report(self):
        """应能生成类别报告。"""
        sample = DEFAULT_SAMPLES[0]
        result = evaluate_sample(sample)
        report = generate_category_report("faq", [result])
        assert report.category == "faq"
        assert report.sample_count == 1

    def test_generate_category_report_empty(self):
        """空结果应生成空报告。"""
        report = generate_category_report("empty", [])
        assert report.sample_count == 0

    def test_generate_category_report_has_averages(self):
        """报告应包含平均值。"""
        results = [evaluate_sample(s) for s in DEFAULT_SAMPLES[:2]]
        report = generate_category_report("test", results)
        assert report.recall_at_k_avg >= 0
        assert report.mrr_avg >= 0


class TestRunEvaluation:
    """运行评测测试。"""

    def test_build_runner_prefers_explicit_config_over_env(self, monkeypatch):
        """显式配置应优先于环境变量，便于命令行复测不同知识库。"""
        monkeypatch.setenv("RAG_LAB_EVAL_KB_ID", "env-kb")
        monkeypatch.setenv("RAG_LAB_EVAL_API_BASE_URL", "http://env.example/api/v1")
        monkeypatch.setenv("RAG_LAB_EVAL_DEV_USER", "env-user")

        runner = build_runner_from_config(
            kb_id="cli-kb",
            api_base_url="http://cli.example/api/v1",
            config_revision_id="cli-revision",
            dev_user="cli-user",
            timeout_seconds=9,
        )

        assert runner.kb_id == "cli-kb"
        assert runner.api_base_url == "http://cli.example/api/v1"
        assert runner.config_revision_id == "cli-revision"
        assert runner.dev_user == "cli-user"
        assert runner.timeout_seconds == 9

    def test_run_evaluation_default(self):
        """默认评测必须走真实链路，未配置时直接失败。"""
        with pytest.raises(RuntimeError, match="真实 QA 评测需要配置"):
            run_evaluation()

    def test_run_evaluation_accepts_real_runner(self):
        """传入真实 Runner 时默认评测应使用 Runner 而不是模拟指标。"""

        class StubRunner:
            """测试用 Runner，为每个样本返回可计算的真实结果结构。"""

            def run(self, sample):
                answer = "抱歉，现有资料不足以回答您的问题。" if sample.should_refuse else "真实 QA 回答"
                return {
                    "answer": answer,
                    "evidence": [{"evidenceId": "e1", "chunkId": "chunk-1", "contentSnapshot": "真实 QA 回答"}],
                    "citations": [{"citationId": "c1", "evidenceId": "e1"}],
                    "metrics": {"latencyMs": 7},
                }

        report = run_evaluation(use_real_qa=True, runner=StubRunner())

        assert report["totalSamples"] == len(DEFAULT_SAMPLES)
        assert report["overall"]["latencyAvgMs"] == 7

    def test_run_evaluation_mock_mode(self):
        """显式模拟模式应能运行默认评测。"""
        report = run_evaluation(use_real_qa=False)
        assert report is not None
        assert report["totalSamples"] > 0
        assert "categories" in report
        assert "overall" in report

    def test_run_evaluation_has_overall_metrics(self):
        """模拟评测报告应包含总体指标。"""
        report = run_evaluation(use_real_qa=False)
        overall = report["overall"]
        assert "recallAtK" in overall
        assert "mrr" in overall
        assert "citationAccuracy" in overall
        assert "faithfulness" in overall
        assert "answerCompleteness" in overall
        assert "refusalAccuracy" in overall
        assert "latencyAvgMs" in overall

    def test_run_evaluation_with_fixture(self):
        """应能使用 fixture 文件运行评测。"""
        import tempfile
        import json

        # 创建临时 fixture 文件
        fixture_data = [
            {
                "sampleId": "test_001",
                "category": "faq",
                "query": "Test query",
                "expectedAnswer": "Test answer",
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(fixture_data, f)
            fixture_path = f.name

        try:
            report = run_evaluation(fixture_path, use_real_qa=False)
            assert report["totalSamples"] == 1
        finally:
            Path(fixture_path).unlink()

    def test_run_evaluation_with_missing_fixture(self):
        """缺失 fixture 文件应使用默认样本。"""
        report = run_evaluation("nonexistent.json", use_real_qa=False)
        assert report["totalSamples"] == len(DEFAULT_SAMPLES)
