"""create parse_revisions table

Revision ID: 0023
Revises: 0022_library_version_mgmt
Create Date: 2026-05-21 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0023"
down_revision: str | None = "0022_library_version_mgmt"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "parse_revisions",
        sa.Column("parse_revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_format", sa.String(length=16), nullable=False),
        sa.Column("content_object_key", sa.String(length=512), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("parser_name", sa.String(length=64), nullable=True),
        sa.Column("parser_version", sa.String(length=32), nullable=True),
        sa.Column("parse_options", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.version_id"],
            name="fk_parse_revisions_document_version_id",
        ),
    )
    op.create_index(
        "ix_parse_revisions_document_version_id",
        "parse_revisions",
        ["document_version_id"],
    )
    op.create_index(
        "ix_parse_revisions_status",
        "parse_revisions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_parse_revisions_status", table_name="parse_revisions")
    op.drop_index("ix_parse_revisions_document_version_id", table_name="parse_revisions")
    op.drop_table("parse_revisions")
