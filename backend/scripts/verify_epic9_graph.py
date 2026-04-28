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
CHUNK_ID = "33333333-3333-3333-3333-333333333333"
DOCUMENT_ID = "44444444-4444-4444-4444-444444444444"


class _FakeResult:
    """Provide the minimal SQLAlchemy result surface used by graph verification."""

    def __init__(self, rows):
        self._rows = rows

    def mappings(self) -> "_FakeResult":
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _FakeSnapshotResult:
    """Return a deterministic graph snapshot id for local API contract checks."""

    def first(self) -> tuple[str]:
        return (SNAPSHOT_ID,)


class _FakeSession:
    """Serve the smallest DB contract required by Epic 9 graph route verification."""

    def execute(self, statement):
        statement_text = str(statement)
        if "FROM knowledge_bases" in statement_text:
            return _FakeResult([{"kb_id": KB_ID}])
        if "graph_snapshots.graph_snapshot_id" in statement_text:
            return _FakeSnapshotResult()
        if "FROM graph_chunk_refs" in statement_text:
            return _FakeResult(
                [
                    {
                        "chunk_id": CHUNK_ID,
                        "ref_type": "entity",
                        "metadata": {"score": 0.91},
                    }
                ]
            )
        if "FROM user_group_members" in statement_text or "FROM kb_member_bindings" in statement_text:
            return _FakeResult([])
        if "FROM role_permission_bindings" in statement_text:
            return _FakeResult([("kb.chunk.read", "allow")])
        if "FROM chunks JOIN documents" in statement_text:
            return _FakeResult(
                [
                    {
                        "chunk_id": CHUNK_ID,
                        "document_id": DOCUMENT_ID,
                        "document_name": "Graph Evidence.md",
                        "chunk_index": 2,
                        "content": "Graph supporting chunk content for deterministic authorization verification.",
                        "security_level": "internal",
                    }
                ]
            )
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


def assert_supporting_chunks_payload(payload: dict) -> None:
    """Check supporting chunk fields required for authorized graph evidence fallback."""
    assert "items" in payload, "supporting chunks missing items"
    assert "filteredCount" in payload, "supporting chunks missing filteredCount"
    assert payload["items"], "supporting chunks should return deterministic fake items"
    for item in payload["items"]:
        assert "chunkId" in item, "supporting chunk missing chunkId"
        assert "contentPreview" in item, "supporting chunk missing contentPreview"
        assert "documentName" in item, "supporting chunk missing documentName"


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

    supporting_chunks = assert_ok(
        client.get(
            f"/api/v1/knowledge-bases/{KB_ID}/graph/supporting-chunks"
            f"?graphSnapshotId={SNAPSHOT_ID}&nodeKey=missing-node"
        ),
        "supporting chunks",
    )
    assert_supporting_chunks_payload(supporting_chunks)


if __name__ == "__main__":
    main()
