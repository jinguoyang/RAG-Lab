"""add active_parse_revision_id to document_versions

Revision ID: 0044
Revises: 0043
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add active_parse_revision_id column to document_versions."""
    op.add_column(
        "document_versions",
        sa.Column("active_parse_revision_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_versions_active_parse_revision_id",
        "document_versions",
        "parse_revisions",
        ["active_parse_revision_id"],
        ["parse_revision_id"],
    )


def downgrade() -> None:
    """Remove active_parse_revision_id column from document_versions."""
    op.drop_constraint(
        "fk_document_versions_active_parse_revision_id",
        "document_versions",
        type_="foreignkey",
    )
    op.drop_column("document_versions", "active_parse_revision_id")
