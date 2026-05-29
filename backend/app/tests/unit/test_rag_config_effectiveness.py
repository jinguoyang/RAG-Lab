"""B-316: RAG 节点配置生效状态审计测试。

验证配置能力清单覆盖所有默认节点，且每个配置项的状态值合法。
"""

import pytest

from app.services.config_effectiveness import (
    NodeCapability,
    build_default_capability_registry,
    build_trace_effective_configs,
    get_effectiveness_summary,
    get_node_effectiveness,
)


class TestCapabilityRegistry:
    """配置能力清单基础测试。"""

    def test_registry_covers_all_default_nodes(self):
        """能力清单必须覆盖 default_pipeline.py 中定义的所有节点。"""
        registry = build_default_capability_registry()
        registry_node_ids = {node.node_id for node in registry}

        # default_pipeline.py 中的节点 ID
        expected_node_ids = {
            "input",
            "queryRewrite",
            "multiQuery",
            "dense",
            "sparse",
            "graph",
            "fusion",
            "permissionFilter",
            "rerank",
            "contextPacking",
            "generation",
            "citation",
            "output",
        }
        assert expected_node_ids == registry_node_ids, (
            f"能力清单节点不匹配。缺少: {expected_node_ids - registry_node_ids}, "
            f"多余: {registry_node_ids - expected_node_ids}"
        )

    def test_all_status_values_are_valid(self):
        """每个配置项的 status 必须是合法枚举值。"""
        valid_statuses = {"effective", "partiallyEffective", "planned", "deprecated"}
        registry = build_default_capability_registry()
        for node in registry:
            for item in node.items:
                assert item.status in valid_statuses, (
                    f"节点 {node.node_id} 配置项 {item.key} 的状态 '{item.status}' 不合法"
                )

    def test_effective_items_have_execution_location(self):
        """标记为 effective 的配置项必须有执行位置说明。"""
        registry = build_default_capability_registry()
        for node in registry:
            for item in node.items:
                if item.status == "effective":
                    assert item.execution_location, (
                        f"节点 {node.node_id} 配置项 {item.key} 标记为 effective 但缺少 execution_location"
                    )

    def test_planned_items_have_note(self):
        """标记为 planned 的配置项必须有说明。"""
        registry = build_default_capability_registry()
        for node in registry:
            for item in node.items:
                if item.status == "planned":
                    assert item.note, (
                        f"节点 {node.node_id} 配置项 {item.key} 标记为 planned 但缺少 note"
                    )

    def test_registry_not_empty(self):
        """能力清单不能为空。"""
        registry = build_default_capability_registry()
        assert len(registry) > 0
        total_items = sum(len(node.items) for node in registry)
        assert total_items > 0


class TestEffectivenessSummary:
    """配置生效状态摘要测试。"""

    def test_summary_counts_are_consistent(self):
        """摘要中的数量统计必须与节点列表一致。"""
        summary = get_effectiveness_summary()
        assert summary["total"] == summary["effective"] + summary["partiallyEffective"] + summary["planned"] + summary["deprecated"]

    def test_summary_contains_all_nodes(self):
        """摘要必须包含所有节点。"""
        summary = get_effectiveness_summary()
        assert len(summary["nodes"]) == len(build_default_capability_registry())

    def test_summary_nodes_have_expected_fields(self):
        """每个节点摘要必须包含必要字段。"""
        summary = get_effectiveness_summary()
        for node in summary["nodes"]:
            assert "nodeId" in node
            assert "nodeType" in node
            assert "stage" in node
            assert "items" in node
            for item in node["items"]:
                assert "key" in item
                assert "status" in item
                assert "executionLocation" in item


