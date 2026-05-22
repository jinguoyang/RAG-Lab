"""Backfill chunks with new three-layer field associations.

Updates existing chunks to populate:
  - chunk_revision_id (via document_kb_bindings -> chunk_revisions)
  - parse_revision_id (via parse_revisions matching version_id)
  - document_version_id (from chunks.version_id)

Idempotent: safe to run multiple times. Only updates rows where
the target column is currently NULL.
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


def update_chunk_revision_id(engine: sa.Engine) -> int:
    """Set chunks.chunk_revision_id from the active binding revision.

    Joins chunks -> document_kb_bindings (on document_id + kb_id + version_id)
    -> chunk_revisions (on binding_id). Picks the active revision.

    Returns the number of rows updated.
    """
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE chunks c
            SET chunk_revision_id = br.chunk_revision_id
            FROM document_kb_bindings dkb
            JOIN chunk_revisions br
                ON br.binding_id = dkb.binding_id
                AND br.deleted_at IS NULL
            WHERE c.document_id = dkb.document_id
              AND c.kb_id = dkb.kb_id
              AND c.version_id = dkb.version_id
              AND dkb.status = 'active'
              AND c.chunk_revision_id IS NULL
        """))
        return result.rowcount


def update_parse_revision_id(engine: sa.Engine) -> int:
    """Set chunks.parse_revision_id from parse_revisions matching version_id.

    Joins chunks -> parse_revisions on chunks.version_id = parse_revisions.document_version_id.

    Returns the number of rows updated.
    """
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE chunks c
            SET parse_revision_id = pr.parse_revision_id
            FROM parse_revisions pr
            WHERE pr.document_version_id = c.version_id
              AND pr.deleted_at IS NULL
              AND c.parse_revision_id IS NULL
        """))
        return result.rowcount


def update_document_version_id(engine: sa.Engine) -> int:
    """Set chunks.document_version_id from chunks.version_id.

    Returns the number of rows updated.
    """
    with engine.begin() as conn:
        result = conn.execute(text("""
            UPDATE chunks
            SET document_version_id = version_id
            WHERE document_version_id IS NULL
        """))
        return result.rowcount


def verify(engine: sa.Engine) -> None:
    """Print summary of chunk field population."""
    with engine.begin() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM chunks")).scalar()
        with_brev = conn.execute(
            text("SELECT COUNT(*) FROM chunks WHERE chunk_revision_id IS NOT NULL")
        ).scalar()
        with_prev = conn.execute(
            text("SELECT COUNT(*) FROM chunks WHERE parse_revision_id IS NOT NULL")
        ).scalar()
        with_dvid = conn.execute(
            text("SELECT COUNT(*) FROM chunks WHERE document_version_id IS NOT NULL")
        ).scalar()

    print(f"\n  Total chunks:                 {total}")
    print(f"  With chunk_revision_id:     {with_brev}")
    print(f"  With parse_revision_id:       {with_prev}")
    print(f"  With document_version_id:     {with_dvid}")
    print(f"  Missing chunk_revision_id:  {total - with_brev}")
    print(f"  Missing parse_revision_id:    {total - with_prev}")
    print(f"  Missing document_version_id:  {total - with_dvid}")


def main() -> None:
    """Backfill chunks with new three-layer field associations."""
    print("=== Backfill Chunks ===\n")

    engine = get_engine()

    print("[1/4] Updating chunks.chunk_revision_id...")
    count_brev = update_chunk_revision_id(engine)
    print(f"  Updated {count_brev} chunks")

    print("[2/4] Updating chunks.parse_revision_id...")
    count_prev = update_parse_revision_id(engine)
    print(f"  Updated {count_prev} chunks")

    print("[3/4] Updating chunks.document_version_id...")
    count_dvid = update_document_version_id(engine)
    print(f"  Updated {count_dvid} chunks")

    print("[4/4] Verifying...")
    verify(engine)

    print("\nDone.")


if __name__ == "__main__":
    main()
