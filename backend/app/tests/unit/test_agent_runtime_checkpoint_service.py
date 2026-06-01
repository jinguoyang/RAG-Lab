"""Agent Runtime Task 3: 官方 Checkpointer 工厂测试。"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.services.agent_runtime.checkpoint_service import create_checkpointer


def test_create_checkpointer_supports_official_memory_backend():
    checkpointer = create_checkpointer(backend="memory", database_url=None)

    assert isinstance(checkpointer, InMemorySaver)


def test_create_checkpointer_raises_when_postgres_missing_url():
    with pytest.raises(ValueError, match="database_url"):
        create_checkpointer(backend="postgres", database_url=None)
