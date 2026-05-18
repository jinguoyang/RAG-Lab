"""Verify the system dictionary API surface is wired.

This import-level check stays database-free so it can run before a
database-backed fixture exists. Runtime CRUD and validation still need the
normal migration-backed smoke checks.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router  # noqa: E402
from app.schemas.dictionary import DictionaryItemDTO, DictionaryTypeDTO  # noqa: E402
from app.services.dictionary_service import (  # noqa: E402
    is_active_dict_item,
    list_dictionary_items,
    list_dictionary_types,
)
from app.tables import system_dict_items, system_dict_types  # noqa: E402


def main() -> None:
    """Confirm dictionary tables, route registration, and service helpers exist."""
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    required_paths = {
        "/dictionaries",
        "/dictionaries/{type_code}/items",
        "/dictionaries/{type_code}/items/{item_code}",
    }
    missing = required_paths - route_paths
    if missing:
        raise SystemExit(f"Dictionary routes are not registered: {sorted(missing)}")

    type_columns = {column.name for column in system_dict_types.columns}
    item_columns = {column.name for column in system_dict_items.columns}
    for required in ("dict_type_id", "code", "name", "status", "deleted_at"):
        if required not in type_columns:
            raise SystemExit(f"system_dict_types missing column: {required}")
    for required in ("dict_item_id", "dict_type_id", "code", "name", "sort_order", "status", "extra", "deleted_at"):
        if required not in item_columns:
            raise SystemExit(f"system_dict_items missing column: {required}")

    print(
        DictionaryTypeDTO.__name__,
        DictionaryItemDTO.__name__,
        list_dictionary_types.__name__,
        list_dictionary_items.__name__,
        is_active_dict_item.__name__,
    )


if __name__ == "__main__":
    main()
