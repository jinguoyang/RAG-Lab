import pytest
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from app.services.document_service import _calculate_file_hash, check_file_hash_duplicate, create_parse_revision


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


def test_create_parse_revision():
    """测试创建 ParseRevision"""
    session = Mock()
    version_id = uuid4()

    with patch('app.services.document_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None

        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
            content_text="# Test Content",
            content_hash="abc123",
            parser_name="test_parser",
            parser_version="1.0",
        )

        assert result is not None
        mock_insert.assert_called_once()


def test_create_parse_revision_with_created_by():
    """测试创建 ParseRevision 时传入 created_by"""
    session = Mock()
    version_id = uuid4()
    user_id = uuid4()

    with patch('app.services.document_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None

        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
            content_text="# Test Content",
            parser_name="test_parser",
            parser_version="1.0",
            created_by=user_id,
        )

        assert result is not None
        mock_insert.assert_called_once()
        # Verify created_by was passed to values
        call_kwargs = mock_insert.return_value.values.call_args[1]
        assert call_kwargs["created_by"] == user_id


def test_create_parse_revision_default_parse_options():
    """测试 create_parse_revision 默认空 parse_options"""
    session = Mock()
    version_id = uuid4()

    with patch('app.services.document_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None

        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
        )

        assert result is not None
        call_kwargs = mock_insert.return_value.values.call_args[1]
        assert call_kwargs["parse_options"] == {}
        assert call_kwargs["status"] == "completed"
