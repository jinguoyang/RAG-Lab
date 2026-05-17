"""Verify RAG App conversation detail read API.

The script seeds one app conversation and assistant/user messages, then
checks that management users can read the conversation under the owning app
and cannot read the same conversation through another app.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import insert

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.tables import app_conversations, app_messages, qa_runs  # noqa: E402


ADMIN_HEADERS = {"X-Dev-User": "admin"}


def _assert_status(response, expected_status: int, label: str) -> None:
    """Fail with the response body so API contract regressions are clear."""
    if response.status_code != expected_status:
        raise AssertionError(f"{label}: expected {expected_status}, got {response.status_code}: {response.text}")


def _seed_conversation(app_id: UUID, kb_id: UUID, config_revision_id: UUID) -> tuple[UUID, UUID]:
    """Insert a deterministic conversation with user and assistant messages."""
    now = datetime.now(UTC)
    conversation_id = uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    run_id = uuid4()
    session = get_session_factory()()
    try:
        session.execute(
            insert(qa_runs).values(
                run_id=run_id,
                kb_id=kb_id,
                config_revision_id=config_revision_id,
                source_run_id=None,
                query="请说明真实会话详情。",
                rewritten_query=None,
                status="success",
                answer="这是来自 app_messages 的回答。",
                has_override=False,
                override_snapshot={},
                pipeline_snapshot={},
                node_param_snapshot={},
                metrics={},
                feedback_status="unrated",
                feedback_note=None,
                started_at=now,
                finished_at=now,
                created_at=now,
                created_by=UUID("00000000-0000-0000-0000-000000000001"),
                updated_at=now,
                updated_by=UUID("00000000-0000-0000-0000-000000000001"),
            )
        )
        session.execute(
            insert(app_conversations).values(
                conversation_id=conversation_id,
                app_id=app_id,
                end_user_id="conversation-detail-smoke",
                status="active",
                metadata={"source": "verify_app_conversation_detail"},
                created_at=now,
                updated_at=now,
            )
        )
        for message_id, role, content, qa_run_id, created_at in [
            (user_message_id, "user", "请说明真实会话详情。", None, now),
            (assistant_message_id, "assistant", "这是来自 app_messages 的回答。", run_id, now + timedelta(seconds=1)),
        ]:
            session.execute(
                insert(app_messages).values(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    qa_run_id=qa_run_id,
                    status="success",
                    metadata={"source": "verify_app_conversation_detail"},
                    created_at=created_at,
                )
            )
        session.commit()
    finally:
        session.close()
    return conversation_id, assistant_message_id


def main() -> None:
    """Run the conversation detail contract against the FastAPI app."""
    client = TestClient(create_app())
    suffix = uuid4().hex[:8]

    kb_response = client.post(
        "/api/v1/knowledge-bases",
        headers=ADMIN_HEADERS,
        json={"name": f"conversation-detail-{suffix}"},
    )
    _assert_status(kb_response, 201, "create knowledge base")
    kb_payload = kb_response.json()
    kb_id = kb_payload["kbId"]
    active_config_revision_id = kb_payload["activeConfigRevisionId"]

    app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={"kbId": kb_id, "name": f"conversation-detail-{suffix}"},
    )
    _assert_status(app_response, 201, "create rag app")
    app_id = app_response.json()["appId"]
    conversation_id, assistant_message_id = _seed_conversation(
        UUID(app_id),
        UUID(kb_id),
        UUID(active_config_revision_id),
    )

    detail_response = client.get(
        f"/api/v1/rag-apps/{app_id}/conversations/{conversation_id}",
        headers=ADMIN_HEADERS,
    )
    _assert_status(detail_response, 200, "read conversation detail")
    payload = detail_response.json()
    if payload.get("conversationId") != str(conversation_id) or payload.get("appId") != app_id:
        raise AssertionError(f"conversation identity mismatch: {payload}")
    if payload.get("endUserId") != "conversation-detail-smoke":
        raise AssertionError(f"endUserId was not returned: {payload}")
    messages = payload.get("messages") or []
    if [message.get("role") for message in messages] != ["user", "assistant"]:
        raise AssertionError(f"messages must be returned in timeline order: {messages}")
    if str(assistant_message_id) not in {message.get("messageId") for message in messages}:
        raise AssertionError(f"assistant message was not returned: {messages}")
    if not any(message.get("qaRunId") for message in messages if message.get("role") == "assistant"):
        raise AssertionError(f"assistant qaRunId must be preserved: {messages}")

    second_app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={"kbId": kb_id, "name": f"conversation-detail-second-{suffix}"},
    )
    _assert_status(second_app_response, 201, "create second rag app")
    second_app_id = second_app_response.json()["appId"]
    cross_response = client.get(
        f"/api/v1/rag-apps/{second_app_id}/conversations/{conversation_id}",
        headers=ADMIN_HEADERS,
    )
    _assert_status(cross_response, 404, "cross app conversation detail")
    print("app conversation detail verification passed")


if __name__ == "__main__":
    main()
