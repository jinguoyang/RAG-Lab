"""数据迁移集成测试：验证三层架构新表和字段。"""

from uuid import uuid4

import pytest
from sqlalchemy import text


class TestParseRevisionsCreation:
    """验证 parse_revisions 表创建和插入。"""

    def test_parse_revisions_creation(self, db):
        """插入一条 parse_revision 并验证它存在。"""
        parse_rev_id = str(uuid4())
        doc_version_id = str(uuid4())

        db.execute(
            text(
                """
                INSERT INTO parse_revisions
                    (parse_revision_id, document_version_id, content_format, status, created_at, parse_options)
                VALUES
                    (:id, :doc_ver_id, 'markdown', 'active', datetime('now'), '{}')
                """
            ),
            {"id": parse_rev_id, "doc_ver_id": doc_version_id},
        )
        db.flush()

        row = db.execute(
            text("SELECT parse_revision_id, document_version_id, content_format, status FROM parse_revisions WHERE parse_revision_id = :id"),
            {"id": parse_rev_id},
        ).fetchone()

        assert row is not None
        assert str(row[0]) == parse_rev_id
        assert str(row[1]) == doc_version_id
        assert row[2] == "markdown"
        assert row[3] == "active"


class TestChunkRevisionsCreation:
    """验证 chunk_revisions 表创建和插入。"""

    def test_chunk_revisions_creation(self, db):
        """插入一条 binding_revision 并验证它存在。"""
        binding_rev_id = str(uuid4())
        binding_id = str(uuid4())
        kb_id = str(uuid4())
        document_id = str(uuid4())
        doc_version_id = str(uuid4())
        parse_rev_id = str(uuid4())

        db.execute(
            text(
                """
                INSERT INTO parse_revisions
                    (parse_revision_id, document_version_id, content_format, status, created_at, parse_options)
                VALUES
                    (:parse_id, :doc_ver_id, 'markdown', 'active', datetime('now'), '{}')
                """
            ),
            {"parse_id": parse_rev_id, "doc_ver_id": doc_version_id},
        )

        db.execute(
            text(
                """
                INSERT INTO chunk_revisions
                    (chunk_revision_id, binding_id, knowledge_base_id, document_id,
                     document_version_id, parse_revision_id, status, chunk_count, created_at)
                VALUES
                    (:bind_rev_id, :binding_id, :kb_id, :doc_id,
                     :doc_ver_id, :parse_id, 'active', 0, datetime('now'))
                """
            ),
            {
                "bind_rev_id": binding_rev_id,
                "binding_id": binding_id,
                "kb_id": kb_id,
                "doc_id": document_id,
                "doc_ver_id": doc_version_id,
                "parse_id": parse_rev_id,
            },
        )
        db.flush()

        row = db.execute(
            text(
                """
                SELECT chunk_revision_id, binding_id, knowledge_base_id,
                       document_id, document_version_id, parse_revision_id, status
                FROM chunk_revisions
                WHERE chunk_revision_id = :id
                """
            ),
            {"id": binding_rev_id},
        ).fetchone()

        assert row is not None
        assert str(row[0]) == binding_rev_id
        assert str(row[1]) == binding_id
        assert str(row[2]) == kb_id
        assert str(row[3]) == document_id
        assert str(row[4]) == doc_version_id
        assert str(row[5]) == parse_rev_id
        assert row[6] == "active"


class TestChunksTableMigration:
    """验证 chunks 表新增字段。"""

    def test_chunks_table_migration(self, db):
        """插入一条带有新字段的 chunk 并验证。"""
        chunk_id = str(uuid4())
        version_id = str(uuid4())
        document_id = str(uuid4())
        kb_id = str(uuid4())
        binding_rev_id = str(uuid4())
        parse_rev_id = str(uuid4())
        doc_version_id = str(uuid4())

        db.execute(
            text(
                """
                INSERT INTO chunks
                    (chunk_id, version_id, document_id, kb_id, chunk_index,
                     content, security_level, status, metadata, created_at,
                     chunk_revision_id, parse_revision_id, document_version_id)
                VALUES
                    (:chunk_id, :version_id, :doc_id, :kb_id, 0,
                     'test content', 'internal', 'active', '{}', datetime('now'),
                     :bind_rev_id, :parse_rev_id, :doc_ver_id)
                """
            ),
            {
                "chunk_id": chunk_id,
                "version_id": version_id,
                "doc_id": document_id,
                "kb_id": kb_id,
                "bind_rev_id": binding_rev_id,
                "parse_rev_id": parse_rev_id,
                "doc_ver_id": doc_version_id,
            },
        )
        db.flush()

        row = db.execute(
            text(
                """
                SELECT chunk_id, chunk_revision_id, parse_revision_id, document_version_id
                FROM chunks
                WHERE chunk_id = :id
                """
            ),
            {"id": chunk_id},
        ).fetchone()

        assert row is not None
        assert str(row[0]) == chunk_id
        assert str(row[1]) == binding_rev_id
        assert str(row[2]) == parse_rev_id
        assert str(row[3]) == doc_version_id


