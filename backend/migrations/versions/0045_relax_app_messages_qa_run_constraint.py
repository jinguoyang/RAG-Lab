"""relax qa_run_id constraints for external LLM API

Revision ID: 0045
Revises: 0044
Create Date: 2026-06-05
"""
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

# --- app_messages ---
_MSG_CONSTRAINT = "ck_app_messages_success_assistant_has_qa_run_id"
_MSG_TABLE = "app_messages"
_MSG_OLD = "role <> 'assistant' OR status <> 'success' OR qa_run_id IS NOT NULL"
_MSG_NEW = (
    "role <> 'assistant' OR status <> 'success' OR qa_run_id IS NOT NULL "
    "OR metadata->>'source' = 'external_llm_api'"
)

# --- app_invocations ---
_INV_CONSTRAINT = "ck_app_invocations_success_has_trace_refs"
_INV_TABLE = "app_invocations"
_INV_OLD = (
    "status <> 'success' "
    "OR (conversation_id IS NOT NULL AND message_id IS NOT NULL AND qa_run_id IS NOT NULL)"
)
_INV_NEW = (
    "status <> 'success' "
    "OR (conversation_id IS NOT NULL AND message_id IS NOT NULL AND qa_run_id IS NOT NULL) "
    "OR (conversation_id IS NOT NULL AND message_id IS NOT NULL AND request_summary->>'endpoint' IS NOT NULL)"
)


def upgrade() -> None:
    op.drop_constraint(_MSG_CONSTRAINT, _MSG_TABLE, type_="check")
    op.create_check_constraint(_MSG_CONSTRAINT, _MSG_TABLE, _MSG_NEW)

    op.drop_constraint(_INV_CONSTRAINT, _INV_TABLE, type_="check")
    op.create_check_constraint(_INV_CONSTRAINT, _INV_TABLE, _INV_NEW)


def downgrade() -> None:
    op.drop_constraint(_INV_CONSTRAINT, _INV_TABLE, type_="check")
    op.create_check_constraint(_INV_CONSTRAINT, _INV_TABLE, _INV_OLD)

    op.drop_constraint(_MSG_CONSTRAINT, _MSG_TABLE, type_="check")
    op.create_check_constraint(_MSG_CONSTRAINT, _MSG_TABLE, _MSG_OLD)
