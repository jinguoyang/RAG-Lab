"""create user and user group tables

Revision ID: 0001_create_user_group_tables
Revises: 
Create Date: 2026-04-24 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_create_user_group_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建用户、用户组和组成员基础表，支撑开发期用户管理主线。"""
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "platform_role",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'platform_user'"),
        ),
        sa.Column(
            "security_level",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'public'"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
            "platform_role IN ('platform_admin', 'platform_user')",
            name="ck_users_platform_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_users_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name="fk_users_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.user_id"],
            name="fk_users_updated_by",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"],
            ["users.user_id"],
            name="fk_users_deleted_by",
        ),
    )
    op.create_index(
        "uk_users_username_active",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_users_status", "users", ["status"])

    op.create_table(
        "user_groups",
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_user_groups_status",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name="fk_user_groups_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.user_id"],
            name="fk_user_groups_updated_by",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"],
            ["users.user_id"],
            name="fk_user_groups_deleted_by",
        ),
    )
    op.create_index(
        "uk_user_groups_name_active",
        "user_groups",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_user_groups_status", "user_groups", ["status"])

    op.create_table(
        "user_group_members",
        sa.Column(
            "group_member_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name="ck_user_group_members_status",
        ),
        sa.CheckConstraint(
            "(status = 'active' AND left_at IS NULL) OR status = 'inactive'",
            name="ck_user_group_members_active_left_at",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["user_groups.group_id"],
            name="fk_user_group_members_group_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_user_group_members_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
            name="fk_user_group_members_created_by",
        ),
    )
    op.create_index(
        "uk_user_group_members_active",
        "user_group_members",
        ["group_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_user_group_members_group_status",
        "user_group_members",
        ["group_id", "status"],
    )
    op.create_index(
        "idx_user_group_members_user_status",
        "user_group_members",
        ["user_id", "status"],
    )


def downgrade() -> None:
    """回滚本次基础表创建，按外键依赖从成员关系表开始删除。"""
    op.drop_index("idx_user_group_members_user_status", table_name="user_group_members")
    op.drop_index("idx_user_group_members_group_status", table_name="user_group_members")
    op.drop_index("uk_user_group_members_active", table_name="user_group_members")
    op.drop_table("user_group_members")

    op.drop_index("idx_user_groups_status", table_name="user_groups")
    op.drop_index("uk_user_groups_name_active", table_name="user_groups")
    op.drop_table("user_groups")

    op.drop_index("idx_users_status", table_name="users")
    op.drop_index("uk_users_username_active", table_name="users")
    op.drop_table("users")
