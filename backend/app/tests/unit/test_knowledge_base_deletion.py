"""知识库删除功能单元测试。"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.services.knowledge_base_service import (
    KnowledgeBaseActiveRagAppsError,
    KnowledgeBaseConfirmNameMismatchError,
    KnowledgeBaseIndexCapabilityLockedError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseRunningJobsError,
    _ensure_index_capabilities_mutable,
    delete_knowledge_base,
    get_kb_delete_impact,
)
from app.schemas.knowledge_base import KnowledgeBaseUpdateRequest
from app.tables import document_kb_bindings, document_libraries, document_versions, documents, knowledge_bases


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

    @patch("app.services.knowledge_base_service._read_visible_kb_row")
    def test_counts_library_documents_from_bindings_when_document_has_no_kb_id(self, mock_read, db, admin_user):
        """删除影响统计应以绑定表识别文档库来源文档，不能依赖 documents.kb_id。"""
        now = datetime.now(timezone.utc)
        kb_id = uuid4()
        owner_id = uuid4()
        library_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()

        mock_read.return_value = {"name": "绑定口径知识库"}
        db.execute(
            knowledge_bases.insert().values(
                kb_id=kb_id,
                name="绑定口径知识库",
                description=None,
                owner_id=owner_id,
                sparse_index_enabled=False,
                graph_index_enabled=False,
                sparse_required_for_activation=False,
                graph_required_for_activation=False,
                status="active",
                active_config_revision_id=None,
                metadata={},
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
            )
        )
        db.execute(
            document_libraries.insert().values(
                library_id=library_id,
                owner_id=owner_id,
                name="测试文档库",
                description=None,
                status="active",
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
                deleted_at=None,
                deleted_by=None,
            )
        )
        db.execute(
            documents.insert().values(
                document_id=document_id,
                kb_id=None,
                owner_id=owner_id,
                library_id=library_id,
                name="绑定表归属源文档",
                source_type="upload",
                status="active",
                active_version_id=version_id,
                metadata={},
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
            )
        )
        db.execute(
            document_versions.insert().values(
                version_id=version_id,
                document_id=document_id,
                version_no=1,
                source_file_id=uuid4(),
                status="active",
                parse_status="success",
                dense_index_status="not_required",
                sparse_index_status="not_required",
                graph_index_status="not_required",
                retrieval_ready=False,
                chunk_count=None,
                token_count=None,
                metadata={},
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
            )
        )
        db.execute(
            document_kb_bindings.insert().values(
                binding_id=uuid4(),
                document_id=document_id,
                kb_id=kb_id,
                version_id=version_id,
                status="active",
                chunk_count=0,
                error_code=None,
                error_message=None,
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
                active_chunk_revision_id=None,
            )
        )

        result = get_kb_delete_impact(db, admin_user, kb_id)

        assert result.cascadeData.bindings == 1
        assert result.cascadeData.kbDocuments == 0
        assert result.unaffected.libraryDocuments == 1


class TestIndexCapabilityLock:
    """知识库索引能力锁定测试。"""

    def test_bound_document_without_document_kb_id_locks_index_capability(self, db):
        """已有绑定文档时应锁定索引能力，不能只检查 documents.kb_id。"""
        now = datetime.now(timezone.utc)
        kb_id = uuid4()
        owner_id = uuid4()
        document_id = uuid4()
        version_id = uuid4()

        db.execute(
            documents.insert().values(
                document_id=document_id,
                kb_id=None,
                owner_id=owner_id,
                library_id=None,
                name="绑定表归属文档",
                source_type="upload",
                status="active",
                active_version_id=version_id,
                metadata={},
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
            )
        )
        db.execute(
            document_kb_bindings.insert().values(
                binding_id=uuid4(),
                document_id=document_id,
                kb_id=kb_id,
                version_id=version_id,
                status="active",
                chunk_count=0,
                error_code=None,
                error_message=None,
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
                active_chunk_revision_id=None,
            )
        )

        with pytest.raises(KnowledgeBaseIndexCapabilityLockedError):
            _ensure_index_capabilities_mutable(
                db,
                kb_id,
                {"sparse_index_enabled": False, "graph_index_enabled": False},
                KnowledgeBaseUpdateRequest(sparseIndexEnabled=True),
            )


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
