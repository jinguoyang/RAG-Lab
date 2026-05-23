"""remove security_level from knowledge_bases, documents, chunks, chunk_access_filters

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-23
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop index on chunks.security_level if it exists
    op.execute("DROP INDEX IF EXISTS idx_chunks_security_level")

    # Remove security_level column from all four tables
    op.drop_column("chunk_access_filters", "security_level")
    op.drop_column("chunks", "security_level")
    op.drop_column("documents", "security_level")
    op.drop_column("knowledge_bases", "default_security_level")


def downgrade() -> None:
    # Restore columns with default values
    op.add_column("knowledge_bases", sa.Column("default_security_level", sa.String(32), nullable=False, server_default="public"))
    op.add_column("documents", sa.Column("security_level", sa.String(32), nullable=False, server_default="public"))
    op.add_column("chunks", sa.Column("security_level", sa.String(32), nullable=False, server_default="public"))
    op.add_column("chunk_access_filters", sa.Column("security_level", sa.String(32), nullable=False, server_default="public"))

    # Restore index
    op.execute("CREATE INDEX idx_chunks_security_level ON chunks (security_level)")
