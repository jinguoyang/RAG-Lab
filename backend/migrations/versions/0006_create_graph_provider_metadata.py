"""create graph provider metadata tables

Revision ID: 0006_graph_provider_metadata
Revises: 0005_qa_run_tables
Create Date: 2026-04-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_graph_provider_metadata"
down_revision: str | None = "0005_qa_run_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建图检索 Provider 元数据表，Neo4j 图结构本体仍保存在图数据库。"""
    op.create_table(
        "graph_snapshots",
        sa.Column("graph_snapshot_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_scope", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("neo4j_graph_key", sa.String(length=128), nullable=True),
        sa.Column("stale_reason", sa.String(length=64), nullable=True),
        sa.Column("stale_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entity_count", sa.Integer(), nullable=True),
        sa.Column("relation_count", sa.Integer(), nullable=True),
        sa.Column("community_count", sa.Integer(), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'running', 'success', 'failed', 'stale')", name="ck_graph_snapshots_status"),
        sa.CheckConstraint("entity_count IS NULL OR entity_count >= 0", name="ck_graph_snapshots_entity_count"),
        sa.CheckConstraint("relation_count IS NULL OR relation_count >= 0", name="ck_graph_snapshots_relation_count"),
        sa.CheckConstraint("community_count IS NULL OR community_count >= 0", name="ck_graph_snapshots_community_count"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_graph_snapshots_kb_id"),
        sa.ForeignKeyConstraint(["job_id"], ["ingest_jobs.job_id"], name="fk_graph_snapshots_job_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_graph_snapshots_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_graph_snapshots_updated_by"),
    )
    op.create_index("idx_graph_snapshots_kb_status_updated_at", "graph_snapshots", ["kb_id", "status", "updated_at"])

    op.create_table(
        "graph_chunk_refs",
        sa.Column("graph_chunk_ref_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("graph_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("neo4j_node_key", sa.String(length=128), nullable=True),
        sa.Column("neo4j_relation_key", sa.String(length=128), nullable=True),
        sa.Column("community_key", sa.String(length=128), nullable=True),
        sa.Column("ref_type", sa.String(length=32), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "ref_type IN ('entity_support', 'relation_support', 'community_support')",
            name="ck_graph_chunk_refs_ref_type",
        ),
        sa.ForeignKeyConstraint(
            ["graph_snapshot_id"],
            ["graph_snapshots.graph_snapshot_id"],
            name="fk_graph_chunk_refs_graph_snapshot_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("idx_graph_chunk_refs_snapshot_type", "graph_chunk_refs", ["graph_snapshot_id", "ref_type"])
    op.create_index("idx_graph_chunk_refs_chunk", "graph_chunk_refs", ["chunk_id"])
    op.create_index("idx_graph_chunk_refs_node", "graph_chunk_refs", ["neo4j_node_key"])


def downgrade() -> None:
    """按依赖顺序回滚图检索 Provider 元数据表。"""
    op.drop_index("idx_graph_chunk_refs_node", table_name="graph_chunk_refs")
    op.drop_index("idx_graph_chunk_refs_chunk", table_name="graph_chunk_refs")
    op.drop_index("idx_graph_chunk_refs_snapshot_type", table_name="graph_chunk_refs")
    op.drop_table("graph_chunk_refs")
    op.drop_index("idx_graph_snapshots_kb_status_updated_at", table_name="graph_snapshots")
    op.drop_table("graph_snapshots")
