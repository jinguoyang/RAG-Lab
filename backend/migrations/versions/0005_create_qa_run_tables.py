"""create qa run tables

Revision ID: 0005_qa_run_tables
Revises: 0004_config_tables
Create Date: 2026-04-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_qa_run_tables"
down_revision: str | None = "0004_config_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """创建 E4 QA Run 最小持久化表，支撑后续状态轮询和详情查询。"""
    op.create_table(
        "qa_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kb_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("rewritten_query", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("has_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("override_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("feedback_status", sa.String(length=32), nullable=False, server_default=sa.text("'unrated'")),
        sa.Column("feedback_note", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'queued', 'running', 'success', 'partial', 'failed', 'cancelled')",
            name="ck_qa_runs_status",
        ),
        sa.CheckConstraint(
            "feedback_status IN ('unrated', 'correct', 'partially_correct', 'wrong', 'citation_error', 'no_evidence')",
            name="ck_qa_runs_feedback_status",
        ),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.kb_id"], name="fk_qa_runs_kb_id"),
        sa.ForeignKeyConstraint(
            ["config_revision_id"],
            ["config_revisions.config_revision_id"],
            name="fk_qa_runs_config_revision_id",
        ),
        sa.ForeignKeyConstraint(["source_run_id"], ["qa_runs.run_id"], name="fk_qa_runs_source_run_id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.user_id"], name="fk_qa_runs_created_by"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.user_id"], name="fk_qa_runs_updated_by"),
    )
    op.create_index("idx_qa_runs_kb_status_created_at", "qa_runs", ["kb_id", "status", "created_at"])
    op.create_index("idx_qa_runs_created_by_created_at", "qa_runs", ["created_by", "created_at"])

    op.create_table(
        "qa_run_trace_steps",
        sa.Column("trace_step_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("step_order >= 1", name="ck_qa_run_trace_steps_step_order"),
        sa.CheckConstraint(
            "status IN ('success', 'skipped', 'failed', 'partial')",
            name="ck_qa_run_trace_steps_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["qa_runs.run_id"], name="fk_qa_run_trace_steps_run_id"),
        sa.UniqueConstraint("run_id", "step_order", name="uk_qa_run_trace_steps_run_step_order"),
    )
    op.create_index("idx_qa_run_trace_steps_run_order", "qa_run_trace_steps", ["run_id", "step_order"])

    op.create_table(
        "qa_run_candidates",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("raw_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("rerank_score", sa.Numeric(10, 6), nullable=True),
        sa.Column("rank_no", sa.Integer(), nullable=True),
        sa.Column("is_authorized", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("drop_reason", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("source_type IN ('dense', 'sparse', 'graph', 'mock')", name="ck_qa_run_candidates_source_type"),
        sa.CheckConstraint("rank_no IS NULL OR rank_no >= 1", name="ck_qa_run_candidates_rank_no"),
        sa.ForeignKeyConstraint(["run_id"], ["qa_runs.run_id"], name="fk_qa_run_candidates_run_id"),
    )
    op.create_index("idx_qa_run_candidates_run_source_rank", "qa_run_candidates", ["run_id", "source_type", "rank_no"])

    op.create_table(
        "qa_run_evidence",
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_order", sa.Integer(), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=True),
        sa.Column("content_snapshot_hash", sa.String(length=128), nullable=True),
        sa.Column("snapshot_policy", sa.String(length=32), nullable=False, server_default=sa.text("'redacted'")),
        sa.Column("redaction_status", sa.String(length=16), nullable=False, server_default=sa.text("'none'")),
        sa.Column("source_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("evidence_order >= 1", name="ck_qa_run_evidence_evidence_order"),
        sa.CheckConstraint(
            "snapshot_policy IN ('full_encrypted', 'redacted', 'hash_only')",
            name="ck_qa_run_evidence_snapshot_policy",
        ),
        sa.CheckConstraint("redaction_status IN ('none', 'redacted')", name="ck_qa_run_evidence_redaction_status"),
        sa.ForeignKeyConstraint(["run_id"], ["qa_runs.run_id"], name="fk_qa_run_evidence_run_id"),
        sa.ForeignKeyConstraint(["candidate_id"], ["qa_run_candidates.candidate_id"], name="fk_qa_run_evidence_candidate_id"),
        sa.UniqueConstraint("run_id", "evidence_order", name="uk_qa_run_evidence_run_order"),
    )
    op.create_index("idx_qa_run_evidence_run_order", "qa_run_evidence", ["run_id", "evidence_order"])

    op.create_table(
        "qa_run_citations",
        sa.Column("citation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("citation_order", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("location_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("citation_order >= 1", name="ck_qa_run_citations_citation_order"),
        sa.ForeignKeyConstraint(["run_id"], ["qa_runs.run_id"], name="fk_qa_run_citations_run_id"),
        sa.ForeignKeyConstraint(["evidence_id"], ["qa_run_evidence.evidence_id"], name="fk_qa_run_citations_evidence_id"),
        sa.UniqueConstraint("run_id", "citation_order", name="uk_qa_run_citations_run_order"),
    )
    op.create_index("idx_qa_run_citations_run_order", "qa_run_citations", ["run_id", "citation_order"])


def downgrade() -> None:
    """按明细依赖顺序回滚 E4 QA Run 基础表。"""
    op.drop_index("idx_qa_run_citations_run_order", table_name="qa_run_citations")
    op.drop_table("qa_run_citations")

    op.drop_index("idx_qa_run_evidence_run_order", table_name="qa_run_evidence")
    op.drop_table("qa_run_evidence")

    op.drop_index("idx_qa_run_candidates_run_source_rank", table_name="qa_run_candidates")
    op.drop_table("qa_run_candidates")

    op.drop_index("idx_qa_run_trace_steps_run_order", table_name="qa_run_trace_steps")
    op.drop_table("qa_run_trace_steps")

    op.drop_index("idx_qa_runs_created_by_created_at", table_name="qa_runs")
    op.drop_index("idx_qa_runs_kb_status_created_at", table_name="qa_runs")
    op.drop_table("qa_runs")
