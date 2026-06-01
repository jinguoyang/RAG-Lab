"""Agent Runtime Task 6: RAG Agent 工厂测试。"""

from unittest.mock import Mock, patch

from app.services.agent_runtime.rag_agent_factory import build_rag_answer_agent


def test_build_rag_answer_agent_uses_langchain_create_agent_and_builtin_middleware():
    model = Mock()
    checkpointer = Mock()
    qa_run_tool = Mock(name="query_knowledge_base")
    qa_run_tool.name = "query_knowledge_base"
    summary = Mock(name="summary")

    with (
        patch("app.services.agent_runtime.rag_agent_factory.create_summary_middleware", return_value=summary),
        patch("app.services.agent_runtime.rag_agent_factory.create_agent") as create_agent,
    ):
        build_rag_answer_agent(
            model=model,
            qa_run_tool=qa_run_tool,
            checkpointer=checkpointer,
            trigger_tokens=4000,
            keep_messages=20,
            system_prompt="请基于知识库回答。",
        )

    middleware = create_agent.call_args.kwargs["middleware"]
    assert middleware[0] is summary
    assert middleware[1].run_limit == 3
    assert middleware[2].tool_name == "query_knowledge_base"
    assert middleware[2].run_limit == 1
    assert create_agent.call_args.kwargs["tools"] == [qa_run_tool]
    assert create_agent.call_args.kwargs["checkpointer"] is checkpointer
