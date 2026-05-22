"""rename binding_revisions to chunk_revisions

Revision ID: 0031
Revises: 0030
Create Date: 2026-05-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Rename table
    op.rename_table("binding_revisions", "chunk_revisions")

    # 2. Rename PK column
    op.alter_column("chunk_revisions", "binding_revision_id", new_column_name="chunk_revision_id")

    # 3. Rename FK columns on other tables
    op.alter_column("chunks", "binding_revision_id", new_column_name="chunk_revision_id")
    op.alter_column("document_kb_bindings", "active_binding_revision_id", new_column_name="active_chunk_revision_id")

    # 4. Add strategy and params columns
    op.add_column("chunk_revisions", sa.Column("strategy", sa.String(32), nullable=False, server_default="fixed_size"))
    op.add_column("chunk_revisions", sa.Column("params", JSONB, nullable=False, server_default="{}"))

    # 5. Backfill params for existing records
    op.execute("UPDATE chunk_revisions SET params = '{\"chunk_size\": 900, \"chunk_overlap\": 120}'")

    # 6. Drop chunk_size/chunk_overlap from document_kb_bindings
    op.drop_column("document_kb_bindings", "chunk_size")
    op.drop_column("document_kb_bindings", "chunk_overlap")

    # 7. Rename FK constraints
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT binding_revisions_pkey TO chunk_revisions_pkey")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_binding_id TO fk_chunk_revisions_binding_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_knowledge_base_id TO fk_chunk_revisions_knowledge_base_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_document_id TO fk_chunk_revisions_document_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_document_version_id TO fk_chunk_revisions_document_version_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_parse_revision_id TO fk_chunk_revisions_parse_revision_id")
    op.execute("ALTER TABLE chunks RENAME CONSTRAINT fk_chunks_binding_revision_id TO fk_chunks_chunk_revision_id")
    op.execute("ALTER TABLE document_kb_bindings RENAME CONSTRAINT fk_document_kb_bindings_active_binding_revision_id TO fk_document_kb_bindings_active_chunk_revision_id")

    # 8. Rename indexes
    op.execute("ALTER INDEX ix_binding_revisions_binding_id RENAME TO ix_chunk_revisions_binding_id")
    op.execute("ALTER INDEX ix_binding_revisions_knowledge_base_id RENAME TO ix_chunk_revisions_knowledge_base_id")
    op.execute("ALTER INDEX ix_binding_revisions_status RENAME TO ix_chunk_revisions_status")
    op.execute("ALTER INDEX ix_chunks_binding_revision_id RENAME TO ix_chunks_chunk_revision_id")
    op.execute("ALTER INDEX ix_document_kb_bindings_active_binding_revision_id RENAME TO ix_document_kb_bindings_active_chunk_revision_id")


def downgrade() -> None:
    # Reverse all operations in reverse order
    op.execute("ALTER INDEX ix_document_kb_bindings_active_chunk_revision_id RENAME TO ix_document_kb_bindings_active_binding_revision_id")
    op.execute("ALTER INDEX ix_chunks_chunk_revision_id RENAME TO ix_chunks_binding_revision_id")
    op.execute("ALTER INDEX ix_chunk_revisions_status RENAME TO ix_binding_revisions_status")
    op.execute("ALTER INDEX ix_chunk_revisions_knowledge_base_id RENAME TO ix_binding_revisions_knowledge_base_id")
    op.execute("ALTER INDEX ix_chunk_revisions_binding_id RENAME TO ix_binding_revisions_binding_id")

    op.execute("ALTER TABLE document_kb_bindings RENAME CONSTRAINT fk_document_kb_bindings_active_chunk_revision_id TO fk_document_kb_bindings_active_binding_revision_id")
    op.execute("ALTER TABLE chunks RENAME CONSTRAINT fk_chunks_chunk_revision_id TO fk_chunks_binding_revision_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_parse_revision_id TO fk_binding_revisions_parse_revision_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_document_version_id TO fk_binding_revisions_document_version_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_document_id TO fk_binding_revisions_document_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_knowledge_base_id TO fk_binding_revisions_knowledge_base_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_chunk_revisions_binding_id TO fk_binding_revisions_binding_id")
    op.execute("ALTER TABLE chunk_revisions RENAME CONSTRAINT chunk_revisions_pkey TO binding_revisions_pkey")

    op.add_column("document_kb_bindings", sa.Column("chunk_size", sa.Integer, nullable=False, server_default="900"))
    op.add_column("document_kb_bindings", sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default="120"))

    op.drop_column("chunk_revisions", "params")
    op.drop_column("chunk_revisions", "strategy")

    op.alter_column("document_kb_bindings", "active_chunk_revision_id", new_column_name="active_binding_revision_id")
    op.alter_column("chunks", "chunk_revision_id", new_column_name="binding_revision_id")
    op.alter_column("chunk_revisions", "chunk_revision_id", new_column_name="binding_revision_id")
    op.rename_table("chunk_revisions", "binding_revisions")
