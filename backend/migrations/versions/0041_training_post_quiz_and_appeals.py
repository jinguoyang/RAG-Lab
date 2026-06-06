"""create training post quiz and appeal tables

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_post_quizzes",
        sa.Column("quiz_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_training_post_quiz_app_document", "training_post_quizzes", ["app_id", "document_id"])
    op.create_index("ix_training_post_quiz_session", "training_post_quizzes", ["session_id"])

    op.create_table(
        "training_question_appeals",
        sa.Column("appeal_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_training_question_appeal_app_question", "training_question_appeals", ["app_id", "question_id"])
    op.create_index("ix_training_question_appeal_status", "training_question_appeals", ["status"])


def downgrade() -> None:
    op.drop_table("training_question_appeals")
    op.drop_table("training_post_quizzes")
