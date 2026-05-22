"""知识库删除功能单元测试。"""
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.services.knowledge_base_service import (
    KnowledgeBaseActiveRagAppsError,
    KnowledgeBaseConfirmNameMismatchError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseRunningJobsError,
    delete_knowledge_base,
    get_kb_delete_impact,
)


@pytest.fixture()
def mock_session():
    session = Mock()
    return session


@pytest.fixture()
def mock_user():
    user = Mock()
    user.user.userId = str(uuid4())
    return user


@pytest.fixture()
def kb_id():
    return uuid4()


class TestGetKbDeleteImpact:
    """删除影响查询测试。"""

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_returns_impact_with_no_blockers(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        mock_session.execute.return_value.scalar_one.return_value = 0
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_kb_delete_impact(mock_session, mock_user, kb_id)

        assert result.kbName == "测试知识库"
        assert result.blockers.activeRagApps == []
        assert result.blockers.runningJobs == []

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_returns_active_apps_as_blockers(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        app_id = uuid4()

        # 第一次 execute 返回 active apps, 后续返回 0
        mock_active_result = MagicMock()
        mock_active_result.mappings.return_value.all.return_value = [
            {"app_id": app_id, "name": "客服助手"}
        ]
        mock_zero_result = MagicMock()
        mock_zero_result.scalar_one.return_value = 0
        mock_empty_result = MagicMock()
        mock_empty_result.mappings.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            mock_active_result,  # active apps
            mock_zero_result,    # running jobs
            mock_zero_result,    # binding count
            mock_zero_result,    # kb doc count
            mock_zero_result,    # chunk count
            mock_zero_result,    # config count
            mock_empty_result,   # inactive apps
            mock_zero_result,    # member count
            mock_zero_result,    # library doc count
        ]

        result = get_kb_delete_impact(mock_session, mock_user, kb_id)

        assert len(result.blockers.activeRagApps) == 1
        assert result.blockers.activeRagApps[0]["name"] == "客服助手"


class TestDeleteKnowledgeBase:
    """删除知识库测试。"""

    @patch("app.services.document_service._create_index_sync_job")
    @patch("app.services.knowledge_base_service.write_audit_log")
    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_successful_deletion(self, mock_perm, mock_read, mock_audit, mock_sync, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        mock_session.execute.return_value.scalar_one.return_value = 0
        mock_session.execute.return_value.scalars.return_value.all.return_value = []

        delete_knowledge_base(mock_session, mock_user, kb_id, "测试知识库")

        mock_session.commit.assert_called()
        mock_audit.assert_called_once()

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_raises_on_name_mismatch(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}

        with pytest.raises(KnowledgeBaseConfirmNameMismatchError):
            delete_knowledge_base(mock_session, mock_user, kb_id, "错误名称")

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_raises_on_active_rag_apps(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        mock_session.execute.return_value.scalar_one.return_value = 1

        with pytest.raises(KnowledgeBaseActiveRagAppsError):
            delete_knowledge_base(mock_session, mock_user, kb_id, "测试知识库")

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_raises_on_running_jobs(self, mock_perm, mock_read, mock_session, mock_user, kb_id):
        mock_read.return_value = {"name": "测试知识库"}
        # 第一次返回 0 (active apps), 第二次返回 1 (running jobs)
        mock_session.execute.return_value.scalar_one.side_effect = [0, 1]

        with pytest.raises(KnowledgeBaseRunningJobsError):
            delete_knowledge_base(mock_session, mock_user, kb_id, "测试知识库")
