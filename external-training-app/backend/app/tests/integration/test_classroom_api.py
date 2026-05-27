"""课堂 API 集成测试。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.tables import metadata


@pytest.fixture
def client():
    """创建测试客户端，注入测试数据库。

    使用 StaticPool + check_same_thread=False 保证 TestClient
    的后台线程与主线程共享同一个 SQLite 连接。
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    def _override_db():
        yield test_session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    test_session.close()
    metadata.drop_all(engine)
    engine.dispose()


def test_create_and_read_session(client):
    """创建会话后可查询。"""
    resp = client.post(
        "/api/v1/classroom/sessions",
        json={
            "appId": "test-app-001",
            "endUserId": "user-001",
        },
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 201
    data = resp.json()
    session_id = data["sessionId"]
    assert data["currentState"] == "INIT"

    resp = client.get(f"/api/v1/classroom/sessions/{session_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["sessionId"] == session_id
    assert detail["messages"] == []


def test_submit_event_state_transition(client):
    """提交事件触发状态流转。"""
    resp = client.post(
        "/api/v1/classroom/sessions",
        json={"appId": "test-app-001", "endUserId": "user-001"},
        headers={"Authorization": "Bearer dev-user"},
    )
    session_id = resp.json()["sessionId"]

    resp = client.post(
        f"/api/v1/classroom/sessions/{session_id}/events",
        json={"eventType": "start", "payload": {"nextState": "PLAN"}},
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["resultState"] == "PLAN"


def test_invalid_transition_rejected(client):
    """非法状态流转返回 409。"""
    resp = client.post(
        "/api/v1/classroom/sessions",
        json={"appId": "test-app-001", "endUserId": "user-001"},
        headers={"Authorization": "Bearer dev-user"},
    )
    session_id = resp.json()["sessionId"]

    resp = client.post(
        f"/api/v1/classroom/sessions/{session_id}/events",
        json={"eventType": "complete", "payload": {"nextState": "COMPLETED"}},
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 409


def test_query_in_classroom(client):
    """课堂提问返回结构化响应。"""
    resp = client.post(
        "/api/v1/classroom/sessions",
        json={"appId": "test-app-001", "endUserId": "user-001"},
        headers={"Authorization": "Bearer dev-user"},
    )
    session_id = resp.json()["sessionId"]

    client.post(
        f"/api/v1/classroom/sessions/{session_id}/events",
        json={"eventType": "start", "payload": {"nextState": "PLAN"}},
        headers={"Authorization": "Bearer dev-user"},
    )
    client.post(
        f"/api/v1/classroom/sessions/{session_id}/events",
        json={"eventType": "start_plan", "payload": {"nextState": "TEACH"}},
        headers={"Authorization": "Bearer dev-user"},
    )

    resp = client.post(
        f"/api/v1/classroom/sessions/{session_id}/events",
        json={"eventType": "query", "payload": {}, "query": "什么是RAG？"},
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["eventType"] == "query"
    assert "visibleContent" in data
    assert "uiActions" in data
    assert "citations" in data
    assert "control" in data


def test_session_not_found(client):
    """查询不存在的会话返回 404。"""
    resp = client.get("/api/v1/classroom/sessions/nonexistent")
    assert resp.status_code == 404
