"""create evaluation samples

Revision ID: 0011_create_evaluation_samples
Revises: 0010_epic7_document_lifecycle
Create Date: 2026-04-28 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011_create_evaluation_samples"
down_revision: str | None = "0010_epic7_document_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 E8 评估样本表，并允许 QA 候选来源记录 PostgreSQL 回表证据。"""
    op.drop_constraint("ck_qa_run_candidates_source_type", "qa_run_candidates", type_="check")
    op.create_check_constraint(
        "ck_qa_run_candidates_source_type",
        "qa_run_candidates",
        "source_type IN ('dense', 'sparse', 'graph', 'mock', 'postgres')",
    )

    op.create_table(
        "evaluation_samples",
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("expected_evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_evaluation_samples_status"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_evaluation_samples_kb_id"),
        sa.ForeignKeyConstraint(["source_run_id"], ["qa_runs.run_id"], name="fk_evaluation_samples_source_run_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_evaluation_samples_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_evaluation_samples_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_evaluation_samples_deleted_by"),
    )
    op.create_index("idx_evaluation_samples_kb_status_created_at", "evaluation_samples", ["kb_id", "status", "created_at"])
    op.create_index("idx_evaluation_samples_source_run", "evaluation_samples", ["source_run_id"])


def downgrade() -> None:
    """回滚评估样本表，并恢复 E4 候选来源约束。"""
    op.drop_index("idx_evaluation_samples_source_run", table_name="evaluation_samples")
    op.drop_index("idx_evaluation_samples_kb_status_created_at", table_name="evaluation_samples")
    op.drop_table("evaluation_samples")

    op.drop_constraint("ck_qa_run_candidates_source_type", "qa_run_candidates", type_="check")
    op.create_check_constraint(
        "ck_qa_run_candidates_source_type",
        "qa_run_candidates",
        "source_type IN ('dense', 'sparse', 'graph', 'mock')",
    )
