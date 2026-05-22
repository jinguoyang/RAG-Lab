"""Backfill chunk_revisions for existing document_kb_bindings.

Creates a chunk_revision record for each active document_kb_binding
that doesn't already have one, and links it via active_chunk_revision_id.
Idempotent: safe to run multiple times.
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


def backfill_chunk_revisions(engine: sa.Engine) -> int:
    """Insert chunk_revisions for document_kb_bindings that lack one.

    Returns the number of rows inserted.
    """
    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO chunk_revisions (
                chunk_revision_id,
                binding_id,
                knowledge_base_id,
                document_id,
                document_version_id,
                parse_revision_id,
                strategy,
                params,
                status,
                chunk_count,
                created_at,
                created_by
            )
            SELECT
                gen_random_uuid(),
                dkb.binding_id,
                dkb.kb_id,
                dkb.document_id,
                dkb.version_id,
                pr.parse_revision_id,
                'fixed_size',
                '{"chunk_size": 900, "chunk_overlap": 120}'::jsonb,
                'active',
                COALESCE(dkb.chunk_count, 0),
                COALESCE(dkb.created_at, now()),
                dkb.created_by
            FROM document_kb_bindings dkb
            JOIN parse_revisions pr
                ON pr.document_version_id = dkb.version_id
                AND pr.deleted_at IS NULL
            WHERE dkb.status = 'active'
              AND NOT EXISTS (
                  SELECT 1 FROM chunk_revisions br
                  WHERE br.binding_id = dkb.binding_id
                    AND br.deleted_at IS NULL
              )
        """))
        return result.rowcount


def link_active_chunk_revisions(engine: sa.Engine) -> int:
    """Update document_kb_bindings.active_chunk_revision_id.

    Returns the number of rows updated.
    """
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE document_kb_bindings dkb
            SET active_chunk_revision_id = br.chunk_revision_id
            FROM chunk_revisions br
            WHERE br.binding_id = dkb.binding_id
              AND br.deleted_at IS NULL
              AND dkb.active_chunk_revision_id IS NULL
        """))
        return result.rowcount


def verify(engine: sa.Engine) -> None:
    """Print summary of chunk_revisions."""
    with engine.begin() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM chunk_revisions WHERE deleted_at IS NULL")
        ).scalar()
        linked = conn.execute(
            text("""
                SELECT COUNT(*) FROM document_kb_bindings
                WHERE status = 'active' AND active_chunk_revision_id IS NOT NULL
            """)
        ).scalar()
        unlinked = conn.execute(
            text("""
                SELECT COUNT(*) FROM document_kb_bindings
                WHERE status = 'active' AND active_chunk_revision_id IS NULL
            """)
        ).scalar()

    print(f"\n  Total chunk_revisions: {total}")
    print(f"  Linked bindings:         {linked}")
    print(f"  Unlinked bindings:       {unlinked}")


def main() -> None:
    """Backfill chunk_revisions for existing document_kb_bindings."""
    print("=== Backfill Binding Revisions ===\n")

    engine = get_engine()

    print("[1/3] Backfilling chunk_revisions...")
    count = backfill_chunk_revisions(engine)
    print(f"  Inserted {count} chunk_revision records")

    print("[2/3] Linking active_chunk_revision_id...")
    updated = link_active_chunk_revisions(engine)
    print(f"  Updated {updated} document_kb_bindings")

    print("[3/3] Verifying...")
    verify(engine)

    print("\nDone.")


if __name__ == "__main__":
    main()
