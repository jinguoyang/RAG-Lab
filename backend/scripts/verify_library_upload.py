"""Verify the library upload API surface is wired.

Import-level check confirming routes, schemas, service, and table definitions
exist for the document library upload flow.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router  # noqa: E402
from app.schemas.library import (  # noqa: E402
    LibraryDocumentDTO,
    LibraryDocumentUploadResponse,
    LibraryDocumentVersionDTO,
    LibraryParseJobDTO,
    LibraryStoredFileDTO,
)
from app.services.library_service import create_library_upload  # noqa: E402
from app.tables import documents, library_parse_jobs, stored_files  # noqa: E402


def main() -> None:
    """Confirm library upload route, service, and table definitions exist."""
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    if "/library/documents" not in route_paths:
        raise SystemExit("Library upload route /library/documents is not registered.")

    # Verify documents table has owner_id column
    doc_columns = {column.name for column in documents.columns}
    for required in ("owner_id", "kb_id", "name", "status", "active_version_id"):
        if required not in doc_columns:
            raise SystemExit(f"documents table missing column: {required}")

    # Verify library_parse_jobs table exists with required columns
    job_columns = {column.name for column in library_parse_jobs.columns}
    for required in ("job_id", "document_id", "version_id", "job_type", "status", "progress"):
        if required not in job_columns:
            raise SystemExit(f"library_parse_jobs table missing column: {required}")

    # Verify stored_files table exists
    file_columns = {column.name for column in stored_files.columns}
    if "file_id" not in file_columns:
        raise SystemExit("stored_files table missing column: file_id")

    print(
        LibraryDocumentDTO.__name__,
        LibraryDocumentUploadResponse.__name__,
        LibraryDocumentVersionDTO.__name__,
        LibraryParseJobDTO.__name__,
        LibraryStoredFileDTO.__name__,
        create_library_upload.__name__,
    )


if __name__ == "__main__":
    main()
