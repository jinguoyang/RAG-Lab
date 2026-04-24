"""create knowledge bases and seed development data

Revision ID: 0002_create_knowledge_bases
Revises: 0001_create_user_group_tables
Create Date: 2026-04-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_create_knowledge_bases"
down_revision: str | None = "0001_create_user_group_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_USER_ID = "00000000-0000-0000-0000-000000000001"
NORMAL_USER_ID = "00000000-0000-0000-0000-000000000002"
DEFAULT_KB_ID = "10000000-0000-0000-0000-000000000001"


def _prepare_knowledge_bases_table() -> bool:
    """处理开发库中可能存在的旧版知识库表，保留旧数据后再创建正式表。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("knowledge_bases"):
        return True

    column_names = {column["name"] for column in inspector.get_columns("knowledge_bases")}
    if "kb_id" in column_names:
        return False

    if inspector.has_table("legacy_knowledge_bases"):
        raise RuntimeError(
            "Found legacy knowledge_bases table, but legacy_knowledge_bases already exists."
        )

    op.rename_table("knowledge_bases", "legacy_knowledge_bases")
    return True


def upgrade() -> None:
    """创建知识库基础表，并写入 E1 开发联调所需的最小种子数据。"""
    should_create_table = _prepare_knowledge_bases_table()
    if should_create_table:
        op.create_table(
            "knowledge_bases",
            sa.Column("kb_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "default_security_level",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'public'"),
            ),
            sa.Column(
                "sparse_index_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "graph_index_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "sparse_required_for_activation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "graph_required_for_activation",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "status",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            sa.Column("active_config_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "metadata",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
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
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.CheckConstraint(
                "status IN ('draft', 'active', 'disabled', 'archived')",
                name="ck_knowledge_bases_status",
            ),
            sa.ForeignKeyConstraint(
                ["owner_id"],
                ["users.user_id"],
                name="fk_knowledge_bases_owner_id",
            ),
            sa.ForeignKeyConstraint(
                ["created_by"],
                ["users.user_id"],
                name="fk_knowledge_bases_created_by",
            ),
            sa.ForeignKeyConstraint(
                ["updated_by"],
                ["users.user_id"],
                name="fk_knowledge_bases_updated_by",
            ),
            sa.ForeignKeyConstraint(
                ["deleted_by"],
                ["users.user_id"],
                name="fk_knowledge_bases_deleted_by",
            ),
        )
        op.create_index(
            "uk_knowledge_bases_name_active",
            "knowledge_bases",
            ["name"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
        )
        op.create_index(
            "idx_knowledge_bases_owner_status",
            "knowledge_bases",
            ["owner_id", "status"],
        )
        op.create_index(
            "idx_knowledge_bases_status_updated_at",
            "knowledge_bases",
            ["status", "updated_at"],
        )

    op.execute(
        f"""
        INSERT INTO users (
            user_id, username, display_name, email, platform_role, security_level, status
        )
        VALUES
            ('{ADMIN_USER_ID}', 'admin', '开发管理员', 'admin@example.com', 'platform_admin', 'public', 'active'),
            ('{NORMAL_USER_ID}', 'user', '开发用户', 'user@example.com', 'platform_user', 'public', 'active')
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO knowledge_bases (
            kb_id, name, description, owner_id, default_security_level,
            sparse_index_enabled, graph_index_enabled,
            sparse_required_for_activation, graph_required_for_activation,
            status, metadata, created_by, updated_by
        )
        VALUES (
            '{DEFAULT_KB_ID}',
            '默认知识库',
            'E1 开发联调默认知识库',
            '{ADMIN_USER_ID}',
            'public',
            false,
            false,
            false,
            false,
            'active',
            '{{}}'::jsonb,
            '{ADMIN_USER_ID}',
            '{ADMIN_USER_ID}'
        )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """回滚知识库表；开发期种子用户保留给用户迁移版本统一处理。"""
    op.drop_index("idx_knowledge_bases_status_updated_at", table_name="knowledge_bases")
    op.drop_index("idx_knowledge_bases_owner_status", table_name="knowledge_bases")
    op.drop_index("uk_knowledge_bases_name_active", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")
