"""Agent Runtime Task 3: 官方 Checkpointer 工厂测试。"""

from unittest.mock import patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.services.agent_runtime.checkpoint_service import create_checkpointer


def test_create_checkpointer_supports_official_memory_backend():
    checkpointer = create_checkpointer(backend="memory", database_url=None)

    assert isinstance(checkpointer, InMemorySaver)


def test_create_checkpointer_raises_when_postgres_missing_url():
    with pytest.raises(ValueError, match="database_url"):
        create_checkpointer(backend="postgres", database_url=None)


def test_create_checkpointer_normalizes_sqlalchemy_psycopg_url():
    """PostgresSaver 只接受 psycopg 原生 DSN，运行时需要转换 SQLAlchemy URL。"""
    with patch("app.services.agent_runtime.checkpoint_service.PostgresSaver.from_conn_string") as create:
        create_checkpointer(
            backend="postgres",
            database_url="postgresql+psycopg://tester:secret@127.0.0.1:5432/runtime_test",
        )

    create.assert_called_once_with("postgresql://tester:secret@127.0.0.1:5432/runtime_test")
