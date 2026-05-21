"""add missing indexes and audit fields to chunks table

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-21 13:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # 添加缺失的索引
    op.create_index("ix_chunks_document_version_id", "chunks", ["document_version_id"])

    # 添加缺失的审计字段
    op.add_column("chunks", sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("chunks", sa.Column("retired_by", postgresql.UUID(as_uuid=True), nullable=True))

def downgrade() -> None:
    # 删除审计字段
    op.drop_column("chunks", "retired_by")
    op.drop_column("chunks", "deleted_by")

    # 删除索引
    op.drop_index("ix_chunks_document_version_id", table_name="chunks")
