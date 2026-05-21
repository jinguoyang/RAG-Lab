"""modify document_kb_bindings table structure

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-21 14:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # 添加新字段
    op.add_column("document_kb_bindings", sa.Column("active_binding_revision_id", postgresql.UUID(as_uuid=True), nullable=True))

    # 添加外键约束
    op.create_foreign_key("fk_document_kb_bindings_active_binding_revision_id", "document_kb_bindings", "binding_revisions", ["active_binding_revision_id"], ["binding_revision_id"])

    # 添加索引
    op.create_index("ix_document_kb_bindings_active_binding_revision_id", "document_kb_bindings", ["active_binding_revision_id"])

def downgrade() -> None:
    # 删除索引
    op.drop_index("ix_document_kb_bindings_active_binding_revision_id", table_name="document_kb_bindings")

    # 删除外键约束
    op.drop_constraint("fk_document_kb_bindings_active_binding_revision_id", "document_kb_bindings", type_="foreignkey")

    # 删除字段
    op.drop_column("document_kb_bindings", "active_binding_revision_id")
