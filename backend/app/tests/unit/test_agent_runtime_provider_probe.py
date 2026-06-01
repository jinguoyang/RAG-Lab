"""Agent Runtime Task 9: Provider 能力探测 DTO 测试。"""

from app.services.agent_runtime.model_adapter import ProviderCapabilityReport
from scripts.verify_agent_runtime_provider import _probe_tool_calling


def test_provider_capability_report_has_explicit_fallback_flags():
    report = ProviderCapabilityReport(
        chat=True,
        toolCalling=False,
        structuredOutput=False,
        summarization=True,
    )

    assert report.toolCalling is False
    assert report.structuredOutput is False
    assert report.chat is True
    assert report.summarization is True


def test_tool_calling_probe_rejects_wrong_tool_name():
    """Provider 返回其他 Tool 时，不能误判为 probe_tool 协议兼容。"""

    class Response:
        tool_calls = [{"name": "wrong_tool", "args": {"query": "test"}}]

    class BoundModel:
        def invoke(self, messages):
            return Response()

    class Model:
        def bind_tools(self, tools):
            return BoundModel()

    assert _probe_tool_calling(Model()) is False


def test_tool_calling_probe_accepts_expected_tool_and_arguments():
    """只有名称和参数均匹配的真实 Tool Call 才能通过探测。"""

    class Response:
        tool_calls = [{"name": "probe_tool", "args": {"query": "test"}}]

    class BoundModel:
        def invoke(self, messages):
            return Response()

    class Model:
        def bind_tools(self, tools):
            return BoundModel()

    assert _probe_tool_calling(Model()) is True
