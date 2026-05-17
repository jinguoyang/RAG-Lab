"""create rag app runtime tables

Revision ID: 0014_rag_app_runtime_tables
Revises: 0013_add_v17_qa_run_snapshots
Create Date: 2026-05-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0014_rag_app_runtime_tables"
down_revision: str | None = "0013_add_v17_qa_run_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 RAG App 运行时表，支撑外部调用回溯到 QARun。"""
    op.create_table(
        "rag_apps",
        sa.Column("app_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("default_config_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("output_policy", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled', 'archived')", name="ck_rag_apps_status"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_rag_apps_kb_id"),
        sa.ForeignKeyConstraint(
            ["default_config_revision_id"],
            ["config_revisions.config_revision_id"],
            name="fk_rag_apps_default_config_revision_id",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_rag_apps_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_rag_apps_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_rag_apps_deleted_by"),
    )
    op.create_index("idx_rag_apps_kb_status_created_at", "rag_apps", ["kb_id", "status", "created_at"])

    op.create_table(
        "rag_app_api_keys",
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_rag_app_api_keys_status"),
        sa.ForeignKeyConstraint(["app_id"], ["rag_apps.app_id"], name="fk_rag_app_api_keys_app_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_rag_app_api_keys_created_by"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.user_id"], name="fk_rag_app_api_keys_revoked_by"),
    )
    op.create_index("uk_rag_app_api_keys_key_hash", "rag_app_api_keys", ["key_hash"], unique=True)

    op.create_table(
        "app_conversations",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("end_user_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_app_conversations_status"),
        sa.ForeignKeyConstraint(["app_id"], ["rag_apps.app_id"], name="fk_app_conversations_app_id"),
    )
    op.create_index(
        "idx_app_conversations_app_end_user_updated_at",
        "app_conversations",
        ["app_id", "end_user_id", "updated_at"],
    )

    op.create_table(
        "app_messages",
        sa.Column("message_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("qa_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'success'")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_app_messages_role"),
        sa.CheckConstraint("status IN ('success', 'failed')", name="ck_app_messages_status"),
        sa.CheckConstraint(
            "role <> 'assistant' OR status <> 'success' OR qa_run_id IS NOT NULL",
            name="ck_app_messages_success_assistant_has_qa_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["app_conversations.conversation_id"],
            name="fk_app_messages_conversation_id",
        ),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.run_id"], name="fk_app_messages_qa_run_id"),
    )
    op.create_index("idx_app_messages_conversation_created_at", "app_messages", ["conversation_id", "created_at"])

    op.create_table(
        "app_invocations",
        sa.Column("invocation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("qa_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("request_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('success', 'failed')", name="ck_app_invocations_status"),
        sa.CheckConstraint("latency_ms IS NULL OR latency_ms >= 0", name="ck_app_invocations_latency_ms"),
        sa.CheckConstraint(
            """
            status <> 'success'
            OR (
                api_key_id IS NOT NULL
                AND conversation_id IS NOT NULL
                AND message_id IS NOT NULL
                AND qa_run_id IS NOT NULL
            )
            """,
            name="ck_app_invocations_success_has_trace_refs",
        ),
        sa.ForeignKeyConstraint(["app_id"], ["rag_apps.app_id"], name="fk_app_invocations_app_id"),
        sa.ForeignKeyConstraint(["api_key_id"], ["rag_app_api_keys.api_key_id"], name="fk_app_invocations_api_key_id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["app_conversations.conversation_id"],
            name="fk_app_invocations_conversation_id",
        ),
        sa.ForeignKeyConstraint(["message_id"], ["app_messages.message_id"], name="fk_app_invocations_message_id"),
        sa.ForeignKeyConstraint(["qa_run_id"], ["qa_runs.run_id"], name="fk_app_invocations_qa_run_id"),
    )
    op.create_index(
        "idx_app_invocations_app_status_created_at",
        "app_invocations",
        ["app_id", "status", "created_at"],
    )
    op.create_index("idx_app_invocations_qa_run_id", "app_invocations", ["qa_run_id"])


def downgrade() -> None:
    """按运行时表依赖顺序回滚 RAG App 运行时表。"""
    op.drop_index("idx_app_invocations_qa_run_id", table_name="app_invocations")
    op.drop_index("idx_app_invocations_app_status_created_at", table_name="app_invocations")
    op.drop_table("app_invocations")

    op.drop_index("idx_app_messages_conversation_created_at", table_name="app_messages")
    op.drop_table("app_messages")

    op.drop_index("idx_app_conversations_app_end_user_updated_at", table_name="app_conversations")
    op.drop_table("app_conversations")

    op.drop_index("uk_rag_app_api_keys_key_hash", table_name="rag_app_api_keys")
    op.drop_table("rag_app_api_keys")

    op.drop_index("idx_rag_apps_kb_status_created_at", table_name="rag_apps")
    op.drop_table("rag_apps")
