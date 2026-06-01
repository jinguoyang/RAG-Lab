"""add runtime_version to training_classroom_sessions

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_classroom_sessions",
        sa.Column("runtime_version", sa.String(length=32), nullable=False, server_default="legacy_v1"),
    )


def downgrade() -> None:
    op.drop_column("training_classroom_sessions", "runtime_version")
