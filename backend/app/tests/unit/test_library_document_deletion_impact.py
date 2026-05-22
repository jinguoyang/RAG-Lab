"""library_service 文档删除影响分析单元测试。"""
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

import pytest

from app.services.library_service import (
    LibraryDocumentDeleteBlockedError,
    LibraryDocumentDeleteRequiresConfirmationError,
    analyze_document_deletion_impact,
    delete_library_document,
)


def _make_mock_execute(*side_effects):
    """创建依次返回多个结果的 session mock。"""
    session = Mock()
    session.execute.side_effect = side_effects
    return session


def _scalar_result(value):
    """创建 scalar_one 返回指定值的 mock。"""
    mock = MagicMock()
    mock.scalar_one.return_value = value
    return mock


def _scalars_result(values):
    """创建 scalars().all() 返回指定列表的 mock。"""
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = values
    return mock


def test_analyze_no_versions():
    """文档无版本时可以直接删除。"""
    session = Mock()
    mock_versions = MagicMock()
    mock_versions.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_versions

    result = analyze_document_deletion_impact(session, uuid4())

    assert result["can_delete"] is True
    assert result["blocking_reasons"] == []
    assert result["total_versions"] == 0
    assert result["requires_strong_confirmation"] is False


def test_analyze_can_delete():
    """无活跃绑定、无运行中任务、无 QA 引用时可以删除。"""
    versions = [uuid4(), uuid4()]
    session = _make_mock_execute(
        _scalars_result(versions),   # versions 查询
        _scalar_result(0),           # active_binding_count
        _scalar_result(0),           # pending_jobs_count
        _scalars_result([]),         # chunks 查询
    )

    result = analyze_document_deletion_impact(session, uuid4())

    assert result["can_delete"] is True
    assert result["blocking_reasons"] == []
    assert result["active_binding_count"] == 0
    assert result["pending_jobs_count"] == 0
    assert result["qa_evidence_count"] == 0


def test_analyze_blocked_by_active_binding():
    """有活跃绑定时禁止删除。"""
    versions = [uuid4()]
    session = _make_mock_execute(
        _scalars_result(versions),
        _scalar_result(2),           # 2 个活跃绑定
        _scalar_result(0),
        _scalars_result([]),
    )

    result = analyze_document_deletion_impact(session, uuid4())

    assert result["can_delete"] is False
    assert len(result["blocking_reasons"]) == 1
    assert "活跃的知识库绑定" in result["blocking_reasons"][0]


def test_analyze_blocked_by_pending_jobs():
    """有运行中任务时禁止删除。"""
    versions = [uuid4()]
    session = _make_mock_execute(
        _scalars_result(versions),
        _scalar_result(0),
        _scalar_result(3),           # 3 个运行中任务
        _scalars_result([]),
    )

    result = analyze_document_deletion_impact(session, uuid4())

    assert result["can_delete"] is False
    assert "运行中的任务" in result["blocking_reasons"][0]


def test_analyze_blocked_by_both():
    """同时有活跃绑定和运行中任务时列出两个原因。"""
    versions = [uuid4()]
    session = _make_mock_execute(
        _scalars_result(versions),
        _scalar_result(1),
        _scalar_result(1),
        _scalars_result([]),
    )

    result = analyze_document_deletion_impact(session, uuid4())

    assert result["can_delete"] is False
    assert len(result["blocking_reasons"]) == 2


def test_analyze_requires_strong_confirmation():
    """有 QA 引用时需要强确认但不阻止删除。"""
    versions = [uuid4()]
    chunks = [uuid4(), uuid4()]
    session = _make_mock_execute(
        _scalars_result(versions),
        _scalar_result(0),
        _scalar_result(0),
        _scalars_result(chunks),
        _scalar_result(5),           # 5 条 QA 引用
    )

    result = analyze_document_deletion_impact(session, uuid4())

    assert result["can_delete"] is True
    assert result["requires_strong_confirmation"] is True
    assert result["qa_evidence_count"] == 5


def test_analyze_blocked_and_requires_confirmation():
    """有活跃绑定和 QA 引用时：阻止删除 + 需要强确认。"""
    versions = [uuid4()]
    chunks = [uuid4()]
    session = _make_mock_execute(
        _scalars_result(versions),
        _scalar_result(2),
        _scalar_result(0),
        _scalars_result(chunks),
        _scalar_result(10),
    )

    result = analyze_document_deletion_impact(session, uuid4())

    assert result["can_delete"] is False
    assert result["requires_strong_confirmation"] is True
    assert len(result["blocking_reasons"]) == 1


def test_delete_blocked_raises_error():
    """删除被阻止时抛出 LibraryDocumentDeleteBlockedError。"""
    session = Mock()
    current_user = Mock()
    current_user.user.userId = str(uuid4())
    doc_id = uuid4()

    with patch("app.services.library_service.analyze_document_deletion_impact") as mock_analyze, \
         patch("app.services.library_service._ensure_owner"):
        mock_analyze.return_value = {
            "can_delete": False,
            "blocking_reasons": ["文档存在 2 个活跃的知识库绑定"],
            "requires_strong_confirmation": False,
        }

        with pytest.raises(LibraryDocumentDeleteBlockedError):
            delete_library_document(session, current_user, doc_id)


def test_delete_requires_confirmation_raises_error():
    """需要强确认但未提供时抛出 LibraryDocumentDeleteRequiresConfirmationError。"""
    session = Mock()
    current_user = Mock()
    current_user.user.userId = str(uuid4())
    doc_id = uuid4()

    with patch("app.services.library_service.analyze_document_deletion_impact") as mock_analyze, \
         patch("app.services.library_service._ensure_owner"):
        mock_analyze.return_value = {
            "can_delete": True,
            "blocking_reasons": [],
            "requires_strong_confirmation": True,
            "qa_evidence_count": 5,
        }

        with pytest.raises(LibraryDocumentDeleteRequiresConfirmationError):
            delete_library_document(session, current_user, doc_id, strong_confirmation=False)


def test_delete_with_strong_confirmation_succeeds():
    """提供强确认且无阻止因素时删除成功。"""
    session = Mock()
    user_id = uuid4()
    current_user = Mock()
    current_user.user.userId = str(user_id)
    doc_id = uuid4()

    # 无活跃绑定
    mock_bindings = MagicMock()
    mock_bindings.mappings.return_value.all.return_value = []

    with patch("app.services.library_service.analyze_document_deletion_impact") as mock_analyze, \
         patch("app.services.library_service._ensure_owner"):
        mock_analyze.return_value = {
            "can_delete": True,
            "blocking_reasons": [],
            "requires_strong_confirmation": True,
            "qa_evidence_count": 5,
        }
        session.execute.return_value = mock_bindings

        result = delete_library_document(session, current_user, doc_id, strong_confirmation=True)

    assert "documentId" in result
    assert result["unboundCount"] >= 0
