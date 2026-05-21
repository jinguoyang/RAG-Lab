"""add source_status to qa_run_evidence

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-21 15:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("qa_run_evidence", sa.Column("source_status", sa.String(length=16), nullable=False, server_default="available"))
    op.create_index("ix_qa_run_evidence_source_status", "qa_run_evidence", ["source_status"])

def downgrade() -> None:
    op.drop_index("ix_qa_run_evidence_source_status", table_name="qa_run_evidence")
    op.drop_column("qa_run_evidence", "source_status")
