"""create system dictionary tables

Revision ID: 0016_system_dictionary_tables
Revises: 0015_app_invocation_running
Create Date: 2026-05-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0016_system_dictionary_tables"
down_revision: str | None = "0015_app_invocation_running"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DICT_TYPES = [
    ("security_level", "密级", "用户、知识库、文档和 Chunk 使用的业务密级"),
    ("document_source_type", "文档来源", "文档来源类型，例如上传、同步、导入"),
    ("file_role", "文件角色", "对象存储文件在业务链路中的角色"),
    ("platform_role", "平台角色", "平台角色展示名称，角色 code 仍由后端权限契约控制"),
    ("kb_role", "知识库角色", "知识库角色展示名称，角色 code 仍由后端权限契约控制"),
    ("feedback_status", "反馈状态", "QA Run 和 App Runtime 的人工反馈标签"),
]

DICT_ITEMS = {
    "security_level": [
        ("public", "公开", 10),
        ("internal", "内部", 20),
        ("confidential", "机密", 30),
    ],
    "document_source_type": [
        ("upload", "上传", 10),
        ("sync", "同步", 20),
        ("import", "导入", 30),
    ],
    "file_role": [
        ("source", "源文件", 10),
        ("parsed_artifact", "解析产物", 20),
        ("attachment", "附件", 30),
    ],
    "platform_role": [
        ("platform_admin", "平台管理员", 10),
        ("platform_user", "平台用户", 20),
    ],
    "kb_role": [
        ("kb_owner", "知识库管理员", 10),
        ("kb_editor", "知识库编辑", 20),
        ("kb_operator", "QA 操作员", 30),
        ("kb_viewer", "知识库读者", 40),
    ],
    "feedback_status": [
        ("unrated", "未标注", 10),
        ("correct", "正确", 20),
        ("partially_correct", "部分正确", 30),
        ("wrong", "错误", 40),
        ("citation_error", "引用错误", 50),
        ("no_evidence", "无证据", 60),
    ],
}


def _seed_type(code: str, name: str, description: str) -> None:
    """写入字典类型种子，保持可重复执行。"""
    op.execute(
        sa.text(
            """
            INSERT INTO system_dict_types (dict_type_id, code, name, description, status)
            VALUES (md5('dict_type:' || :code)::uuid, :code, :name, :description, 'active')
            ON CONFLICT DO NOTHING
            """
        ).bindparams(code=code, name=name, description=description)
    )


def _seed_item(type_code: str, code: str, name: str, sort_order: int) -> None:
    """写入字典项种子，使用 dict type code 定位父类型。"""
    op.execute(
        sa.text(
            """
            INSERT INTO system_dict_items (
                dict_item_id, dict_type_id, code, name, sort_order, status, extra
            )
            SELECT
                md5('dict_item:' || :type_code || ':' || :code)::uuid,
                dict_type_id,
                :code,
                :name,
                :sort_order,
                'active',
                '{}'::jsonb
            FROM system_dict_types
            WHERE code = :type_code AND deleted_at IS NULL
            ON CONFLICT DO NOTHING
            """
        ).bindparams(type_code=type_code, code=code, name=name, sort_order=sort_order)
    )


def upgrade() -> None:
    """创建系统字典表，并将第一批运营字典写入种子数据。"""
    op.create_table(
        "system_dict_types",
        sa.Column("dict_type_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_system_dict_types_status"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_system_dict_types_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_system_dict_types_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_system_dict_types_deleted_by"),
    )
    op.create_index(
        "uk_system_dict_types_code_active",
        "system_dict_types",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_system_dict_types_status", "system_dict_types", ["status"])

    op.create_table(
        "system_dict_items",
        sa.Column("dict_item_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dict_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("extra", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_system_dict_items_status"),
        sa.ForeignKeyConstraint(
            ["dict_type_id"],
            ["system_dict_types.dict_type_id"],
            name="fk_system_dict_items_dict_type_id",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_system_dict_items_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_system_dict_items_updated_by"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.user_id"], name="fk_system_dict_items_deleted_by"),
    )
    op.create_index(
        "uk_system_dict_items_type_code_active",
        "system_dict_items",
        ["dict_type_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_system_dict_items_type_status_sort",
        "system_dict_items",
        ["dict_type_id", "status", "sort_order"],
    )

    op.drop_constraint("ck_stored_files_file_role", "stored_files", type_="check")
    op.drop_constraint("ck_documents_source_type", "documents", type_="check")
    op.drop_constraint("ck_qa_runs_feedback_status", "qa_runs", type_="check")

    for code, name, description in DICT_TYPES:
        _seed_type(code, name, description)
    for type_code, items in DICT_ITEMS.items():
        for code, name, sort_order in items:
            _seed_item(type_code, code, name, sort_order)


def downgrade() -> None:
    """回滚字典表；恢复被字典接管前的稳定 CHECK 约束。"""
    op.create_check_constraint(
        "ck_qa_runs_feedback_status",
        "qa_runs",
        "feedback_status IN ('unrated', 'correct', 'partially_correct', 'wrong', 'citation_error', 'no_evidence')",
    )
    op.create_check_constraint(
        "ck_documents_source_type",
        "documents",
        "source_type IN ('upload', 'sync', 'import')",
    )
    op.create_check_constraint(
        "ck_stored_files_file_role",
        "stored_files",
        "file_role IN ('source', 'parsed_artifact', 'attachment')",
    )
    op.drop_index("idx_system_dict_items_type_status_sort", table_name="system_dict_items")
    op.drop_index("uk_system_dict_items_type_code_active", table_name="system_dict_items")
    op.drop_table("system_dict_items")
    op.drop_index("idx_system_dict_types_status", table_name="system_dict_types")
    op.drop_index("uk_system_dict_types_code_active", table_name="system_dict_types")
    op.drop_table("system_dict_types")
