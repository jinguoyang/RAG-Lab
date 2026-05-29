"""B-318: 文档解析 Provider 路由测试。

验证解析器路由能根据策略选择合适的解析器，并正确处理回退。
"""

import pytest

from app.services.parser_routing import (
    ParseStrategy,
    ParserCapability,
    route_and_parse,
    get_routing_strategy_info,
    list_parser_capabilities,
    register_parser_provider,
)
from app.services.document_parsing import DocumentParseError


class TestParserRouting:
    """解析器路由测试。"""

    def test_default_strategy_uses_basic_parser(self):
        """默认策略应使用基础解析器。"""
        info = get_routing_strategy_info()
        assert len(info["strategies"]) > 0
        assert any(s["name"] == "default" for s in info["strategies"])

    def test_all_strategies_exist(self):
        """应包含所有定义的策略。"""
        info = get_routing_strategy_info()
        strategy_names = {s["name"] for s in info["strategies"]}
        assert "default" in strategy_names
        assert "low-cost" in strategy_names
        assert "high-quality" in strategy_names
        assert "strong-ocr" in strategy_names
        assert "table-priority" in strategy_names

    def test_providers_info_included(self):
        """策略信息应包含 Provider 信息。"""
        info = get_routing_strategy_info()
        assert "providers" in info
        assert len(info["providers"]) > 0

    def test_basic_parser_capability(self):
        """基础解析器应有正确的能力描述。"""
        capabilities = list_parser_capabilities()
        basic = next((c for c in capabilities if c.parser_name == "basic"), None)
        assert basic is not None
        assert ".txt" in basic.supported_types
        assert ".md" in basic.supported_types
        assert ".pdf" in basic.supported_types
        assert ".docx" in basic.supported_types
        assert basic.cost_level == "low"


class TestRouteAndParse:
    """路由并解析测试。"""

    def test_route_and_parse_txt_file(self):
        """应能解析 txt 文件。"""
        content = "这是一个测试文档。\n\n这是第二段。"
        result, record = route_and_parse(
            file_name="test.txt",
            mime_type="text/plain",
            file_bytes=content.encode("utf-8"),
            strategy=ParseStrategy.DEFAULT,
        )
        assert result is not None
        assert len(result.chunks) > 0
        assert record.success is True
        assert record.parser_name == "basic"

    def test_route_and_parse_md_file(self):
        """应能解析 md 文件。"""
        content = "# 标题\n\n这是内容。"
        result, record = route_and_parse(
            file_name="test.md",
            mime_type="text/markdown",
            file_bytes=content.encode("utf-8"),
            strategy=ParseStrategy.DEFAULT,
        )
        assert result is not None
        assert len(result.chunks) > 0
        assert record.success is True

    def test_route_and_parse_with_strategy_string(self):
        """应支持字符串格式的策略。"""
        content = "测试内容"
        result, record = route_and_parse(
            file_name="test.txt",
            mime_type="text/plain",
            file_bytes=content.encode("utf-8"),
            strategy="default",
        )
        assert result is not None
        assert record.success is True

    def test_route_and_parse_invalid_strategy_falls_back(self):
        """无效策略应回退到默认策略。"""
        content = "测试内容"
        result, record = route_and_parse(
            file_name="test.txt",
            mime_type="text/plain",
            file_bytes=content.encode("utf-8"),
            strategy="invalid-strategy",
        )
        assert result is not None
        assert record.success is True

    def test_route_and_parse_unsupported_file_type(self):
        """不支持的文件类型应抛出错误。"""
        with pytest.raises(DocumentParseError) as exc_info:
            route_and_parse(
                file_name="test.xyz",
                mime_type="application/octet-stream",
                file_bytes=b"test",
                strategy=ParseStrategy.DEFAULT,
            )
        assert exc_info.value.error_code == "ALL_PARSERS_FAILED"

    def test_route_and_parse_empty_content(self):
        """空内容应抛出错误。"""
        with pytest.raises(DocumentParseError):
            route_and_parse(
                file_name="test.txt",
                mime_type="text/plain",
                file_bytes=b"",
                strategy=ParseStrategy.DEFAULT,
            )

    def test_route_and_parse_low_cost_strategy(self):
        """低成本策略应使用基础解析器。"""
        content = "测试内容"
        result, record = route_and_parse(
            file_name="test.txt",
            mime_type="text/plain",
            file_bytes=content.encode("utf-8"),
            strategy=ParseStrategy.LOW_COST,
        )
        assert result is not None
        assert record.parser_name == "basic"

    def test_task_record_has_quality_flags(self):
        """任务记录应包含质量标记。"""
        content = "测试内容"
        _, record = route_and_parse(
            file_name="test.txt",
            mime_type="text/plain",
            file_bytes=content.encode("utf-8"),
            strategy=ParseStrategy.DEFAULT,
        )
        assert "parserName" in record.quality_flags
        assert "strategy" in record.quality_flags


class TestParserProviderRegistration:
    """解析器 Provider 注册测试。"""

    def test_register_new_provider(self):
        """应能注册新的解析器 Provider。"""
        from app.services.document_parsing import ParsedDocument, ParsedChunk

        class MockParserProvider:
            def parse(self, file_name, mime_type, file_bytes, chunk_size, chunk_overlap):
                return ParsedDocument(
                    parser_name="mock",
                    parser_version="1.0",
                    source_file_name=file_name,
                    mime_type=mime_type,
                    chunks=[
                        ParsedChunk(
                            content="Mock content",
                            token_count=10,
                            section=None,
                            page_no=None,
                        )
                    ],
                )

        capability = ParserCapability(
            parser_name="mock",
            supported_types={".mock"},
            cost_level="low",
        )

        register_parser_provider("mock", capability, MockParserProvider())

        # 验证注册成功
        capabilities = list_parser_capabilities()
        mock_cap = next((c for c in capabilities if c.parser_name == "mock"), None)
        assert mock_cap is not None
        assert ".mock" in mock_cap.supported_types
