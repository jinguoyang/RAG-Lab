"""add request_id to training_classroom_events

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_classroom_events",
        sa.Column("request_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_classroom_event_request_id",
        "training_classroom_events",
        ["session_id", "request_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_classroom_event_request_id", "training_classroom_events", type_="unique")
    op.drop_column("training_classroom_events", "request_id")
