"""App Runtime 知识库保护单元测试。"""
from datetime import UTC, datetime
from uuid import uuid4
from unittest.mock import Mock, MagicMock

import pytest

from app.services.app_runtime_service import (
    AppRuntimeNotFoundError,
    KnowledgeBaseDisabledError,
    KnowledgeBaseNotFoundError,
    _check_kb_status,
    _get_or_create_conversation,
)
from app.core.config import get_settings


def test_check_kb_status_active():
    """测试知识库正常状态不抛出异常。"""
    session = Mock()
    kb_id = uuid4()

    mock_kb = {
        "kb_id": kb_id,
        "status": "active",
    }
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = mock_kb
    session.execute.return_value = mock_result

    # 不应该抛出异常
    _check_kb_status(session, kb_id)


def test_check_kb_status_disabled():
    """测试知识库禁用状态抛出 KnowledgeBaseDisabledError。"""
    session = Mock()
    kb_id = uuid4()

    mock_kb = {
        "kb_id": kb_id,
        "status": "disabled",
    }
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = mock_kb
    session.execute.return_value = mock_result

    with pytest.raises(KnowledgeBaseDisabledError) as exc_info:
        _check_kb_status(session, kb_id)

    assert exc_info.value.kb_id == kb_id


def test_check_kb_status_not_found():
    """测试知识库不存在抛出 KnowledgeBaseNotFoundError。"""
    session = Mock()
    kb_id = uuid4()

    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    session.execute.return_value = mock_result

    with pytest.raises(KnowledgeBaseNotFoundError) as exc_info:
        _check_kb_status(session, kb_id)

    assert exc_info.value.kb_id == kb_id


def test_check_kb_status_error_messages():
    """测试错误消息包含知识库 ID。"""
    kb_id = uuid4()

    disabled_error = KnowledgeBaseDisabledError(kb_id)
    assert str(kb_id) in str(disabled_error)

    not_found_error = KnowledgeBaseNotFoundError(kb_id)
    assert str(kb_id) in str(not_found_error)


def test_conversation_cannot_cross_app():
    """会话不能跨 App 访问——conversationId 在不同 App 下应返回 NotFound。"""
    from app.schemas.app_runtime import AppRuntimeChatRequest

    app_a_id = uuid4()
    app_b_id = uuid4()
    conversation_id = str(uuid4())

    session = Mock()
    # 模拟 conversation 存在于 app_a 但通过 app_b 访问
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None  # 找不到
    session.execute.return_value = mock_result

    request = AppRuntimeChatRequest(query="继续", conversationId=conversation_id, endUserId="u1")

    with pytest.raises(AppRuntimeNotFoundError):
        _get_or_create_conversation(session, app_b_id, request, datetime.now(UTC))


def test_new_conversation_defaults_to_legacy_when_agent_runtime_disabled(db, monkeypatch):
    """Agent Runtime 未开启时，新 App 会话固定使用 Legacy。"""
    from app.schemas.app_runtime import AppRuntimeChatRequest

    monkeypatch.setenv("RAG_LAB_AGENT_RUNTIME_ENABLED", "false")
    monkeypatch.setenv("RAG_LAB_AGENT_RUNTIME_DEFAULT_VERSION", "langgraph_primary_v1")
    get_settings.cache_clear()
    try:
        row = _get_or_create_conversation(
            db,
            uuid4(),
            AppRuntimeChatRequest(query="问题"),
            datetime.now(UTC),
        )
    finally:
        get_settings.cache_clear()

    assert row["metadata"]["runtimeVersion"] == "legacy_v1"


def test_new_conversation_records_primary_version_when_enabled(db, monkeypatch):
    """Agent Runtime 开启后，新 App 会话固定记录配置版本。"""
    from app.schemas.app_runtime import AppRuntimeChatRequest

    monkeypatch.setenv("RAG_LAB_AGENT_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("RAG_LAB_AGENT_RUNTIME_DEFAULT_VERSION", "langgraph_primary_v1")
    get_settings.cache_clear()
    try:
        row = _get_or_create_conversation(
            db,
            uuid4(),
            AppRuntimeChatRequest(query="问题"),
            datetime.now(UTC),
        )
    finally:
        get_settings.cache_clear()

    assert row["metadata"]["runtimeVersion"] == "langgraph_primary_v1"
