"""create document ingest tables

Revision ID: 0003_create_document_ingest_tables
Revises: 0002_create_knowledge_bases
Create Date: 2026-04-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_create_document_ingest_tables"
down_revision: str | None = "0002_create_knowledge_bases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 E2 文档中心最小链路所需表，暂不引入 Chunk 与检索副本表。"""
    op.create_table(
        "stored_files",
        sa.Column("file_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("file_role", sa.String(length=32), nullable=False, server_default=sa.text("'source'")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("file_role IN ('source', 'parsed_artifact', 'attachment')", name="ck_stored_files_file_role"),
        sa.CheckConstraint("status IN ('active', 'deleted')", name="ck_stored_files_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_stored_files_created_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_stored_files_deleted_by"),
    )
    op.create_index("idx_stored_files_status_created_at", "stored_files", ["status", "created_at"])
    op.create_index("idx_stored_files_checksum", "stored_files", ["checksum"])

    op.create_table(
        "documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default=sa.text("'upload'")),
        sa.Column("security_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("active_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("source_type IN ('upload', 'sync', 'import')", name="ck_documents_source_type"),
        sa.CheckConstraint("status IN ('active', 'disabled', 'archived')", name="ck_documents_status"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_documents_kb_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_documents_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_documents_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_documents_deleted_by"),
    )
    op.create_index("idx_documents_kb_status_updated_at", "documents", ["kb_id", "status", "updated_at"])

    op.create_table(
        "document_versions",
        sa.Column("version_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'processing'")),
        sa.Column("parse_status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("dense_index_status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("sparse_index_status", sa.String(length=16), nullable=False, server_default=sa.text("'not_required'")),
        sa.Column("graph_index_status", sa.String(length=16), nullable=False, server_default=sa.text("'not_required'")),
        sa.Column("retrieval_ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('processing', 'active', 'inactive', 'failed')", name="ck_document_versions_status"),
        sa.CheckConstraint("parse_status IN ('pending', 'running', 'success', 'failed')", name="ck_document_versions_parse_status"),
        sa.CheckConstraint("dense_index_status IN ('not_required', 'pending', 'running', 'success', 'failed')", name="ck_document_versions_dense_index_status"),
        sa.CheckConstraint("sparse_index_status IN ('not_required', 'pending', 'running', 'success', 'failed')", name="ck_document_versions_sparse_index_status"),
        sa.CheckConstraint("graph_index_status IN ('not_required', 'pending', 'running', 'success', 'failed')", name="ck_document_versions_graph_index_status"),
        sa.CheckConstraint("version_no >= 1", name="ck_document_versions_version_no"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_document_versions_chunk_count"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name="fk_document_versions_document_id"),
        sa.ForeignKeyConstraint(["source_file_id"], ["stored_files.file_id"], name="fk_document_versions_source_file_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_document_versions_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_document_versions_updated_by"),
        sa.UniqueConstraint("document_id", "version_no", name="uk_document_versions_document_version_no"),
    )
    op.create_index(
        "uk_document_versions_active_per_document",
        "document_versions",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("idx_document_versions_document_status_created_at", "document_versions", ["document_id", "status", "created_at"])

    op.create_foreign_key(
        "fk_documents_active_version_id",
        "documents",
        "document_versions",
        ["active_version_id"],
        ["version_id"],
    )

    op.create_table(
        "ingest_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("retry_of_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("job_type IN ('upload_parse', 'reparse', 'rebuild_index', 'build_graph')", name="ck_ingest_jobs_job_type"),
        sa.CheckConstraint("status IN ('queued', 'running', 'success', 'failed', 'cancelled')", name="ck_ingest_jobs_status"),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_ingest_jobs_progress"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_ingest_jobs_kb_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name="fk_ingest_jobs_document_id"),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.version_id"], name="fk_ingest_jobs_version_id"),
        sa.ForeignKeyConstraint(["retry_of_job_id"], ["ingest_jobs.job_id"], name="fk_ingest_jobs_retry_of_job_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_ingest_jobs_created_by"),
    )
    op.create_index("idx_ingest_jobs_kb_status_created_at", "ingest_jobs", ["kb_id", "status", "created_at"])
    op.create_index("idx_ingest_jobs_document_created_at", "ingest_jobs", ["document_id", "created_at"])


def downgrade() -> None:
    """按外键依赖回滚文档中心最小链路表。"""
    op.drop_index("idx_ingest_jobs_document_created_at", table_name="ingest_jobs")
    op.drop_index("idx_ingest_jobs_kb_status_created_at", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")

    op.drop_constraint("fk_documents_active_version_id", "documents", type_="foreignkey")
    op.drop_index("idx_document_versions_document_status_created_at", table_name="document_versions")
    op.drop_index("uk_document_versions_active_per_document", table_name="document_versions")
    op.drop_table("document_versions")

    op.drop_index("idx_documents_kb_status_updated_at", table_name="documents")
    op.drop_table("documents")

    op.drop_index("idx_stored_files_checksum", table_name="stored_files")
    op.drop_index("idx_stored_files_status_created_at", table_name="stored_files")
    op.drop_table("stored_files")
