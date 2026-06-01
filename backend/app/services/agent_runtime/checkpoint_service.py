"""LangGraph 官方 Checkpointer 工厂。"""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver


def create_checkpointer(*, backend: str, database_url: str | None):
    """创建官方 Checkpointer；生产使用 PostgreSQL，测试允许使用内存实现。"""
    if backend == "memory":
        return InMemorySaver()
    if backend == "postgres" and database_url:
        return PostgresSaver.from_conn_string(database_url)
    raise ValueError("PostgreSQL Checkpointer 需要 database_url。")
