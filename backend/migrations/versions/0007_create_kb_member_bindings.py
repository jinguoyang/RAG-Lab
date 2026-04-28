"""create knowledge base member bindings

Revision ID: 0007_create_kb_member_bindings
Revises: 0006_graph_provider_metadata
Create Date: 2026-04-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_create_kb_member_bindings"
down_revision: str | None = "0006_graph_provider_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    """创建知识库成员绑定表，并为默认知识库补齐 owner 绑定。"""
    op.create_table(
        "kb_member_bindings",
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kb_role", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "subject_type IN ('user', 'group')",
            name="ck_kb_member_bindings_subject_type",
        ),
        sa.CheckConstraint(
            "kb_role IN ('kb_owner', 'kb_editor', 'kb_operator', 'kb_viewer')",
            name="ck_kb_member_bindings_kb_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_kb_member_bindings_status",
        ),
        sa.ForeignKeyConstraint(
            ["kb_id"],
            ["knowledge_bases.kb_id"],
            name="fk_kb_member_bindings_kb_id",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name="fk_kb_member_bindings_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.user_id"],
            name="fk_kb_member_bindings_updated_by",
        ),
    )
    op.create_index(
        "uk_kb_member_bindings_active_subject",
        "kb_member_bindings",
        ["kb_id", "subject_type", "subject_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_kb_member_bindings_kb_status",
        "kb_member_bindings",
        ["kb_id", "status"],
    )
    op.create_index(
        "idx_kb_member_bindings_subject",
        "kb_member_bindings",
        ["subject_type", "subject_id", "status"],
    )

    op.execute(
        f"""
        INSERT INTO kb_member_bindings (
            binding_id, kb_id, subject_type, subject_id, kb_role,
            status, created_by, updated_by
        )
        SELECT
            md5(kb_id::text || 'owner')::uuid,
            kb_id,
            'user',
            owner_id,
            'kb_owner',
            'active',
            COALESCE(created_by, '{ADMIN_USER_ID}'),
            COALESCE(updated_by, '{ADMIN_USER_ID}')
        FROM knowledge_bases
        WHERE deleted_at IS NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """回滚知识库成员绑定表。"""
    op.drop_index("idx_kb_member_bindings_subject", table_name="kb_member_bindings")
    op.drop_index("idx_kb_member_bindings_kb_status", table_name="kb_member_bindings")
    op.drop_index("uk_kb_member_bindings_active_subject", table_name="kb_member_bindings")
    op.drop_table("kb_member_bindings")
