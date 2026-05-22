"""drop library visibility column

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_document_libraries_visibility_status", table_name="document_libraries")
    op.drop_constraint("ck_document_libraries_visibility", "document_libraries", type_="check")
    op.drop_column("document_libraries", "visibility")


def downgrade() -> None:
    op.add_column(
        "document_libraries",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default=sa.text("'personal'")),
    )
    op.create_check_constraint(
        "ck_document_libraries_visibility",
        "document_libraries",
        "visibility IN ('public', 'personal', 'partial')",
    )
    op.create_index(
        "idx_document_libraries_visibility_status",
        "document_libraries",
        ["visibility", "status"],
    )
