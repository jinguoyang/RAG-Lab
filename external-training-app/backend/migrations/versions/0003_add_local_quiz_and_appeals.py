"""add local post quizzes and question appeals

Revision ID: 0003_add_local_quiz_and_appeals
Revises: 0002
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_add_local_quiz_and_appeals"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 ex-app 本地题目异议与课后测验表。"""
    op.create_table(
        "training_question_appeals",
        sa.Column("appeal_id", sa.String(length=36), primary_key=True),
        sa.Column("question_id", sa.String(length=36), nullable=False),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("answer_record_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "training_post_quizzes",
        sa.Column("quiz_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("answers", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("results", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("score", sa.Numeric(10, 2), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="started"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """删除 ex-app 本地题目异议与课后测验表。"""
    op.drop_table("training_post_quizzes")
    op.drop_table("training_question_appeals")
