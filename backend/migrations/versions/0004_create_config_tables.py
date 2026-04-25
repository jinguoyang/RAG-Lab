"""create config template and revision tables

Revision ID: 0004_config_tables
Revises: 0003_document_ingest
Create Date: 2026-04-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_config_tables"
down_revision: str | None = "0003_document_ingest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 E3 配置中心基础表，保存受约束 Pipeline 模板与 Revision。"""
    op.create_table(
        "config_templates",
        sa.Column("template_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pipeline_definition", postgresql.JSONB(), nullable=False),
        sa.Column("default_params", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled', 'archived')", name="ck_config_templates_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_config_templates_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_config_templates_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_config_templates_deleted_by"),
    )
    op.create_index(
        "uk_config_templates_name_active",
        "config_templates",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_config_templates_status_updated_at", "config_templates", ["status", "updated_at"])

    op.create_table(
        "config_revisions",
        sa.Column("config_revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("source_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'saved'")),
        sa.Column("pipeline_definition", postgresql.JSONB(), nullable=False),
        sa.Column("validation_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'saved', 'active', 'archived', 'invalid')",
            name="ck_config_revisions_status",
        ),
        sa.CheckConstraint("revision_no >= 1", name="ck_config_revisions_revision_no"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_config_revisions_kb_id"),
        sa.ForeignKeyConstraint(
            ["source_template_id"],
            ["config_templates.template_id"],
            name="fk_config_revisions_source_template_id",
        ),
        sa.ForeignKeyConstraint(["activated_by"], ["users.user_id"], name="fk_config_revisions_activated_by"),
        sa.ForeignKeyConstraint(["deactivated_by"], ["users.user_id"], name="fk_config_revisions_deactivated_by"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_config_revisions_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_config_revisions_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_config_revisions_deleted_by"),
        sa.UniqueConstraint("kb_id", "revision_no", name="uk_config_revisions_kb_revision_no"),
    )
    op.create_index(
        "uk_config_revisions_active_per_kb",
        "config_revisions",
        ["kb_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
    op.create_index("idx_config_revisions_kb_status_created_at", "config_revisions", ["kb_id", "status", "created_at"])

    op.create_foreign_key(
        "fk_knowledge_bases_active_config_revision_id",
        "knowledge_bases",
        "config_revisions",
        ["active_config_revision_id"],
        ["config_revision_id"],
    )


def downgrade() -> None:
    """按外键依赖回滚 E3 配置中心基础表。"""
    op.drop_constraint("fk_knowledge_bases_active_config_revision_id", "knowledge_bases", type_="foreignkey")
    op.drop_index("idx_config_revisions_kb_status_created_at", table_name="config_revisions")
    op.drop_index("uk_config_revisions_active_per_kb", table_name="config_revisions")
    op.drop_table("config_revisions")
    op.drop_index("idx_config_templates_status_updated_at", table_name="config_templates")
    op.drop_index("uk_config_templates_name_active", table_name="config_templates")
    op.drop_table("config_templates")
