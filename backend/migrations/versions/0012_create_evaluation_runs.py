"""create evaluation runs

Revision ID: 0012_create_evaluation_runs
Revises: 0011_create_evaluation_samples
Create Date: 2026-04-29 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012_create_evaluation_runs"
down_revision: str | None = "0011_create_evaluation_samples"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 V1.1 评估运行与评估结果表。"""
    op.create_table(
        "evaluation_runs",
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("total_samples", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("passed_samples", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_samples", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cancelled_samples", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'success', 'failed', 'cancelled')",
            name="ck_evaluation_runs_status",
        ),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_evaluation_runs_kb_id"),
        sa.ForeignKeyConstraint(
            ["config_revision_id"],
            ["config_revisions.config_revision_id"],
            name="fk_evaluation_runs_config_revision_id",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_evaluation_runs_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_evaluation_runs_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_evaluation_runs_deleted_by"),
    )
    op.create_index("idx_evaluation_runs_kb_created_at", "evaluation_runs", ["kb_id", "created_at"])
    op.create_index("idx_evaluation_runs_kb_status", "evaluation_runs", ["kb_id", "status"])

    op.create_table(
        "evaluation_results",
        sa.Column("evaluation_result_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actual_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("actual_answer", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.String(length=128), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'cancelled')",
            name="ck_evaluation_results_status",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation_runs.evaluation_run_id"],
            name="fk_evaluation_results_evaluation_run_id",
        ),
        sa.ForeignKeyConstraint(["sample_id"], ["evaluation_samples.sample_id"], name="fk_evaluation_results_sample_id"),
        sa.ForeignKeyConstraint(["source_run_id"], ["qa_runs.run_id"], name="fk_evaluation_results_source_run_id"),
        sa.ForeignKeyConstraint(["actual_run_id"], ["qa_runs.run_id"], name="fk_evaluation_results_actual_run_id"),
    )
    op.create_index(
        "idx_evaluation_results_run_status",
        "evaluation_results",
        ["evaluation_run_id", "status", "created_at"],
    )
    op.create_index("idx_evaluation_results_sample", "evaluation_results", ["sample_id"])


def downgrade() -> None:
    """回滚 V1.1 评估运行与评估结果表。"""
    op.drop_index("idx_evaluation_results_sample", table_name="evaluation_results")
    op.drop_index("idx_evaluation_results_run_status", table_name="evaluation_results")
    op.drop_table("evaluation_results")

    op.drop_index("idx_evaluation_runs_kb_status", table_name="evaluation_runs")
    op.drop_index("idx_evaluation_runs_kb_created_at", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