class TestNodeEffectiveness:
    """单节点配置生效状态测试。"""

    def test_get_existing_node(self):
        """查询存在的节点类型应返回结果。"""
        result = get_node_effectiveness("denseRetrieval")
        assert result is not None
        assert result["nodeType"] == "denseRetrieval"

    def test_get_nonexistent_node(self):
        """查询不存在的节点类型应返回 None。"""
        result = get_node_effectiveness("nonexistentNode")
        assert result is None

    def test_query_rewrite_has_expected_configs(self):
        """queryRewrite 节点必须包含关键配置项。"""
        result = get_node_effectiveness("queryRewrite")
        assert result is not None
        config_keys = {item["key"] for item in result["items"]}
        assert "enabled" in config_keys
        assert "rewriteStrategy" in config_keys
        assert "preserveOriginalQuery" in config_keys

    def test_dense_retrieval_has_expected_configs(self):
        """denseRetrieval 节点必须包含关键配置项。"""
        result = get_node_effectiveness("denseRetrieval")
        assert result is not None
        config_keys = {item["key"] for item in result["items"]}
        assert "topK" in config_keys
        assert "scoreThreshold" in config_keys
        assert "fusionWeight" in config_keys


class TestTraceEffectiveConfigs:
    """QA Run trace 配置审计测试。"""

    def test_disabled_channel_appears_in_ignored(self):
        """未启用的检索通道配置应出现在 ignoredConfigs 中。"""
        pipeline_params = {
            "multiQuery": {"enabled": False},
            "rerank": {"enabled": True},
        }
        enabled_channels = {"dense"}  # sparse 和 graph 未启用

        result = build_trace_effective_configs(pipeline_params, enabled_channels)

        ignored_keys = {(c["nodeType"], c["key"]) for c in result["ignoredConfigs"]}
        # sparse 和 graph 的配置项应该在 ignored 中
        assert any(node_type == "sparseRetrieval" for node_type, _ in ignored_keys)
        assert any(node_type == "graphRetrieval" for node_type, _ in ignored_keys)

    def test_enabled_channel_appears_in_effective(self):
        """已启用的检索通道配置应出现在 effectiveConfigs 中。"""
        pipeline_params = {
            "multiQuery": {"enabled": False},
            "rerank": {"enabled": True},
        }
        enabled_channels = {"dense", "sparse"}

        result = build_trace_effective_configs(pipeline_params, enabled_channels)

        effective_node_types = {c["nodeType"] for c in result["effectiveConfigs"]}
        assert "denseRetrieval" in effective_node_types
        assert "sparseRetrieval" in effective_node_types

    def test_planned_items_always_in_ignored(self):
        """planned 配置项始终出现在 ignoredConfigs 中。"""
        pipeline_params = {
            "multiQuery": {"enabled": True},
            "rerank": {"enabled": True},
        }
        enabled_channels = {"dense", "sparse", "graph"}

        result = build_trace_effective_configs(pipeline_params, enabled_channels)

        ignored_statuses = {c["status"] for c in result["ignoredConfigs"]}
        assert "planned" in ignored_statuses

    def test_disabled_multi_query_in_ignored(self):
        """未启用的 multiQuery 配置应出现在 ignoredConfigs 中。"""
        pipeline_params = {
            "multiQuery": {"enabled": False},
            "rerank": {"enabled": True},
        }
        enabled_channels = {"dense"}

        result = build_trace_effective_configs(pipeline_params, enabled_channels)

        ignored_multi_query = [c for c in result["ignoredConfigs"] if c["nodeType"] == "multiQuery"]
        assert len(ignored_multi_query) > 0

    def test_disabled_rerank_in_ignored(self):
        """未启用的 rerank 配置应出现在 ignoredConfigs 中。"""
        pipeline_params = {
            "multiQuery": {"enabled": False},
            "rerank": {"enabled": False},
        }
        enabled_channels = {"dense"}

        result = build_trace_effective_configs(pipeline_params, enabled_channels)

        ignored_rerank = [c for c in result["ignoredConfigs"] if c["nodeType"] == "rerank"]
        assert len(ignored_rerank) > 0

    def test_summary_counts_match(self):
        """摘要中的数量必须与实际列表长度一致。"""
        pipeline_params = {
            "multiQuery": {"enabled": False},
            "rerank": {"enabled": True},
        }
        enabled_channels = {"dense"}

        result = build_trace_effective_configs(pipeline_params, enabled_channels)

        assert result["summary"]["effectiveCount"] == len(result["effectiveConfigs"])
        assert result["summary"]["ignoredCount"] == len(result["ignoredConfigs"])
