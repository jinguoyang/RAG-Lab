"""add training domain tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop old proxy tables
    op.drop_table("training_class_messages")
    op.drop_table("training_class_sessions")

    # Create classroom tables (from platform migration 0035)
    op.create_table(
        "training_classroom_sessions",
        sa.Column("session_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("current_state", sa.String(length=32), nullable=False, server_default="INIT"),
        sa.Column("current_section_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=36), nullable=True),
    )

    op.create_table(
        "training_classroom_messages",
        sa.Column("message_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("state_at_time", sa.String(length=32), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
    )

    op.create_table(
        "training_classroom_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("result_state", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="processed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
    )

    # Create plans table (from platform migration 0036)
    op.create_table(
        "training_plans",
        sa.Column("plan_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("job_title", sa.String(length=256), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("ability_groups", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("documents", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("recommend_reason", sa.Text(), nullable=True),
        sa.Column("reading_order", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=36), nullable=True),
    )

    # Create questions table (from platform migration 0037)
    op.create_table(
        "training_questions",
        sa.Column("question_id", sa.String(length=36), primary_key=True),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False, server_default="practice"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("correct_answer", sa.String(length=256), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("rubric", sa.JSON(), nullable=True),
        sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("training_questions")
    op.drop_table("training_plans")
    op.drop_table("training_classroom_events")
    op.drop_table("training_classroom_messages")
    op.drop_table("training_classroom_sessions")

    # Recreate old proxy tables
    op.create_table(
        "training_class_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_user_id", sa.String(length=36), nullable=False),
        sa.Column("platform_session_id", sa.String(length=36), nullable=True),
        sa.Column("platform_plan_id", sa.String(length=36), nullable=True),
        sa.Column("current_state", sa.String(length=32), nullable=False, server_default="INIT"),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "training_class_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("platform_message_id", sa.String(length=36), nullable=True),
        sa.Column("ui_actions_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
