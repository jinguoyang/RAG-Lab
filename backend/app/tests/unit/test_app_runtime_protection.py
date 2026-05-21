"""App Runtime 知识库保护单元测试。"""
from uuid import uuid4
from unittest.mock import Mock, MagicMock

import pytest

from app.services.app_runtime_service import (
    KnowledgeBaseDisabledError,
    KnowledgeBaseNotFoundError,
    _check_kb_status,
)


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
