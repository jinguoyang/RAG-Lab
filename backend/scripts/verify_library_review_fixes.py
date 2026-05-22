"""Verify regression guards for document library review fixes.

This script intentionally uses source-level checks so it can run even when the
local test environment is missing optional runtime dependencies. It guards the
security and versioning contracts reviewed for the library feature.
"""

from __future__ import annotations

import ast
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
LIBRARY_SERVICE = BACKEND_DIR / "app" / "services" / "library_service.py"
BINDING_SERVICE = BACKEND_DIR / "app" / "services" / "binding_service.py"
LIBRARY_MANAGEMENT_SERVICE = BACKEND_DIR / "app" / "services" / "library_management_service.py"


def _function_source(path: Path, function_name: str) -> str:
    """Return the exact source segment for a top-level function."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            segment = ast.get_source_segment(source, node)
            if segment:
                return segment
    raise AssertionError(f"Function not found: {path.name}:{function_name}")


def _assert_contains(source: str, needle: str, message: str) -> None:
    """Fail with a readable message when a required source marker is absent."""
    if needle not in source:
        raise AssertionError(message)


def main() -> None:
    """Run focused checks for library permission and versioning contracts."""
    create_upload = _function_source(LIBRARY_SERVICE, "create_library_upload")
    list_docs = _function_source(LIBRARY_SERVICE, "list_library_documents")
    delete_doc = _function_source(LIBRARY_SERVICE, "delete_library_document")
    parse_job = _function_source(LIBRARY_SERVICE, "run_library_parse_job_by_id")
    delete_version = _function_source(LIBRARY_SERVICE, "delete_library_version")
    upload_version = _function_source(LIBRARY_SERVICE, "upload_library_version")
    library_stats = _function_source(LIBRARY_SERVICE, "get_library_stats")
    bind_docs = _function_source(BINDING_SERVICE, "bind_documents_to_kb")
    kb_permission = _function_source(BINDING_SERVICE, "_ensure_kb_permission")
    library_owner = _function_source(BINDING_SERVICE, "_ensure_library_owner")
    list_libraries = _function_source(LIBRARY_MANAGEMENT_SERVICE, "list_libraries")
    delete_library = _function_source(LIBRARY_MANAGEMENT_SERVICE, "delete_library")
    library_detail = _function_source(LIBRARY_MANAGEMENT_SERVICE, "get_library_detail")

    _assert_contains(
        create_upload,
        "_ensure_library_access(",
        "create_library_upload must validate create permission for explicit library_id.",
    )
    _assert_contains(
        create_upload,
        'permission_code="library.document.create"',
        "create_library_upload must require library.document.create for explicit libraries.",
    )
    _assert_contains(
        list_docs,
        'permission_code="library.document.read"',
        "list_library_documents must validate read permission when library_id is specified.",
    )
    _assert_contains(
        delete_doc,
        '"library.document.delete"',
        "delete_library_document must require delete permission, not default read permission.",
    )
    _assert_contains(
        library_detail,
        "has_library_access",
        "get_library_detail must enforce library read access.",
    )
    _assert_contains(
        bind_docs,
        '"library_version_id"',
        "bind_documents_to_kb must record source library_version_id on KB-side version metadata.",
    )
    _assert_contains(
        delete_version,
        '"library_version_id"',
        "delete_library_version must check active KB bindings by source library_version_id.",
    )
    _assert_contains(
        parse_job,
        'job_row["job_type"]',
        "run_library_parse_job_by_id must branch by job_type.",
    )
    _assert_contains(
        parse_job,
        '"upload_version"',
        "upload_version parse jobs must not auto-activate the new document version.",
    )
    _assert_contains(
        bind_docs,
        "BindingDispatchError",
        "bind_documents_to_kb must not silently swallow Celery dispatch failures.",
    )
    _assert_contains(
        bind_docs,
        "INGEST_ENQUEUE_FAILED",
        "bind_documents_to_kb must mark failed bindings/jobs when Celery dispatch fails.",
    )
    _assert_contains(
        kb_permission,
        '"platform_admin"',
        "_ensure_kb_permission must recognize platform_admin, not admin.",
    )
    _assert_contains(
        delete_library,
        "document_kb_bindings",
        "delete_library must cascade active KB bindings for documents in the library.",
    )
    _assert_contains(
        delete_library,
        'status="archived"',
        "delete_library must archive documents and the library consistently.",
    )
    _assert_contains(
        list_libraries,
        'escape="\\\\"',
        "list_libraries must escape LIKE wildcards in keyword searches.",
    )
    _assert_contains(
        upload_version,
        "storage_object_prefix",
        "upload_library_version must apply storage_object_prefix consistently.",
    )
    _assert_contains(
        library_stats,
        "source_type.in_",
        "get_library_stats must support library source documents without dropping upload compatibility.",
    )
    _assert_contains(
        library_owner,
        "has_library_access",
        "_ensure_library_owner must use the document library access model.",
    )

    print("Library review regression guards passed.")


if __name__ == "__main__":
    main()
