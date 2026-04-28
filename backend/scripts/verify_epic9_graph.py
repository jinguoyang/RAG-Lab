"""Verify Epic 9 graph API behavior with FastAPI TestClient.

The first run should fail before B-043 routes exist, proving the verification
can catch missing path and community graph APIs.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_db_session
from app.main import app

KB_ID = "11111111-1111-1111-1111-111111111111"
SNAPSHOT_ID = "22222222-2222-2222-2222-222222222222"


class _FakeMappingResult:
    """Provide the minimal SQLAlchemy result surface used by graph visibility checks."""

    def mappings(self) -> "_FakeMappingResult":
        return self

    def first(self) -> dict:
        return {"kb_id": KB_ID}


class _FakeSnapshotResult:
    """Return a deterministic graph snapshot id for local API contract checks."""

    def first(self) -> tuple[str]:
        return (SNAPSHOT_ID,)


class _FakeSession:
    """Serve the smallest DB contract required by B-043 graph route verification."""

    def execute(self, statement):
        statement_text = str(statement)
        if "FROM knowledge_bases" in statement_text:
            return _FakeMappingResult()
        if "graph_snapshots.graph_snapshot_id" in statement_text:
            return _FakeSnapshotResult()
        raise AssertionError(f"Unexpected SQL in graph verification: {statement_text}")

    def close(self) -> None:
        pass


def _override_db_session():
    """Inject an in-memory fake session so this verification does not require PostgreSQL."""
    session = _FakeSession()
    try:
        yield session
    finally:
        session.close()


def assert_ok(response, label: str) -> dict:
    """Fail with a compact message that keeps local verification readable."""
    assert response.status_code == 200, f"{label} failed: {response.status_code} {response.text}"
    return response.json()


def assert_graph_search_payload(payload: dict, label: str) -> None:
    """Check the stable response envelope required by the P11 graph page."""
    assert "items" in payload, f"{label} missing items"
    assert "diagnostics" in payload, f"{label} missing diagnostics"
    assert isinstance(payload["diagnostics"]["degraded"], bool), f"{label} degraded must be boolean"


def main() -> None:
    """Run the local TestClient smoke verification for B-043 graph APIs."""
    app.dependency_overrides[get_db_session] = _override_db_session
    client = TestClient(app)

    paths = assert_ok(
        client.get(f"/api/v1/knowledge-bases/{KB_ID}/graph/paths?keyword=Supplier&limit=5"),
        "paths",
    )
    assert_graph_search_payload(paths, "paths")

    communities = assert_ok(
        client.get(f"/api/v1/knowledge-bases/{KB_ID}/graph/communities?keyword=Supplier&limit=5"),
        "communities",
    )
    assert_graph_search_payload(communities, "communities")


if __name__ == "__main__":
    main()
