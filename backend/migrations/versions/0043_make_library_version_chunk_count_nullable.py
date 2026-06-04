"""make document_versions.chunk_count nullable for library versions

Revision ID: 0043
Revises: 0042
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Allow source-library document versions to omit KB-only chunk counts."""
    op.alter_column(
        "document_versions",
        "chunk_count",
        existing_type=sa.Integer(),
        nullable=True,
        server_default=None,
        existing_server_default=sa.text("0"),
    )
    op.execute(
        """
        UPDATE document_versions AS dv
        SET chunk_count = NULL
        FROM documents AS d
        WHERE d.document_id = dv.document_id
          AND d.library_id IS NOT NULL
          AND d.kb_id IS NULL
        """
    )


def downgrade() -> None:
    """Restore the old NOT NULL shape after normalizing omitted counts to 0."""
    op.execute("UPDATE document_versions SET chunk_count = 0 WHERE chunk_count IS NULL")
    op.alter_column(
        "document_versions",
        "chunk_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
