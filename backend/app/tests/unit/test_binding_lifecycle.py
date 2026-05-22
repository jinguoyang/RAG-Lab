"""BindingRevision 生命周期单元测试。"""
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

import pytest

from app.services.binding_service import (
    BindingBuildInProgressError,
    BindingNotFoundError,
    _to_binding_dto,
    activate_chunk_revision,
    complete_chunk_revision_build,
    create_chunk_revision,
    fail_chunk_revision,
)


def test_create_chunk_revision():
    """测试创建 BindingRevision"""
    session = Mock()
    binding_id = uuid4()
    kb_id = uuid4()
    doc_id = uuid4()
    version_id = uuid4()
    parse_rev_id = uuid4()

    result = create_chunk_revision(
        session=session,
        binding_id=binding_id,
        knowledge_base_id=kb_id,
        document_id=doc_id,
        document_version_id=version_id,
        parse_revision_id=parse_rev_id,
    )

    assert result is not None
    session.execute.assert_called_once()


def test_to_binding_dto_exposes_active_revision_status():
    """绑定 DTO 应暴露 active ChunkRevision 状态，供前端展示三层链路。"""
    binding_id = uuid4()
    revision_id = uuid4()
    target_version_id = uuid4()
    row = {
        "binding_id": binding_id,
        "document_id": uuid4(),
        "kb_id": uuid4(),
        "version_id": uuid4(),
        "chunk_size": 900,
        "chunk_overlap": 120,
        "status": "processing",
        "chunk_count": 12,
        "error_code": None,
        "error_message": None,
        "active_chunk_revision_id": revision_id,
        "chunk_revision_status": "building",
        "chunk_revision_chunk_count": 0,
        "chunk_revision_version_id": target_version_id,
        "created_at": datetime.now(timezone.utc),
        "created_by": uuid4(),
    }

    dto = _to_binding_dto(row, doc_name="研发手册")

    assert dto.activeChunkRevisionId == str(revision_id)
    assert dto.chunkRevisionStatus == "building"
    assert dto.chunkRevisionChunkCount == 0
    assert dto.chunkRevisionVersionId == str(target_version_id)


def test_create_chunk_revision_with_created_by():
    """测试创建 BindingRevision 时记录创建人"""
    session = Mock()
    user_id = uuid4()

    result = create_chunk_revision(
        session=session,
        binding_id=uuid4(),
        knowledge_base_id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        parse_revision_id=uuid4(),
        created_by=user_id,
    )

    assert result is not None
    call_args = session.execute.call_args
    values = call_args[0][0].compile().params
    assert values["created_by"] == user_id


def test_activate_chunk_revision():
    """测试激活 BindingRevision"""
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

    # 查询当前/旧 revision，并更新 binding、旧 revision 与旧 Chunk 状态。
    assert session.execute.call_count >= 5


def test_activate_chunk_revision_not_found():
    """测试激活不存在的 BindingRevision"""
    session = Mock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    session.execute.return_value = mock_result

    with pytest.raises(BindingNotFoundError):
        activate_chunk_revision(session, uuid4())


def test_fail_chunk_revision():
    """测试标记 BindingRevision 为失败"""
    session = Mock()
    binding_rev_id = uuid4()

    fail_chunk_revision(session, binding_rev_id)

    session.execute.assert_called_once()


def test_complete_chunk_revision_build():
    """测试完成构建并激活"""
    session = Mock()
    binding_rev_id = uuid4()

    with patch("app.services.binding_service.activate_chunk_revision") as mock_activate:
        complete_chunk_revision_build(session, binding_rev_id, chunk_count=10)

        # 验证调用了 execute (更新状态) 和 activate_chunk_revision
        session.execute.assert_called_once()
        mock_activate.assert_called_once_with(session, binding_rev_id)
