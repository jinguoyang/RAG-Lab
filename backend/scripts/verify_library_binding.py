"""Verify the library binding API surface is wired.

Import-level check confirming bind/unbind/list routes exist alongside the
service layer, DTO classes, and table definitions.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router  # noqa: E402
from app.schemas.binding import (  # noqa: E402
    LibraryBindingDTO,
    LibraryBindRequest,
    LibraryBindResponse,
    LibraryUnbindResponse,
)
from app.services.binding_service import (  # noqa: E402
    bind_documents_to_kb,
    unbind_document_from_kb,
    list_kb_bindings,
)
from app.tables import document_kb_bindings  # noqa: E402


def main() -> None:
    """Confirm library binding routes, services, and DTOs exist."""
    # 1. Check route is registered
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    binding_prefix = "/knowledge-bases/{kb_id}/library-bindings"
    if binding_prefix not in route_paths:
        raise SystemExit(f"Library binding route is not registered: {binding_prefix}")

    # 2. Verify all DTO classes can be imported and instantiated
    req = LibraryBindRequest(documentIds=["a" * 36])
    if not req.documentIds:
        raise SystemExit("LibraryBindRequest cannot be constructed")

    # 3. Verify all service functions are callable
    assert callable(bind_documents_to_kb), "bind_documents_to_kb is not callable"
    assert callable(unbind_document_from_kb), "unbind_document_from_kb is not callable"
    assert callable(list_kb_bindings), "list_kb_bindings is not callable"

    # 4. Verify document_kb_bindings table has required columns
    binding_columns = {column.name for column in document_kb_bindings.columns}
    for required in ("binding_id", "document_id", "kb_id", "version_id", "status", "chunk_size", "chunk_overlap"):
        if required not in binding_columns:
            raise SystemExit(f"document_kb_bindings table missing column: {required}")

    print(
        LibraryBindingDTO.__name__,
        LibraryBindRequest.__name__,
        LibraryBindResponse.__name__,
        LibraryUnbindResponse.__name__,
        bind_documents_to_kb.__name__,
        unbind_document_from_kb.__name__,
        list_kb_bindings.__name__,
    )


if __name__ == "__main__":
    main()
