"""create document library tables

Revision ID: 0017_document_library
Revises: 0016_system_dictionary_tables
Create Date: 2026-05-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0017_document_library"
down_revision: str | None = "0016_system_dictionary_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Sprint 36: 添加文档库支持。

    1. documents 表新增 owner_id（文档归属用户）
    2. 新建 document_kb_bindings 表（文档与知识库多对多绑定）
    3. 新建 library_parse_jobs 表（文档库文本提取作业）
    """
    # --- documents: 新增 owner_id，kb_id 改为可空 ---
    op.alter_column("documents", "kb_id", nullable=True)
    op.add_column(
        "documents",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_owner_id",
        "documents",
        "users",
        ["owner_id"],
        ["user_id"],
    )
    op.create_index("idx_documents_owner_status_updated_at", "documents", ["owner_id", "status", "updated_at"])

    # 回填已有文档的 owner_id = created_by（历史兼容）
    op.execute("UPDATE documents SET owner_id = created_by WHERE owner_id IS NULL")

    # --- document_kb_bindings ---
    op.create_table(
        "document_kb_bindings",
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default=sa.text("900")),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default=sa.text("120")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'active', 'failed', 'disabled')",
            name="ck_document_kb_bindings_status",
        ),
        sa.CheckConstraint("chunk_size > 0", name="ck_document_kb_bindings_chunk_size"),
        sa.CheckConstraint("chunk_overlap >= 0", name="ck_document_kb_bindings_chunk_overlap"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_document_kb_bindings_chunk_count"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name="fk_document_kb_bindings_document_id"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_document_kb_bindings_kb_id"),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.version_id"], name="fk_document_kb_bindings_version_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_document_kb_bindings_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_document_kb_bindings_updated_by"),
    )
    op.create_index(
        "idx_document_kb_bindings_document_status",
        "document_kb_bindings",
        ["document_id", "status"],
    )
    op.create_index(
        "idx_document_kb_bindings_kb_status",
        "document_kb_bindings",
        ["kb_id", "status"],
    )
    op.create_index(
        "uk_document_kb_bindings_active",
        "document_kb_bindings",
        ["document_id", "kb_id", "version_id"],
        unique=True,
        postgresql_where=sa.text("status != 'disabled'"),
    )

    # --- library_parse_jobs ---
    op.create_table(
        "library_parse_jobs",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False, server_default=sa.text("'extract_text'")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "job_type IN ('extract_text', 'generate_preview', 'reparse_library')",
            name="ck_library_parse_jobs_job_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'success', 'failed', 'cancelled')",
            name="ck_library_parse_jobs_status",
        ),
        sa.CheckConstraint("progress >= 0 AND progress <= 100", name="ck_library_parse_jobs_progress"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name="fk_library_parse_jobs_document_id"),
        sa.ForeignKeyConstraint(["version_id"], ["document_versions.version_id"], name="fk_library_parse_jobs_version_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_library_parse_jobs_created_by"),
    )
    op.create_index(
        "idx_library_parse_jobs_document_created_at",
        "library_parse_jobs",
        ["document_id", "created_at"],
    )
    op.create_index(
        "idx_library_parse_jobs_status_created_at",
        "library_parse_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    """回滚文档库表和字段变更。"""
    op.drop_index("idx_library_parse_jobs_status_created_at", table_name="library_parse_jobs")
    op.drop_index("idx_library_parse_jobs_document_created_at", table_name="library_parse_jobs")
    op.drop_table("library_parse_jobs")

    op.drop_index("uk_document_kb_bindings_active", table_name="document_kb_bindings")
    op.drop_index("idx_document_kb_bindings_kb_status", table_name="document_kb_bindings")
    op.drop_index("idx_document_kb_bindings_document_status", table_name="document_kb_bindings")
    op.drop_table("document_kb_bindings")

    op.drop_index("idx_documents_owner_status_updated_at", table_name="documents")
    op.drop_constraint("fk_documents_owner_id", "documents", type_="foreignkey")
    op.drop_column("documents", "owner_id")
