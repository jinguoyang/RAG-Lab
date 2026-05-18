"""Verify RAG App and knowledge base status guard rules."""

from pathlib import Path
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import update

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.tables import knowledge_bases  # noqa: E402


ADMIN_HEADERS = {"X-Dev-User": "admin"}


def _assert_status(response, expected_status: int, label: str) -> None:
    """让状态守卫验证失败时明确指出失败阶段。"""
    if response.status_code != expected_status:
        raise AssertionError(f"{label}: expected {expected_status}, got {response.status_code}: {response.text}")


def _force_kb_status(kb_id: UUID, status: str) -> None:
    """直接调整夹具 KB 状态，用于验证管理端收口动作。"""
    session = get_session_factory()()
    try:
        session.execute(
            update(knowledge_bases)
            .where(knowledge_bases.c.kb_id == kb_id)
            .values(status=status)
        )
        session.commit()
    finally:
        session.close()


def main() -> None:
    """验证 active 应用阻止 KB 停用，且停用 KB 下仍可停用应用。"""
    client = TestClient(create_app())
    suffix = uuid4().hex[:8]

    kb_response = client.post(
        "/api/v1/knowledge-bases",
        headers=ADMIN_HEADERS,
        json={"name": f"kb-state-guard-{suffix}", "description": "state guard fixture"},
    )
    _assert_status(kb_response, 201, "create knowledge base")
    kb_id = UUID(kb_response.json()["kbId"])

    app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={"kbId": str(kb_id), "name": f"kb-state-guard-app-{suffix}"},
    )
    _assert_status(app_response, 201, "create rag app")
    app_id = app_response.json()["appId"]

    blocked_disable_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/disable", headers=ADMIN_HEADERS)
    _assert_status(blocked_disable_response, 409, "disable kb with active rag app")
    if blocked_disable_response.json().get("detail") != "KB_HAS_ACTIVE_RAG_APPS":
        raise AssertionError(f"active app guard detail mismatch: {blocked_disable_response.text}")

    _force_kb_status(kb_id, "disabled")
    disable_app_response = client.patch(
        f"/api/v1/rag-apps/{app_id}",
        headers=ADMIN_HEADERS,
        json={"status": "disabled"},
    )
    _assert_status(disable_app_response, 200, "disable app after kb disabled")

    enable_app_response = client.patch(
        f"/api/v1/rag-apps/{app_id}",
        headers=ADMIN_HEADERS,
        json={"status": "active"},
    )
    _assert_status(enable_app_response, 409, "enable app while kb disabled")
    if enable_app_response.json().get("detail") != "KB_DISABLED":
        raise AssertionError(f"enable app guard detail mismatch: {enable_app_response.text}")

    print("rag app kb state guards passed")


if __name__ == "__main__":
    main()
