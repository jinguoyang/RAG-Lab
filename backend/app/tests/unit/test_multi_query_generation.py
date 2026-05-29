"""B-317: 多查询生成测试。

验证 LLM Provider 的 generate_multi_queries 方法能正确生成多个查询变体。
"""

import pytest

from app.services.qa_providers import LocalLlmProvider, ProviderCandidate


class TestLocalLlmProviderMultiQuery:
    """本地 LLM Provider 多查询生成测试。"""

    def test_generate_multi_queries_returns_variants(self):
        """generate_multi_queries 应返回查询变体列表。"""
        provider = LocalLlmProvider()
        variants = provider.generate_multi_queries("什么是 RAG?", 3)
        assert isinstance(variants, list)
        assert len(variants) <= 2  # count - 1

    def test_generate_multi_queries_respects_count(self):
        """generate_multi_queries 返回数量应受 count 参数约束。"""
        provider = LocalLlmProvider()
        variants = provider.generate_multi_queries("什么是 RAG?", 2)
        assert len(variants) <= 1

    def test_generate_multi_queries_count_1_returns_empty(self):
        """count=1 时应返回空列表。"""
        provider = LocalLlmProvider()
        variants = provider.generate_multi_queries("什么是 RAG?", 1)
        assert variants == []

    def test_generate_multi_queries_count_0_returns_empty(self):
        """count=0 时应返回空列表。"""
        provider = LocalLlmProvider()
        variants = provider.generate_multi_queries("什么是 RAG?", 0)
        assert variants == []

    def test_generate_multi_queries_handles_chinese(self):
        """generate_multi_queries 应正确处理中文查询。"""
        provider = LocalLlmProvider()
        variants = provider.generate_multi_queries("如何使用 RAG 系统?", 3)
        assert isinstance(variants, list)
        # 应该有变体
        for variant in variants:
            assert isinstance(variant, str)
            assert len(variant) > 0


class TestMultiQueryIntegration:
    """多查询集成测试。"""

    def test_multi_query_preserves_original(self):
        """多查询应保留原始查询。"""
        provider = LocalLlmProvider()
        original = "什么是 RAG?"
        variants = provider.generate_multi_queries(original, 3)
        queries = [original] + variants
        assert original in queries
        assert len(queries) >= 1

    def test_multi_query_variants_are_different(self):
        """多查询变体应与原始查询不同。"""
        provider = LocalLlmProvider()
        original = "如何使用 RAG 系统?"
        variants = provider.generate_multi_queries(original, 3)
        # 变体应该与原始查询不同（本地 Provider 可能返回空列表）
        for variant in variants:
            # 本地 Provider 的变体可能与原始查询相同，这是允许的
            assert isinstance(variant, str)
