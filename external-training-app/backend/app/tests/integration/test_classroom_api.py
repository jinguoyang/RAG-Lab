"""课堂 API 集成测试。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.tables import metadata, training_plans


class FakePlatformClassroomClient:
    """模拟平台课堂 Agent，验证应用端只做调用与镜像。"""

    def __init__(self):
        self.sessions = {}
        self.last_create_payload = None

    def create_classroom_session(self, payload):
        self.last_create_payload = payload
        session_id = "platform-session-001"
        data = {
            "sessionId": session_id,
            "appId": "platform-app-001",
            "planId": payload.get("planId"),
            "endUserId": payload["endUserId"],
            "currentState": "INIT",
            "currentSectionIndex": 0,
            "createdAt": "2026-05-29T00:00:00+00:00",
        }
        self.sessions[session_id] = data
        return data

    def get_classroom_session(self, session_id):
        if session_id not in self.sessions:
            import httpx

            response = httpx.Response(status_code=404, request=httpx.Request("GET", "http://platform/test"))
            raise httpx.HTTPStatusError("not found", request=response.request, response=response)
        data = self.sessions[session_id]
        return {
            **data,
            "messages": data.get("messages", []),
            "metadata": data.get("metadata", {}),
            "updatedAt": "2026-05-29T00:00:00+00:00",
        }

    def submit_classroom_event(self, session_id, payload):
        if session_id not in self.sessions:
            import httpx

            response = httpx.Response(status_code=404, request=httpx.Request("POST", "http://platform/test"))
            raise httpx.HTTPStatusError("not found", request=response.request, response=response)
        current = self.sessions[session_id]["currentState"]
        event_type = payload["eventType"]
        if event_type == "complete" and current == "INIT":
            import httpx

            response = httpx.Response(status_code=409, request=httpx.Request("POST", "http://platform/test"))
            raise httpx.HTTPStatusError("conflict", request=response.request, response=response)
        if event_type == "start":
            next_state = "PLAN"
        elif event_type in {"start_plan", "continue"}:
            next_state = "TEACH"
        elif event_type == "query":
            next_state = current
        else:
            next_state = current
        self.sessions[session_id]["currentState"] = next_state
        return {
            "eventId": f"event-{event_type}",
            "sessionId": session_id,
            "eventType": event_type,
            "resultState": next_state,
            "visibleContent": f"{event_type} handled",
            "classroomState": next_state,
            "uiActions": [{"actionType": "button_group", "data": {"buttons": []}}],
            "citations": [],
            "control": {"canProceed": True, "requiresInput": False, "inputType": None},
            "progressUpdate": None,
            "messages": [],
            "createdAt": "2026-05-29T00:00:00+00:00",
        }


@pytest.fixture
def client(monkeypatch):
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
    fake_platform = FakePlatformClassroomClient()
    monkeypatch.setattr("app.services.training_classroom_service._platform_client", lambda: fake_platform)

    def _override_db():
        yield test_session

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        c.test_session = test_session
        c.fake_platform = fake_platform
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


def test_read_session_restores_checkpoint_and_section_progress(client):
    """刷新课堂时应恢复历史消息、待答 Checkpoint 和小节进度。"""
    response = client.post(
        "/api/v1/classroom/sessions",
        json={"endUserId": "user-001", "planId": "plan-001"},
        headers={"Authorization": "Bearer dev-user"},
    )
    session_id = response.json()["sessionId"]
    client.fake_platform.sessions[session_id].update({
        "currentState": "QUIZ",
        "currentSectionIndex": 1,
        "messages": [{
            "messageId": "message-001",
            "role": "assistant",
            "content": "请说明发现异常振动后的处置动作。",
            "stateAtTime": "QUIZ",
            "metadata": {
                "uiActions": [{
                    "actionType": "subjective",
                    "data": {
                        "questionId": "question-001",
                        "sectionId": "section-002",
                        "checkpointCriteria": ["说明停机动作", "说明上报要求"],
                    },
                }],
            },
            "createdAt": "2026-06-08T00:00:00+00:00",
        }],
        "metadata": {
            "completedSectionIds": ["section-001"],
            "pendingActions": [{"label": "提交答案", "eventType": "submit_answer"}],
            "inputs": {
                "courseSnapshot": {
                    "sections": [
                        {"sectionId": "section-001", "title": "启动检查"},
                        {"sectionId": "section-002", "title": "异常停机"},
                    ]
                }
            },
        },
    })

    detail = client.get(f"/api/v1/classroom/sessions/{session_id}").json()

    assert detail["currentState"] == "QUIZ"
    assert detail["currentSectionIndex"] == 1
    assert detail["metadata"]["completedSectionIds"] == ["section-001"]
    action = detail["messages"][0]["metadata"]["uiActions"][0]
    assert action["data"]["sectionId"] == "section-002"
    assert action["data"]["checkpointCriteria"] == ["说明停机动作", "说明上报要求"]


def test_create_session_passes_frozen_course_snapshot(client):
    """创建课堂时应把 ex-app 保存的小节快照传给平台。"""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    client.test_session.execute(
        training_plans.insert().values(
            plan_id="plan-with-sections",
            app_id="app-001",
            job_title="安全员",
            job_description="负责风险识别",
            status="saved",
            ability_groups=[],
            documents=[{"documentId": "doc-001", "title": "安全手册"}],
            evidence_chunk_ids=["chunk-001"],
            recommend_reason="",
            reading_order=["doc-001"],
            version=1,
            metadata={
                "sections": [
                    {
                        "sectionId": "section-001",
                        "title": "风险识别",
                        "learningObjective": "能够识别风险",
                        "sourceDocumentIds": ["doc-001"],
                    }
                ]
            },
            created_at=now,
            updated_at=now,
        )
    )
    client.test_session.commit()

    response = client.post(
        "/api/v1/classroom/sessions",
        json={"endUserId": "user-001", "planId": "plan-with-sections"},
        headers={"Authorization": "Bearer dev-user"},
    )

    assert response.status_code == 201
    snapshot = client.fake_platform.last_create_payload["inputs"]["courseSnapshot"]
    assert snapshot["sections"][0]["sectionId"] == "section-001"
    assert snapshot["documents"][0]["documentId"] == "doc-001"


def test_submit_event_state_transition(client):
    """提交事件触发状态流转。"""
    resp = client.post(
        "/api/v1/classroom/sessions",
        json={"endUserId": "user-001"},
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
        json={"endUserId": "user-001"},
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
        json={"endUserId": "user-001"},
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
