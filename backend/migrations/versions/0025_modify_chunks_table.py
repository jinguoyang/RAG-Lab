"""modify chunks table structure

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-21 12:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # 添加新字段
    op.add_column("chunks", sa.Column("binding_revision_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("chunks", sa.Column("parse_revision_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("chunks", sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("chunks", sa.Column("start_offset", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("end_offset", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("section_path", sa.String(length=255), nullable=True))
    op.add_column("chunks", sa.Column("heading", sa.String(length=255), nullable=True))
    op.add_column("chunks", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("chunks", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("chunks", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # 添加外键约束
    op.create_foreign_key("fk_chunks_binding_revision_id", "chunks", "binding_revisions", ["binding_revision_id"], ["binding_revision_id"])
    op.create_foreign_key("fk_chunks_parse_revision_id", "chunks", "parse_revisions", ["parse_revision_id"], ["parse_revision_id"])
    op.create_foreign_key("fk_chunks_document_version_id", "chunks", "document_versions", ["document_version_id"], ["version_id"])

    # 添加索引
    op.create_index("ix_chunks_binding_revision_id", "chunks", ["binding_revision_id"])
    op.create_index("ix_chunks_parse_revision_id", "chunks", ["parse_revision_id"])

def downgrade() -> None:
    # 删除索引
    op.drop_index("ix_chunks_parse_revision_id", table_name="chunks")
    op.drop_index("ix_chunks_binding_revision_id", table_name="chunks")

    # 删除外键约束
    op.drop_constraint("fk_chunks_document_version_id", "chunks", type_="foreignkey")
    op.drop_constraint("fk_chunks_parse_revision_id", "chunks", type_="foreignkey")
    op.drop_constraint("fk_chunks_binding_revision_id", "chunks", type_="foreignkey")

    # 删除字段
    op.drop_column("chunks", "deleted_at")
    op.drop_column("chunks", "retired_at")
    op.drop_column("chunks", "summary")
    op.drop_column("chunks", "heading")
    op.drop_column("chunks", "section_path")
    op.drop_column("chunks", "end_offset")
    op.drop_column("chunks", "start_offset")
    op.drop_column("chunks", "document_version_id")
    op.drop_column("chunks", "parse_revision_id")
    op.drop_column("chunks", "binding_revision_id")
