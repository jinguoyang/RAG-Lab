"""Verify the library list/detail API surface is wired.

Import-level check confirming list, detail, update, download, and parse-jobs
routes exist alongside the service layer and table definitions.
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
    LibraryDocumentDetailDTO,
    LibraryDocumentUpdateRequest,
)
from app.services.library_service import (  # noqa: E402
    list_library_documents,
    get_library_document_detail,
    update_library_document,
    get_library_document_source_download,
    get_library_parse_jobs,
)
from app.tables import documents, document_kb_bindings, library_parse_jobs  # noqa: E402


def main() -> None:
    """Confirm library CRUD routes, services, and table definitions exist."""
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    required_paths = {
        "/library/documents",
        "/library/documents/{document_id}",
        "/library/documents/{document_id}/download",
        "/library/documents/{document_id}/parse-jobs",
    }
    missing = required_paths - route_paths
    if missing:
        raise SystemExit(f"Library CRUD routes are not registered: {sorted(missing)}")

    # Verify document_kb_bindings table exists with required columns
    binding_columns = {column.name for column in document_kb_bindings.columns}
    for required in ("binding_id", "document_id", "kb_id", "version_id", "status"):
        if required not in binding_columns:
            raise SystemExit(f"document_kb_bindings table missing column: {required}")

    # Verify kb_id is nullable in documents (for library documents)
    kb_id_col = documents.c.kb_id
    if kb_id_col.nullable is not True:
        raise SystemExit("documents.kb_id must be nullable for library documents (owner_id-based).")

    print(
        LibraryDocumentDTO.__name__,
        LibraryDocumentDetailDTO.__name__,
        LibraryDocumentUpdateRequest.__name__,
        list_library_documents.__name__,
        get_library_document_detail.__name__,
        update_library_document.__name__,
        get_library_document_source_download.__name__,
        get_library_parse_jobs.__name__,
    )


if __name__ == "__main__":
    main()
