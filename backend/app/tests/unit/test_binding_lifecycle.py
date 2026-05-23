"""ChunkRevision 生命周期单元测试。"""
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

import pytest
from pydantic import ValidationError

from app.schemas.binding import RechunkRequest
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
    """测试创建 ChunkRevision"""
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


def test_to_binding_dto_uses_chunk_revision_params_when_binding_row_has_no_chunk_fields():
    """绑定表不存分块参数时，DTO 应从 ChunkRevision 参数回填。"""
    row = {
        "binding_id": uuid4(),
        "document_id": uuid4(),
        "kb_id": uuid4(),
        "version_id": uuid4(),
        "status": "processing",
        "chunk_count": 0,
        "active_chunk_revision_id": None,
        "chunk_revision_params": {"chunk_size": 900, "chunk_overlap": 120},
        "created_at": datetime.now(timezone.utc),
        "created_by": uuid4(),
    }

    dto = _to_binding_dto(row, doc_name="研发手册")

    assert dto.chunkSize == 900
    assert dto.chunkOverlap == 120


def test_rechunk_request_accepts_valid_fixed_size_params():
    """重分块请求只允许明确合法的固定长度参数进入队列。"""
    request = RechunkRequest(params={"chunk_size": 900, "chunk_overlap": 120})

    assert request.strategy == "fixed_size"
    assert request.params == {"chunk_size": 900, "chunk_overlap": 120}


@pytest.mark.parametrize(
    "payload",
    [
        {"strategy": "semantic", "params": {"chunk_size": 900, "chunk_overlap": 120}},
        {"params": {"chunk_size": 0, "chunk_overlap": 0}},
        {"params": {"chunk_size": 900, "chunk_overlap": 900}},
        {"params": {"chunk_size": 900, "chunk_overlap": -1}},
    ],
)
def test_rechunk_request_rejects_invalid_params(payload):
    """非法重分块参数应在 API 入参阶段失败，避免异步 Worker 才暴露错误。"""
    with pytest.raises(ValidationError):
        RechunkRequest(**payload)


def test_create_chunk_revision_with_created_by():
    """测试创建 ChunkRevision 时记录创建人"""
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
    """测试激活 ChunkRevision"""
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
    """测试激活不存在的 ChunkRevision"""
    session = Mock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    session.execute.return_value = mock_result

    with pytest.raises(BindingNotFoundError):
        activate_chunk_revision(session, uuid4())


def test_fail_chunk_revision():
    """测试标记 ChunkRevision 为失败"""
    session = Mock()
    binding_rev_id = uuid4()

    fail_chunk_revision(session, binding_rev_id)

    session.execute.assert_called_once()


def test_complete_chunk_revision_build():
    """测试完成构建时同步 ChunkRevision 与绑定摘要状态。"""
    session = Mock()
    binding_rev_id = uuid4()

    with patch("app.services.binding_service.activate_chunk_revision") as mock_activate:
        complete_chunk_revision_build(session, binding_rev_id, chunk_count=10)

        # 验证调用了 execute 更新 revision 与 binding 摘要，并激活 revision。
        assert session.execute.call_count == 2
        mock_activate.assert_called_once_with(session, binding_rev_id)
