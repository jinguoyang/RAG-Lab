from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from app.services.document_service import (
    _calculate_file_hash,
    _to_chunk_dto,
    check_file_hash_duplicate,
    create_parse_revision,
    list_chunks,
)
from app.tables import (
    chunk_revisions,
    chunks,
    document_kb_bindings,
    document_versions,
    documents,
    knowledge_bases,
)


def test_calculate_file_hash():
    """测试文件 hash 计算"""
    content = b"test content"
    hash1 = _calculate_file_hash(content)
    hash2 = _calculate_file_hash(content)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 hex digest length


def test_calculate_file_hash_different_content():
    """测试不同内容产生不同 hash"""
    hash1 = _calculate_file_hash(b"content 1")
    hash2 = _calculate_file_hash(b"content 2")
    assert hash1 != hash2


def test_calculate_file_hash_empty_content():
    """测试空内容产生有效 hash"""
    hash_val = _calculate_file_hash(b"")
    assert len(hash_val) == 64


def test_check_file_hash_duplicate_no_duplicate():
    """测试没有重复文件时返回 None"""
    session = Mock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = None
    session.execute.return_value = mock_result

    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is None


def test_check_file_hash_duplicate_found():
    """测试发现重复文件时返回信息"""
    from datetime import datetime, timezone

    session = Mock()
    mock_file = {
        "file_id": uuid4(),
        "file_name": "test.pdf",
        "created_at": datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc),
    }
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = mock_file
    session.execute.return_value = mock_result

    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is not None
    assert result["file_name"] == "test.pdf"
    assert result["file_id"] == mock_file["file_id"]
    assert result["created_at"] == "2026-05-21T10:00:00+00:00"


def test_check_file_hash_duplicate_found_null_created_at():
    """测试 created_at 为 None 时返回 None"""
    session = Mock()
    mock_file = {
        "file_id": uuid4(),
        "file_name": "test.pdf",
        "created_at": None,
    }
    mock_result = MagicMock()
    mock_result.mappings.return_value.first.return_value = mock_file
    session.execute.return_value = mock_result

    result = check_file_hash_duplicate(session, uuid4(), "abc123")
    assert result is not None
    assert result["created_at"] is None


def test_create_parse_revision():
    """测试创建 ParseRevision"""
    session = Mock()
    version_id = uuid4()

    with patch('app.services.document_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None

        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
            content_text="# Test Content",
            content_hash="abc123",
            parser_name="test_parser",
            parser_version="1.0",
        )

        assert result is not None
        mock_insert.assert_called_once()


def test_create_parse_revision_with_created_by():
    """测试创建 ParseRevision 时传入 created_by"""
    session = Mock()
    version_id = uuid4()
    user_id = uuid4()

    with patch('app.services.document_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None

        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
            content_text="# Test Content",
            parser_name="test_parser",
            parser_version="1.0",
            created_by=user_id,
        )

        assert result is not None
        mock_insert.assert_called_once()
        # Verify created_by was passed to values
        call_kwargs = mock_insert.return_value.values.call_args[1]
        assert call_kwargs["created_by"] == user_id


def test_create_parse_revision_default_parse_options():
    """测试 create_parse_revision 默认空 parse_options"""
    session = Mock()
    version_id = uuid4()

    with patch('app.services.document_service.insert') as mock_insert:
        mock_insert.return_value.values.return_value = None

        result = create_parse_revision(
            session=session,
            document_version_id=version_id,
            content_format="markdown",
        )

        assert result is not None
        call_kwargs = mock_insert.return_value.values.call_args[1]
        assert call_kwargs["parse_options"] == {}
        assert call_kwargs["status"] == "completed"


def test_to_chunk_dto_exposes_traceability_fields():
    """Chunk DTO 应暴露 ChunkRevision、ParseRevision 和正文位置回溯信息。"""
    now = datetime.now(timezone.utc)
    chunk_revision_id = uuid4()
    parse_revision_id = uuid4()
    document_version_id = uuid4()
    row = {
        "chunk_id": uuid4(),
        "version_id": uuid4(),
        "document_id": uuid4(),
        "kb_id": uuid4(),
        "chunk_index": 3,
        "page_no": 12,
        "section": "第二章",
        "content": "chunk content",
        "content_hash": "abc123",
        "token_count": 42,
        "status": "active",
        "metadata": {},
        "created_at": now,
        "chunk_revision_id": chunk_revision_id,
        "parse_revision_id": parse_revision_id,
        "document_version_id": document_version_id,
        "start_offset": 10,
        "end_offset": 22,
        "section_path": "第一部分/第二章",
        "heading": "第二章",
        "summary": "摘要",
    }

    dto = _to_chunk_dto(row)

    assert dto.chunkRevisionId == str(chunk_revision_id)
    assert dto.parseRevisionId == str(parse_revision_id)
    assert dto.documentVersionId == str(document_version_id)
    assert dto.startOffset == 10
    assert dto.endOffset == 22
    assert dto.sectionPath == "第一部分/第二章"
    assert dto.heading == "第二章"
    assert dto.summary == "摘要"


