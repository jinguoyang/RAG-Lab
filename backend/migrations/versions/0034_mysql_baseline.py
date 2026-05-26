"""mysql baseline - create all tables using generic types

Revision ID: 0034
Revises: 0033
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from app.tables import metadata

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """MySQL: create all tables. PostgreSQL: no-op (handled by migrations 0001-0033)."""
    bind = op.get_bind()
    if "mysql" not in str(bind.dialect.name):
        return  # PG already has all tables from prior migrations
    metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if "mysql" in str(bind.dialect.name):
        metadata.drop_all(bind)
