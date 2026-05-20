"""add library_id to documents

Revision ID: 0021_documents_library_id
Revises: 0020_library_member_bindings
Create Date: 2026-05-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0021_documents_library_id"
down_revision: str | None = "0020_library_member_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. documents 表新增 library_id
    op.add_column(
        "documents",
        sa.Column("library_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_library_id",
        "documents",
        "document_libraries",
        ["library_id"],
        ["library_id"],
    )
    op.create_index(
        "idx_documents_library_id",
        "documents",
        ["library_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 2. 数据迁移：为每个已有 owner_id 创建默认个人文档库
    op.execute("""
        INSERT INTO document_libraries (library_id, owner_id, name, visibility, status, created_at, updated_at)
        SELECT DISTINCT ON (owner_id)
            gen_random_uuid(), owner_id, '默认文档库', 'personal', 'active', now(), now()
        FROM documents
        WHERE owner_id IS NOT NULL AND deleted_at IS NULL
        ON CONFLICT DO NOTHING
    """)

    # 3. 将现有文档关联到其 owner 的默认文档库
    op.execute("""
        UPDATE documents d
        SET library_id = dl.library_id
        FROM document_libraries dl
        WHERE d.owner_id = dl.owner_id
          AND dl.name = '默认文档库'
          AND d.deleted_at IS NULL
          AND d.library_id IS NULL
    """)


def downgrade() -> None:
    op.drop_index("idx_documents_library_id", table_name="documents")
    op.drop_constraint("fk_documents_library_id", "documents", type_="foreignkey")
    op.drop_column("documents", "library_id")
