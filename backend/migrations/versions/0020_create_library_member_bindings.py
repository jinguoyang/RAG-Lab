"""create library_member_bindings table

Revision ID: 0020_library_member_bindings
Revises: 0019_document_libraries
Create Date: 2026-05-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0020_library_member_bindings"
down_revision: str | None = "0019_document_libraries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_member_bindings",
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("library_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "subject_type IN ('user', 'group')",
            name="ck_library_member_bindings_subject_type",
        ),
        sa.CheckConstraint(
            "permission_level IN ('read_only', 'document_manage')",
            name="ck_library_member_bindings_permission_level",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_library_member_bindings_status",
        ),
        sa.ForeignKeyConstraint(["library_id"], ["document_libraries.library_id"], name="fk_library_member_bindings_library_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_library_member_bindings_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_library_member_bindings_updated_by"),
    )
    op.create_index(
        "idx_library_member_bindings_library_status",
        "library_member_bindings",
        ["library_id", "status"],
    )
    op.create_index(
        "uk_library_member_bindings_active",
        "library_member_bindings",
        ["library_id", "subject_type", "subject_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uk_library_member_bindings_active", table_name="library_member_bindings")
    op.drop_index("idx_library_member_bindings_library_status", table_name="library_member_bindings")
    op.drop_table("library_member_bindings")
