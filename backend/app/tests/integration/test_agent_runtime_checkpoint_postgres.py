"""Agent Runtime Task 3: PostgreSQL Checkpointer 集成测试。"""

import os

import pytest
from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict

from app.services.agent_runtime.checkpoint_service import create_checkpointer


class State(TypedDict):
    value: str


@pytest.mark.skipif(not os.getenv("RAG_LAB_TEST_POSTGRES_URL"), reason="需要 PostgreSQL 测试库")
def test_postgres_checkpointer_persists_thread_state():
    with create_checkpointer(
        backend="postgres",
        database_url=os.environ["RAG_LAB_TEST_POSTGRES_URL"],
    ) as checkpointer:
        checkpointer.setup()
        builder = StateGraph(State)
        builder.add_node("copy", lambda state: {"value": state["value"]})
        builder.add_edge(START, "copy")
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "foundation-test-thread"}}

        graph.invoke({"value": "saved"}, config)

        assert graph.get_state(config).values["value"] == "saved"
