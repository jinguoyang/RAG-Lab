"""create epic7 document lifecycle tables

Revision ID: 0010_epic7_document_lifecycle
Revises: 0009_create_chunk_access_filters
Create Date: 2026-04-27 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010_epic7_document_lifecycle"
down_revision: str | None = "0009_create_chunk_access_filters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """补齐 E7 Chunk 真值、索引同步状态和文档生命周期审计表。"""
    op.create_table(
        "audit_logs",
        sa.Column("audit_log_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"], name="fk_audit_logs_actor_id"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_audit_logs_kb_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name="fk_audit_logs_document_id"),
    )
    op.create_index("idx_audit_logs_resource_created_at", "audit_logs", ["resource_type", "resource_id", "created_at"])
    op.create_index("idx_audit_logs_kb_created_at", "audit_logs", ["kb_id", "created_at"])

    op.create_table(
        "chunks",
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("security_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("chunk_index >= 1", name="ck_chunks_chunk_index"),
        sa.CheckConstraint("token_count IS NULL OR token_count >= 0", name="ck_chunks_token_count"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'deleted')", name="ck_chunks_status"),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.version_id"], name="fk_chunks_version_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name="fk_chunks_document_id"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_chunks_kb_id"),
        sa.UniqueConstraint("version_id", "chunk_index", name="uk_chunks_version_chunk_index"),
    )
    op.create_index("idx_chunks_kb_version_status", "chunks", ["kb_id", "version_id", "status", "chunk_index"])
    op.create_index("idx_chunks_document_version", "chunks", ["document_id", "version_id"])
    op.create_index("idx_chunks_security_level", "chunks", ["security_level"])

    op.create_foreign_key(
        "fk_chunk_access_filters_chunk_id",
        "chunk_access_filters",
        "chunks",
        ["chunk_id"],
        ["chunk_id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "index_sync_jobs",
        sa.Column("sync_job_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_store", sa.String(length=32), nullable=False),
        sa.Column("sync_type", sa.String(length=32), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("required_for_activation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("target_store IN ('milvus', 'opensearch', 'neo4j')", name="ck_index_sync_jobs_target_store"),
        sa.CheckConstraint("sync_type IN ('upsert', 'delete', 'rebuild')", name="ck_index_sync_jobs_sync_type"),
        sa.CheckConstraint("status IN ('queued', 'running', 'success', 'failed', 'cancelled')", name="ck_index_sync_jobs_status"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_index_sync_jobs_kb_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_index_sync_jobs_created_by"),
    )
    op.create_index("idx_index_sync_jobs_kb_target_status", "index_sync_jobs", ["kb_id", "target_store", "status", "created_at"])
    op.create_index("idx_index_sync_jobs_scope", "index_sync_jobs", ["scope"], postgresql_using="gin")

    op.create_table(
        "index_sync_records",
        sa.Column("sync_record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sync_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_store", sa.String(length=32), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("target_store IN ('milvus', 'opensearch', 'neo4j')", name="ck_index_sync_records_target_store"),
        sa.CheckConstraint("resource_type IN ('chunk', 'graph_snapshot')", name="ck_index_sync_records_resource_type"),
        sa.CheckConstraint("operation IN ('upsert', 'delete')", name="ck_index_sync_records_operation"),
        sa.CheckConstraint("status IN ('success', 'failed', 'skipped')", name="ck_index_sync_records_status"),
        sa.ForeignKeyConstraint(
            ["sync_job_id"],
            ["index_sync_jobs.sync_job_id"],
            name="fk_index_sync_records_sync_job_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_index_sync_records_job_status", "index_sync_records", ["sync_job_id", "status"])
    op.create_index("idx_index_sync_records_resource", "index_sync_records", ["resource_type", "resource_id"])


def downgrade() -> None:
    """按依赖顺序回滚 E7 文档生命周期表。"""
    op.drop_index("idx_index_sync_records_resource", table_name="index_sync_records")
    op.drop_index("idx_index_sync_records_job_status", table_name="index_sync_records")
    op.drop_table("index_sync_records")

    op.drop_index("idx_index_sync_jobs_scope", table_name="index_sync_jobs")
    op.drop_index("idx_index_sync_jobs_kb_target_status", table_name="index_sync_jobs")
    op.drop_table("index_sync_jobs")

    op.drop_constraint("fk_chunk_access_filters_chunk_id", "chunk_access_filters", type_="foreignkey")
    op.drop_index("idx_chunks_security_level", table_name="chunks")
    op.drop_index("idx_chunks_document_version", table_name="chunks")
    op.drop_index("idx_chunks_kb_version_status", table_name="chunks")
    op.drop_table("chunks")

    op.drop_index("idx_audit_logs_kb_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
