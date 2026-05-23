"""Run real document + real Provider App Runtime E2E verification.

This script intentionally does not replace providers with local fakes. It
creates a real text document, runs the ingest job with the configured
providers, calls App Runtime through an API key, and verifies that returned
citations point back to PostgreSQL chunks from the uploaded document.
"""

from datetime import UTC, datetime
from pathlib import Path
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, update

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import document_service  # noqa: E402
from app.services.dev_auth_service import get_dev_user  # noqa: E402
from app.tables import chunks, config_revisions, knowledge_bases  # noqa: E402


ADMIN_HEADERS = {"X-Dev-User": "admin"}
REAL_PROVIDER_FIELDS = {
    "embedding_provider": {"http"},
    "dense_retrieval_provider": {"milvus"},
    "llm_provider": {"http"},
}


def _assert_status(response, expected_status: int, label: str) -> None:
    """Fail with response details so release evidence is easy to audit."""
    if response.status_code != expected_status:
        raise AssertionError(f"{label}: expected {expected_status}, got {response.status_code}: {response.text}")


def _ensure_real_provider_settings() -> None:
    """Refuse to run if the core E2E providers are configured as local fakes."""
    settings = get_settings()
    for field, allowed_values in REAL_PROVIDER_FIELDS.items():
        value = getattr(settings, field)
        if value not in allowed_values:
            raise AssertionError(f"{field} must be one of {sorted(allowed_values)}, got {value!r}.")


def _upload_and_ingest_document(kb_id: UUID, marker: str) -> UUID:
    """Upload a text document and run its ingest job in-process with real providers."""
    settings = get_settings()
    current_user = get_dev_user("admin", settings)
    if current_user is None:
        raise AssertionError("admin dev user is not available.")

    original_enqueue = document_service.enqueue_ingest_job
    document_service.enqueue_ingest_job = lambda session, job_id: None
    session = get_session_factory()()
    try:
        upload = document_service.create_document_upload(
            session=session,
            current_user=current_user,
            kb_id=kb_id,
            file_name=f"app-runtime-real-provider-{marker}.txt",
            mime_type="text/plain",
            file_bytes=(
                f"App Runtime real provider E2E marker {marker}.\n"
                "Citation must come from this PostgreSQL chunk after real ingestion.\n"
                "The retrieval answer should reference this marker."
            ).encode("utf-8"),
            name=f"app-runtime-real-provider-{marker}.txt",
        )
    finally:
        document_service.enqueue_ingest_job = original_enqueue
        session.close()

    if upload is None:
        raise AssertionError("document upload returned no response.")
    ingest_result = document_service.run_ingest_job_by_id(UUID(upload.ingestJob.jobId))
    if ingest_result.get("status") != "success":
        raise AssertionError(f"ingest job did not succeed: {ingest_result}")
    return UUID(upload.document.documentId)


def _relax_active_pipeline_for_smoke(kb_id: UUID) -> None:
    """Lower retrieval thresholds so the fresh one-document KB is always citable."""
    session = get_session_factory()()
    try:
        kb_row = session.execute(
            select(knowledge_bases.c.active_config_revision_id).where(knowledge_bases.c.kb_id == kb_id)
        ).mappings().one()
        revision_id = kb_row["active_config_revision_id"]
        revision_row = session.execute(
            select(config_revisions).where(config_revisions.c.config_revision_id == revision_id)
        ).mappings().one()
        pipeline_definition = dict(revision_row["pipeline_definition"])
        nodes = [dict(node) for node in pipeline_definition.get("nodes", [])]
        for node in nodes:
            node_type = node.get("type")
            params = dict(node.get("params") or {})
            if node_type == "queryRewrite":
                node["enabled"] = False
            if node_type == "denseRetrieval":
                params["scoreThreshold"] = 0
                params["topK"] = 20
            if node_type == "rerank":
                node["enabled"] = False
            node["params"] = params
        pipeline_definition["nodes"] = nodes
        session.execute(
            update(config_revisions)
            .where(config_revisions.c.config_revision_id == revision_id)
            .values(pipeline_definition=pipeline_definition, updated_at=datetime.now(UTC))
        )
        session.commit()
    finally:
        session.close()


def _read_chunk_content(chunk_id: str) -> str:
    """Read the cited PostgreSQL chunk content by chunkId."""
    session = get_session_factory()()
    try:
        row = session.execute(select(chunks).where(chunks.c.chunk_id == UUID(chunk_id))).mappings().first()
    finally:
        session.close()
    if row is None:
        raise AssertionError(f"cited chunk {chunk_id} was not found in PostgreSQL.")
    return row["content"]


def main() -> None:
    """Execute the real-provider App Runtime E2E check."""
    _ensure_real_provider_settings()
    client = TestClient(create_app())
    marker = f"b154-{uuid4().hex[:8]}"

    kb_response = client.post(
        "/api/v1/knowledge-bases",
        headers=ADMIN_HEADERS,
        json={"name": f"app-runtime-real-provider-{marker}", "sparseIndexEnabled": False, "graphIndexEnabled": False},
    )
    _assert_status(kb_response, 201, "create knowledge base")
    kb_id = UUID(kb_response.json()["kbId"])
    _relax_active_pipeline_for_smoke(kb_id)

    document_id = _upload_and_ingest_document(kb_id, marker)

    app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={"kbId": str(kb_id), "name": f"real-provider-runtime-{marker}"},
    )
    _assert_status(app_response, 201, "create rag app")
    app_id = app_response.json()["appId"]

    key_response = client.post(f"/api/v1/rag-apps/{app_id}/api-keys", headers=ADMIN_HEADERS, json={})
    _assert_status(key_response, 201, "create app api key")
    api_key = key_response.json()["apiKey"]

    chat_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": f"请回答 App Runtime real provider E2E marker {marker} 来自哪里？"},
    )
    _assert_status(chat_response, 200, "app runtime chat")
    payload = chat_response.json()
    citations = payload.get("citations") or []
    if not citations:
        raise AssertionError(f"real provider runtime response returned no citations: {payload}")

    cited_chunk_ids = [
        item.get("locationSnapshot", {}).get("chunkId")
        for item in citations
        if item.get("locationSnapshot", {}).get("chunkId")
    ]
    if not cited_chunk_ids:
        raise AssertionError(f"citations did not expose chunkId: {citations}")
    cited_contents = [_read_chunk_content(chunk_id) for chunk_id in cited_chunk_ids]
    if not any(marker in content for content in cited_contents):
        raise AssertionError(f"no cited PostgreSQL chunk contained marker {marker}: {cited_contents}")

    print(
        {
            "status": "success",
            "marker": marker,
            "documentId": str(document_id),
            "appId": app_id,
            "runId": payload["runId"],
            "citationCount": len(citations),
            "citedChunkIds": cited_chunk_ids,
            "verifiedAt": datetime.now(UTC).isoformat(),
        }
    )


if __name__ == "__main__":
    main()
