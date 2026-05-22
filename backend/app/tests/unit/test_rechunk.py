"""rechunk_document 单元测试。"""
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

import pytest

from app.services.binding_service import (
    BindingBuildInProgressError,
    BindingNotFoundError,
    BindingVersionNotReadyError,
    rechunk_document,
)


def _make_binding_row(binding_id, active_rev_id, version_id, kb_id, doc_id):
    return {
        "binding_id": binding_id,
        "active_chunk_revision_id": active_rev_id,
        "version_id": version_id,
        "knowledge_base_id": kb_id,
        "document_id": doc_id,
    }


def _make_active_rev(rev_id, parse_rev_id, doc_version_id):
    return {
        "chunk_revision_id": rev_id,
        "parse_revision_id": parse_rev_id,
        "document_version_id": doc_version_id,
    }


def test_rechunk_binding_not_found():
    """绑定不存在时抛出 BindingNotFoundError。"""
    session = Mock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    session.execute.return_value = mock_result

    with pytest.raises(BindingNotFoundError):
        rechunk_document(session, str(uuid4()), str(uuid4()), str(uuid4()))


def test_rechunk_building_in_progress():
    """有 building 状态的 ChunkRevision 时抛出 BindingBuildInProgressError。"""
    session = Mock()
    binding_id = uuid4()
    active_rev_id = uuid4()

    # 第一次 execute: binding 查询
    mock_binding = MagicMock()
    mock_binding.mappings.return_value.first.return_value = _make_binding_row(
        binding_id, active_rev_id, uuid4(), uuid4(), uuid4()
    )

    # 第二次 execute: building 查询
    mock_building = MagicMock()
    mock_building.mappings.return_value.first.return_value = {"status": "building"}

    session.execute.side_effect = [mock_binding, mock_building]

    with pytest.raises(BindingBuildInProgressError):
        rechunk_document(session, str(uuid4()), str(uuid4()), str(uuid4()))


def test_rechunk_no_active_revision():
    """没有 active ChunkRevision 时抛出 BindingVersionNotReadyError。"""
    session = Mock()
    binding_id = uuid4()

    # binding 无 active_chunk_revision_id
    mock_binding = MagicMock()
    mock_binding.mappings.return_value.first.return_value = _make_binding_row(
        binding_id, None, uuid4(), uuid4(), uuid4()
    )

    # 无 building
    mock_building = MagicMock()
    mock_building.mappings.return_value.first.return_value = None

    session.execute.side_effect = [mock_binding, mock_building]

    with pytest.raises(BindingVersionNotReadyError):
        rechunk_document(session, str(uuid4()), str(uuid4()), str(uuid4()))


def test_rechunk_success():
    """正常 rechunk 流程：创建新 ChunkRevision + ingest job。"""
    session = Mock()
    binding_id = uuid4()
    active_rev_id = uuid4()
    parse_rev_id = uuid4()
    doc_version_id = uuid4()
    version_id = uuid4()
    kb_id = uuid4()
    doc_id = uuid4()
    user_id = str(uuid4())

    mock_binding = MagicMock()
    mock_binding.mappings.return_value.first.return_value = _make_binding_row(
        binding_id, active_rev_id, version_id, kb_id, doc_id
    )

    mock_building = MagicMock()
    mock_building.mappings.return_value.first.return_value = None

    mock_active_rev = MagicMock()
    mock_active_rev.mappings.return_value.first.return_value = _make_active_rev(
        active_rev_id, parse_rev_id, doc_version_id
    )

    # kb_doc_id 查询
    mock_kb_doc = MagicMock()
    mock_kb_doc.scalar.return_value = uuid4()

    session.execute.side_effect = [
        mock_binding,     # binding 查询
        mock_building,    # building 查询
        mock_active_rev,  # active revision 查询
        mock_kb_doc,      # kb_doc_id 查询
        None,             # create_chunk_revision 的 execute (mock)
        None,             # insert ingest_job 的 execute
    ]

    with patch("app.services.binding_service.create_chunk_revision") as mock_create_rev, \
         patch("app.services.binding_service.uuid4") as mock_uuid:
        mock_create_rev.return_value = uuid4()
        mock_uuid.return_value = uuid4()

        result = rechunk_document(
            session=session,
            current_user=user_id,
            kb_id=str(kb_id),
            document_id=str(doc_id),
            strategy="semantic",
            params={"max_chunk_size": 500},
        )

    assert "chunk_revision_id" in result
    assert "job_id" in result
    assert result["strategy"] == "semantic"
    assert result["params"] == {"max_chunk_size": 500}
    session.commit.assert_called_once()


def test_rechunk_default_strategy():
    """默认策略为 fixed_size。"""
    session = Mock()
    binding_id = uuid4()
    active_rev_id = uuid4()
    parse_rev_id = uuid4()
    doc_version_id = uuid4()
    version_id = uuid4()
    kb_id = uuid4()
    doc_id = uuid4()
    user_id = str(uuid4())

    mock_binding = MagicMock()
    mock_binding.mappings.return_value.first.return_value = _make_binding_row(
        binding_id, active_rev_id, version_id, kb_id, doc_id
    )

    mock_building = MagicMock()
    mock_building.mappings.return_value.first.return_value = None

    mock_active_rev = MagicMock()
    mock_active_rev.mappings.return_value.first.return_value = _make_active_rev(
        active_rev_id, parse_rev_id, doc_version_id
    )

    mock_kb_doc = MagicMock()
    mock_kb_doc.scalar.return_value = uuid4()

    session.execute.side_effect = [
        mock_binding, mock_building, mock_active_rev, mock_kb_doc, None, None,
    ]

    with patch("app.services.binding_service.create_chunk_revision") as mock_create_rev, \
         patch("app.services.binding_service.uuid4") as mock_uuid:
        mock_create_rev.return_value = uuid4()
        mock_uuid.return_value = uuid4()

        result = rechunk_document(
            session=session,
            current_user=user_id,
            kb_id=str(kb_id),
            document_id=str(doc_id),
        )

    assert result["strategy"] == "fixed_size"
    assert result["params"] == {}