def test_list_chunks_filters_active_chunk_revision(db, admin_user):
    """知识库文档页只展示当前 active ChunkRevision 对应的 active Chunk。"""
    now = datetime.now(timezone.utc)
    kb_id = uuid4()
    owner_id = uuid4()
    kb_doc_id = uuid4()
    library_doc_id = uuid4()
    version_id = uuid4()
    binding_id = uuid4()
    active_chunk_revision_id = uuid4()
    retired_chunk_revision_id = uuid4()
    active_chunk_id = uuid4()
    retired_chunk_id = uuid4()

    db.execute(
        knowledge_bases.insert().values(
            kb_id=kb_id,
            name="测试知识库",
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
        documents.insert().values(
            document_id=kb_doc_id,
            kb_id=kb_id,
            library_id=None,
            owner_id=owner_id,
            name="绑定文档",
            source_type="library_bind",
            status="active",
            active_version_id=version_id,
            metadata={"library_document_id": str(library_doc_id)},
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
        )
    )
    db.execute(
        document_versions.insert().values(
            version_id=version_id,
            document_id=kb_doc_id,
            version_no=1,
            source_file_id=uuid4(),
            status="active",
            parse_status="success",
            dense_index_status="success",
            sparse_index_status="not_required",
            graph_index_status="not_required",
            retrieval_ready=True,
            chunk_count=2,
            token_count=20,
            metadata={"library_document_id": str(library_doc_id)},
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
        )
    )
    db.execute(
        document_kb_bindings.insert().values(
            binding_id=binding_id,
            document_id=library_doc_id,
            kb_id=kb_id,
            version_id=version_id,
            status="active",
            chunk_count=1,
            error_code=None,
            error_message=None,
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
            active_chunk_revision_id=active_chunk_revision_id,
        )
    )
    db.execute(
        chunk_revisions.insert(),
        [
            {
                "chunk_revision_id": active_chunk_revision_id,
                "binding_id": binding_id,
                "knowledge_base_id": kb_id,
                "document_id": library_doc_id,
                "document_version_id": version_id,
                "parse_revision_id": uuid4(),
                "status": "active",
                "chunk_count": 1,
                "index_status": None,
                "build_started_at": now,
                "build_finished_at": now,
                "activated_at": now,
                "retired_at": None,
                "deleted_at": None,
                "created_by": owner_id,
                "created_at": now,
            },
            {
                "chunk_revision_id": retired_chunk_revision_id,
                "binding_id": binding_id,
                "knowledge_base_id": kb_id,
                "document_id": library_doc_id,
                "document_version_id": version_id,
                "parse_revision_id": uuid4(),
                "status": "retired",
                "chunk_count": 1,
                "index_status": None,
                "build_started_at": now,
                "build_finished_at": now,
                "activated_at": now,
                "retired_at": now,
                "deleted_at": None,
                "created_by": owner_id,
                "created_at": now,
            },
        ],
    )
    base_chunk = {
        "version_id": version_id,
        "document_id": kb_doc_id,
        "kb_id": kb_id,
        "page_no": 1,
        "section": "概述",
        "content_hash": "hash",
        "token_count": 10,
        "status": "active",
        "metadata": {},
        "created_at": now,
        "parse_revision_id": uuid4(),
        "document_version_id": version_id,
        "start_offset": None,
        "end_offset": None,
        "section_path": "概述",
        "heading": "概述",
        "summary": None,
        "retired_at": None,
        "retired_by": None,
        "deleted_at": None,
        "deleted_by": None,
    }
    db.execute(
        chunks.insert(),
        [
            {
                **base_chunk,
                "chunk_id": active_chunk_id,
                "chunk_index": 1,
                "content": "active content",
                "chunk_revision_id": active_chunk_revision_id,
            },
            {
                **base_chunk,
                "chunk_id": retired_chunk_id,
                "chunk_index": 2,
                "content": "retired content",
                "chunk_revision_id": retired_chunk_revision_id,
            },
        ],
    )

    with patch("app.services.document_service.has_kb_permission", return_value=True):
        page = list_chunks(db, admin_user, kb_id, kb_doc_id, version_id, 1, 10)

    assert page is not None
    assert page.total == 1
    assert [item.chunkId for item in page.items] == [str(active_chunk_id)]
