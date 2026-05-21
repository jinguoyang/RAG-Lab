import pytest
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from app.services.document_service import _calculate_file_hash, check_file_hash_duplicate


def test_calculate_file_hash():
    """测试文件 hash 计算"""
    content = b"test content"
    hash1 = _calculate_file_hash(content)
    hash2 = _calculate_file_hash(content)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest length


def test_calculate_file_hash_different_content():
    """测试不同内容产生不同 hash"""
    hash1 = _calculate_file_hash(b"content 1")
    hash2 = _calculate_file_hash(b"content 2")
    assert hash1 != hash2


def test_calculate_file_hash_empty_content():
    """测试空内容产生有效 hash"""
    hash_val = _calculate_file_hash(b"")
    assert len(hash_val) == 64


def test_check_file_hash_duplicate_no_duplicate():
    """测试没有重复文件时返回 None"""
    session = Mock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    session.execute.return_value = mock_result

    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is None


def test_check_file_hash_duplicate_found():
    """测试发现重复文件时返回信息"""
    from datetime import datetime, timezone

    session = Mock()
    mock_file = {
        "file_id": uuid4(),
        "file_name": "test.pdf",
        "created_at": datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc),
    }
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = mock_file
    session.execute.return_value = mock_result

    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is not None
    assert result["file_name"] == "test.pdf"
    assert result["file_id"] == mock_file["file_id"]
    assert result["created_at"] == "2026-05-21T10:00:00+00:00"


def test_check_file_hash_duplicate_found_null_created_at():
    """测试 created_at 为 None 时返回 None"""
    session = Mock()
    mock_file = {
        "file_id": uuid4(),
        "file_name": "test.pdf",
        "created_at": None,
    }
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = mock_file
    session.execute.return_value = mock_result

    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is not None
    assert result["created_at"] is None
