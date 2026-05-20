"""library version management

Revision ID: 0022_library_version_mgmt
Revises: 0021_documents_library_id
Create Date: 2026-05-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0022_library_version_mgmt"
down_revision: str | None = "0021_documents_library_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. document_versions 新增软删除列
    op.add_column(
        "document_versions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_versions",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 2. 部分索引：加速查询未删除版本
    op.create_index(
        "idx_document_versions_document_not_deleted",
        "document_versions",
        ["document_id", "deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # 3. 扩展 library_parse_jobs.job_type CHECK 约束，新增 upload_version
    op.drop_constraint("ck_library_parse_jobs_job_type", "library_parse_jobs", type_="check")
    op.create_check_constraint(
        "ck_library_parse_jobs_job_type",
        "library_parse_jobs",
        "job_type IN ('extract_text', 'generate_preview', 'reparse_library', 'upload_version')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_library_parse_jobs_job_type", "library_parse_jobs", type_="check")
    op.create_check_constraint(
        "ck_library_parse_jobs_job_type",
        "library_parse_jobs",
        "job_type IN ('extract_text', 'generate_preview', 'reparse_library')",
    )
    op.drop_index("idx_document_versions_document_not_deleted", table_name="document_versions")
    op.drop_column("document_versions", "deleted_by")
    op.drop_column("document_versions", "deleted_at")
