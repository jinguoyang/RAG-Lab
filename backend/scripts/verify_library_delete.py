"""验证 library delete 功能完整性。"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    errors: list[str] = []

    # 1. Check delete_library_document is callable
    try:
        from app.services.library_service import delete_library_document

        if not callable(delete_library_document):
            errors.append("delete_library_document is not callable")
    except ImportError as exc:
        errors.append(f"Cannot import delete_library_document: {exc}")

    # 2. Verify documents table has deleted_at, deleted_by columns
    try:
        from app.tables import documents

        col_names = {c.name for c in documents.columns}
        for col in ("deleted_at", "deleted_by"):
            if col not in col_names:
                errors.append(f"documents table missing column: {col}")
    except ImportError as exc:
        errors.append(f"Cannot import documents table: {exc}")

    # 3. Verify document_kb_bindings table has status column
    try:
        from app.tables import document_kb_bindings

        col_names = {c.name for c in document_kb_bindings.columns}
        if "status" not in col_names:
            errors.append("document_kb_bindings table missing column: status")
    except ImportError as exc:
        errors.append(f"Cannot import document_kb_bindings table: {exc}")

    # Report
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        sys.exit(1)

    print("PASS: delete_library_document is callable")
    print("PASS: documents table has deleted_at, deleted_by columns")
    print("PASS: document_kb_bindings table has status column")
    print("All checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
