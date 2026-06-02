"""Agent Runtime Task 3: PostgreSQL Checkpointer 集成测试。"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict

from app.services.agent_runtime.checkpoint_service import create_checkpointer

# 加载 backend/.env 使 RAG_LAB_DATABASE_URL 可用
_backend_env = Path(__file__).resolve().parents[3] / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env, override=False)


def _normalize_pg_url(url: str | None) -> str | None:
    """将 SQLAlchemy 格式 (postgresql+psycopg://) 转为 psycopg 原生格式 (postgresql://)。"""
    if not url:
        return url
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


# 优先使用专用测试库，回退到项目主库
_PG_URL = _normalize_pg_url(
    os.getenv("RAG_LAB_TEST_POSTGRES_URL") or os.getenv("RAG_LAB_DATABASE_URL")
)


class State(TypedDict):
    value: str


def test_postgres_checkpointer_persists_thread_state():
    """Postgres Checkpointer 应正确持久化 thread state 并可恢复。"""
    assert _PG_URL, "需要设置 RAG_LAB_TEST_POSTGRES_URL 或 RAG_LAB_DATABASE_URL"
    with create_checkpointer(
        backend="postgres",
        database_url=_PG_URL,
    ) as checkpointer:
        checkpointer.setup()
        builder = StateGraph(State)
        builder.add_node("copy", lambda state: {"value": state["value"]})
        builder.add_edge(START, "copy")
        graph = builder.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": "foundation-test-thread"}}

        graph.invoke({"value": "saved"}, config)

        assert graph.get_state(config).values["value"] == "saved"
