"""生命周期集成测试。"""
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

import pytest

from app.services.document_service import (
    create_parse_revision,
    analyze_document_version_deletion_impact,
    delete_document_version,
)
from app.services.binding_service import (
    BindingBuildInProgressError,
    BindingNotFoundError,
    activate_chunk_revision,
    complete_chunk_revision_build,
    create_chunk_revision,
    fail_chunk_revision,
)
from app.services.app_runtime_service import (
    KnowledgeBaseDisabledError,
    KnowledgeBaseNotFoundError,
    _check_kb_status,
)


class TestDocumentLifecycle:
    """文档生命周期测试。"""

    def test_create_parse_revision(self):
        """测试创建 ParseRevision。"""
        session = Mock()
        version_id = uuid4()

        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
            content_text="# Test",
        )

        assert result is not None
        session.execute.assert_called_once()

    def test_analyze_deletion_impact_can_delete(self):
        """测试可以删除的情况。"""
        session = Mock()
        version_id = uuid4()
        other_version_id = uuid4()

        mock_active = MagicMock()
        mock_active.scalar.return_value = other_version_id

        mock_binding = MagicMock()
        mock_binding.scalar_one.return_value = 0

        mock_jobs = MagicMock()
        mock_jobs.scalar_one.return_value = 0

        mock_chunks = MagicMock()
        mock_chunks.scalars.return_value.all.return_value = []

        session.execute.side_effect = [mock_active, mock_binding, mock_jobs, mock_chunks]

        impact = analyze_document_version_deletion_impact(session, version_id)

        assert impact["can_delete"] is True
        assert len(impact["blocking_reasons"]) == 0

    def test_delete_document_version_success(self):
        """测试成功删除文档版本。"""
        session = Mock()
        version_id = uuid4()
        user_id = uuid4()
        current_user = Mock()
        current_user.user.userId = str(user_id)

        with patch("app.services.document_service.analyze_document_version_deletion_impact") as mock_analyze:
            mock_analyze.return_value = {
                "can_delete": True,
                "requires_strong_confirmation": False,
                "qa_evidence_count": 0,
                "qa_citation_count": 0,
            }

            mock_scalars = MagicMock()
            mock_scalars.scalars.return_value.all.return_value = []
            session.execute.return_value = mock_scalars

            result = delete_document_version(
                session=session,
                current_user=current_user,
                document_version_id=version_id,
            )

            assert result["status"] == "success"


class TestChunkRevisionLifecycle:
    """绑定生命周期测试。"""

    def test_create_chunk_revision(self):
        """测试创建 BindingRevision。"""
        session = Mock()

        result = create_chunk_revision(
            session=session,
            binding_id=uuid4(),
            knowledge_base_id=uuid4(),
            document_id=uuid4(),
            document_version_id=uuid4(),
            parse_revision_id=uuid4(),
        )

        assert result is not None
        session.execute.assert_called_once()

    def test_activate_chunk_revision(self):
        """测试激活 BindingRevision。"""
        session = Mock()
        binding_rev_id = uuid4()
        binding_id = uuid4()

        mock_rev = {
            "chunk_revision_id": binding_rev_id,
            "binding_id": binding_id,
            "status": "building",
        }
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_rev
        session.execute.return_value = mock_result

        activate_chunk_revision(session, binding_rev_id)

        assert session.execute.call_count >= 5

    def test_fail_chunk_revision(self):
        """测试标记 BindingRevision 为失败。"""
        session = Mock()

        fail_chunk_revision(session, uuid4())

        session.execute.assert_called_once()

    def test_complete_chunk_revision_build(self):
        """测试完成构建并激活。"""
        session = Mock()

        with patch("app.services.binding_service.activate_chunk_revision") as mock_activate:
            complete_chunk_revision_build(session, uuid4(), chunk_count=10)

            session.execute.assert_called_once()
            mock_activate.assert_called_once()


class TestAppRuntimeProtection:
    """App Runtime 保护测试。"""

    def test_kb_active(self):
        """测试知识库正常状态。"""
        session = Mock()
        kb_id = uuid4()

        mock_kb = {"kb_id": kb_id, "status": "active"}
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_kb
        session.execute.return_value = mock_result

        _check_kb_status(session, kb_id)

    def test_kb_disabled(self):
        """测试知识库禁用状态。"""
        session = Mock()
        kb_id = uuid4()

        mock_kb = {"kb_id": kb_id, "status": "disabled"}
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_kb
        session.execute.return_value = mock_result

        with pytest.raises(KnowledgeBaseDisabledError) as exc_info:
            _check_kb_status(session, kb_id)

        assert exc_info.value.kb_id == kb_id

    def test_kb_not_found(self):
        """测试知识库不存在。"""
        session = Mock()
        kb_id = uuid4()

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        session.execute.return_value = mock_result

        with pytest.raises(KnowledgeBaseNotFoundError) as exc_info:
            _check_kb_status(session, kb_id)

        assert exc_info.value.kb_id == kb_id
