"""add v17 qa run snapshots

Revision ID: 0013_add_v17_qa_run_snapshots
Revises: 0012_create_evaluation_runs
Create Date: 2026-04-30 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0013_add_v17_qa_run_snapshots"
down_revision: str | None = "0012_create_evaluation_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """为 QARun 固化配置快照，保证历史评估不受后续配置改动影响。"""
    op.add_column(
        "qa_runs",
        sa.Column("pipeline_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "qa_runs",
        sa.Column("node_param_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    """回滚 V1.7 QARun 快照字段。"""
    op.drop_column("qa_runs", "node_param_snapshot")
    op.drop_column("qa_runs", "pipeline_snapshot")
