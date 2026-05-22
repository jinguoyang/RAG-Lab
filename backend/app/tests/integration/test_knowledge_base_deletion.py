"""知识库删除功能集成测试。"""
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.services.knowledge_base_service import (
    KnowledgeBaseActiveRagAppsError,
    KnowledgeBaseConfirmNameMismatchError,
    KnowledgeBaseRunningJobsError,
    delete_knowledge_base,
    get_kb_delete_impact,
)


class TestKbDeletionIntegration:
    """删除知识库端到端流程测试。"""

    @patch("app.services.document_service._create_index_sync_job")
    @patch("app.services.knowledge_base_service.write_audit_log")
    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_full_deletion_flow(self, mock_perm, mock_read, mock_audit, mock_sync):
        """验证删除流程：校验 → 软删除 KB → 禁用绑定 → 归档文档 → 清理配置 → 审计 → 提交。"""
        session = Mock()
        user = Mock()
        user.user.userId = str(uuid4())
        kb_id = uuid4()

        mock_read.return_value = {"name": "测试知识库"}

        # 所有 scalar_one 调用返回 0（无阻断条件）
        session.execute.return_value.scalar_one.return_value = 0
        session.execute.return_value.scalars.return_value.all.return_value = []

        delete_knowledge_base(session, user, kb_id, "测试知识库")

        # 验证提交和审计
        session.commit.assert_called()
        mock_audit.assert_called_once()

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_deletion_blocked_by_active_apps(self, mock_perm, mock_read):
        """存在活跃应用时应阻断删除。"""
        session = Mock()
        user = Mock()
        user.user.userId = str(uuid4())
        kb_id = uuid4()

        mock_read.return_value = {"name": "测试知识库"}
        session.execute.return_value.scalar_one.return_value = 1

        with pytest.raises(KnowledgeBaseActiveRagAppsError):
            delete_knowledge_base(session, user, kb_id, "测试知识库")

        session.commit.assert_not_called()

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    @patch("app.services.knowledge_base_service._ensure_kb_manage_permission")
    def test_deletion_blocked_by_name_mismatch(self, mock_perm, mock_read):
        """名称不匹配时应阻断删除。"""
        session = Mock()
        user = Mock()
        user.user.userId = str(uuid4())
        kb_id = uuid4()

        mock_read.return_value = {"name": "测试知识库"}

        with pytest.raises(KnowledgeBaseConfirmNameMismatchError):
            delete_knowledge_base(session, user, kb_id, "错误名称")

        session.commit.assert_not_called()
