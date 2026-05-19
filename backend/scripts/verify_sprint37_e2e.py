"""Sprint 37 comprehensive verification script.

Validates all new symbols, routes, and table structures added in Sprint 37:
- DTOs from library and binding schemas
- Service functions from library_service and binding_service
- API routes registered on api_router
- Table column structures
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    errors: list[str] = []

    # ------------------------------------------------------------------
    # 1. Verify all new DTOs are importable
    # ------------------------------------------------------------------
    try:
        from app.schemas.library import (  # noqa: F401
            LibraryTextPreviewResponse,
            LibraryFullTextResponse,
            LibraryParsedChunksResponse,
            LibraryParsedChunkDTO,
            LibraryDocumentUsageDTO,
            LibraryDocumentUsageResponse,
        )
    except ImportError as exc:
        errors.append(f"Cannot import library DTOs: {exc}")

    try:
        from app.schemas.binding import (  # noqa: F401
            LibraryBindingDTO,
            LibraryBindRequest,
            LibraryBindResponse,
            LibraryUnbindResponse,
        )
    except ImportError as exc:
        errors.append(f"Cannot import binding DTOs: {exc}")

    # ------------------------------------------------------------------
    # 2. Verify all new service functions are importable
    # ------------------------------------------------------------------
    try:
        from app.services.library_service import (  # noqa: F401
            get_document_text,
            delete_library_document,
            retry_library_parse,
            get_document_usage,
        )
    except ImportError as exc:
        errors.append(f"Cannot import library_service functions: {exc}")

    try:
        from app.services.binding_service import (  # noqa: F401
            bind_documents_to_kb,
            unbind_document_from_kb,
            list_kb_bindings,
            retry_binding,
        )
    except ImportError as exc:
        errors.append(f"Cannot import binding_service functions: {exc}")

    # ------------------------------------------------------------------
    # 3. Verify all new routes are registered on api_router
    # ------------------------------------------------------------------
    try:
        from app.api.router import api_router

        route_paths = {getattr(route, "path", "") for route in api_router.routes}

        expected_routes = [
            "/library/documents/{document_id}/text",
            "/library/documents/{document_id}/usage",
            "/library/documents/{document_id}/parse-retry",
            "/knowledge-bases/{kb_id}/library-bindings",
            "/knowledge-bases/{kb_id}/library-bindings/{binding_id}",
            "/knowledge-bases/{kb_id}/library-bindings/{binding_id}/retry",
        ]
        for route_path in expected_routes:
            if route_path not in route_paths:
                errors.append(f"Route not registered: {route_path}")
    except ImportError as exc:
        errors.append(f"Cannot import api_router: {exc}")

    # ------------------------------------------------------------------
    # 4. Verify table structures
    # ------------------------------------------------------------------
    try:
        from app.tables import document_kb_bindings

        binding_cols = {c.name for c in document_kb_bindings.columns}
        for col in ("binding_id", "document_id", "kb_id", "version_id",
                     "status", "chunk_size", "chunk_overlap"):
            if col not in binding_cols:
                errors.append(f"document_kb_bindings missing column: {col}")
    except ImportError as exc:
        errors.append(f"Cannot import document_kb_bindings: {exc}")

    try:
        from app.tables import documents

        doc_cols = {c.name for c in documents.columns}
        for col in ("source_type", "owner_id"):
            if col not in doc_cols:
                errors.append(f"documents missing column: {col}")
    except ImportError as exc:
        errors.append(f"Cannot import documents: {exc}")

    try:
        from app.tables import document_versions

        ver_cols = {c.name for c in document_versions.columns}
        if "metadata" not in ver_cols:
            errors.append("document_versions missing column: metadata")
    except ImportError as exc:
        errors.append(f"Cannot import document_versions: {exc}")

    # ------------------------------------------------------------------
    # 5. Verify service functions are callable
    # ------------------------------------------------------------------
    try:
        from app.services.library_service import (
            get_document_text,
            delete_library_document,
            retry_library_parse,
            get_document_usage,
        )
        for fn in (get_document_text, delete_library_document,
                   retry_library_parse, get_document_usage):
            if not callable(fn):
                errors.append(f"{fn.__name__} is not callable")
    except Exception:
        pass  # already reported above

    try:
        from app.services.binding_service import (
            bind_documents_to_kb,
            unbind_document_from_kb,
            list_kb_bindings,
            retry_binding,
        )
        for fn in (bind_documents_to_kb, unbind_document_from_kb,
                   list_kb_bindings, retry_binding):
            if not callable(fn):
                errors.append(f"{fn.__name__} is not callable")
    except Exception:
        pass  # already reported above

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)

    print("verify_sprint37_e2e: PASS")


if __name__ == "__main__":
    main()
