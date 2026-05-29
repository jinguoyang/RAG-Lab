"""create training skill calls, progress records, answer records tables

Revision ID: 0040
Revises: 0039
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_skill_calls",
        sa.Column("skill_call_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("app_id", sa.String(length=36), nullable=True),
        sa.Column("skill_name", sa.String(length=64), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_training_skill_calls_app_id", "training_skill_calls", ["app_id"])
    op.create_index("ix_training_skill_calls_skill_name", "training_skill_calls", ["skill_name"])
    op.create_index("ix_training_skill_calls_created_at", "training_skill_calls", ["created_at"])

    op.create_table(
        "training_progress_records",
        sa.Column("progress_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("current_section_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_sections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_training_progress_session_app_user",
        "training_progress_records",
        ["session_id", "app_id", "end_user_id"],
    )
    op.create_index("ix_training_progress_app_id", "training_progress_records", ["app_id"])

    op.create_table(
        "training_answer_records",
        sa.Column("answer_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_training_answer_session_app", "training_answer_records", ["session_id", "app_id"])
    op.create_index("ix_training_answer_question_id", "training_answer_records", ["question_id"])
    op.create_index("ix_training_answer_app_id", "training_answer_records", ["app_id"])


def downgrade() -> None:
    op.drop_table("training_answer_records")
    op.drop_table("training_progress_records")
    op.drop_table("training_skill_calls")
