"""内部客服 LangChain Agent 调用适配器测试。"""
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError

from app.services.agent_runtime.customer_service_agent import (
    ensure_customer_service_tool_result,
    invoke_customer_service_agent,
)


class _FakeAgent:
    """记录调用参数并返回带官方摘要标记的消息。"""

    def __init__(self):
        self.config = None
        self.payload = None

    def invoke(self, payload, config):
        self.payload = payload
        self.config = config
        return {
            "messages": [
                HumanMessage(
                    content="summary",
                    additional_kwargs={"lc_source": "summarization"},
                ),
                AIMessage(content="请按制度提交申请。"),
            ]
        }


def test_invoke_customer_service_agent_uses_stable_subthread_and_reads_summary():
    """客服 Agent 应使用稳定子线程，并识别官方摘要中间件生成的消息。"""
    agent = _FakeAgent()

    result = invoke_customer_service_agent(
        rag_agent=agent,
        conversation_id="conv-1",
        query="如何提交申请？",
    )

    assert agent.config == {"configurable": {"thread_id": "conv-1:rag-agent"}}
    assert agent.payload == {"messages": [{"role": "user", "content": "如何提交申请？"}]}
    assert result["answer"] == "请按制度提交申请。"
    assert result["summaryVersion"] == 1
    assert result["summaryStatus"] == "success"
    assert result["modelStatus"] == "success"
    assert result["modelCallId"]


def test_invoke_customer_service_agent_marks_summary_failure():
    """官方摘要中间件降级错误必须进入 Trace，不能误报成功。"""

    class FailedSummaryAgent:
        def invoke(self, payload, config):
            return {
                "messages": [
                    HumanMessage(
                        content="Here is a summary of the conversation to date:\n\nError generating summary: timeout",
                        additional_kwargs={"lc_source": "summarization"},
                    ),
                    AIMessage(content="降级回答"),
                ]
            }

    result = invoke_customer_service_agent(
        rag_agent=FailedSummaryAgent(),
        conversation_id="conv-2",
        query="继续",
    )

    assert result["summaryVersion"] == 1
    assert result["summaryStatus"] == "failed"


def test_ensure_customer_service_tool_result_uses_guard_when_agent_skips_tool():
    """模型跳过 Tool 时，Runtime 必须通过同一个只读 Tool 补一次授权检索。"""

    class FakeTool:
        def invoke(self, payload):
            assert "回答草稿：上下文回答" in payload["query"]
            return {"runId": "run-guard", "skillCallId": "skill-guard"}

    tool_result = {}

    mode = ensure_customer_service_tool_result(
        qa_run_tool=FakeTool(),
        query="继续追问",
        agent_answer="上下文回答",
        tool_result=tool_result,
    )

    assert mode == "guard"
    assert tool_result["runId"] == "run-guard"


def test_ensure_customer_service_tool_result_keeps_agent_tool_result():
    """模型已经调用 Tool 时不重复检索。"""
    tool_result = {"runId": "run-agent"}

    mode = ensure_customer_service_tool_result(
        qa_run_tool=None,
        query="问题",
        agent_answer="回答",
        tool_result=tool_result,
    )

    assert mode == "agent"


def test_invoke_customer_service_agent_recovers_tool_limit_state():
    """Provider 重复调用 Tool 命中硬限额时，返回可审计状态供 Runtime 使用授权结果收敛。"""

    class LimitedAgent:
        def invoke(self, payload, config):
            raise ToolCallLimitExceededError(
                thread_count=3,
                run_count=3,
                thread_limit=None,
                run_limit=2,
                tool_name="query_knowledge_base",
            )

        def get_state(self, config):
            return type("State", (), {"values": {"messages": []}})()

    result = invoke_customer_service_agent(
        rag_agent=LimitedAgent(),
        conversation_id="conv-limit",
        query="问题",
    )

    assert result["answer"] == ""
    assert result["modelStatus"] == "tool_limit_reached"