class TestDataIntegrityAfterMigration:
    """验证完整数据链的 JOIN 完整性。"""

    def test_data_integrity_after_migration(self, db):
        """插入完整数据链 (parse_revision -> binding_revision -> chunk) 并验证 JOIN 关系。"""
        parse_rev_id = str(uuid4())
        binding_rev_id = str(uuid4())
        binding_id = str(uuid4())
        kb_id = str(uuid4())
        document_id = str(uuid4())
        doc_version_id = str(uuid4())
        chunk_id = str(uuid4())
        version_id = str(uuid4())

        # 1. 插入 parse_revision
        db.execute(
            text(
                """
                INSERT INTO parse_revisions
                    (parse_revision_id, document_version_id, content_format, status, created_at, parse_options)
                VALUES
                    (:id, :doc_ver_id, 'markdown', 'active', datetime('now'), '{}')
                """
            ),
            {"id": parse_rev_id, "doc_ver_id": doc_version_id},
        )

        # 2. 插入 binding_revision（引用 parse_revision）
        db.execute(
            text(
                """
                INSERT INTO chunk_revisions
                    (chunk_revision_id, binding_id, knowledge_base_id, document_id,
                     document_version_id, parse_revision_id, status, chunk_count, created_at)
                VALUES
                    (:bind_rev_id, :binding_id, :kb_id, :doc_id,
                     :doc_ver_id, :parse_id, 'active', 1, datetime('now'))
                """
            ),
            {
                "bind_rev_id": binding_rev_id,
                "binding_id": binding_id,
                "kb_id": kb_id,
                "doc_id": document_id,
                "doc_ver_id": doc_version_id,
                "parse_id": parse_rev_id,
            },
        )

        # 3. 插入 chunk（引用 binding_revision 和 parse_revision）
        db.execute(
            text(
                """
                INSERT INTO chunks
                    (chunk_id, version_id, document_id, kb_id, chunk_index,
                     content, security_level, status, metadata, created_at,
                     chunk_revision_id, parse_revision_id, document_version_id)
                VALUES
                    (:chunk_id, :version_id, :doc_id, :kb_id, 0,
                     'integrity test content', 'internal', 'active', '{}', datetime('now'),
                     :bind_rev_id, :parse_rev_id, :doc_ver_id)
                """
            ),
            {
                "chunk_id": chunk_id,
                "version_id": version_id,
                "doc_id": document_id,
                "kb_id": kb_id,
                "bind_rev_id": binding_rev_id,
                "parse_rev_id": parse_rev_id,
                "doc_ver_id": doc_version_id,
            },
        )
        db.flush()

        # 验证 JOIN：chunk -> binding_revision -> parse_revision
        row = db.execute(
            text(
                """
                SELECT
                    c.chunk_id,
                    c.chunk_revision_id,
                    c.parse_revision_id,
                    br.chunk_revision_id AS br_id,
                    br.parse_revision_id AS br_parse_rev_id,
                    pr.parse_revision_id AS pr_id
                FROM chunks c
                JOIN chunk_revisions br ON c.chunk_revision_id = br.chunk_revision_id
                JOIN parse_revisions pr ON c.parse_revision_id = pr.parse_revision_id
                WHERE c.chunk_id = :chunk_id
                """
            ),
            {"chunk_id": chunk_id},
        ).fetchone()

        assert row is not None, "JOIN 查询应返回结果"
        assert str(row[0]) == chunk_id
        assert str(row[1]) == binding_rev_id
        assert str(row[2]) == parse_rev_id
        assert str(row[3]) == binding_rev_id
        assert str(row[4]) == parse_rev_id
        assert str(row[5]) == parse_rev_id
