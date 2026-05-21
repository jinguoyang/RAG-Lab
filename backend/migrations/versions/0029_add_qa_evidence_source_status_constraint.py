"""add source_status check constraint to qa_run_evidence

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-21 16:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_qa_run_evidence_source_status",
        "qa_run_evidence",
        "source_status IN ('available', 'source_deleted')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_qa_run_evidence_source_status", "qa_run_evidence", type_="check")
