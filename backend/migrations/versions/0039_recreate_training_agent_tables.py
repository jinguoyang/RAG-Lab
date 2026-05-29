"""recreate training agent tables

Revision ID: 0039
Revises: 0038
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_plans",
        sa.Column("plan_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("job_title", sa.String(length=256), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("ability_groups", sa.JSON(), nullable=False),
        sa.Column("documents", sa.JSON(), nullable=False),
        sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("recommend_reason", sa.Text(), nullable=True),
        sa.Column("reading_order", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=36), nullable=True),
    )
    op.create_table(
        "training_questions",
        sa.Column("question_id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.String(length=256), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("rubric", sa.JSON(), nullable=True),
        sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    )
    op.create_table(
        "training_classroom_sessions",
        sa.Column("session_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("current_state", sa.String(length=32), nullable=False),
        sa.Column("current_section_index", sa.Integer(), nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=128), nullable=True),
    )
    op.create_table(
        "training_classroom_messages",
        sa.Column("message_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("state_at_time", sa.String(length=32), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
    )
    op.create_table(
        "training_classroom_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result_state", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("training_classroom_events")
    op.drop_table("training_classroom_messages")
    op.drop_table("training_classroom_sessions")
    op.drop_table("training_questions")
    op.drop_table("training_plans")
