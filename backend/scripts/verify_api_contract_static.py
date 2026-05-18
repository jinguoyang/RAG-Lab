"""Static checks for generated API contracts that do not need FastAPI imports."""

from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from pydantic import ValidationError  # noqa: E402

from app.schemas.dictionary import DictionaryItemUpdateRequest  # noqa: E402


def _load_openapi() -> dict:
    """Read the committed OpenAPI artifact used by release acceptance."""
    openapi_path = ROOT_DIR / "docs" / "06-发布与运维" / "openapi.json"
    return json.loads(openapi_path.read_text(encoding="utf-8"))


def _assert_dictionary_update_rejects_nulls() -> None:
    """Ensure nullable PATCH input cannot reach non-null dictionary columns."""
    for field_name in ("sortOrder", "status", "extra"):
        try:
            DictionaryItemUpdateRequest.model_validate({field_name: None})
        except ValidationError:
            continue
        raise SystemExit(f"DictionaryItemUpdateRequest must reject null {field_name}.")


def _assert_openapi_paths_are_current(openapi: dict) -> None:
    """Catch stale generated contract paths after route changes."""
    paths = openapi.get("paths", {})
    rag_app_path = paths.get("/api/v1/rag-apps/{app_id}", {})
    api_key_path = paths.get("/api/v1/rag-apps/{app_id}/api-keys/{api_key_id}", {})
    if "delete" not in rag_app_path:
        raise SystemExit("OpenAPI is missing DELETE /api/v1/rag-apps/{app_id}.")
    if "delete" not in api_key_path:
        raise SystemExit("OpenAPI is missing DELETE /api/v1/rag-apps/{app_id}/api-keys/{api_key_id}.")
    if "/api/v1/rag-apps/{app_id}/api-keys/{api_key_id}/revoke" in paths:
        raise SystemExit("OpenAPI still contains the removed API Key revoke route.")
    for required_path in (
        "/api/v1/dictionaries",
        "/api/v1/dictionaries/{type_code}/items",
        "/api/v1/dictionaries/{type_code}/items/{item_code}",
    ):
        if required_path not in paths:
            raise SystemExit(f"OpenAPI is missing {required_path}.")


def main() -> None:
    """Run static contract checks for review-time regressions."""
    _assert_dictionary_update_rejects_nulls()
    _assert_openapi_paths_are_current(_load_openapi())
    print("static API contract verified")


if __name__ == "__main__":
    main()
