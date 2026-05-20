"""create document_libraries table

Revision ID: 0019_document_libraries
Revises: 0018_library_perms
Create Date: 2026-05-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0019_document_libraries"
down_revision: str | None = "0018_library_perms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_libraries",
        sa.Column("library_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default=sa.text("'personal'")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "visibility IN ('public', 'personal', 'partial')",
            name="ck_document_libraries_visibility",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'archived')",
            name="ck_document_libraries_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.user_id"], name="fk_document_libraries_owner_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_document_libraries_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_document_libraries_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_document_libraries_deleted_by"),
    )
    op.create_index(
        "idx_document_libraries_owner_status",
        "document_libraries",
        ["owner_id", "status"],
    )
    op.create_index(
        "idx_document_libraries_visibility_status",
        "document_libraries",
        ["visibility", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_document_libraries_visibility_status", table_name="document_libraries")
    op.drop_index("idx_document_libraries_owner_status", table_name="document_libraries")
    op.drop_table("document_libraries")
