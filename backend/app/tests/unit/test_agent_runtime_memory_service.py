"""Agent Runtime Task 4: 官方摘要中间件工厂测试。"""

from unittest.mock import patch

from app.services.agent_runtime.memory_service import create_summary_middleware


def test_create_summary_middleware_uses_langchain_builtin():
    with patch("app.services.agent_runtime.memory_service.SummarizationMiddleware") as middleware:
        create_summary_middleware(model="summary-model", trigger_tokens=4000, keep_messages=20)

    middleware.assert_called_once_with(
        model="summary-model",
        trigger=("tokens", 4000),
        keep=("messages", 20),
    )
