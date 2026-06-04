"""Verify the library parsing service and Celery task surface is wired.

Import-level check confirming the parse job runner, Celery task registration,
and document_parsing integration exist.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.library_service import run_library_parse_job_by_id  # noqa: E402
from app.services.document_parsing import parse_document, DocumentParseError  # noqa: E402
from app.worker import celery_app, run_library_parse_task  # noqa: E402
from app.tables import library_parse_jobs, document_versions  # noqa: E402


def main() -> None:
    """Confirm library parsing service, Celery task, and table definitions exist."""
    # Verify Celery task is registered
    registered_tasks = set(celery_app.tasks.keys())
    if "library_parse.run" not in registered_tasks:
        raise SystemExit("Celery task 'library_parse.run' is not registered.")

    # Verify library_parse_jobs table columns
    job_columns = {column.name for column in library_parse_jobs.columns}
    for required in ("job_id", "document_id", "version_id", "job_type", "status", "progress", "error_code", "error_message"):
        if required not in job_columns:
            raise SystemExit(f"library_parse_jobs table missing column: {required}")

    # Verify document_versions table has parse-related columns
    ver_columns = {column.name for column in document_versions.columns}
    for required in ("version_id", "document_id", "parse_status", "chunk_count", "token_count"):
        if required not in ver_columns:
            raise SystemExit(f"document_versions table missing column: {required}")

    # Verify parse_document handles common formats
    test_cases = [
        ("test.txt", "text/plain", b"Hello world"),
        ("test.md", "text/markdown", b"# Title\n\nContent"),
    ]
    for file_name, mime_type, content in test_cases:
        try:
            result = parse_document(file_name, mime_type, content)
            if not result.blocks:
                raise SystemExit(f"parse_document returned no blocks for {file_name}")
        except DocumentParseError as exc:
            raise SystemExit(f"parse_document failed for {file_name}: {exc}") from exc

    print(
        run_library_parse_job_by_id.__name__,
        run_library_parse_task.name,
        parse_document.__name__,
        DocumentParseError.__name__,
    )


if __name__ == "__main__":
    main()
