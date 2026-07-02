"""add embedded app deployment records

Revision ID: 0047
Revises: 0046
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增内置嵌入应用部署记录，并为 API Key 增加系统管理标识。"""
    op.add_column(
        "rag_app_api_keys",
        sa.Column("key_type", sa.String(length=32), nullable=False, server_default="normal"),
    )
    op.add_column(
        "rag_app_api_keys",
        sa.Column("managed_by", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.add_column("rag_app_api_keys", sa.Column("display_name", sa.String(length=128), nullable=True))
    op.add_column(
        "rag_app_api_keys",
        sa.Column("deletable", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("idx_rag_app_api_keys_app_type", "rag_app_api_keys", ["app_id", "key_type"])

    op.create_table(
        "embedded_app_deployments",
        sa.Column("deployment_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("app_type", sa.String(length=32), nullable=False),
        sa.Column("api_key_id", sa.String(length=36), nullable=False),
        sa.Column("database_name", sa.String(length=128), nullable=False),
        sa.Column("backend_port", sa.Integer(), nullable=False),
        sa.Column("frontend_port", sa.Integer(), nullable=False),
        sa.Column("backend_pid", sa.Integer(), nullable=True),
        sa.Column("frontend_pid", sa.Integer(), nullable=True),
        sa.Column("service_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("health_status", sa.String(length=16), nullable=False),
        sa.Column("public_url", sa.String(length=512), nullable=True),
        sa.Column("last_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_stop_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'failed', 'stopped')",
            name="ck_embedded_app_deployments_status",
        ),
        sa.CheckConstraint(
            "health_status IN ('unknown', 'healthy', 'unhealthy')",
            name="ck_embedded_app_deployments_health_status",
        ),
        sa.CheckConstraint("backend_port > 0 AND backend_port <= 65535", name="ck_embedded_app_backend_port"),
        sa.CheckConstraint("frontend_port > 0 AND frontend_port <= 65535", name="ck_embedded_app_frontend_port"),
    )
    op.create_index(
        "uk_embedded_app_deployments_app_type",
        "embedded_app_deployments",
        ["app_id", "app_type"],
        unique=True,
    )
    op.create_index(
        "uk_embedded_app_deployments_database",
        "embedded_app_deployments",
        ["database_name"],
        unique=True,
    )
    op.create_index(
        "uk_embedded_app_deployments_backend_port",
        "embedded_app_deployments",
        ["backend_port"],
        unique=True,
    )
    op.create_index(
        "uk_embedded_app_deployments_frontend_port",
        "embedded_app_deployments",
        ["frontend_port"],
        unique=True,
    )
    op.create_index(
        "idx_embedded_app_deployments_status",
        "embedded_app_deployments",
        ["status", "health_status"],
    )


def downgrade() -> None:
    """回滚本次新增表与新增列；生产回滚前需确认无依赖数据。"""
    op.drop_index("idx_embedded_app_deployments_status", table_name="embedded_app_deployments")
    op.drop_index("uk_embedded_app_deployments_frontend_port", table_name="embedded_app_deployments")
    op.drop_index("uk_embedded_app_deployments_backend_port", table_name="embedded_app_deployments")
    op.drop_index("uk_embedded_app_deployments_database", table_name="embedded_app_deployments")
    op.drop_index("uk_embedded_app_deployments_app_type", table_name="embedded_app_deployments")
    op.drop_table("embedded_app_deployments")

    op.drop_index("idx_rag_app_api_keys_app_type", table_name="rag_app_api_keys")
    op.drop_column("rag_app_api_keys", "deletable")
    op.drop_column("rag_app_api_keys", "display_name")
    op.drop_column("rag_app_api_keys", "managed_by")
    op.drop_column("rag_app_api_keys", "key_type")
