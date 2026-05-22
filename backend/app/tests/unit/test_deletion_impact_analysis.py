"""删除影响分析单元测试。"""
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

import pytest

from app.services.document_service import analyze_document_version_deletion_impact, delete_document_version


def _make_scalar_side_effect(*values):
    """创建一个依次返回多个值的 scalar mock。"""
    mock = MagicMock()
    mock.scalar_one.side_effect = values
    mock.scalar.side_effect = values
    return mock


def test_analyze_deletion_impact_can_delete():
    """测试可以删除的情况：非 active version，无 active binding，无运行中任务，无 QA 引用。"""
    session = Mock()
    version_id = uuid4()
    other_version_id = uuid4()

    # 第一次 execute: 查 active_version_id
    mock_active = MagicMock()
    mock_active.scalar.return_value = other_version_id

    # 第二次 execute: 查 active_binding_count
    mock_binding = MagicMock()
    mock_binding.scalar_one.return_value = 0

    # 第三次 execute: 查 pending_ingest_jobs
    mock_jobs = MagicMock()
    mock_jobs.scalar_one.return_value = 0

    # 第四次 execute: 查 version_chunks
    mock_chunks = MagicMock()
    mock_chunks.scalars.return_value.all.return_value = []

    session.execute.side_effect = [mock_active, mock_binding, mock_jobs, mock_chunks]

    result = analyze_document_version_deletion_impact(session, version_id)

    assert result["can_delete"] is True
    assert len(result["blocking_reasons"]) == 0
    assert result["requires_strong_confirmation"] is False


def test_analyze_deletion_impact_active_version():
    """测试删除 active version 被阻止。"""
    session = Mock()
    version_id = uuid4()

    mock_active = MagicMock()
    mock_active.scalar.return_value = version_id  # 同一个 version

    mock_binding = MagicMock()
    mock_binding.scalar_one.return_value = 0

    mock_jobs = MagicMock()
    mock_jobs.scalar_one.return_value = 0

    mock_chunks = MagicMock()
    mock_chunks.scalars.return_value.all.return_value = []

    session.execute.side_effect = [mock_active, mock_binding, mock_jobs, mock_chunks]

    result = analyze_document_version_deletion_impact(session, version_id)

    assert result["can_delete"] is False
    assert "不能删除文档库当前 active version" in result["blocking_reasons"]


def test_analyze_deletion_impact_active_binding():
    """测试有 active ChunkRevision 时被阻止。"""
    session = Mock()
    version_id = uuid4()

    mock_active = MagicMock()
    mock_active.scalar.return_value = uuid4()  # 不同的 version

    mock_binding = MagicMock()
    mock_binding.scalar_one.return_value = 2  # 有 2 个 active binding

    mock_jobs = MagicMock()
    mock_jobs.scalar_one.return_value = 0

    mock_chunks = MagicMock()
    mock_chunks.scalars.return_value.all.return_value = []

    session.execute.side_effect = [mock_active, mock_binding, mock_jobs, mock_chunks]

    result = analyze_document_version_deletion_impact(session, version_id)

    assert result["can_delete"] is False
    assert any("active BindingRevision" in r for r in result["blocking_reasons"])


def test_analyze_deletion_impact_pending_jobs():
    """测试有运行中任务时被阻止。"""
    session = Mock()
    version_id = uuid4()

    mock_active = MagicMock()
    mock_active.scalar.return_value = uuid4()

    mock_binding = MagicMock()
    mock_binding.scalar_one.return_value = 0

    mock_jobs = MagicMock()
    mock_jobs.scalar_one.return_value = 1  # 有 1 个运行中任务

    mock_chunks = MagicMock()
    mock_chunks.scalars.return_value.all.return_value = []

    session.execute.side_effect = [mock_active, mock_binding, mock_jobs, mock_chunks]

    result = analyze_document_version_deletion_impact(session, version_id)

    assert result["can_delete"] is False
    assert any("运行中" in r for r in result["blocking_reasons"])


def test_analyze_deletion_impact_with_qa_references():
    """测试有 QA 引用时需要强确认。"""
    session = Mock()
    version_id = uuid4()
    chunk_id = uuid4()

    mock_active = MagicMock()
    mock_active.scalar.return_value = uuid4()

    mock_binding = MagicMock()
    mock_binding.scalar_one.return_value = 0

    mock_jobs = MagicMock()
    mock_jobs.scalar_one.return_value = 0

    mock_chunks = MagicMock()
    mock_chunks.scalars.return_value.all.return_value = [chunk_id]

    mock_evidence = MagicMock()
    mock_evidence.scalar_one.return_value = 5

    session.execute.side_effect = [mock_active, mock_binding, mock_jobs, mock_chunks, mock_evidence]

    result = analyze_document_version_deletion_impact(session, version_id)

    assert result["can_delete"] is True
    assert result["requires_strong_confirmation"] is True
    assert result["qa_evidence_count"] == 5


def test_delete_document_version_success():
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

        # Mock all the execute calls for cascade cleanup
        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
        )

        assert result["status"] == "success"


def test_delete_document_version_blocked():
    """测试删除被阻止。"""
    session = Mock()
    version_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(uuid4())

    with patch("app.services.document_service.analyze_document_version_deletion_impact") as mock_analyze:
        mock_analyze.return_value = {
            "can_delete": False,
            "blocking_reasons": ["不能删除 active version"],
            "requires_strong_confirmation": False,
        }

        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
        )

        assert result["status"] == "blocked"


def test_delete_document_version_requires_confirmation():
    """测试需要强确认。"""
    session = Mock()
    version_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(uuid4())

    with patch("app.services.document_service.analyze_document_version_deletion_impact") as mock_analyze:
        mock_analyze.return_value = {
            "can_delete": True,
            "requires_strong_confirmation": True,
            "qa_evidence_count": 5,
        }

        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
            strong_confirmation=False,
        )

        assert result["status"] == "confirmation_required"


def test_delete_document_version_with_strong_confirmation():
    """测试强确认后删除成功。"""
    session = Mock()
    version_id = uuid4()
    user_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(user_id)

    with patch("app.services.document_service.analyze_document_version_deletion_impact") as mock_analyze:
        mock_analyze.return_value = {
            "can_delete": True,
            "requires_strong_confirmation": True,
            "qa_evidence_count": 5,
            "qa_citation_count": 3,
        }

        mock_scalars = MagicMock()
        mock_scalars.scalars.return_value.all.return_value = []
        session.execute.return_value = mock_scalars

        result = delete_document_version(
            session=session,
            current_user=current_user,
            document_version_id=version_id,
            strong_confirmation=True,
        )

        assert result["status"] == "success"
