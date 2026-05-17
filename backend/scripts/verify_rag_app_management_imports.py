"""Verify RAG App management API modules can be imported.

This smoke check intentionally stays import-level so it can run before a
database-backed TestClient fixture exists in the repository.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.router import api_router
from app.schemas.rag_app import RagAppCreateRequest, RagAppDTO
from app.services.rag_app_service import create_rag_app


def main() -> None:
    """Import the management API surface and confirm its route is registered."""
    route_paths = {getattr(route, "path", "") for route in api_router.routes}
    if "/rag-apps" not in route_paths:
        raise SystemExit("RAG App management route is not registered.")
    print(RagAppCreateRequest.__name__, RagAppDTO.__name__, create_rag_app.__name__)


if __name__ == "__main__":
    main()
