"""Backfill parse_revisions for existing document_versions.

Creates a parse_revision record for each non-deleted document_version
that doesn't already have one. Idempotent: safe to run multiple times.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import sqlalchemy as sa
from sqlalchemy import text

from app.core.database import get_engine


def backfill_parse_revisions(engine: sa.Engine) -> int:
    """Insert parse_revisions for document_versions that lack one.

    Returns the number of rows inserted.
    """
    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO parse_revisions (
                parse_revision_id,
                document_version_id,
                content_format,
                parser_name,
                parser_version,
                parse_options,
                status,
                created_at,
                created_by
            )
            SELECT
                gen_random_uuid(),
                dv.version_id,
                'markdown',
                'legacy_parser',
                '1.0',
                '{}',
                'completed',
                COALESCE(dv.created_at, now()),
                dv.created_by
            FROM document_versions dv
            WHERE dv.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM parse_revisions pr
                  WHERE pr.document_version_id = dv.version_id
                    AND pr.deleted_at IS NULL
              )
        """))
        return result.rowcount


def verify(engine: sa.Engine) -> None:
    """Print summary of parse_revisions."""
    with engine.begin() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM parse_revisions WHERE deleted_at IS NULL")
        ).scalar()
        legacy = conn.execute(
            text("""
                SELECT COUNT(*) FROM parse_revisions
                WHERE deleted_at IS NULL AND parser_name = 'legacy_parser'
            """)
        ).scalar()
        orphans = conn.execute(text("""
            SELECT COUNT(*) FROM document_versions dv
            WHERE dv.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM parse_revisions pr
                  WHERE pr.document_version_id = dv.version_id
                    AND pr.deleted_at IS NULL
              )
        """)).scalar()

    print(f"\n  Total parse_revisions: {total}")
    print(f"  Legacy backfilled:    {legacy}")
    print(f"  Remaining orphans:    {orphans}")


def main() -> None:
    """Backfill parse_revisions for existing document_versions."""
    print("=== Backfill Parse Revisions ===\n")

    engine = get_engine()

    print("[1/2] Backfilling parse_revisions...")
    count = backfill_parse_revisions(engine)
    print(f"  Inserted {count} parse_revision records")

    print("[2/2] Verifying...")
    verify(engine)

    print("\nDone.")


if __name__ == "__main__":
    main()
