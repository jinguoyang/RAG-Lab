"""create binding_revisions table

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-21 11:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "binding_revisions",
        sa.Column("binding_revision_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parse_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("index_status", sa.String(length=16), nullable=True),
        sa.Column("build_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("build_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["binding_id"], ["document_kb_bindings.binding_id"], name="fk_binding_revisions_binding_id"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.kb_id"], name="fk_binding_revisions_knowledge_base_id"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], name="fk_binding_revisions_document_id"),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.version_id"], name="fk_binding_revisions_document_version_id"),
        sa.ForeignKeyConstraint(["parse_revision_id"], ["parse_revisions.parse_revision_id"], name="fk_binding_revisions_parse_revision_id"),
    )
    op.create_index("ix_binding_revisions_binding_id", "binding_revisions", ["binding_id"])
    op.create_index("ix_binding_revisions_knowledge_base_id", "binding_revisions", ["knowledge_base_id"])
    op.create_index("ix_binding_revisions_status", "binding_revisions", ["status"])

def downgrade() -> None:
    op.drop_index("ix_binding_revisions_status", table_name="binding_revisions")
    op.drop_index("ix_binding_revisions_knowledge_base_id", table_name="binding_revisions")
    op.drop_index("ix_binding_revisions_binding_id", table_name="binding_revisions")
    op.drop_table("binding_revisions")
