"""LangGraph 官方 Checkpointer 工厂。"""
from __future__ import annotations

import re

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver


def _to_psycopg_dsn(url: str | None) -> str | None:
    """将 SQLAlchemy PostgreSQL URL 转为 psycopg 原生 DSN。"""
    if not url:
        return url
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


def create_checkpointer(*, backend: str, database_url: str | None):
    """创建官方 Checkpointer；生产使用 PostgreSQL，测试允许使用内存实现。"""
    if backend == "memory":
        return InMemorySaver()
    if backend == "postgres" and database_url:
        return PostgresSaver.from_conn_string(_to_psycopg_dsn(database_url))
    raise ValueError("PostgreSQL Checkpointer 需要 database_url。")
