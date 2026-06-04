"""Library 服务单元测试。"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select

from app.services.library_service import (
    LibraryDocumentNotFoundError,
    LibraryPermissionError,
    _get_error_suggestion,
    batch_action,
    create_library_parse_revision_job,
    get_document_text,
    list_library_parse_revisions,
)
from app.tables import document_versions, documents, library_parse_jobs, parse_revisions, stored_files


class TestGetErrorSuggestion:
    """测试错误建议函数。"""

    def test_known_error_codes(self):
        assert "拆分" in _get_error_suggestion("PARSE_TIMEOUT")
        assert "格式" in _get_error_suggestion("UNSUPPORTED_FORMAT")
        assert "重新上传" in _get_error_suggestion("FILE_CORRUPTED")
        assert "稍后" in _get_error_suggestion("STORAGE_ERROR")

    def test_unknown_error_code(self):
        assert "管理员" in _get_error_suggestion("UNKNOWN")
        assert "管理员" in _get_error_suggestion("SOME_NEW_ERROR")


class TestBatchAction:
    """测试批量操作。"""

    def test_batch_action_with_invalid_ids(self, db, test_user):
        """无效 ID 应返回失败。"""
        result = batch_action(db, test_user, ["not-a-uuid"], "delete")
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "INVALID_ID"
        assert result["summary"]["total"] == 1
        assert result["summary"]["failed"] == 1

    def test_batch_action_with_nonexistent_docs(self, db, test_user):
        """不存在的文档应返回 NOT_FOUND。"""
        fake_id = str(uuid4())
        result = batch_action(db, test_user, [fake_id], "delete")
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "NOT_FOUND"


class TestLibraryParseRevisions:
    """测试文档库解析版本能力。"""

    def _seed_document_version(self, db, test_user):
        now = datetime.now(timezone.utc)
        owner_id = UUID(test_user.user.userId)
        document_id = uuid4()
        version_id = uuid4()
        file_id = uuid4()
        db.execute(
            insert(stored_files).values(
                file_id=file_id,
                bucket="local",
                object_key=f"test/{file_id}.txt",
                file_name="demo.txt",
                mime_type="text/plain",
                file_size=12,
                checksum="abc",
                file_role="source",
                status="active",
                created_at=now,
                created_by=owner_id,
            )
        )
        db.execute(
            insert(documents).values(
                document_id=document_id,
                kb_id=None,
                owner_id=owner_id,
                library_id=None,
                name="demo.txt",
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
            insert(document_versions).values(
                version_id=version_id,
                document_id=document_id,
                version_no=1,
                source_file_id=file_id,
                status="active",
                parse_status="success",
                dense_index_status="not_required",
                sparse_index_status="not_required",
                graph_index_status="not_required",
                retrieval_ready=False,
                token_count=None,
                metadata={},
                created_at=now,
                created_by=owner_id,
                updated_at=now,
                updated_by=owner_id,
            )
        )
        db.commit()
        return document_id, version_id

    def test_list_library_parse_revisions_returns_content_metadata(self, db, test_user):
        """解析版本列表应返回解析参数和正文长度，不包含分块语义。"""
        document_id, version_id = self._seed_document_version(db, test_user)
        parse_revision_id = uuid4()
        owner_id = UUID(test_user.user.userId)
        db.execute(
            insert(parse_revisions).values(
                parse_revision_id=parse_revision_id,
                document_version_id=version_id,
                content_format="markdown",
                content_text="hello library",
                content_hash="hash-1",
                parser_name="auto",
                parser_version="v1",
                parse_options={"ocrEnabled": False},
                status="success",
                created_at=datetime.now(timezone.utc),
                created_by=owner_id,
            )
        )
        db.commit()

        result = list_library_parse_revisions(db, test_user, document_id, version_id)

        assert len(result) == 1
        assert result[0].parseRevisionId == str(parse_revision_id)
        assert result[0].contentLength == len("hello library")
        assert result[0].parseOptions == {"ocrEnabled": False}

    def test_create_library_parse_revision_job_does_not_create_document_version(self, db, test_user, monkeypatch):
        """重解析应创建 ParseRevision 和解析任务，不新增源文件版本。"""
        document_id, version_id = self._seed_document_version(db, test_user)

        class _Task:
            @staticmethod
            def delay(_job_id):
                return None

        monkeypatch.setattr("app.worker.run_library_parse_task", _Task)

        result = create_library_parse_revision_job(
            db,
            test_user,
            document_id,
            version_id,
            parser_name="auto",
            parser_version=None,
            content_format="markdown",
            parse_options={"ocrEnabled": True},
            reason="manual_reparse",
        )

        version_count = db.execute(select(document_versions.c.version_id)).all()
        parse_revision_count = db.execute(select(parse_revisions.c.parse_revision_id)).all()
        job_count = db.execute(select(library_parse_jobs.c.job_id)).all()

        assert result["status"] == "queued"
        assert len(version_count) == 1
        assert len(parse_revision_count) == 1
        assert len(job_count) == 1

    def test_get_document_text_supports_parse_revision_from_inactive_version(self, db, test_user):
        """指定 parseRevisionId 时，应允许预览同一文档的非活跃源文件版本解析结果。"""
        document_id, active_version_id = self._seed_document_version(db, test_user)
        inactive_version_id = uuid4()
        inactive_parse_revision_id = uuid4()
        file_id = db.execute(
            select(document_versions.c.source_file_id)
            .where(document_versions.c.version_id == active_version_id)
        ).scalar_one()
        now = datetime.now(timezone.utc)
        db.execute(
            insert(document_versions).values(
                version_id=inactive_version_id,
                document_id=document_id,
                version_no=2,
                source_file_id=file_id,
                status="inactive",
                parse_status="success",
                dense_index_status="not_required",
                sparse_index_status="not_required",
                graph_index_status="not_required",
                retrieval_ready=False,
                token_count=None,
                metadata={},
                created_at=now,
                created_by=UUID(test_user.user.userId),
                updated_at=now,
                updated_by=UUID(test_user.user.userId),
            )
        )
        db.execute(
            insert(parse_revisions).values(
                parse_revision_id=inactive_parse_revision_id,
                document_version_id=inactive_version_id,
                content_format="markdown",
                content_text="inactive version text",
                content_hash="hash-2",
                parser_name="auto",
                parser_version="v1",
                parse_options={},
                status="success",
                created_at=now,
                created_by=UUID(test_user.user.userId),
            )
        )
        db.commit()

        result = get_document_text(db, test_user, document_id, "full", inactive_parse_revision_id)

        assert result.text == "inactive version text"
