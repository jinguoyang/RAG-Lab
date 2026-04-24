import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

metadata = sa.MetaData()

knowledge_bases = sa.Table(
    "knowledge_bases",
    metadata,
    sa.Column("kb_id", postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("name", sa.String(length=128), nullable=False),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column("default_security_level", sa.String(length=32), nullable=False),
    sa.Column("sparse_index_enabled", sa.Boolean(), nullable=False),
    sa.Column("graph_index_enabled", sa.Boolean(), nullable=False),
    sa.Column("sparse_required_for_activation", sa.Boolean(), nullable=False),
    sa.Column("graph_required_for_activation", sa.Boolean(), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False),
    sa.Column("active_config_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("metadata", postgresql.JSONB(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
)
