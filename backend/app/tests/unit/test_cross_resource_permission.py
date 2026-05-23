"""跨资源权限校验服务单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.cross_resource_permission import (
    check_cross_resource_permission,
    check_document_version_delete_permission,
)


class TestCheckCrossResourcePermission:
    """测试 check_cross_resource_permission 函数。"""

    def test_both_allowed(self):
        """两个权限都通过 → True。"""
        session = MagicMock()
        current_user = MagicMock()
        library_id = uuid4()
        kb_id = uuid4()

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=True,
        ) as mock_lib, patch(
            "app.services.cross_resource_permission.has_kb_permission",
            return_value=True,
        ) as mock_kb:
            result = check_cross_resource_permission(
                session, current_user, library_id, kb_id,
            )

        assert result is True
        mock_lib.assert_called_once_with(session, current_user, "library.document.bind")
        mock_kb.assert_called_once_with(session, current_user, kb_id, "kb.document.bind")

    def test_library_denied(self):
        """源文档库权限被拒绝 → False。"""
        session = MagicMock()
        current_user = MagicMock()
        library_id = uuid4()
        kb_id = uuid4()

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=False,
        ) as mock_lib, patch(
            "app.services.cross_resource_permission.has_kb_permission",
            return_value=True,
        ) as mock_kb:
            result = check_cross_resource_permission(
                session, current_user, library_id, kb_id,
            )

        assert result is False
        mock_lib.assert_called_once()
        mock_kb.assert_not_called()

    def test_kb_denied(self):
        """目标知识库权限被拒绝 → False。"""
        session = MagicMock()
        current_user = MagicMock()
        library_id = uuid4()
        kb_id = uuid4()

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=True,
        ) as mock_lib, patch(
            "app.services.cross_resource_permission.has_kb_permission",
            return_value=False,
        ) as mock_kb:
            result = check_cross_resource_permission(
                session, current_user, library_id, kb_id,
            )

        assert result is False
        mock_lib.assert_called_once()
        mock_kb.assert_called_once()


class TestCheckDocumentVersionDeletePermission:
    """测试 check_document_version_delete_permission 函数。"""

    def _make_user(self):
        user = MagicMock()
        user.user.userId = str(uuid4())
        user.user.platformRole = "user"
        return user

    def _mock_session(self, *results):
        """按顺序返回多个查询结果。"""
        session = MagicMock()
        mock_results = []
        for value in results:
            mock_result = MagicMock()
            mock_result.scalar.return_value = value
            if isinstance(value, list):
                mock_result.first.return_value = value[0] if value else None
                mock_result.scalars.return_value.all.return_value = value
            else:
                mock_result.first.return_value = value
                mock_result.scalars.return_value.all.return_value = []
            mock_results.append(mock_result)

        call_index = {"i": 0}

        def side_effect(*args, **kwargs):
            idx = call_index["i"]
            call_index["i"] += 1
            return mock_results[idx]

        session.execute.side_effect = side_effect
        return session

    def test_no_permission(self):
        """没有删除权限 → False。"""
        session = MagicMock()
        user = self._make_user()
        library_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=False,
        ):
            allowed, reason = check_document_version_delete_permission(
                session, user, library_id, document_id, version_id,
            )

        assert allowed is False
        assert "没有 library.version.delete 权限" in reason

    def test_active_version(self):
        """版本是当前活跃版本 → False。"""
        user = self._make_user()
        library_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()

        # 第一个查询返回活跃版本 ID（等于当前版本）
        session = self._mock_session(version_id)

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=True,
        ):
            allowed, reason = check_document_version_delete_permission(
                session, user, library_id, document_id, version_id,
            )

        assert allowed is False
        assert "该版本是文档的当前活跃版本" in reason

    def test_active_binding(self):
        """版本有活跃的 ChunkRevision → False。"""
        user = self._make_user()
        library_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()

        # 第一个查询: 活跃版本 ID = None（不是活跃版本）
        # 第二个查询: chunk_revision_id = uuid4()（有活跃绑定）
        session = self._mock_session(None, uuid4())

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=True,
        ):
            allowed, reason = check_document_version_delete_permission(
                session, user, library_id, document_id, version_id,
            )

        assert allowed is False
        assert "该版本有活跃的绑定修订" in reason

    def test_pending_jobs(self):
        """版本有待处理的解析任务 → False。"""
        user = self._make_user()
        library_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()

        # 第一个查询: 活跃版本 ID = None
        # 第二个查询: chunk_revision_id = None（无活跃绑定）
        # 第三个查询: 有待处理的解析任务
        session = self._mock_session(None, None, [uuid4()])

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=True,
        ):
            allowed, reason = check_document_version_delete_permission(
                session, user, library_id, document_id, version_id,
            )

        assert allowed is False
        assert "该版本有待处理的解析任务" in reason

    def test_allowed(self):
        """所有检查通过 → True。"""
        user = self._make_user()
        library_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()

        # 第一个查询: 活跃版本 ID = None
        # 第二个查询: chunk_revision_id = None
        # 第三个查询: 无待处理解析任务（空列表）
        # 第四个查询: 无待处理入库任务（空列表）
        session = self._mock_session(None, None, [], [])

        with patch(
            "app.services.cross_resource_permission.has_library_permission",
            return_value=True,
        ):
            allowed, reason = check_document_version_delete_permission(
                session, user, library_id, document_id, version_id,
            )

        assert allowed is True
        assert reason == ""
