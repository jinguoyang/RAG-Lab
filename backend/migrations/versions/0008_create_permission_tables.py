"""create permission and acl tables

Revision ID: 0008_create_permission_tables
Revises: 0007_create_kb_member_bindings
Create Date: 2026-04-27 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008_create_permission_tables"
down_revision: str | None = "0007_create_kb_member_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = [
    ("platform.user.manage", "platform", "平台用户与用户组管理"),
    ("kb.view", "kb", "查看知识库"),
    ("kb.manage", "kb", "管理知识库基础信息"),
    ("kb.member.manage", "kb", "管理知识库成员"),
    ("kb.document.upload", "kb", "上传和维护文档"),
    ("kb.document.read", "kb", "查看文档摘要"),
    ("kb.document.download", "kb", "下载原始文档"),
    ("kb.chunk.read", "chunk", "查看 Chunk 正文"),
    ("kb.config.manage", "kb", "保存和激活配置"),
    ("kb.qa.run", "kb", "执行 QA 调试"),
    ("kb.qa.history.read", "kb", "查看 QA 历史"),
    ("kb.evaluation.manage", "kb", "管理评估样本"),
]

ROLE_PERMISSIONS = {
    "platform_admin": [code for code, _, _ in PERMISSIONS],
    "platform_user": [],
    "kb_owner": [code for code, _, _ in PERMISSIONS if code.startswith("kb.")],
    "kb_editor": [
        "kb.view",
        "kb.manage",
        "kb.document.upload",
        "kb.document.read",
        "kb.document.download",
        "kb.chunk.read",
        "kb.config.manage",
        "kb.qa.run",
        "kb.qa.history.read",
        "kb.evaluation.manage",
    ],
    "kb_operator": [
        "kb.view",
        "kb.document.read",
        "kb.chunk.read",
        "kb.qa.run",
        "kb.qa.history.read",
    ],
    "kb_viewer": [
        "kb.view",
        "kb.document.read",
        "kb.chunk.read",
        "kb.qa.history.read",
    ],
}


def upgrade() -> None:
    """创建稳定权限码、角色授权绑定和 ACL 规则表，并写入默认权限矩阵。"""
    op.create_table(
        "permissions",
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("permission_code", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("scope IN ('platform', 'kb', 'document', 'chunk')", name="ck_permissions_scope"),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_permissions_status"),
        sa.UniqueConstraint("permission_code", name="uk_permissions_permission_code"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_permissions_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_permissions_updated_by"),
    )
    op.create_index("idx_permissions_scope_status", "permissions", ["scope", "status"])

    op.create_table(
        "role_permission_bindings",
        sa.Column("role_permission_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_scope", sa.String(length=16), nullable=False),
        sa.Column("role_code", sa.String(length=32), nullable=False),
        sa.Column("permission_code", sa.String(length=64), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False, server_default=sa.text("'allow'")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("role_scope IN ('platform', 'kb')", name="ck_role_permission_bindings_role_scope"),
        sa.CheckConstraint("effect IN ('allow', 'deny')", name="ck_role_permission_bindings_effect"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_role_permission_bindings_status"),
        sa.ForeignKeyConstraint(
            ["permission_code"],
            ["permissions.permission_code"],
            name="fk_role_permission_bindings_permission_code",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_role_permission_bindings_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_role_permission_bindings_updated_by"),
    )
    op.create_index(
        "uk_role_permission_bindings_active",
        "role_permission_bindings",
        ["role_scope", "role_code", "permission_code", "effect"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("idx_role_permission_bindings_role", "role_permission_bindings", ["role_scope", "role_code", "status"])
    op.create_index("idx_role_permission_bindings_permission", "role_permission_bindings", ["permission_code", "status"])

    op.create_table(
        "acl_rules",
        sa.Column("acl_rule_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("permission_code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "resource_type IN ('document', 'document_version', 'chunk')",
            name="ck_acl_rules_resource_type",
        ),
        sa.CheckConstraint("subject_type IN ('user', 'group')", name="ck_acl_rules_subject_type"),
        sa.CheckConstraint("effect IN ('allow', 'deny')", name="ck_acl_rules_effect"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_acl_rules_status"),
        sa.ForeignKeyConstraint(["permission_code"], ["permissions.permission_code"], name="fk_acl_rules_permission_code"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_acl_rules_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_acl_rules_updated_by"),
    )
    op.create_index("idx_acl_rules_resource", "acl_rules", ["resource_type", "resource_id", "status"])
    op.create_index("idx_acl_rules_subject", "acl_rules", ["subject_type", "subject_id", "permission_code", "status"])
    op.create_index("idx_acl_rules_permission_status", "acl_rules", ["permission_code", "status"])

    for code, scope, name in PERMISSIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (permission_id, permission_code, scope, name, status)
                VALUES (md5(:code)::uuid, :code, :scope, :name, 'active')
                ON CONFLICT DO NOTHING
                """
            ).bindparams(code=code, scope=scope, name=name)
        )

    for role_code, permission_codes in ROLE_PERMISSIONS.items():
        role_scope = "platform" if role_code.startswith("platform_") else "kb"
        for permission_code in permission_codes:
            op.execute(
                sa.text(
                    """
                    INSERT INTO role_permission_bindings (
                        role_permission_id, role_scope, role_code, permission_code, effect, status
                    )
                    VALUES (
                        md5(:role_scope || ':' || :role_code || ':' || :permission_code)::uuid,
                        :role_scope,
                        :role_code,
                        :permission_code,
                        'allow',
                        'active'
                    )
                    ON CONFLICT DO NOTHING
                    """
                ).bindparams(
                    role_scope=role_scope,
                    role_code=role_code,
                    permission_code=permission_code,
                )
            )


def downgrade() -> None:
    """按依赖顺序回滚权限矩阵和 ACL 表。"""
    op.drop_index("idx_acl_rules_permission_status", table_name="acl_rules")
    op.drop_index("idx_acl_rules_subject", table_name="acl_rules")
    op.drop_index("idx_acl_rules_resource", table_name="acl_rules")
    op.drop_table("acl_rules")

    op.drop_index("idx_role_permission_bindings_permission", table_name="role_permission_bindings")
    op.drop_index("idx_role_permission_bindings_role", table_name="role_permission_bindings")
    op.drop_index("uk_role_permission_bindings_active", table_name="role_permission_bindings")
    op.drop_table("role_permission_bindings")

    op.drop_index("idx_permissions_scope_status", table_name="permissions")
    op.drop_table("permissions")
