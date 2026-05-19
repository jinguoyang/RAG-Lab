"""Library 服务单元测试。"""

from uuid import uuid4

import pytest

from app.services.library_service import (
    LibraryDocumentNotFoundError,
    LibraryPermissionError,
    _get_error_suggestion,
    batch_action,
)


class TestGetErrorSuggestion:
    """测试错误建议函数。"""

    def test_known_error_codes(self):
        assert "拆分" in _get_error_suggestion("PARSE_TIMEOUT")
        assert "格式" in _get_error_suggestion("UNSUPPORTED_FORMAT")
        assert "重新上传" in _get_error_suggestion("FILE_CORRUPTED")
        assert "稍后" in _get_error_suggestion("STORAGE_ERROR")

    def test_unknown_error_code(self):
        assert "管理员" in _get_error_suggestion("UNKNOWN")
        assert "管理员" in _get_error_suggestion("SOME_NEW_ERROR")


class TestBatchAction:
    """测试批量操作。"""

    def test_batch_action_with_invalid_ids(self, db, test_user):
        """无效 ID 应返回失败。"""
        result = batch_action(db, test_user, ["not-a-uuid"], "delete")
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "INVALID_ID"
        assert result["summary"]["total"] == 1
        assert result["summary"]["failed"] == 1

    def test_batch_action_with_nonexistent_docs(self, db, test_user):
        """不存在的文档应返回 NOT_FOUND。"""
        fake_id = str(uuid4())
        result = batch_action(db, test_user, [fake_id], "delete")
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "NOT_FOUND"
