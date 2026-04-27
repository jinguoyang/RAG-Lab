"""create chunk access filter table

Revision ID: 0009_create_chunk_access_filters
Revises: 0008_create_permission_tables
Create Date: 2026-04-27 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009_create_chunk_access_filters"
down_revision: str | None = "0008_create_permission_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 Chunk 访问过滤摘要表；Chunk 真值表在 E7 落地后再补外键约束。"""
    op.create_table(
        "chunk_access_filters",
        sa.Column("access_filter_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_code", sa.String(length=64), nullable=False),
        sa.Column("allow_subject_keys", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("deny_subject_keys", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("security_level", sa.String(length=32), nullable=False),
        sa.Column("document_status", sa.String(length=16), nullable=False),
        sa.Column("version_status", sa.String(length=16), nullable=False),
        sa.Column("chunk_status", sa.String(length=16), nullable=False),
        sa.Column("filter_hash", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_chunk_access_filters_kb_id"),
        sa.ForeignKeyConstraint(["permission_code"], ["permissions.permission_code"], name="fk_chunk_access_filters_permission_code"),
    )
    op.create_index("idx_chunk_access_filters_chunk_permission", "chunk_access_filters", ["chunk_id", "permission_code"])
    op.create_index("idx_chunk_access_filters_kb_hash", "chunk_access_filters", ["kb_id", "filter_hash"])


def downgrade() -> None:
    """回滚 Chunk 访问过滤摘要表。"""
    op.drop_index("idx_chunk_access_filters_kb_hash", table_name="chunk_access_filters")
    op.drop_index("idx_chunk_access_filters_chunk_permission", table_name="chunk_access_filters")
    op.drop_table("chunk_access_filters")
