"""extend app invocation running status

Revision ID: 0015_app_invocation_running
Revises: 0014_rag_app_runtime_tables
Create Date: 2026-05-18 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0015_app_invocation_running"
down_revision: str | None = "0014_rag_app_runtime_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """允许 running 调用，并支持删除 API Key 后保留调用审计。"""
    op.drop_constraint("ck_app_invocations_status", "app_invocations", type_="check")
    op.create_check_constraint(
        "ck_app_invocations_status",
        "app_invocations",
        "status IN ('running', 'success', 'failed')",
    )
    op.drop_constraint("ck_app_invocations_success_has_trace_refs", "app_invocations", type_="check")
    op.create_check_constraint(
        "ck_app_invocations_success_has_trace_refs",
        "app_invocations",
        """
        status <> 'success'
        OR (
            conversation_id IS NOT NULL
            AND message_id IS NOT NULL
            AND qa_run_id IS NOT NULL
        )
        """,
    )


def downgrade() -> None:
    """回退前要求调用记录已无 running 状态，且成功记录仍有 api_key_id。"""
    op.drop_constraint("ck_app_invocations_success_has_trace_refs", "app_invocations", type_="check")
    op.create_check_constraint(
        "ck_app_invocations_success_has_trace_refs",
        "app_invocations",
        """
        status <> 'success'
        OR (
            api_key_id IS NOT NULL
            AND conversation_id IS NOT NULL
            AND message_id IS NOT NULL
            AND qa_run_id IS NOT NULL
        )
        """,
    )
    op.drop_constraint("ck_app_invocations_status", "app_invocations", type_="check")
    op.create_check_constraint(
        "ck_app_invocations_status",
        "app_invocations",
        "status IN ('success', 'failed')",
    )
